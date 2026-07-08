"""EMOS 知识卡片与组件版本。"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

import pandas as pd

from ..db import connect
from .load_data import load_knowledge_cards


def list_knowledge_cards() -> pd.DataFrame:
    with connect(read_only=True) as con:
        try:
            return con.execute(
                "SELECT * FROM meta_emos_knowledge_card ORDER BY 知识卡片编号"
            ).fetchdf()
        except Exception:  # noqa: BLE001
            return pd.DataFrame(load_knowledge_cards())


def save_knowledge_card(
    主题: str,
    核心结论: str,
    适用场景: str = "",
    来源项目: str = "",
    关联组件: str = "",
    AI使用方式: str = "",
    是否可复用: bool = True,
) -> str:
    card_id = f"KC-{uuid4().hex[:6].upper()}"
    ts = datetime.now()
    with connect() as con:
        con.execute(
            """
            INSERT INTO meta_emos_knowledge_card
            (知识卡片编号, 主题, 核心结论, 适用场景, 来源项目, 关联组件, AI使用方式, 是否可复用, 数据更新时间)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [card_id, 主题, 核心结论, 适用场景, 来源项目, 关联组件, AI使用方式, 是否可复用, ts],
        )
    return card_id


def delete_knowledge_card(card_id: str) -> None:
    with connect() as con:
        con.execute("DELETE FROM meta_emos_knowledge_card WHERE 知识卡片编号 = ?", [card_id])


def record_component_version(
    组件编号: str,
    原版本: str,
    新版本: str,
    更新原因: str,
    来源项目: str = "",
) -> str:
    vid = f"VER-{uuid4().hex[:8]}"
    ts = datetime.now()
    with connect() as con:
        con.execute(
            """
            INSERT INTO meta_emos_component_version
            (版本记录ID, 组件编号, 原版本, 新版本, 更新原因, 来源项目, 数据更新时间)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [vid, 组件编号, 原版本, 新版本, 更新原因, 来源项目, ts],
        )
    return vid


def list_component_versions(limit: int = 50) -> pd.DataFrame:
    with connect(read_only=True) as con:
        try:
            return con.execute(
                """
                SELECT * FROM meta_emos_component_version
                ORDER BY 数据更新时间 DESC LIMIT ?
                """,
                [limit],
            ).fetchdf()
        except Exception:  # noqa: BLE001
            return pd.DataFrame()
