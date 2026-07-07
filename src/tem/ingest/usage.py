"""raw_usage 用量数据 ingest（§7）。"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from ..normalize import (
    apply_aliases_with_report,
    mb_to_gb,
    normalize_account_period,
    normalize_phone,
    seconds_to_minutes,
)
from .common import IngestContext, inject_platform_columns, read_any, scan_files, write_dataframe


def _normalize_usage_df(df: pd.DataFrame, ctx: IngestContext) -> tuple[pd.DataFrame, dict[str, str], list[str]]:
    source_columns = [str(c).strip() for c in df.columns]
    df, rename = apply_aliases_with_report(df, "usage")

    if "服务号码" in df.columns:
        df["服务号码"] = df["服务号码"].map(normalize_phone)

    if "账期" in df.columns:
        df["账期"] = df["账期"].map(normalize_account_period)
    elif ctx.账期:
        df["账期"] = ctx.账期

    # U02 / U03 单位换算（缺失时回填）
    if "总通话分钟" not in df.columns and "总通话时长_秒" in df.columns:
        df["总通话分钟"] = df["总通话时长_秒"].map(seconds_to_minutes)
    if "总流量_GB" not in df.columns and "总流量_M" in df.columns:
        df["总流量_GB"] = df["总流量_M"].map(mb_to_gb)

    for col in [
        "总短信条数", "总通话时长_秒", "总通话分钟", "总流量_M", "总流量_GB",
        "主叫通话时长", "被叫通话时长",
        "国内漫游流量", "港澳台漫游流量", "国际漫游流量",
    ]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # U05: 是否零用量；U06: 漫游
    voice = df.get("总通话分钟", pd.Series([0] * len(df))).fillna(0)
    data = df.get("总流量_GB", pd.Series([0] * len(df))).fillna(0)
    sms = df.get("总短信条数", pd.Series([0] * len(df))).fillna(0)
    df["是否有语音"] = voice > 0
    df["是否有流量"] = data > 0
    df["是否有短信"] = sms > 0
    df["是否零用量"] = (voice == 0) & (data == 0) & (sms == 0)

    roam_cols = [c for c in ["国际漫游流量", "港澳台漫游流量"] if c in df.columns]
    if roam_cols:
        df["是否漫游使用"] = df[roam_cols].fillna(0).sum(axis=1) > 0
    else:
        df["是否漫游使用"] = False

    # U04: 同 (客户ID + 项目ID + 账期 + 服务号码) 多条记录聚合
    df = inject_platform_columns(df, ctx)
    df = df.dropna(subset=["服务号码"])
    if df.empty:
        return df, rename, source_columns

    group_keys = ["客户ID", "项目ID", "账期", "服务号码"]
    agg_map = {
        "总短信条数": "sum",
        "总通话时长_秒": "sum",
        "总通话分钟": "sum",
        "总流量_M": "sum",
        "总流量_GB": "sum",
        "主叫通话时长": "sum",
        "被叫通话时长": "sum",
        "国内漫游流量": "sum",
        "港澳台漫游流量": "sum",
        "国际漫游流量": "sum",
        "是否有语音": "any",
        "是否有流量": "any",
        "是否有短信": "any",
        "是否零用量": "all",
        "是否漫游使用": "any",
        "客户名称": "first",
        "项目名称": "first",
        "数据月份": "first",
        "数据来源": "first",
        "导入批次号": "first",
        "数据更新时间": "first",
    }
    agg_map = {k: v for k, v in agg_map.items() if k in df.columns}
    df = df.groupby(group_keys, dropna=False, as_index=False).agg(agg_map)

    return df, rename, source_columns


def ingest_usage(ctx: IngestContext, files: list[Path] | None = None) -> int:
    ctx.resolve_meta()
    paths = files or scan_files("usage", ctx)
    if not paths:
        return 0
    frames: list[pd.DataFrame] = []
    alias_map: dict[str, str] = {}
    source_columns: list[str] = []
    source_file: str | None = None
    for p in paths:
        df = read_any(p)
        if isinstance(df, dict):
            for sheet_df in df.values():
                norm, rename, src_cols = _normalize_usage_df(sheet_df, ctx)
                frames.append(norm)
                alias_map.update(rename)
                source_columns = src_cols
                source_file = p.name
        else:
            norm, rename, src_cols = _normalize_usage_df(df, ctx)
            frames.append(norm)
            alias_map.update(rename)
            source_columns = src_cols
            source_file = p.name
    merged = pd.concat([f for f in frames if not f.empty], ignore_index=True) if frames else pd.DataFrame()
    if merged.empty:
        return 0
    return write_dataframe(
        merged, "raw_usage", ctx, replace_scope=True,
        alias_map=alias_map or None,
        source_columns=source_columns or None,
        source_file=source_file,
    )
