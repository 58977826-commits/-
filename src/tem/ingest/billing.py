"""raw_billing_list / raw_billing_detail 账单数据 ingest（§8）。

文件命名约定（任选其一即可）：
    *清单*.xlsx       -> raw_billing_list
    *list*.xlsx       -> raw_billing_list
    *明细*.xlsx       -> raw_billing_detail
    *detail*.xlsx     -> raw_billing_detail
    若一个 .xlsx 含多个 sheet，sheet 名包含上述关键字也可识别。
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from ..normalize import apply_aliases, normalize_account_period, normalize_phone
from .common import IngestContext, inject_platform_columns, read_any, scan_files, write_dataframe


_LIST_KEYWORDS = ("清单", "list", "List", "汇总")
_DETAIL_KEYWORDS = ("明细", "detail", "Detail")


def _classify_sheet_name(name: str) -> str | None:
    n = (name or "").strip().lower()
    if any(k.lower() in n for k in _LIST_KEYWORDS):
        return "billing_list"
    if any(k.lower() in n for k in _DETAIL_KEYWORDS):
        return "billing_detail"
    return None


def _classify_file_name(path: Path) -> str | None:
    n = path.stem.lower()
    if any(k.lower() in n for k in _LIST_KEYWORDS):
        return "billing_list"
    if any(k.lower() in n for k in _DETAIL_KEYWORDS):
        return "billing_detail"
    return None


def _normalize_billing_df(df: pd.DataFrame, ctx: IngestContext, table: str) -> pd.DataFrame:
    df = apply_aliases(df, table)

    if "服务号码" in df.columns:
        df["服务号码"] = df["服务号码"].map(normalize_phone)
    if "账期" in df.columns:
        df["账期"] = df["账期"].map(normalize_account_period)
    elif ctx.账期:
        df["账期"] = ctx.账期

    for col in ["计费应收", "账务优惠", "实际应收"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df = inject_platform_columns(df, ctx)
    df = df.dropna(subset=["服务号码"])
    return df


def ingest_billing(ctx: IngestContext, files: list[Path] | None = None) -> dict[str, int]:
    """返回 {"billing_list": n1, "billing_detail": n2}。"""
    ctx.resolve_meta()
    paths = files or scan_files("billing", ctx)
    list_frames: list[pd.DataFrame] = []
    detail_frames: list[pd.DataFrame] = []

    for p in paths:
        suffix = p.suffix.lower()
        if suffix == ".csv":
            kind = _classify_file_name(p) or "billing_list"
            df = read_any(p)
            df = _normalize_billing_df(df, ctx, kind)
            (list_frames if kind == "billing_list" else detail_frames).append(df)
            continue

        # Excel: 优先按 sheet 名分类，否则按文件名
        try:
            xl = pd.ExcelFile(p)
        except Exception as e:  # noqa: BLE001
            raise RuntimeError(f"读取账单文件失败: {p}") from e

        file_kind = _classify_file_name(p)
        for sheet in xl.sheet_names:
            kind = _classify_sheet_name(sheet) or file_kind
            if kind not in {"billing_list", "billing_detail"}:
                # sheet 无关键字、文件也无 -> 默认按 list 处理
                kind = "billing_list"
            sheet_df = pd.read_excel(p, sheet_name=sheet, dtype=object)
            sheet_df = _normalize_billing_df(sheet_df, ctx, kind)
            if sheet_df.empty:
                continue
            (list_frames if kind == "billing_list" else detail_frames).append(sheet_df)

    counts: dict[str, int] = {"billing_list": 0, "billing_detail": 0}
    if list_frames:
        merged = pd.concat(list_frames, ignore_index=True)
        # 同号码同账期可能多条（不同账户 ID），按主键聚合实际应收
        if not merged.empty:
            counts["billing_list"] = write_dataframe(merged, "raw_billing_list", ctx, replace_scope=True)
    if detail_frames:
        merged = pd.concat(detail_frames, ignore_index=True)
        if not merged.empty:
            counts["billing_detail"] = write_dataframe(merged, "raw_billing_detail", ctx, replace_scope=True)
    return counts
