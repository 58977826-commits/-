"""§15.5 异常费用预警清单。"""
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

_APP = Path(__file__).resolve().parents[1]
if str(_APP) not in sys.path:
    sys.path.insert(0, str(_APP))

from _shared import apply_brand_theme, query_fact, require_filters, section_tag  # noqa: E402


apply_brand_theme("异常清单", layout="wide")
section_tag("§15.5 系统判断 + 人工说明")
st.title("🚨 异常费用预警清单")

if not require_filters():
    st.stop()

# 异常类型分布
df_dist = query_fact("""
    SELECT 异常类型, COUNT(*) AS 号码数, SUM(异常金额) AS 异常金额合计
    FROM fact_tem_monthly
    WHERE 客户ID = ? AND 项目ID = ? AND 账期 = ?
      AND 异常类型 IS NOT NULL AND 异常类型 <> ''
    GROUP BY 异常类型
    ORDER BY 号码数 DESC, 异常金额合计 DESC NULLS LAST
""")
st.subheader("异常类型分布（按组合标签）")
st.dataframe(df_dist, use_container_width=True)

st.divider()
st.subheader("异常清单明细")

# 类型筛选
options = ["全部", "超套", "零用量", "高流量", "高通话", "漫游",
           "增值业务", "离职后计费", "事件未闭环", "资产缺失", "人员缺失", "长期闲置"]
choice = st.selectbox("筛选异常类型", options)

if choice == "全部":
    df_list = query_fact("SELECT * FROM v_anomaly_list WHERE 客户ID = ? AND 项目ID = ? AND 账期 = ? ORDER BY 异常金额 DESC NULLS LAST")
else:
    df_list = query_fact(
        "SELECT * FROM v_anomaly_list WHERE 客户ID = ? AND 项目ID = ? AND 账期 = ? AND 异常类型 LIKE ? ORDER BY 异常金额 DESC NULLS LAST",
        extra_params=[f"%{choice}%"],
    )
st.dataframe(df_list, use_container_width=True)
