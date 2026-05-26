"""异常规则 - §13.5。

包括：
  - 漫游异常       apply_roaming
  - 增值业务异常   apply_value_added（基于账单明细）
  - 离职后计费     apply_post_termination
  - 资产缺失 / 人员缺失 / 事件未闭环 由 build 阶段聚合标签
  - aggregate_anomaly_summary 把所有 是否XXX 标签聚合为 异常类型 / 异常金额 / 建议动作
"""
from __future__ import annotations

import pandas as pd

from ..config import get_rules


# 标签 -> (异常类型名称, 建议动作)
ANOMALY_LABELS: list[tuple[str, str, str]] = [
    ("是否超套",         "超套",         "通知主管确认是否需要套餐升级或费用核减"),
    ("是否零用量但计费", "零用量",       "确认是否需要停机/销户或回收号码"),
    ("是否高流量",       "高流量",       "提醒员工注意流量使用，必要时调整套餐"),
    ("是否高通话",       "高通话",       "提醒员工注意通话时长，必要时调整套餐"),
    ("是否漫游",         "漫游",         "确认是否合规，必要时通知主管审批"),
    ("是否增值业务异常", "增值业务",     "核对增值业务费用合理性，剔除非合规扣费"),
    ("是否离职后计费",   "离职后计费",   "立即停机/销户，并核减离职后产生费用"),
    ("是否资产缺失",     "资产缺失",     "补登资产记录或核对账单号码归属"),
    ("是否人员缺失",     "人员缺失",     "补登人员归属或核对账单号码归属"),
    ("是否事件未闭环",   "事件未闭环",   "推动事件经办人完成闭环"),
    ("是否长期闲置",     "长期闲置",     "纳入销户/回收建议清单"),
]


# ---------------------------------------------------------------------------
# 漫游
# ---------------------------------------------------------------------------
def apply_roaming(df: pd.DataFrame, billing_detail: pd.DataFrame | None = None) -> pd.DataFrame:
    """根据用量字段 + 账单明细一级科目识别漫游使用。"""
    rules = get_rules()
    df = df.copy()

    flag_usage = pd.Series([False] * len(df), index=df.index)
    for col in ["国际漫游流量", "港澳台漫游流量"]:
        if col in df.columns:
            flag_usage = flag_usage | (pd.to_numeric(df[col], errors="coerce").fillna(0) > 0)

    flag_bill = pd.Series([False] * len(df), index=df.index)
    if billing_detail is not None and not billing_detail.empty:
        keywords = rules.roaming_bill_keywords
        if keywords:
            mask = (
                billing_detail["一级科目"].astype(str).str.contains("|".join(keywords), na=False)
                & (pd.to_numeric(billing_detail["实际应收"], errors="coerce").fillna(0) > 0)
            )
            roam_phones = set(billing_detail.loc[mask, "服务号码"].dropna().astype(str))
            if "服务号码" in df.columns:
                flag_bill = df["服务号码"].astype(str).isin(roam_phones)

    df["是否漫游"] = (flag_usage | flag_bill).fillna(False)
    return df


# ---------------------------------------------------------------------------
# 增值业务（B05）
# ---------------------------------------------------------------------------
def apply_value_added(df: pd.DataFrame, billing_detail: pd.DataFrame | None = None) -> pd.DataFrame:
    """基于账单明细 一级科目 ∈ 关键字 且 实际应收 > 0，二级/三级不在白名单。"""
    rules = get_rules()
    df = df.copy()

    if billing_detail is None or billing_detail.empty:
        df["是否增值业务异常"] = False
        df["增值业务金额"] = 0.0
        return df

    keywords = rules.value_added_bill_keywords
    if not keywords:
        df["是否增值业务异常"] = False
        df["增值业务金额"] = 0.0
        return df

    mask = (
        billing_detail["一级科目"].astype(str).str.contains("|".join(keywords), na=False)
        & (pd.to_numeric(billing_detail["实际应收"], errors="coerce").fillna(0) > 0)
    )

    whitelist = {str(x).strip() for x in rules.value_added_whitelist if x}
    if whitelist:
        for col in ["二级科目", "三级科目"]:
            if col in billing_detail.columns:
                mask = mask & ~billing_detail[col].astype(str).isin(whitelist)

    sub = billing_detail.loc[mask].groupby("服务号码", dropna=False)["实际应收"].apply(
        lambda s: pd.to_numeric(s, errors="coerce").fillna(0).sum()
    )
    if "服务号码" in df.columns:
        df["增值业务金额"] = df["服务号码"].astype(str).map(sub).fillna(0.0)
    else:
        df["增值业务金额"] = 0.0
    df["是否增值业务异常"] = df["增值业务金额"] > 0
    return df


