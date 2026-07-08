"""AI Brief 与 AI 审查报告生成。"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from ..db import connect
from .load_data import load_ai_prompts, read_component_markdown
from .matcher import MatchResult, ProjectProfile


def _format_profile_summary(profile: ProjectProfile) -> str:
    flags = []
    for label, key in [
        ("终端", "涉及终端"), ("号卡", "涉及号卡"), ("账务", "涉及账务"),
        ("库存", "涉及库存"), ("事件", "涉及事件"), ("服务台", "涉及服务台"), ("驻场", "涉及驻场"),
    ]:
        if getattr(profile, key):
            flags.append(label)
    return (
        f"- 客户：{profile.客户名称}\n"
        f"- 行业：{profile.行业 or '—'}\n"
        f"- 项目类型：{', '.join(profile.项目类型) or '—'}\n"
        f"- 用户规模：{profile.用户规模 or '—'}\n"
        f"- 参考样板：{profile.参考样板项目 or '—'}\n"
        f"- 涉及模块：{', '.join(flags) or '—'}\n"
        f"- 特殊说明：{profile.特殊说明 or '—'}"
    )


def _format_service_items(result: MatchResult) -> str:
    lines = []
    for s in result.service_items:
        lines.append(f"- **{s.item_id}** {s.name} — {s.reason}")
    return "\n".join(lines) or "（无）"


def _format_components_table(result: MatchResult) -> str:
    lines = ["| 组件编号 | 组件名称 | 来源项目 | 推荐原因 |", "|---|---|---|---|"]
    for c in result.components:
        lines.append(f"| {c.item_id} | {c.name} | {c.source_project or '—'} | {c.reason} |")
    return "\n".join(lines)


def _format_diffs_table(result: MatchResult) -> str:
    lines = ["| 规则ID | 标准规则 | 本项目规则 | 确认方 |", "|---|---|---|---|"]
    for d in result.pending_diffs[:15]:
        lines.append(
            f"| {d.get('规则ID', '—')} | {d.get('标准规则', '—')} | "
            f"{d.get('本项目规则', '—')} | {d.get('确认方', '—')} |"
        )
    return "\n".join(lines) if len(lines) > 2 else "（暂无差异规则，可在 config/project_diff.yaml 维护）"


def build_ai_brief(profile: ProjectProfile, result: MatchResult) -> str:
    """生成 AI 分析上下文包（Markdown）。"""
    from ..config import REPO_ROOT
    tpl = (REPO_ROOT / "templates" / "emos" / "ai_brief_template.md").read_text(encoding="utf-8")

    body = tpl.replace("{{客户名称}}", profile.客户名称)
    body = body.replace("{{行业}}", profile.行业 or "—")
    body = body.replace("{{项目类型}}", ", ".join(profile.项目类型))
    body = body.replace("{{用户规模}}", profile.用户规模 or "—")
    body = body.replace("{{推荐服务项}}", _format_service_items(result))
    body = body.replace("{{组件表格}}", _format_components_table(result))
    body = body.replace("{{差异表格}}", _format_diffs_table(result))

    # 附加核心组件 Markdown 摘要（前 5 个）
    appendix = ["\n\n---\n\n## 附录：核心组件 AI 摘要\n"]
    for c in result.components[:5]:
        md = read_component_markdown(c.item_id)
        if md:
            appendix.append(f"\n### {c.item_id}\n\n{md[:800]}...\n")
    body += "".join(appendix)
    return body


def build_ai_review_report(profile: ProjectProfile, result: MatchResult) -> str:
    """基于 Prompt 模板生成 AI 审查报告（结构化初稿，供人工/ChatGPT 复核）。"""
    prompts = load_ai_prompts()
    review = next((p for p in prompts if p.get("PromptID") == "PROMPT-REVIEW"), None)
    if not review:
        return build_ai_brief(profile, result)

    tpl = review["模板正文"]
    filled = tpl.format(
        profile_summary=_format_profile_summary(profile),
        service_items=_format_service_items(result),
        components_table=_format_components_table(result),
        diffs_table=_format_diffs_table(result),
    )

    report = f"""# AI 审查报告（系统初稿）

> 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}
> 画像ID：{profile.画像ID}
> 说明：以下为基于规则匹配与 Prompt 模板生成的审查提纲，请复制到 ChatGPT 或使用内部 AI 进一步分析。

---

## 审查 Prompt

{filled}

---

## 系统自动识别的风险项

"""
    for i, r in enumerate(result.risks, 1):
        report += f"{i}. **{r.name}** — 来源规则 {r.rule_id}；{r.reason}\n"

    report += "\n## 建议人工确认清单\n\n"
    for i, c in enumerate(result.components[:10], 1):
        report += f"{i}. 组件 **{c.item_id}** ({c.name}) 是否适用于本项目？理由：{c.reason}\n"

    return report


def save_ai_suggestion(
    profile_id: str | None,
    scene: str,
    ai_output: str,
    human_conclusion: str = "",
    adopted: str = "待确认",
    reflux: bool = False,
) -> str:
    from uuid import uuid4
    record_id = f"AIS-{uuid4().hex[:10]}"
    ts = datetime.now()
    with connect() as con:
        con.execute(
            """
            INSERT INTO meta_emos_ai_suggestion
            (记录ID, 画像ID, 场景, AI输出, 人工结论, 是否采纳, 是否回流, 数据更新时间)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [record_id, profile_id, scene, ai_output, human_conclusion, adopted, reflux, ts],
        )
    return record_id


def list_ai_suggestions(limit: int = 50) -> Any:
    import pandas as pd
    with connect(read_only=True) as con:
        return con.execute(
            """
            SELECT 记录ID, 画像ID, 场景, 是否采纳, 是否回流, 数据更新时间
            FROM meta_emos_ai_suggestion ORDER BY 数据更新时间 DESC LIMIT ?
            """,
            [limit],
        ).fetchdf()
