"""项目落地包生成：RACI / SOP索引 / 事件字典 / 风险清单 / AI Brief。"""
from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from .ai_brief import build_ai_brief, build_ai_review_report
from .load_data import OUTPUT_EMOS_ROOT, REPO_ROOT, TEMPLATES_DIR, get_component_by_id
from .matcher import MatchResult, ProjectProfile
from .office_export import export_landing_pack_office


def _copy_template(name: str, dest: Path) -> None:
    src = TEMPLATES_DIR / name
    if src.exists():
        shutil.copy2(src, dest)


def generate_landing_pack(
    profile: ProjectProfile,
    result: MatchResult,
    *,
    output_root: Path | None = None,
) -> dict[str, Any]:
    """生成项目落地包目录与核心文档。"""
    root = output_root or OUTPUT_EMOS_ROOT
    pack_dir = root / profile.画像ID / f"{profile.客户名称}_落地包"
    pack_dir.mkdir(parents=True, exist_ok=True)

    # 1. 元数据
    meta = {
        "画像ID": profile.画像ID,
        "客户名称": profile.客户名称,
        "生成时间": datetime.now().isoformat(),
        "服务项数": len(result.service_items),
        "组件数": len(result.components),
        "风险数": len(result.risks),
    }
    (pack_dir / "pack_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    # 2. 模板文档
    for tpl in ["raci_template.md", "event_dictionary.md", "risk_checklist.md", "sop_index.md"]:
        _copy_template(tpl, pack_dir / tpl)

    # 3. 填充 SOP 索引
    sop_lines = [
        "# 项目 SOP 索引\n",
        "| 组件编号 | SOP名称 | 来源 | 成熟度 | Markdown |",
        "|---|---|---|---|---|",
    ]
    for c in result.components:
        comp = get_component_by_id(c.item_id) or {}
        if str(comp.get("组件类型", "")).upper() in {"SOP", "FLOW"} or c.item_id.startswith("SOP"):
            md = comp.get("AI摘要文件", "")
            sop_lines.append(
                f"| {c.item_id} | {c.name} | {c.source_project or comp.get('来源项目', '—')} | "
                f"{comp.get('成熟度', '—')} | {md} |"
            )
    (pack_dir / "sop_index.md").write_text("\n".join(sop_lines), encoding="utf-8")

    # 4. 填充风险清单
    risk_lines = [
        "# 项目风险清单\n",
        "| 风险ID | 风险描述 | 关联规则 | 确认方 | 状态 |",
        "|---|---|---|---|---|",
    ]
    for r in result.risks:
        risk_lines.append(f"| {r.item_id} | {r.name} | {r.rule_id} | PM/运营 | 待确认 |")
    (pack_dir / "risk_checklist_filled.md").write_text("\n".join(risk_lines), encoding="utf-8")

    # 5. 推荐结果 JSON
    (pack_dir / "recommendation.json").write_text(
        json.dumps(result.to_dict(), ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )

    # 6. 复制组件 Markdown
    md_dest = pack_dir / "components_md"
    md_dest.mkdir(exist_ok=True)
    copied = 0
    for c in result.components:
        comp = get_component_by_id(c.item_id)
        if not comp:
            continue
        rel = comp.get("AI摘要文件")
        if not rel:
            continue
        src = REPO_ROOT / str(rel)
        if src.exists():
            shutil.copy2(src, md_dest / src.name)
            copied += 1

    # 7. AI Brief + 审查报告
    brief = build_ai_brief(profile, result)
    review = build_ai_review_report(profile, result)
    (pack_dir / "AI_Brief.md").write_text(brief, encoding="utf-8")
    (pack_dir / "AI_审查报告.md").write_text(review, encoding="utf-8")

    # 8. 差异确认表（Markdown）
    diff_lines = ["# 项目差异确认表\n", "| 规则ID | 标准规则 | 本项目规则 | 确认方 | 是否可复用 |", "|---|---|---|---|---|"]
    for d in result.pending_diffs:
        diff_lines.append(
            f"| {d.get('规则ID','—')} | {d.get('标准规则','—')} | {d.get('本项目规则','—')} | "
            f"{d.get('确认方','—')} | {d.get('是否可复用','—')} |"
        )
    (pack_dir / "差异确认表.md").write_text("\n".join(diff_lines), encoding="utf-8")

    # 9. README
    readme = f"""# {profile.客户名称} 项目落地包

- 画像ID：`{profile.画像ID}`
- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}

## 目录说明
- `AI_Brief.md` — AI 分析上下文包
- `AI_审查报告.md` — 系统审查提纲
- `recommendation.json` — 推荐服务项/组件/风险
- `sop_index.md` — SOP 索引
- `risk_checklist_filled.md` — 风险清单
- `差异确认表.md` — 标准 vs 本项目差异
- `components_md/` — 组件 AI 摘要（{copied} 份）
"""
    (pack_dir / "README.md").write_text(readme, encoding="utf-8")

    # 10. Word / Excel 落地包（M6）
    office_paths = export_landing_pack_office(pack_dir, profile, result, brief_excerpt=brief[:2000])
    if office_paths.get("xlsx"):
        readme += f"\n- `{Path(office_paths['xlsx']).name}` — Excel 多 sheet 落地包\n"
    if office_paths.get("docx"):
        readme += f"\n- `{Path(office_paths['docx']).name}` — Word 落地包初稿\n"
    (pack_dir / "README.md").write_text(readme, encoding="utf-8")

    file_names = [p.name for p in pack_dir.iterdir() if p.is_file()]
    return {
        "pack_dir": str(pack_dir),
        "files": file_names,
        "components_md_count": copied,
        "office": office_paths,
    }
