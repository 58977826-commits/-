"""§15.4 超套分析。"""
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

_APP = Path(__file__).resolve().parents[1]
if str(_APP) not in sys.path:
    sys.path.insert(0, str(_APP))

from _shared import apply_brand_theme, query_fact, require_filters, section_tag  # noqa: E402


apply_brand_theme("超套分析", layout="wide")
section_tag("§15.4 标准套餐金额 vs 实际应收")
st.title("📈 超套分析")

if not require_filters():
    st.stop()

summary = query_fact("""
    SELECT
        COUNT(*) AS 号码数,
        SUM(CASE WHEN 是否超套 THEN 1 ELSE 0 END) AS 超套号码数,
        SUM(超套金额) AS 超套金额合计,
        AVG(超套率) AS 平均超套率
    FROM fact_tem_monthly
    WHERE 客户ID = ? AND 项目ID = ? AND 账期 = ?
""")
if not summary.empty:
    row = summary.iloc[0]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("分析号码数", int(row["号码数"] or 0))
    c2.metric("超套号码数", int(row["超套号码数"] or 0))
    c3.metric("超套金额", f"￥{float(row['超套金额合计'] or 0):,.2f}")
    avg = row["平均超套率"]
    c4.metric("平均超套率", f"{float(avg or 0) * 100:,.1f}%")

st.subheader("超套清单")
df_over = query_fact("""
    SELECT * FROM v_overpackage_list
    WHERE 客户ID = ? AND 项目ID = ? AND 账期 = ?
    ORDER BY 超套金额 DESC NULLS LAST
""")
st.dataframe(df_over, use_container_width=True)

st.subheader("部门超套排行")
df_dept = query_fact("""
    SELECT Department, COUNT(*) AS 超套号码数, SUM(超套金额) AS 超套金额
    FROM fact_tem_monthly
    WHERE 客户ID = ? AND 项目ID = ? AND 账期 = ? AND 是否超套 = TRUE
    GROUP BY Department
    ORDER BY 超套金额 DESC NULLS LAST
""")
st.dataframe(df_dept, use_container_width=True)

st.subheader("成本中心超套排行")
df_cc = query_fact("""
    SELECT CostCenter, COUNT(*) AS 超套号码数, SUM(超套金额) AS 超套金额
    FROM fact_tem_monthly
    WHERE 客户ID = ? AND 项目ID = ? AND 账期 = ? AND 是否超套 = TRUE
    GROUP BY CostCenter
    ORDER BY 超套金额 DESC NULLS LAST
""")
st.dataframe(df_cc, use_container_width=True)
