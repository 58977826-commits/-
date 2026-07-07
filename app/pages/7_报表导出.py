"""数据导出 - 一键生成月度 Excel 报表（§15 报表打包）。"""
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

_APP = Path(__file__).resolve().parents[1]
_SRC = _APP.parent / "src"
for _p in (_APP, _SRC):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from _shared import init_page, get_filters, require_filters, section_tag  # noqa: E402
from tem.reports import export_monthly_reports  # noqa: E402


init_page("报表导出", layout="wide")
section_tag("§15 月度报表打包")
st.title("⬇️ 月度报表导出")
st.caption("一键生成包含七张管理报表的 Excel 文件，落到 data/output/ 目录")

if not require_filters():
    st.stop()

客户ID, 项目ID, 账期 = get_filters()

if st.button("生成月度 Excel 报表", type="primary"):
    with st.spinner("生成中..."):
        out_path = export_monthly_reports(客户ID, 项目ID, 账期)
    st.success(f"已生成：{out_path}")
    with open(out_path, "rb") as f:
        st.download_button(
            label="下载报表",
            data=f.read(),
            file_name=out_path.name,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
