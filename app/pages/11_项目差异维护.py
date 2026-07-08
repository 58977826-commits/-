"""项目差异规则维护 - EMOS↔TEM 差异闭环（管理员）。"""
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
from tem.config import get_settings  # noqa: E402
from tem.meta.project_diff import (  # noqa: E402
    ProjectDiffError,
    delete_diff_rule,
    list_all_project_diffs,
    sync_project_diff_from_config,
    upsert_diff_rule,
)

init_page("项目差异维护", admin_only=True)
section_tag("EMOS ↔ TEM")
st.title("📋 项目差异维护")
st.caption(
    "维护「标准规则 vs 本项目规则」差异表。"
    "保存后写入 `config/project_diff.yaml`，同步至 DuckDB，供 **Import Gate** 与 **EMOS 落地包** 使用。"
)

if st.sidebar.button("立即同步到 DuckDB", use_container_width=True):
    n = sync_project_diff_from_config()
    st.sidebar.success(f"已同步 {n} 条")

settings = get_settings()
client_options = ["* (全局默认)"]
client_map: dict[str, str] = {"* (全局默认)": "*"}
for c in settings.clients:
    cid = c.get("客户ID", "")
    label = f"{cid} · {c.get('客户名称', cid)}"
    client_options.append(label)
    client_map[label] = cid

all_df = list_all_project_diffs()
st.subheader("当前差异规则")
if all_df.empty:
    st.info("暂无差异规则。可在下方新增，或运行 `tem sync-diff`。")
else:
    show_cols = ["客户ID", "项目ID", "规则ID", "规则类别", "标准规则", "本项目规则", "确认方", "是否可复用", "备注"]
    show_cols = [c for c in show_cols if c in all_df.columns]
    st.dataframe(all_df[show_cols], use_container_width=True, hide_index=True)

st.divider()
st.subheader("新增 / 更新差异规则")

with st.form("upsert_diff_form", clear_on_submit=False):
    scope = st.radio("作用范围", ["全局默认（所有项目继承）", "指定客户/项目"], horizontal=True)
    c1, c2 = st.columns(2)
    with c1:
        if scope.startswith("全局"):
            客户ID = "*"
            项目ID = "*"
            st.caption("全局默认规则：客户ID=*，项目ID=*")
        else:
            client_label = st.selectbox("客户", client_options[1:] or client_options)
            客户ID = client_map.get(client_label, client_label.split(" · ")[0])
            proj_list = []
            for c in settings.clients:
                if c.get("客户ID") == 客户ID:
                    proj_list = [p.get("项目ID", "") for p in c.get("projects", [])]
            项目ID = st.selectbox("项目", proj_list or ["work-phone"])
    with c2:
        规则ID = st.text_input("规则ID *", placeholder="如 DATA-004 / BILL-XXX-001")
        规则类别 = st.selectbox("规则类别", ["字段映射", "导入策略", "跨表匹配", "账单结构", "流程差异", "其他"])

    标准规则 = st.text_area("标准规则 *", placeholder="标准逻辑是什么")
    本项目规则 = st.text_area("本项目规则 *", placeholder="本项目实际如何处理")
    c3, c4, c5 = st.columns(3)
    with c3:
        确认方 = st.text_input("确认方", value="运营经理")
    with c4:
        是否可复用 = st.checkbox("是否可复用", value=True)
    with c5:
        生效账期 = st.text_input("生效账期（可选）", placeholder="YYYYMM 或留空")

    备注 = st.text_input("备注")
    save_submitted = st.form_submit_button("保存并同步", type="primary")

if save_submitted:
    if not (规则ID and 标准规则 and 本项目规则):
        st.error("规则ID、标准规则、本项目规则 不能为空")
    else:
        try:
            upsert_diff_rule(
                规则ID, 规则类别, 标准规则, 本项目规则, 确认方,
                客户ID=客户ID, 项目ID=项目ID,
                是否可复用=是否可复用, 备注=备注, 生效账期=生效账期 or None,
            )
            st.success(f"已保存规则 `{规则ID}` 并同步到 DuckDB")
            st.rerun()
        except ProjectDiffError as e:
            st.error(str(e))

st.divider()
st.subheader("删除差异规则")
if all_df.empty:
    st.caption("无可删除规则。")
else:
    with st.form("delete_diff_form"):
        pick = st.selectbox(
            "选择要删除的规则",
            [
                f"{r['规则ID']} @ {r['客户ID']}/{r['项目ID']}"
                for _, r in all_df.iterrows()
            ],
        )
        confirm_del = st.checkbox("确认删除（不可恢复，除非从 Git 还原 YAML）")
        if st.form_submit_button("删除并同步"):
            if not confirm_del:
                st.warning("请勾选确认")
            else:
                rid = pick.split(" @ ")[0]
                scope = pick.split(" @ ")[1]
                cid, pid = scope.split("/")
                try:
                    delete_diff_rule(rid, 客户ID=cid, 项目ID=pid)
                    st.success(f"已删除 {rid}")
                    st.rerun()
                except ProjectDiffError as e:
                    st.error(str(e))

st.caption(
    "提示：EMOS 生成落地包时会拉取本表写入「差异确认表」；"
    "TEM 导入时 Import Gate 也会引用相关规则。"
)
