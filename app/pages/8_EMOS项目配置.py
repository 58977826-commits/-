"""EMOS 项目配置：画像 → 组件推荐 → 落地包导出。"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

_ROOT = Path(__file__).resolve().parents[2]
for _p in (_ROOT / "src", _ROOT / "app"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from _shared import get_current_user, init_page, section_tag  # noqa: E402
from tem.emos import (  # noqa: E402
    ProjectProfile,
    build_ai_brief,
    build_ai_review_report,
    generate_landing_pack,
    list_profiles,
    load_project_types,
    match_profile,
    match_result_from_dict,
    save_profile,
    save_recommendation,
    sync_emos_from_config,
)

init_page("EMOS 项目配置")
section_tag("MMS/EMOS")
st.title("🧭 EMOS 项目落地配置")
st.caption("填写项目画像 → 规则匹配推荐组件 → 生成落地包与 AI 审查报告")

if st.sidebar.button("同步 EMOS 知识库", help="从 config/emos/*.yaml 刷新组件与规则"):
    sync_emos_from_config()
    st.sidebar.success("已同步")

user = get_current_user()
created_by = user["username"] if user else None

project_types = load_project_types()
type_names = [p["项目类型名称"] for p in project_types]
type_ids = {p["项目类型名称"]: p["项目类型ID"] for p in project_types}

tab1, tab2, tab3, tab4 = st.tabs(["① 项目画像", "② 组件推荐", "③ 落地包导出", "④ 历史画像"])

with tab1:
    st.subheader("项目配置问卷")
    with st.form("emos_profile_form"):
        c1, c2 = st.columns(2)
        with c1:
            客户名称 = st.text_input("客户名称 *", placeholder="如：强生、礼来")
            行业 = st.text_input("行业", placeholder="如：医药、制造")
            用户规模 = st.selectbox("用户规模", ["<500", "500-2000", "2000-5000", ">5000", "未知"])
        with c2:
            selected_types = st.multiselect("项目类型 *", type_names, default=type_names[:1] if type_names else [])
            参考样板 = st.selectbox(
                "参考样板项目",
                ["", "GEHC", "强生MT", "强生Vision", "礼来", "西安杨森"],
                help="可选：优先推荐该样板项目的组件",
            )
            特殊说明 = st.text_area("特殊说明", placeholder="客户政策、运营商、SLA 等补充信息")

        st.markdown("**涉及模块（勾选）**")
        m1, m2, m3, m4 = st.columns(4)
        with m1:
            涉及终端 = st.checkbox("终端/资产")
            涉及号卡 = st.checkbox("号卡/SIM", value=True)
        with m2:
            涉及账务 = st.checkbox("账务/TEM", value=True)
            涉及库存 = st.checkbox("库存")
        with m3:
            涉及事件 = st.checkbox("事件运营", value=True)
            涉及服务台 = st.checkbox("服务台")
        with m4:
            涉及驻场 = st.checkbox("驻场")

        submitted = st.form_submit_button("生成推荐", type="primary")

    if submitted:
        if not 客户名称 or not selected_types:
            st.error("请填写客户名称并选择至少一个项目类型")
        else:
            profile = ProjectProfile(
                客户名称=客户名称.strip(),
                行业=行业.strip(),
                项目类型=selected_types,
                用户规模=用户规模,
                参考样板项目=参考样板,
                涉及终端=涉及终端,
                涉及号卡=涉及号卡,
                涉及账务=涉及账务,
                涉及库存=涉及库存,
                涉及事件=涉及事件,
                涉及服务台=涉及服务台,
                涉及驻场=涉及驻场,
                特殊说明=特殊说明.strip(),
            )
            result = match_profile(profile)
            save_profile(profile, created_by=created_by)
            rec_id = save_recommendation(profile.画像ID, result)
            st.session_state["emos_profile"] = profile.to_dict()
            st.session_state["emos_result"] = result.to_dict()
            st.session_state["emos_rec_id"] = rec_id
            st.success(f"已生成推荐 · 画像ID `{profile.画像ID}` · 推荐ID `{rec_id}`")

with tab2:
    st.subheader("组件推荐结果")
    result_dict = st.session_state.get("emos_result")
    if not result_dict:
        st.info("请先在「项目画像」页填写问卷并生成推荐。")
    else:
        profile_dict = st.session_state.get("emos_profile", {})
        st.caption(f"客户：{profile_dict.get('客户名称')} · 画像ID：{profile_dict.get('画像ID')}")

        c1, c2, c3 = st.columns(3)
        c1.metric("推荐服务项", len(result_dict.get("service_items", [])))
        c2.metric("推荐组件", len(result_dict.get("components", [])))
        c3.metric("识别风险", len(result_dict.get("risks", [])))

        st.markdown("##### 推荐服务项")
        si_rows = result_dict.get("service_items", [])
        if si_rows:
            st.dataframe(pd.DataFrame(si_rows)[["item_id", "name", "reason"]], use_container_width=True, hide_index=True)

        st.markdown("##### 推荐组件（含推荐理由）")
        comp_rows = result_dict.get("components", [])
        if comp_rows:
            st.dataframe(
                pd.DataFrame(comp_rows)[["item_id", "name", "source_project", "reason"]],
                use_container_width=True,
                hide_index=True,
            )

        st.markdown("##### 关联风险")
        for r in result_dict.get("risks", []):
            st.markdown(f"- **{r.get('name')}** — {r.get('reason')}")

        st.markdown("##### 待确认差异（来自 TEM 差异表）")
        diffs = result_dict.get("pending_diffs", [])
        if diffs:
            st.dataframe(pd.DataFrame(diffs)[["规则ID", "标准规则", "本项目规则", "确认方"]], use_container_width=True, hide_index=True)
        else:
            st.caption("暂无差异规则。")

with tab3:
    st.subheader("落地包与 AI 审查")
    if not st.session_state.get("emos_result"):
        st.info("请先生成组件推荐。")
    else:
        profile_dict = st.session_state["emos_profile"]
        result = match_result_from_dict(profile_dict, st.session_state["emos_result"])
        profile = result.profile

        if st.button("📦 生成项目落地包", type="primary"):
            with st.spinner("生成 Markdown + Excel + Word 落地包..."):
                pack = generate_landing_pack(profile, result)
            st.session_state["emos_pack_dir"] = pack["pack_dir"]
            st.session_state["emos_pack_info"] = pack
            st.success(f"已生成：{pack['pack_dir']}")
            st.json(pack)

        pack_dir = st.session_state.get("emos_pack_dir")
        pack_info = st.session_state.get("emos_pack_info") or {}
        if pack_dir:
            st.markdown(f"**输出目录：** `{pack_dir}`")
            office = pack_info.get("office") or {}
            dl1, dl2 = st.columns(2)
            if office.get("xlsx") and Path(office["xlsx"]).exists():
                with dl1:
                    st.download_button(
                        "⬇️ 下载 Excel 落地包",
                        Path(office["xlsx"]).read_bytes(),
                        file_name=Path(office["xlsx"]).name,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True,
                    )
            if office.get("docx") and Path(office["docx"]).exists():
                with dl2:
                    st.download_button(
                        "⬇️ 下载 Word 落地包",
                        Path(office["docx"]).read_bytes(),
                        file_name=Path(office["docx"]).name,
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        use_container_width=True,
                    )

        st.markdown("##### AI Brief 预览")
        brief = build_ai_brief(profile, result)
        st.download_button("下载 AI_Brief.md", brief, file_name="AI_Brief.md", mime="text/markdown")
        with st.expander("查看 AI Brief", expanded=False):
            st.markdown(brief)

        st.markdown("##### AI 审查报告预览")
        review = build_ai_review_report(profile, result)
        st.download_button("下载 AI_审查报告.md", review, file_name="AI_审查报告.md", mime="text/markdown")
        with st.expander("查看 AI 审查报告", expanded=False):
            st.markdown(review)

with tab4:
    st.subheader("历史项目画像")
    df = list_profiles()
    if df.empty:
        st.caption("暂无历史记录。")
    else:
        st.dataframe(df, use_container_width=True, hide_index=True)
