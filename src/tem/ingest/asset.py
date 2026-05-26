"""raw_asset 资产管理系统 ingest（§9）。"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from ..normalize import apply_aliases, coerce_date, normalize_phone
from .common import IngestContext, inject_platform_columns, read_any, scan_files, write_dataframe


def _normalize_asset_df(df: pd.DataFrame, ctx: IngestContext) -> pd.DataFrame:
    df = apply_aliases(df, "asset")

    if "服务号码" in df.columns:
        df["服务号码"] = df["服务号码"].map(normalize_phone)

    for col in ["采购日期", "投产日期", "保修到期日"]:
        if col in df.columns:
            df[col] = df[col].map(coerce_date)

    if "标准套餐金额" in df.columns:
        df["标准套餐金额"] = pd.to_numeric(df["标准套餐金额"], errors="coerce")

    df = inject_platform_columns(df, ctx)
    return df


def ingest_asset(ctx: IngestContext, files: list[Path] | None = None) -> int:
    ctx.resolve_meta()
    paths = files or scan_files("asset", ctx)
    if not paths:
        return 0
    frames: list[pd.DataFrame] = []
    for p in paths:
        df = read_any(p)
        if isinstance(df, dict):
            for sheet_df in df.values():
                frames.append(_normalize_asset_df(sheet_df, ctx))
        else:
            frames.append(_normalize_asset_df(df, ctx))
    merged = pd.concat([f for f in frames if not f.empty], ignore_index=True) if frames else pd.DataFrame()
    if merged.empty:
        return 0
    return write_dataframe(merged, "raw_asset", ctx, replace_scope=True)
