"""项目差异规则：从 config/project_diff.yaml 同步到 DuckDB。"""
from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd
import yaml

from ..config import CONFIG_DIR, load_yaml
from ..db import connect

_YAML_HEADER = """# 项目差异规则表（标准逻辑 vs 本项目实际）
# init-db / tem sync-diff 会同步到 DuckDB meta_project_diff。
# 运营确认后的差异应记录在此，供 Import Gate 提示与 EMOS 知识回流。

"""


class ProjectDiffError(ValueError):
    """差异规则读写失败。"""

def load_project_diff_yaml(path=None) -> dict[str, Any]:
    path = path or CONFIG_DIR / "project_diff.yaml"
    if not path.exists():
        return {"defaults": [], "projects": []}
    return load_yaml(path)


def _flatten_diff_rows(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    now = datetime.now()

    for item in cfg.get("defaults", []) or []:
        rows.append({
            "客户ID": "*",
            "项目ID": "*",
            "规则ID": item.get("规则ID"),
            "规则类别": item.get("规则类别"),
            "标准规则": item.get("标准规则"),
            "本项目规则": item.get("本项目规则"),
            "确认方": item.get("确认方"),
            "是否可复用": bool(item.get("是否可复用", True)),
            "备注": item.get("备注"),
            "生效账期": item.get("生效账期"),
            "数据来源": "config/project_diff.yaml#defaults",
            "数据更新时间": now,
        })

    for proj in cfg.get("projects", []) or []:
        cid = proj.get("客户ID")
        pid = proj.get("项目ID")
        for item in proj.get("diffs", []) or []:
            rows.append({
                "客户ID": cid,
                "项目ID": pid,
                "规则ID": item.get("规则ID"),
                "规则类别": item.get("规则类别"),
                "标准规则": item.get("标准规则"),
                "本项目规则": item.get("本项目规则"),
                "确认方": item.get("确认方"),
                "是否可复用": bool(item.get("是否可复用", True)),
                "备注": item.get("备注"),
                "生效账期": item.get("生效账期"),
                "数据来源": "config/project_diff.yaml#projects",
                "数据更新时间": now,
            })
    return [r for r in rows if r.get("规则ID")]


def sync_project_diff_from_config(verbose: bool = True) -> int:
    """把 YAML 中的差异规则 upsert 到 meta_project_diff。返回写入行数。"""
    cfg = load_project_diff_yaml()
    rows = _flatten_diff_rows(cfg)
    if not rows:
        return 0

    df = pd.DataFrame(rows)
    with connect() as con:
        con.execute("DELETE FROM meta_project_diff WHERE 数据来源 LIKE 'config/project_diff.yaml%'")
        con.register("_diff_df", df)
        con.execute("""
            INSERT INTO meta_project_diff SELECT * FROM _diff_df
        """)
        con.unregister("_diff_df")
    if verbose:
        print(f"[sync-diff] meta_project_diff: {len(rows)} 条规则")
    return len(rows)


def save_project_diff_yaml(cfg: dict[str, Any], path=None) -> None:
    """写回 config/project_diff.yaml（Streamlit 维护页使用）。"""
    path = path or CONFIG_DIR / "project_diff.yaml"
    body = yaml.dump(
        {
            "defaults": cfg.get("defaults", []) or [],
            "projects": cfg.get("projects", []) or [],
        },
        allow_unicode=True,
        sort_keys=False,
    )
    path.write_text(_YAML_HEADER + body, encoding="utf-8")


def list_all_project_diffs() -> pd.DataFrame:
    """列出库中全部差异规则（含全局与项目级）。"""
    with connect(read_only=True) as con:
        return con.execute(
            "SELECT * FROM meta_project_diff ORDER BY 客户ID, 项目ID, 规则ID"
        ).fetchdf()


def upsert_diff_rule(
    规则ID: str,
    规则类别: str,
    标准规则: str,
    本项目规则: str,
    确认方: str,
    *,
    客户ID: str = "*",
    项目ID: str = "*",
    是否可复用: bool = True,
    备注: str = "",
    生效账期: str | None = None,
) -> None:
    """新增或更新一条差异规则，写 YAML 并同步 DuckDB。"""
    rid = 规则ID.strip()
    if not rid:
        raise ProjectDiffError("规则ID 不能为空")

    rule: dict[str, Any] = {
        "规则ID": rid,
        "规则类别": 规则类别.strip(),
        "标准规则": 标准规则.strip(),
        "本项目规则": 本项目规则.strip(),
        "确认方": 确认方.strip(),
        "是否可复用": bool(是否可复用),
        "备注": 备注.strip() or None,
        "生效账期": 生效账期,
    }

    cfg = load_project_diff_yaml()
    global_scope = 客户ID in ("*", "", None) and 项目ID in ("*", "", None)

    if global_scope:
        defaults = cfg.setdefault("defaults", [])
        replaced = False
        for idx, item in enumerate(defaults):
            if item.get("规则ID") == rid:
                defaults[idx] = rule
                replaced = True
                break
        if not replaced:
            defaults.append(rule)
    else:
        if not 客户ID or not 项目ID or 客户ID == "*" or 项目ID == "*":
            raise ProjectDiffError("项目级差异需填写具体的客户ID 与 项目ID")
        projects = cfg.setdefault("projects", [])
        proj = next(
            (p for p in projects if p.get("客户ID") == 客户ID and p.get("项目ID") == 项目ID),
            None,
        )
        if proj is None:
            proj = {"客户ID": 客户ID, "项目ID": 项目ID, "diffs": []}
            projects.append(proj)
        diffs = proj.setdefault("diffs", [])
        replaced = False
        for idx, item in enumerate(diffs):
            if item.get("规则ID") == rid:
                diffs[idx] = rule
                replaced = True
                break
        if not replaced:
            diffs.append(rule)

    save_project_diff_yaml(cfg)
    sync_project_diff_from_config(verbose=False)


def delete_diff_rule(规则ID: str, *, 客户ID: str = "*", 项目ID: str = "*") -> None:
    """删除一条差异规则，写 YAML 并同步 DuckDB。"""
    rid = 规则ID.strip()
    if not rid:
        raise ProjectDiffError("规则ID 不能为空")

    cfg = load_project_diff_yaml()
    if 客户ID in ("*", "", None) and 项目ID in ("*", "", None):
        cfg["defaults"] = [d for d in cfg.get("defaults", []) if d.get("规则ID") != rid]
    else:
        for proj in cfg.get("projects", []):
            if proj.get("客户ID") == 客户ID and proj.get("项目ID") == 项目ID:
                proj["diffs"] = [d for d in proj.get("diffs", []) if d.get("规则ID") != rid]
    save_project_diff_yaml(cfg)
    sync_project_diff_from_config(verbose=False)


def list_project_diffs(客户ID: str | None = None, 项目ID: str | None = None) -> pd.DataFrame:
    """查询适用的项目差异规则（含全局 default */*）。"""
    with connect(read_only=True) as con:
        where = ["(客户ID = '*' OR 客户ID = ?)", "(项目ID = '*' OR 项目ID = ?)"]
        params: list[Any] = [客户ID or "", 项目ID or ""]
        sql = f"SELECT * FROM meta_project_diff WHERE {' AND '.join(where)} ORDER BY 规则ID"
        return con.execute(sql, params).fetchdf()
