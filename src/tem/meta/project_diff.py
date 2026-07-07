"""项目差异规则：从 config/project_diff.yaml 同步到 DuckDB。"""
from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd

from ..config import CONFIG_DIR, get_settings, load_yaml
from ..db import connect


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


def list_project_diffs(客户ID: str | None = None, 项目ID: str | None = None) -> pd.DataFrame:
    """查询适用的项目差异规则（含全局 default */*）。"""
    with connect(read_only=True) as con:
        where = ["(客户ID = '*' OR 客户ID = ?)", "(项目ID = '*' OR 项目ID = ?)"]
        params: list[Any] = [客户ID or "", 项目ID or ""]
        sql = f"SELECT * FROM meta_project_diff WHERE {' AND '.join(where)} ORDER BY 规则ID"
        return con.execute(sql, params).fetchdf()
