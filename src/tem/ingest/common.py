"""ingest 公共工具：批次号、文件扫描、DataFrame 写库。"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable

import pandas as pd

from ..config import ClientProject, get_settings
from ..db import connect, truncate


@dataclass
class IngestContext:
    """每次 ingest 的上下文（来自 CLI 或调用方）。"""

    客户ID: str
    项目ID: str
    账期: str | None = None              # 用量 / 账单必填；asset / employee / event 可空
    数据来源: str = "联通账单"
    导入批次号: str = field(default_factory=lambda: datetime.now().strftime("%Y%m%d%H%M%S"))
    数据更新时间: datetime = field(default_factory=datetime.now)
    客户名称: str | None = None
    项目名称: str | None = None

    def resolve_meta(self) -> "IngestContext":
        """通过 settings.yaml 补全客户/项目名称。"""
        settings = get_settings()
        meta: ClientProject = settings.lookup_project(self.客户ID, self.项目ID)
        if not self.客户名称:
            self.客户名称 = meta.客户名称
        if not self.项目名称:
            self.项目名称 = meta.项目名称
        return self


def build_batch_id() -> str:
    return datetime.now().strftime("%Y%m%d%H%M%S")


def scan_files(table_type: str, ctx: IngestContext, exts: Iterable[str] = (".xlsx", ".xls", ".csv")) -> list[Path]:
    """按 data/raw/{type}/{客户ID}/{项目ID}/[{账期}/]* 扫描原始文件。

    优先级：
      1. 若 ctx.账期 提供且 ./{账期}/ 存在 -> 使用该账期目录递归
      2. 否则使用项目级目录递归（适配 asset / employee 不带账期的情况）
    避免同时扫两层导致跨月污染。
    """
    settings = get_settings()
    project_root = settings.raw_root / table_type / ctx.客户ID / ctx.项目ID

    base: Path | None = None
    if ctx.账期:
        period_root = project_root / ctx.账期
        if period_root.exists():
            base = period_root
    if base is None and project_root.exists():
        base = project_root
    if base is None:
        return []

    out: list[Path] = []
    for ext in exts:
        out.extend(sorted(base.rglob(f"*{ext}")))
    # 去重并排除 Excel 临时文件 ~$xxx.xlsx
    seen: set[Path] = set()
    deduped: list[Path] = []
    for p in out:
        if p in seen or p.name.startswith("~$"):
            continue
        seen.add(p)
        deduped.append(p)
    return deduped


def read_any(path: Path, sheet_name: str | int | None = 0) -> pd.DataFrame:
    """自动按扩展名选择读取方式。"""
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path, dtype=str, encoding_errors="ignore")
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(path, sheet_name=sheet_name, dtype=object)
    raise ValueError(f"不支持的文件类型: {path}")


def inject_platform_columns(df: pd.DataFrame, ctx: IngestContext) -> pd.DataFrame:
    """注入 §6.1 八个平台通用字段。

    若 df 已有同名列，平台字段会覆盖（保证一致性）。
    """
    df = df.copy()
    df["客户ID"] = ctx.客户ID
    df["客户名称"] = ctx.客户名称
    df["项目ID"] = ctx.项目ID
    df["项目名称"] = ctx.项目名称
    df["数据月份"] = ctx.账期
    df["数据来源"] = ctx.数据来源
    df["导入批次号"] = ctx.导入批次号
    df["数据更新时间"] = ctx.数据更新时间
    return df


def _table_columns(con, table: str) -> list[str]:
    """读取 DuckDB 表的列名列表（PRAGMA table_info: cid, name, ...）。"""
    return [r[1] for r in con.execute(f"PRAGMA table_info('{table}')").fetchall()]


def align_to_table(df: pd.DataFrame, table: str) -> pd.DataFrame:
    """把 DataFrame 列对齐到 DuckDB 表的列顺序，并丢弃多余列。"""
    with connect(read_only=True) as con:
        cols = _table_columns(con, table)
    for c in cols:
        if c not in df.columns:
            df[c] = None
    return df[cols]


def write_dataframe(
    df: pd.DataFrame,
    table: str,
    ctx: IngestContext,
    *,
    replace_scope: bool = True,
) -> int:
    """把 df 写入 DuckDB 表。

    replace_scope=True 时按 (客户ID, 项目ID, 账期) 先删后插，避免重复。
    返回写入行数。
    """
    if df.empty:
        return 0
    df = align_to_table(df, table)
    with connect() as con:
        if replace_scope:
            params = [ctx.客户ID, ctx.项目ID]
            where = "客户ID = ? AND 项目ID = ?"
            if ctx.账期 and "账期" in _table_columns(con, table):
                where += " AND 账期 = ?"
                params.append(ctx.账期)
            con.execute(f"DELETE FROM {table} WHERE {where}", params)
        con.register("incoming_df", df)
        con.execute(f"INSERT INTO {table} SELECT * FROM incoming_df")
        con.unregister("incoming_df")
    return len(df)
