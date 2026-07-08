"""EMOS YAML → DuckDB 同步。"""
from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd

from ..db import connect
from .load_data import (
    load_ai_prompts,
    load_components,
    load_knowledge_cards,
    load_match_rules,
    load_project_types,
    load_service_items,
)


def _stamp(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    now = datetime.now()
    for r in rows:
        r["数据更新时间"] = now
    return rows


def sync_emos_from_config(verbose: bool = True) -> dict[str, int]:
    """从 config/emos/*.yaml 同步静态知识库到 DuckDB。"""
    counts: dict[str, int] = {}

    specs = [
        ("meta_emos_project_type", load_project_types(), "config/emos/project_types.yaml"),
        ("meta_emos_service_item", load_service_items(), "config/emos/service_items.yaml"),
        ("meta_emos_component", load_components(), "config/emos/components.yaml"),
        ("meta_emos_match_rule", load_match_rules(), "config/emos/match_rules.yaml"),
        ("meta_emos_knowledge_card", load_knowledge_cards(), "config/emos/knowledge_cards.yaml"),
        ("meta_emos_ai_prompt", [
            {
                "PromptID": p["PromptID"],
                "场景": p["场景"],
                "模板名称": p["模板名称"],
                "模板正文": p["模板正文"],
                "版本": p.get("版本", "V0.1"),
            }
            for p in load_ai_prompts()
        ], "config/emos/ai_prompts.yaml"),
    ]

    with connect() as con:
        for table, rows, source in specs:
            stamped = _stamp([dict(r) for r in rows])
            if not stamped:
                counts[table] = 0
                continue
            df = pd.DataFrame(stamped)
            con.execute(f"DELETE FROM {table}")
            con.register("_emos_df", df)
            con.execute(f"INSERT INTO {table} SELECT * FROM _emos_df")
            con.unregister("_emos_df")
            counts[table] = len(stamped)
            if verbose:
                print(f"[sync-emos] {table}: {len(stamped)} rows ({source})")

    return counts
