"""§15.3 用量分析。"""
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

_APP = Path(__file__).resolve().parents[1]
if str(_APP) not in sys.path:
    sys.path.insert(0, str(_APP))

from _shared import init_page, query_fact, require_filters, section_tag  # noqa: E402


init_page("用量分析", layout="wide")
section_tag("§15.3 流量 / 语音 / 短信")
st.title("📊 用量分析")

if not require_filters():
    st.stop()

summary = query_fact("""
    SELECT
        SUM(总流量GB) AS 总流量GB,
        SUM(总通话分钟) AS 总通话分钟,
        SUM(短信条数) AS 短信总量,
        AVG(总流量GB) AS 人均流量GB,
        AVG(总通话分钟) AS 人均通话分钟,
        SUM(CASE WHEN 是否零用量 THEN 1 ELSE 0 END) AS 零用量号码数,
        SUM(CASE WHEN 是否低用量 THEN 1 ELSE 0 END) AS 低用量号码数
    FROM fact_tem_monthly
    WHERE 客户ID = ? AND 项目ID = ? AND 账期 = ?
""")
if not summary.empty:
    row = summary.iloc[0]
    c1, c2, c3 = st.columns(3)
    c1.metric("总流量(GB)", f"{float(row['总流量GB'] or 0):,.2f}")
    c2.metric("总通话(分钟)", f"{float(row['总通话分钟'] or 0):,.0f}")
    c3.metric("短信总量", int(row["短信总量"] or 0))
    c4, c5, c6, c7 = st.columns(4)
    c4.metric("人均流量(GB)", f"{float(row['人均流量GB'] or 0):,.2f}")
    c5.metric("人均通话(分钟)", f"{float(row['人均通话分钟'] or 0):,.0f}")
    c6.metric("零用量号码数", int(row["零用量号码数"] or 0))
    c7.metric("低用量号码数", int(row["低用量号码数"] or 0))

st.divider()

c1, c2 = st.columns(2)

with c1:
    st.subheader("流量 TOP 20")
    df_top_data = query_fact("""
        SELECT 服务号码, 员工姓名, Department, CostCenter, 总流量GB, 实际应收
        FROM fact_tem_monthly
        WHERE 客户ID = ? AND 项目ID = ? AND 账期 = ?
        ORDER BY 总流量GB DESC NULLS LAST
        LIMIT 20
    """)
    st.dataframe(df_top_data, use_container_width=True)

with c2:
    st.subheader("通话 TOP 20")
    df_top_voice = query_fact("""
        SELECT 服务号码, 员工姓名, Department, CostCenter, 总通话分钟, 实际应收
        FROM fact_tem_monthly
        WHERE 客户ID = ? AND 项目ID = ? AND 账期 = ?
        ORDER BY 总通话分钟 DESC NULLS LAST
        LIMIT 20
    """)
    st.dataframe(df_top_voice, use_container_width=True)

st.subheader("零用量清单")
df_zero = query_fact("""
    SELECT 服务号码, 员工姓名, Department, CostCenter, 资产状态,
           实际应收, 是否零用量但计费, 是否长期闲置, 当月事件类型
    FROM fact_tem_monthly
    WHERE 客户ID = ? AND 项目ID = ? AND 账期 = ? AND 是否零用量 = TRUE
    ORDER BY 实际应收 DESC NULLS LAST
""")
st.dataframe(df_zero, use_container_width=True)
