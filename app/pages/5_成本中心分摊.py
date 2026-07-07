"""§15.6 成本中心分摊。"""
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

_APP = Path(__file__).resolve().parents[1]
if str(_APP) not in sys.path:
    sys.path.insert(0, str(_APP))

from _shared import init_page, query_fact, require_filters, section_tag  # noqa: E402


init_page("成本中心分摊", layout="wide")
section_tag("§15.6 BU / Department / Cost Center 三级分摊")
st.title("🏢 成本中心分摊")

if not require_filters():
    st.stop()

df = query_fact("SELECT * FROM v_costcenter_allocation WHERE 客户ID = ? AND 项目ID = ? AND 账期 = ? ORDER BY 实际应收合计 DESC NULLS LAST")
st.dataframe(df, use_container_width=True)

if not df.empty:
    st.divider()
    st.subheader("成本中心金额排行")
    chart_df = df.set_index("CostCenter")[["实际应收合计", "超套金额", "异常费用"]].fillna(0)
    st.bar_chart(chart_df)