# ---------------------------------------------------------------------------
# 离职后计费
# ---------------------------------------------------------------------------
def apply_post_termination(df: pd.DataFrame) -> pd.DataFrame:
    """离职日期早于账期月末，且账单实际应收 > 0 -> 离职后计费异常。"""
    rules = get_rules()
    df = df.copy()
    df["是否离职后计费"] = False

    if "员工状态" not in df.columns and "离职日期" not in df.columns:
        return df

    actual = pd.to_numeric(df.get("实际应收", 0), errors="coerce").fillna(0)

    # 通过离职日期：把账期 yyyymm 转成月末日期
    leave_flag = pd.Series([False] * len(df), index=df.index)
    if "离职日期" in df.columns and "账期" in df.columns:
        try:
            month_end = pd.to_datetime(df["账期"].astype(str) + "01", format="%Y%m%d", errors="coerce") + pd.offsets.MonthEnd(0)
            leave = pd.to_datetime(df["离职日期"], errors="coerce")
            tolerance = pd.Timedelta(days=rules.post_termination_tolerance_days)
            leave_flag = (leave + tolerance < month_end) & (actual > 0)
        except Exception:  # noqa: BLE001
            leave_flag = pd.Series([False] * len(df), index=df.index)

    # 通过员工状态字符串
    status_flag = pd.Series([False] * len(df), index=df.index)
    if "员工状态" in df.columns:
        status_flag = (
            df["员工状态"].astype(str).str.contains("离职|Terminat|inactive", case=False, na=False)
            & (actual > 0)
        )

    df["是否离职后计费"] = (leave_flag | status_flag).fillna(False)
    return df


# ---------------------------------------------------------------------------
# 异常聚合 - 把所有 是否XXX 标签收敛为 异常类型 / 异常金额 / 建议动作
# ---------------------------------------------------------------------------
def aggregate_anomaly_summary(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    types: list[list[str]] = []
    actions: list[list[str]] = []
    for _, row in df.iterrows():
        ts: list[str] = []
        acts: list[str] = []
        for col, label, action in ANOMALY_LABELS:
            if col in df.columns and bool(row.get(col, False)):
                ts.append(label)
                acts.append(action)
        types.append(ts)
        actions.append(acts)

    df["异常类型"] = ["、".join(ts) for ts in types]
    df["建议动作"] = [" / ".join(dict.fromkeys(a)) for a in actions]

    # 异常金额：超套金额 + 增值业务金额 + 离职后实际应收
    overpkg = pd.to_numeric(df.get("超套金额", 0), errors="coerce").fillna(0)
    vas = pd.to_numeric(df.get("增值业务金额", 0), errors="coerce").fillna(0)
    actual = pd.to_numeric(df.get("实际应收", 0), errors="coerce").fillna(0)
    is_post = df.get("是否离职后计费", pd.Series([False] * len(df))).fillna(False).astype(bool)
    is_zero_billed = df.get("是否零用量但计费", pd.Series([False] * len(df))).fillna(False).astype(bool)

    anomaly_amount = overpkg.copy()
    anomaly_amount = anomaly_amount + vas
    anomaly_amount = anomaly_amount + actual.where(is_post, 0)
    anomaly_amount = anomaly_amount + actual.where(is_zero_billed, 0)
    df["异常金额"] = anomaly_amount

    if "处理状态" not in df.columns:
        df["处理状态"] = "未处理"
    else:
        df["处理状态"] = df["处理状态"].fillna("未处理")
    return df
