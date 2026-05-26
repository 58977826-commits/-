"""高用量规则 - H01 ~ H04。

H01 高流量按套餐阈值判断（暂未维护套餐阈值表，先用 hard_cap）
H02 无套餐阈值时按 P95 判断
H03 高通话同 H02
H04 高用量且高费用 -> 重点分析（在 anomalies 中聚合）
"""
from __future__ import annotations

import pandas as pd

from ..config import get_rules


def apply_high_usage(df: pd.DataFrame) -> pd.DataFrame:
    """添加 是否高流量 / 是否高通话 列。

    高用量判定：先看 hard_cap；再看分位值（在当前批次内动态计算 P95）。
    """
    rules = get_rules()
    df = df.copy()

    voice = pd.to_numeric(df.get("总通话分钟"), errors="coerce").fillna(0)
    data = pd.to_numeric(df.get("总流量GB"), errors="coerce").fillna(0)

    # hard cap
    high_data = data >= rules.high_usage_data_gb_hard_cap
    high_voice = voice >= rules.high_usage_voice_min_hard_cap

    if rules.high_usage_use_percentile and len(df) >= 5:
        data_p95 = float(data.quantile(0.95)) if rules.high_usage_data_gb_p95_default is None \
            else rules.high_usage_data_gb_p95_default
        voice_p95 = float(voice.quantile(0.95)) if rules.high_usage_voice_min_p95_default is None \
            else rules.high_usage_voice_min_p95_default
        # P95 至少需要 > 0 才有意义
        if data_p95 > 0:
            high_data = high_data | (data >= data_p95)
        if voice_p95 > 0:
            high_voice = high_voice | (voice >= voice_p95)

    df["是否高流量"] = high_data.fillna(False)
    df["是否高通话"] = high_voice.fillna(False)
    return df
