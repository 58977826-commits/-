"""EMOS 知识回流：知识卡片、AI 建议记录、组件版本。"""
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

_ROOT = Path(__file__).resolve().parents[2]
for _p in (_ROOT / "src", _ROOT / "app"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from _shared import init_page, section_tag  # noqa: E402
from tem.emos import (  # noqa: E402
    delete_knowledge_card,
    list_ai_suggestions,
    list_component_versions,
    list_knowledge_cards,
    record_component_version,
    save_ai_suggestion,
    save_knowledge_card,
)

init_page("EMOS 知识回流")
section_tag("经验回流")
st.title("📚 EMOS 知识回流")
st.caption("管理知识卡片、记录 AI 建议采纳情况、追踪组件版本更新")

tab1, tab2, tab3 = st.tabs(["知识卡片", "AI 建议记录", "组件版本"])

with tab1:
    st.subheader("知识卡片库")
    cards = list_knowledge_cards()
    if not cards.empty:
        st.dataframe(cards, use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("新增知识卡片")
    with st.form("new_kc"):
        主题 = st.text_input("主题")
        核心结论 = st.text_area("核心结论")
        适用场景 = st.text_input("适用场景")
        来源项目 = st.text_input("来源项目")
        关联组件 = st.text_input("关联组件", placeholder="SOP-002,RULE-001")
        AI使用方式 = st.text_input("AI 使用方式")
        if st.form_submit_button("保存知识卡片", type="primary"):
            if 主题 and 核心结论:
                kid = save_knowledge_card(主题, 核心结论, 适用场景, 来源项目, 关联组件, AI使用方式)
                st.success(f"已创建 {kid}")
                st.rerun()
            else:
                st.error("主题与核心结论不能为空")

    if not cards.empty:
        st.divider()
        with st.form("del_kc"):
            kid = st.selectbox("删除知识卡片", cards["知识卡片编号"].tolist())
            if st.form_submit_button("删除"):
                delete_knowledge_card(kid)
                st.success("已删除")
                st.rerun()

with tab2:
    st.subheader("AI 建议采纳记录")
    with st.form("ai_suggestion"):
        画像ID = st.text_input("关联画像ID（可选）")
        场景 = st.selectbox("场景", ["风险审查", "流程生成", "经验回流", "月报摘要", "其他"])
        AI输出 = st.text_area("AI 输出摘要")
        人工结论 = st.text_area("人工结论")
        是否采纳 = st.selectbox("是否采纳", ["待确认", "采纳", "部分采纳", "不采纳"])
        是否回流 = st.checkbox("写入知识回流")
        if st.form_submit_button("保存记录", type="primary"):
            rid = save_ai_suggestion(画像ID or None, 场景, AI输出, 人工结论, 是否采纳, 是否回流)
            st.success(f"已保存 {rid}")
            st.rerun()

    sug = list_ai_suggestions()
    if not sug.empty:
        st.dataframe(sug, use_container_width=True, hide_index=True)

with tab3:
    st.subheader("组件版本更新")
    with st.form("comp_ver"):
        组件编号 = st.text_input("组件编号", placeholder="SOP-002")
        原版本 = st.text_input("原版本", value="V1.0")
        新版本 = st.text_input("新版本", value="V1.1")
        更新原因 = st.text_area("更新原因")
        来源项目 = st.text_input("来源项目")
        if st.form_submit_button("记录版本更新", type="primary"):
            vid = record_component_version(组件编号, 原版本, 新版本, 更新原因, 来源项目)
            st.success(f"已记录 {vid}")
            st.rerun()

    vers = list_component_versions()
    if not vers.empty:
        st.dataframe(vers, use_container_width=True, hide_index=True)
