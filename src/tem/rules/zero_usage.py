"""零用量与低用量规则 - Z01 ~ Z04 + 低用量。

Z01 总流量GB = 0 且 总通话分钟 = 0 且 短信条数 = 0 -> 零用量
Z02 零用量但 实际应收 > 0 -> "零用量但计费"
Z03 连续多月零用量但仍计费 -> "长期闲置号码"（依赖历史 fact_tem_monthly）
Z04 若零用量号码存在入职/库存变更/离职归还事件，结合事件解释（在 event_rules.py 处理）

低用量参数：voice_min_threshold / data_gb_threshold（来自 rules.yaml）
"""
from __future__ import annotations

import pandas as pd

from ..config import get_rules
from ..db import connect


def _safe_num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce").fillna(0)


def apply_zero_usage(df: pd.DataFrame) -> pd.DataFrame:
    """添加 是否零用量 / 是否低用量 / 是否长期闲置 / 是否零用量但计费 列。"""
    rules = get_rules()
    df = df.copy()

    voice = _safe_num(df.get("总通话分钟", pd.Series([0] * len(df))))
    data = _safe_num(df.get("总流量GB", df.get("总流量_GB", pd.Series([0] * len(df)))))
    sms = _safe_num(df.get("短信条数", df.get("总短信条数", pd.Series([0] * len(df)))))

    # 统一字段命名
    df["总通话分钟"] = voice
    df["总流量GB"] = data
    df["短信条数"] = sms.astype(int)

    df["是否零用量"] = (voice == 0) & (data == 0) & (sms == 0)            # Z01
    df["是否低用量"] = (
        (voice <= rules.low_usage_voice_min) & (data <= rules.low_usage_data_gb)
    ) & ~df["是否零用量"]

    actual = pd.to_numeric(df.get("实际应收", 0), errors="coerce").fillna(0)
    df["是否零用量但计费"] = df["是否零用量"] & (actual > 0)              # Z02

    # Z03: 连续 N 个月零用量
    df["是否长期闲置"] = _flag_consecutive_zero_usage(df, rules.zero_usage_consecutive_months)

    return df


def _flag_consecutive_zero_usage(df: pd.DataFrame, n: int) -> pd.Series:
    """根据历史 fact_tem_monthly 判断连续 N 个月零用量。

    若历史表为空或无任何记录，则只能本月判断 -> False。
    """
    if n <= 1 or df.empty:
        return df.get("是否零用量", pd.Series([False] * len(df))).fillna(False)

    flag = pd.Series([False] * len(df), index=df.index)
    try:
        with connect(read_only=True) as con:
            hist = con.execute(
                """
                SELECT 客户ID, 项目ID, 服务号码, 账期, 是否零用量
                FROM fact_tem_monthly
                """
            ).fetchdf()
    except Exception:  # noqa: BLE001
        return flag

    if hist.empty:
        return flag

    hist = hist.sort_values(["客户ID", "项目ID", "服务号码", "账期"], ascending=[True, True, True, False])
    grouped = hist.groupby(["客户ID", "项目ID", "服务号码"])

    for idx, row in df.iterrows():
        key = (row.get("客户ID"), row.get("项目ID"), row.get("服务号码"))
        if key not in grouped.groups:
            continue
        recent = grouped.get_group(key).head(n - 1)["是否零用量"].fillna(False).tolist()
        if len(recent) < n - 1:
            continue
        if all(bool(x) for x in recent) and bool(row.get("是否零用量", False)):
            flag.at[idx] = True
    return flag
