"""单位换算 - U02 / U03 / A05 / EV15。"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

import pandas as pd


_EXCEL_EPOCH = datetime(1899, 12, 30)


def seconds_to_minutes(seconds: Any) -> float | None:
    """U02: 秒 -> 分钟（保留 2 位小数）。"""
    if seconds is None or (isinstance(seconds, float) and pd.isna(seconds)):
        return None
    try:
        return round(float(seconds) / 60.0, 2)
    except (TypeError, ValueError):
        return None


def mb_to_gb(mb: Any) -> float | None:
    """U03: M -> GB（保留 4 位小数）。"""
    if mb is None or (isinstance(mb, float) and pd.isna(mb)):
        return None
    try:
        return round(float(mb) / 1024.0, 4)
    except (TypeError, ValueError):
        return None


def excel_serial_to_date(value: Any) -> date | None:
    """A05 / EV15: Excel 日期序列号 -> 标准日期。

    Excel 序列号约定 1899-12-30 为 0；典型范围 1~60000。
    """
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    if n < 1 or n > 80000:
        return None
    return (_EXCEL_EPOCH + timedelta(days=n)).date()


def coerce_date(value: Any) -> date | None:
    """通用日期解析：支持 Excel 序列号 / 日期 / 字符串。"""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, pd.Timestamp):
        if pd.isna(value):
            return None
        return value.to_pydatetime().date()
    if isinstance(value, (int, float)):
        if isinstance(value, float) and pd.isna(value):
            return None
        return excel_serial_to_date(value)
    s = str(value).strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y%m%d", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    try:
        return pd.to_datetime(s, errors="coerce").to_pydatetime().date()
    except (ValueError, AttributeError):
        return None


def period_yyyymm(value: Any) -> str | None:
    """从任意日期 / 字符串派生 YYYYMM。"""
    d = coerce_date(value)
    if d is None:
        return None
    return f"{d.year:04d}{d.month:02d}"
