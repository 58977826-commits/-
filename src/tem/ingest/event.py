"""raw_event 月度事件变更总表 ingest（§11）。

第一阶段以"总表" sheet 为准（EV01）。若文件名/sheet 名包含"总表"，优先使用；
否则把所有 sheet 合并导入（让分类子表也作为来源辅助核对）。
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from ..normalize import apply_aliases, coerce_date, normalize_phone, period_yyyymm
from .common import IngestContext, inject_platform_columns, read_any, scan_files, write_dataframe


_TOTAL_KEYWORDS = ("总表", "汇总", "all", "All", "ALL")
_DICT_KEYWORDS = ("事件字典", "字典", "dict", "Dict")
_DROPDOWN_KEYWORDS = ("_下拉选项", "下拉", "Dropdown", "dropdown")


def _is_skip_sheet(name: str) -> bool:
    n = (name or "").strip()
    if not n:
        return True
    return any(k in n for k in (*_DICT_KEYWORDS, *_DROPDOWN_KEYWORDS))


def _is_total_sheet(name: str) -> bool:
    n = (name or "").strip()
    return any(k in n for k in _TOTAL_KEYWORDS)


def _normalize_event_df(df: pd.DataFrame, ctx: IngestContext) -> pd.DataFrame:
    df = apply_aliases(df, "event")

    # EV03 / EV04 / EV05 / EV06: 三路服务号码标准化
    for col in ["原始服务号码", "新服务号码", "副卡号码"]:
        if col in df.columns:
            df[col] = df[col].map(lambda v: None if str(v).strip() in {"", "/"} else normalize_phone(v))

    # EV15: 日期转换
    for col in ["开始时间", "完成时间"]:
        if col in df.columns:
            df[col] = df[col].map(coerce_date)

    # 派生 事件月份（按开始时间），便于按账期 join
    if "开始时间" in df.columns:
        df["事件月份"] = df["开始时间"].map(period_yyyymm)

    df = inject_platform_columns(df, ctx)

    # 只保留有事件类型的行
    if "事件类型" in df.columns:
        df = df[df["事件类型"].notna() & (df["事件类型"].astype(str).str.strip() != "")]
    return df


def ingest_event(ctx: IngestContext, files: list[Path] | None = None) -> int:
    ctx.resolve_meta()
    paths = files or scan_files("event", ctx)
    if not paths:
        return 0

    frames: list[pd.DataFrame] = []
    for p in paths:
        suffix = p.suffix.lower()
        if suffix == ".csv":
            df = read_any(p)
            frames.append(_normalize_event_df(df, ctx))
            continue

        try:
            xl = pd.ExcelFile(p)
        except Exception as e:  # noqa: BLE001
            raise RuntimeError(f"读取事件表失败: {p}") from e

        # 优先取"总表"
        total_sheets = [s for s in xl.sheet_names if _is_total_sheet(s)]
        target_sheets = total_sheets if total_sheets else [
            s for s in xl.sheet_names if not _is_skip_sheet(s)
        ]
        for sheet in target_sheets:
            sheet_df = pd.read_excel(p, sheet_name=sheet, dtype=object)
            sheet_df = _normalize_event_df(sheet_df, ctx)
            if not sheet_df.empty:
                frames.append(sheet_df)

    merged = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if merged.empty:
        return 0
    return write_dataframe(merged, "raw_event", ctx, replace_scope=True)
