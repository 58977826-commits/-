"""§15.2 费用统计 - 多维度。"""
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

_APP = Path(__file__).resolve().parents[1]
if str(_APP) not in sys.path:
    sys.path.insert(0, str(_APP))

from _shared import init_page, query_fact, require_filters, section_tag  # noqa: E402


init_page("费用统计", layout="wide")
section_tag("§15.2 多维度聚合")
st.title("💰 费用统计")

if not require_filters():
    st.stop()

st.subheader("按部门 / BU")
df_dept = query_fact("""
    SELECT BU, Department,
           COUNT(*) AS 号码数,
           COUNT(DISTINCT 员工ID) AS 员工数,
           SUM(实际应收) AS 实际应收合计,
           SUM(超套金额) AS 超套金额合计
    FROM fact_tem_monthly
    WHERE 客户ID = ? AND 项目ID = ? AND 账期 = ?
    GROUP BY BU, Department
    ORDER BY 实际应收合计 DESC NULLS LAST
""")
st.dataframe(df_dept, use_container_width=True)

st.subheader("按成本中心")
df_cc = query_fact("""
    SELECT CostCenter, BU, Department,
           COUNT(*) AS 号码数,
           SUM(实际应收) AS 实际应收合计,
           SUM(超套金额) AS 超套金额合计
    FROM fact_tem_monthly
    WHERE 客户ID = ? AND 项目ID = ? AND 账期 = ?
    GROUP BY CostCenter, BU, Department
    ORDER BY 实际应收合计 DESC NULLS LAST
""")
st.dataframe(df_cc, use_container_width=True)

st.subheader("按号码 TOP 20")
df_phone = query_fact("""
    SELECT 服务号码, 员工姓名, Department, CostCenter,
           标准套餐金额, 实际应收, 超套金额, 总流量GB, 总通话分钟
    FROM fact_tem_monthly
    WHERE 客户ID = ? AND 项目ID = ? AND 账期 = ?
    ORDER BY 实际应收 DESC NULLS LAST
    LIMIT 20
""")
st.dataframe(df_phone, use_container_width=True)
