"""Streamlit 入口页 - 月度首页（§15.1）。

侧边栏统一选择 客户 / 项目 / 账期，通过 ``st.session_state`` 跨页共享。
"""
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

# 让 Streamlit 子页能 import tem 包（开发期）
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
APP = ROOT / "app"
for _p in (SRC, APP):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from _shared import init_page, hero, section_tag  # noqa: E402
from tem.config import get_settings  # noqa: E402
from tem.db import connect  # noqa: E402


init_page("月度首页", layout="wide")


# ---------------------------------------------------------------------------
# 数据源 - 列出库中已有的客户/项目/账期 + settings.yaml 中配置的客户
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner=False, ttl=30)
def list_clients_periods() -> dict:
    out = {"客户": {}, "账期": []}
    try:
        with connect(read_only=True) as con:
            rows = con.execute(
                """
                SELECT DISTINCT 客户ID, 客户名称, 项目ID, 项目名称, 账期
                FROM fact_tem_monthly
                ORDER BY 客户ID, 项目ID, 账期 DESC
                """
            ).fetchall()
        for c_id, c_name, p_id, p_name, period in rows:
            out["客户"].setdefault(c_id or "?", {
                "name": c_name or c_id,
                "projects": {},
            })
            out["客户"][c_id]["projects"].setdefault(p_id or "?", {
                "name": p_name or p_id,
                "periods": [],
            })
            if period:
                out["客户"][c_id]["projects"][p_id]["periods"].append(period)
                if period not in out["账期"]:
                    out["账期"].append(period)
    except Exception:  # noqa: BLE001
        pass

    settings = get_settings()
    for c in settings.clients:
        c_id = c.get("客户ID")
        out["客户"].setdefault(c_id, {
            "name": c.get("客户名称", c_id),
            "projects": {},
        })
        for p in c.get("projects", []):
            out["客户"][c_id]["projects"].setdefault(p.get("项目ID"), {
                "name": p.get("项目名称", p.get("项目ID")),
                "periods": [],
            })
    return out


# ---------------------------------------------------------------------------
# 侧边栏
# ---------------------------------------------------------------------------
def render_sidebar() -> None:
    st.sidebar.markdown(
        """
        <div style="padding: 0.4rem 0.2rem 1rem 0.2rem;">
            <div style="font-size: 1.25rem; font-weight: 800; color: #E60012;">📡 TEM 看板</div>
            <div style="font-size: 0.78rem; color: #5C5C66; margin-top: 2px;">
                终端全生命周期管理平台 · 一期账务底座
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    catalog = list_clients_periods()

    client_ids = sorted(catalog["客户"].keys())
    if not client_ids:
        st.sidebar.warning("暂无客户数据。请到 **📤 数据导入** 页上传，或运行 `tem run`。")
        return

    default_client = st.session_state.get("客户ID", client_ids[0])
    if default_client not in client_ids:
        default_client = client_ids[0]
    client_id = st.sidebar.selectbox(
        "客户",
        client_ids,
        index=client_ids.index(default_client),
        format_func=lambda x: f"{x} · {catalog['客户'][x]['name']}",
    )

    projects = list(catalog["客户"][client_id]["projects"].keys())
    if not projects:
        st.sidebar.warning("该客户暂无项目")
        return
    default_project = st.session_state.get("项目ID", projects[0])
    if default_project not in projects:
        default_project = projects[0]
    project_id = st.sidebar.selectbox(
        "项目",
        projects,
        index=projects.index(default_project),
        format_func=lambda x: f"{x} · {catalog['客户'][client_id]['projects'][x]['name']}",
    )

    periods = catalog["客户"][client_id]["projects"][project_id]["periods"]
    if not periods:
        st.sidebar.warning("该项目暂无可分析账期。请先到 **📤 数据导入** 页。")
        period = None
    else:
        default_period = st.session_state.get("账期", periods[0])
        if default_period not in periods:
            default_period = periods[0]
        period = st.sidebar.selectbox("账期", periods, index=periods.index(default_period))

    st.session_state["客户ID"] = client_id
    st.session_state["客户名称"] = catalog["客户"][client_id]["name"]
    st.session_state["项目ID"] = project_id
    st.session_state["项目名称"] = catalog["客户"][client_id]["projects"][project_id]["name"]
    st.session_state["账期"] = period


# ---------------------------------------------------------------------------
# 主区
# ---------------------------------------------------------------------------
def render_main() -> None:
    客户ID = st.session_state.get("客户ID")
    项目ID = st.session_state.get("项目ID")
    账期 = st.session_state.get("账期")
    客户名称 = st.session_state.get("客户名称") or ""
    项目名称 = st.session_state.get("项目名称") or ""

    if not (客户ID and 项目ID and 账期):
        hero(
            title="TEM 通信费用管理 · 月度首页",
            subtitle="把账单、用量、资产、人员、事件五类数据贯通成统一的费用画像。",
        )
        st.info(
            "👈 请在左侧选择 **客户 / 项目 / 账期**。\n\n"
            "如果库中还没有数据，请点击侧边栏 **📤 数据导入** 上传 Excel；"
            "或在终端运行 `tem run --客户 X --项目 Y --账期 YYYYMM`。"
        )
        return

    hero(
        title=f"愿与{客户名称}携手共创价值",
        subtitle=f"§15.1 月度核心指标 · 数据来源：联通账单 + 企业资产/人员/事件",
        meta=f"客户 {客户名称}　/　项目 {项目名称}　/　账期 {账期}",
    )

    with connect(read_only=True) as con:
        df = con.execute(
            "SELECT * FROM v_monthly_summary WHERE 客户ID = ? AND 项目ID = ? AND 账期 = ?",
            [客户ID, 项目ID, 账期],
        ).fetchdf()

    if df.empty:
        st.warning("当前账期下未找到 fact_tem_monthly 记录。请先到 **📤 数据导入** 页。")
        return

    row = df.iloc[0]

    # ----- 第一组：账务核心 -----
    section_tag("§15.1.1 账务核心")
    st.subheader("账务核心指标")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("月度账单总额", f"￥{float(row['月度账单总额'] or 0):,.2f}")
    c2.metric("分析号码数", int(row["分析号码数"] or 0))
    c3.metric("人均账单金额", f"￥{float(row['人均账单金额'] or 0):,.2f}")
    c4.metric("超套金额", f"￥{float(row['超套金额'] or 0):,.2f}")

    # ----- 第二组：用量画像 -----
    section_tag("§15.1.2 用量画像")
    st.subheader("用量画像")
    c5, c6, c7, c8 = st.columns(4)
    c5.metric("超套号码数", int(row["超套号码数"] or 0))
    c6.metric("零用量号码数", int(row["零用量号码数"] or 0))
    c7.metric("高流量号码数", int(row["高流量号码数"] or 0))
    c8.metric("高通话号码数", int(row["高通话号码数"] or 0))

    # ----- 第三组：异常与事件 -----
    section_tag("§15.1.3 异常与事件")
    st.subheader("异常与事件")
    c9, c10, c11 = st.columns(3)
    c9.metric("漫游号码数", int(row["漫游号码数"] or 0))
    c10.metric("未闭环事件数", int(row["未闭环事件数"] or 0))
    c11.metric("异常待处理数", int(row["异常待处理数"] or 0))

    st.divider()
    st.caption(
        "数据来源：fact_tem_monthly。指标定义对齐《一期账务底座与 TEM 通信费用管理模块详细设计 v1.1》§15.1。"
    )


render_sidebar()
render_main()
