"""§15.7 事件运营报表。"""
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

_APP = Path(__file__).resolve().parents[1]
_SRC = _APP.parent / "src"
for _p in (_APP, _SRC):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from _shared import apply_brand_theme, get_filters, require_filters, section_tag  # noqa: E402
from tem.db import connect  # noqa: E402


apply_brand_theme("事件运营", layout="wide")
section_tag("§15.7 按事件类型 / 动作 / 状态 统计")
st.title("📅 事件运营")

if not require_filters():
    st.stop()

客户ID, 项目ID, 账期 = get_filters()

with connect(read_only=True) as con:
    summary = con.execute("""
        SELECT 事件类型, 事件动作, 事件状态, COUNT(*) AS 事件数
        FROM raw_event
        WHERE 客户ID = ? AND 项目ID = ? AND (数据月份 = ? OR 事件月份 = ?)
        GROUP BY 事件类型, 事件动作, 事件状态
        ORDER BY 事件数 DESC
    """, [客户ID, 项目ID, 账期, 账期]).fetchdf()

st.subheader("当月事件汇总")
st.dataframe(summary, use_container_width=True)

# 各分类清单
tabs = st.tabs(["On-Boarding（待跟进）", "Completed（已闭环）", "Canceled（已取消）", "改号", "副卡申请", "离职归还", "维修 / 丢失"])

with connect(read_only=True) as con:
    def load(where_extra: str, params: list = None):
        sql = f"""
            SELECT 事件类型, 事件动作, 事件状态, 原始服务号码, 新服务号码, 副卡号码,
                   当前使用人, 员工ID, 部门, 系统流水号, 开始时间, 完成时间, 备注
            FROM raw_event
            WHERE 客户ID = ? AND 项目ID = ? AND (数据月份 = ? OR 事件月份 = ?)
              AND {where_extra}
            ORDER BY 开始时间 DESC NULLS LAST
        """
        return con.execute(sql, [客户ID, 项目ID, 账期, 账期] + (params or [])).fetchdf()

    with tabs[0]:
        st.dataframe(load("事件状态 IN ('On-Boarding', '处理中', '新建')"), use_container_width=True)
    with tabs[1]:
        st.dataframe(load("事件状态 IN ('Completed', '已完成')"), use_container_width=True)
    with tabs[2]:
        st.dataframe(load("事件状态 IN ('Canceled', '已取消')"), use_container_width=True)
    with tabs[3]:
        st.dataframe(load("事件动作 LIKE '%改号%'"), use_container_width=True)
    with tabs[4]:
        st.dataframe(load("事件动作 LIKE '%副卡%'"), use_container_width=True)
    with tabs[5]:
        st.dataframe(load("事件类型 = '离职归还'"), use_container_width=True)
    with tabs[6]:
        st.dataframe(load("事件类型 IN ('维修', '设备丢失')"), use_container_width=True)
