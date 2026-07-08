"""EMOS 组件库浏览：56 个样板组件 + Markdown 摘要 + Prompt 模板。"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

_ROOT = Path(__file__).resolve().parents[2]
for _p in (_ROOT / "src", _ROOT / "app"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from _shared import init_page, section_tag  # noqa: E402
from tem.emos.load_data import load_ai_prompts, load_components, read_component_markdown  # noqa: E402

init_page("EMOS 组件库")
section_tag("知识资产")
st.title("🗂️ EMOS 组件库")
st.caption("56 个样板组件（GE / 强生 MT·Vision / 礼来 / 西安杨森）· 32 份 AI Markdown 摘要")

components = load_components()
if not components:
    st.warning("组件库为空。请运行 `python scripts/bootstrap_emos_assets.py` 后执行 `tem sync-emos`。")
    st.stop()

df = pd.DataFrame(components)
st.metric("组件总数", len(df))

c1, c2 = st.columns(2)
with c1:
    src_filter = st.multiselect("来源项目", sorted(df["来源项目"].dropna().unique()))
with c2:
    type_filter = st.multiselect("组件类型", sorted(df["组件类型"].dropna().unique()))

filtered = df.copy()
if src_filter:
    filtered = filtered[filtered["来源项目"].isin(src_filter)]
if type_filter:
    filtered = filtered[filtered["组件类型"].isin(type_filter)]

st.dataframe(
    filtered[["组件编号", "组件名称", "组件类型", "来源项目", "成熟度", "对应服务项"]],
    use_container_width=True,
    hide_index=True,
)

st.divider()
st.subheader("组件 AI 摘要")
cid = st.selectbox("选择组件", filtered["组件编号"].tolist(), format_func=lambda x: f"{x} · {df.set_index('组件编号').loc[x, '组件名称']}")
md = read_component_markdown(cid)
if md:
    st.markdown(md)
else:
    st.caption("该组件暂无 Markdown 摘要（仅前 32 个核心组件已生成摘要）。")

st.divider()
st.subheader("Prompt 模板库")
prompts = load_ai_prompts()
for p in prompts:
    with st.expander(f"{p['PromptID']} · {p['模板名称']}（{p['场景']}）"):
        st.code(p["模板正文"], language="markdown")
