"""事件规则 - EV09 ~ EV14。

apply_event_status: 把当月事件聚合到号码维度，回写 是否存在当月事件 / 当月事件类型 / 当月事件状态 / 是否事件未闭环
apply_event_change: 标记 是否改号 / 新服务号码 / 是否副卡申请 / 副卡号码 / 系统流水号
"""
from __future__ import annotations

import pandas as pd

from ..config import get_rules


def _events_for_month(events: pd.DataFrame, 客户ID: str, 项目ID: str, 账期: str) -> pd.DataFrame:
    if events is None or events.empty:
        return pd.DataFrame()
    df = events.copy()
    if "事件月份" not in df.columns and "开始时间" in df.columns:
        df["事件月份"] = pd.to_datetime(df["开始时间"], errors="coerce").dt.strftime("%Y%m")
    df = df[(df["客户ID"] == 客户ID) & (df["项目ID"] == 项目ID)]
    if "事件月份" in df.columns:
        df = df[df["事件月份"] == 账期]
    return df


def apply_event_status(df: pd.DataFrame, events: pd.DataFrame, 账期: str) -> pd.DataFrame:
    """对 base 中每个号码补充：当月事件类型 / 动作 / 状态 / 是否未闭环 / 系统流水号。"""
    rules = get_rules()
    df = df.copy()

    df["是否存在当月事件"] = False
    df["当月事件类型"] = pd.NA
    df["当月事件动作"] = pd.NA
    df["当月事件状态"] = pd.NA
    df["是否事件未闭环"] = False
    df["系统流水号"] = pd.NA

    if events is None or events.empty:
        return df

    if df.empty:
        return df

    客户ID = df["客户ID"].iloc[0] if "客户ID" in df.columns and not df["客户ID"].empty else None
    项目ID = df["项目ID"].iloc[0] if "项目ID" in df.columns and not df["项目ID"].empty else None
    if 客户ID is None or 项目ID is None:
        return df

    month_events = _events_for_month(events, 客户ID, 项目ID, 账期)
    if month_events.empty:
        return df

    open_states = set(rules.event_open_states)
    closed_states = set(rules.event_closed_states)

    # 把事件按"涉及的服务号码"展开（原始 / 新 / 副卡 三路都要算）
    rows: list[dict] = []
    for _, e in month_events.iterrows():
        for col in ["原始服务号码", "新服务号码", "副卡号码"]:
            phone = e.get(col)
            if pd.isna(phone) or phone in (None, "", "/"):
                continue
            rows.append({
                "服务号码": phone,
                "事件类型": e.get("事件类型"),
                "事件动作": e.get("事件动作"),
                "事件状态": e.get("事件状态"),
                "系统流水号": e.get("系统流水号"),
            })

    if not rows:
        return df

    ev_df = pd.DataFrame(rows)
    # 同号码多事件 -> 聚合为字符串
    agg_df = ev_df.groupby("服务号码", as_index=False).agg({
        "事件类型": lambda s: "、".join({str(x) for x in s if pd.notna(x)}),
        "事件动作": lambda s: "、".join({str(x) for x in s if pd.notna(x)}),
        "事件状态": lambda s: "、".join({str(x) for x in s if pd.notna(x)}),
        "系统流水号": lambda s: "、".join({str(x) for x in s if pd.notna(x)}),
    })

    df = df.merge(agg_df.rename(columns={
        "事件类型": "_ev_type",
        "事件动作": "_ev_action",
        "事件状态": "_ev_status",
        "系统流水号": "_ev_no",
    }), on="服务号码", how="left")

    df["是否存在当月事件"] = df["_ev_type"].notna()
    df["当月事件类型"] = df["_ev_type"]
    df["当月事件动作"] = df["_ev_action"]
    df["当月事件状态"] = df["_ev_status"]
    df["系统流水号"] = df["_ev_no"]

    # 是否未闭环：事件状态包含开放态，且不全在关闭态
    def _is_open(status_str) -> bool:
        if pd.isna(status_str) or not status_str:
            return False
        parts = [p.strip() for p in str(status_str).split("、") if p.strip()]
        if not parts:
            return False
        # 任一处于开放态 -> 未闭环
        if any(p in open_states for p in parts):
            return True
        # 所有都在关闭态/取消态 -> 已闭环
        return False

    df["是否事件未闭环"] = df["当月事件状态"].map(_is_open).fillna(False)

    df = df.drop(columns=["_ev_type", "_ev_action", "_ev_status", "_ev_no"], errors="ignore")
    return df


def apply_event_change(df: pd.DataFrame, events: pd.DataFrame, 账期: str) -> pd.DataFrame:
    """标记 是否改号 / 新服务号码 / 是否副卡申请 / 副卡号码。"""
    df = df.copy()
    df["是否改号"] = False
    df["新服务号码"] = pd.NA
    df["是否副卡申请"] = False
    df["副卡号码"] = pd.NA

    if events is None or events.empty or df.empty:
        return df

    客户ID = df["客户ID"].iloc[0] if "客户ID" in df.columns else None
    项目ID = df["项目ID"].iloc[0] if "项目ID" in df.columns else None
    if 客户ID is None or 项目ID is None:
        return df

    month_events = _events_for_month(events, 客户ID, 项目ID, 账期)
    if month_events.empty:
        return df

    # 改号事件
    change_mask = month_events["事件动作"].astype(str).str.contains("改号", na=False)
    chg = month_events.loc[change_mask, ["原始服务号码", "新服务号码"]].dropna(subset=["原始服务号码"])
    chg = chg.dropna(how="all")
    chg_map = chg.set_index("原始服务号码")["新服务号码"].to_dict() if not chg.empty else {}
    if chg_map:
        df["新服务号码"] = df["服务号码"].map(chg_map)
        df["是否改号"] = df["新服务号码"].notna()

    # 副卡申请事件
    sub_mask = month_events["事件动作"].astype(str).str.contains("副卡", na=False)
    sub = month_events.loc[sub_mask, ["原始服务号码", "副卡号码"]].dropna(subset=["原始服务号码"])
    sub_map = sub.set_index("原始服务号码")["副卡号码"].to_dict() if not sub.empty else {}
    if sub_map:
        df["副卡号码"] = df["服务号码"].map(sub_map)
        df["是否副卡申请"] = df["副卡号码"].notna()

    return df
