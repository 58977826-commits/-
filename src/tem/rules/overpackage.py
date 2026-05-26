"""超套规则 - C01 ~ C06。

C01 标准套餐金额来自资产表标准套餐金额字段（§9 / §13.1）
C02 超套金额 = max(实际应收 - 标准套餐金额, 0)
C03 若超套金额 <= 0，记 0
C04 超套率 = 超套金额 / 标准套餐金额
C05 实际应收超过标准套餐金额 5% -> 是否超套 = True
C06 若存在套餐升级事件，结合事件表解释（在 event_rules.py / build 阶段联动）
"""
from __future__ import annotations

import pandas as pd

from ..config import get_rules


def apply_overpackage(df: pd.DataFrame) -> pd.DataFrame:
    """在 df 上添加 标准套餐金额 / 超套金额 / 超套率 / 是否超套。"""
    rules = get_rules()
    warn_ratio = rules.overpackage_warn_ratio
    default_fee = rules.overpackage_default_standard_fee

    df = df.copy()

    if "标准套餐金额" not in df.columns:
        df["标准套餐金额"] = None
    if "实际应收" not in df.columns:
        df["实际应收"] = 0.0

    df["标准套餐金额"] = pd.to_numeric(df["标准套餐金额"], errors="coerce")
    df["实际应收"] = pd.to_numeric(df["实际应收"], errors="coerce").fillna(0.0)

    # default fee 回填
    if default_fee is not None:
        df["标准套餐金额"] = df["标准套餐金额"].fillna(default_fee)

    # C02 / C03
    diff = df["实际应收"] - df["标准套餐金额"]
    df["超套金额"] = diff.where(diff > 0, 0.0)
    df.loc[df["标准套餐金额"].isna(), "超套金额"] = pd.NA

    # C04
    standard = df["标准套餐金额"].astype("float64")
    over = pd.to_numeric(df["超套金额"], errors="coerce")
    rate = over / standard
    rate = rate.replace([float("inf"), float("-inf")], pd.NA)
    df["超套率"] = rate.where(standard.fillna(0) > 0, pd.NA)

    # C05
    threshold = df["标准套餐金额"] * (1 + warn_ratio)
    df["是否超套"] = (df["实际应收"] > threshold).fillna(False)
    # 标准套餐金额缺失 -> 不判超套
    df.loc[df["标准套餐金额"].isna(), "是否超套"] = False

    return df
