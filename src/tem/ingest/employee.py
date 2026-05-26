"""raw_employee 企业人员信息 ingest（§10）。

注意：人员表通常按客户全量提供，§10 中"项目ID"字段允许为空。
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from ..normalize import apply_aliases, coerce_date
from .common import IngestContext, inject_platform_columns, read_any, scan_files, write_dataframe


def _normalize_employee_df(df: pd.DataFrame, ctx: IngestContext) -> pd.DataFrame:
    df = apply_aliases(df, "employee")

    for col in ["生效日期", "离职日期"]:
        if col in df.columns:
            df[col] = df[col].map(coerce_date)

    df = inject_platform_columns(df, ctx)
    df = df.dropna(subset=["员工ID"]) if "员工ID" in df.columns else df
    return df


def ingest_employee(ctx: IngestContext, files: list[Path] | None = None) -> int:
    ctx.resolve_meta()
    paths = files or scan_files("employee", ctx)
    if not paths:
        return 0
    frames: list[pd.DataFrame] = []
    for p in paths:
        df = read_any(p)
        if isinstance(df, dict):
            for sheet_df in df.values():
                frames.append(_normalize_employee_df(sheet_df, ctx))
        else:
            frames.append(_normalize_employee_df(df, ctx))
    merged = pd.concat([f for f in frames if not f.empty], ignore_index=True) if frames else pd.DataFrame()
    if merged.empty:
        return 0
    # 人员表通常按客户级别覆盖；项目ID 可为空，此时仅按 客户ID 重写
    return write_dataframe(merged, "raw_employee", ctx, replace_scope=True)
