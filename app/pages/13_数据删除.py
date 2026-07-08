"""导入数据删除 - 仅管理员（调试用/重导前清理）。"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

_APP = Path(__file__).resolve().parents[1]
if str(_APP) not in sys.path:
    sys.path.insert(0, str(_APP))

from _shared import init_page, section_tag  # noqa: E402
from tem.config import get_settings  # noqa: E402
from tem.data import (  # noqa: E402
    PurgeError,
    list_clients_in_db,
    list_import_scopes,
    preview_purge,
    preview_purge_client,
    purge_client_data,
    purge_import_data,
)

init_page("数据删除", admin_only=True)
section_tag("系统管理")
st.title("🗑️ 导入数据删除")
st.caption(
    "按 **客户 / 项目 / 账期** 删除 DuckDB 中已导入的测试或正式数据，便于重新导入。"
    "此操作不可撤销（除非有 raw 备份）。"
)

client_summary = list_clients_in_db()
scopes = list_import_scopes()

st.subheader("库内客户概览")
if client_summary.empty:
    st.info("fact_tem_monthly 中暂无客户数据。仍可在下方手动指定范围删除 raw 表残留。")
else:
    st.dataframe(client_summary, use_container_width=True, hide_index=True)

with st.expander("各客户 / 项目 / 账期明细", expanded=False):
    if scopes.empty:
        st.caption("暂无明细。")
    else:
        st.dataframe(scopes, use_container_width=True, hide_index=True)

st.divider()

settings = get_settings()
client_options: list[tuple[str, str]] = []
for c in settings.clients:
    cid = c.get("客户ID", "")
    cname = c.get("客户名称", cid)
    client_options.append((cid, f"{cid} · {cname}"))
if not client_options:
    client_options = [(settings.default_客户ID, settings.default_客户名称)]

labels = [x[1] for x in client_options]
values = [x[0] for x in client_options]

tab_project, tab_client = st.tabs(["按项目 / 账期删除", "按客户删除（全部项目）"])

with tab_project:
    st.subheader("删除配置")
    c1, c2, c3 = st.columns(3)
    with c1:
        客户ID = values[labels.index(st.selectbox("客户", labels, key="purge_client"))]
    with c2:
        projects: list[str] = []
        for c in settings.clients:
            if c.get("客户ID") == 客户ID:
                projects = [p.get("项目ID", "") for p in c.get("projects", [])]
        项目ID = st.selectbox("项目", projects or [settings.default_项目ID], key="purge_project")
    with c3:
        period_choices = ["（删除该项目全部账期）"]
        if not scopes.empty:
            sub = scopes[(scopes["客户ID"] == 客户ID) & (scopes["项目ID"] == 项目ID)]
            period_choices += [str(p) for p in sub["账期"].dropna().unique()]
        period_sel = st.selectbox("账期", period_choices, key="purge_period")
        账期 = None if period_sel.startswith("（") else period_sel

    scope_label = f"{客户ID} / {项目ID}" + (f" / {账期}" if 账期 else " / 全部账期")

    try:
        live_preview = preview_purge(
            客户ID, 项目ID, 账期,
            include_project_tables=账期 is None,
        )
        if live_preview:
            st.markdown(f"**当前范围 `{scope_label}` 匹配行数：** {sum(live_preview.values())}")
    except PurgeError:
        pass

    with st.form("purge_form"):
        st.markdown("**删除选项**")
        include_proj = st.checkbox(
            "同时删除资产 / 人员 / 事件表（raw_asset、raw_employee、raw_event）",
            value=账期 is None,
            help="删单账期时默认不动三张项目表；删整个项目时建议勾选",
        )
        delete_raw = st.checkbox(
            "同时删除 data/raw/ 下归档 Excel",
            value=False,
        )
        delete_output = st.checkbox(
            "同时删除 data/output/ 下该账期 TEM 月报 Excel",
            value=False,
            disabled=账期 is None,
        )
        confirm_text = st.text_input("输入 DELETE 确认执行", placeholder="必须输入大写 DELETE")
        preview_btn = st.form_submit_button("预览将删除的行数")
        purge_btn = st.form_submit_button("执行删除", type="primary")

    if preview_btn:
        try:
            preview = preview_purge(
                客户ID, 项目ID, 账期,
                include_project_tables=include_proj,
            )
            if preview:
                st.warning(f"预览 · {scope_label}")
                st.dataframe(
                    pd.DataFrame([{"表名": k, "将删除行数": v} for k, v in preview.items()]),
                    use_container_width=True,
                    hide_index=True,
                )
                st.caption(f"合计 {sum(preview.values())} 行")
            else:
                st.info("该范围内没有匹配数据。")
        except PurgeError as e:
            st.error(str(e))

    if purge_btn:
        if confirm_text.strip() != "DELETE":
            st.error("请在确认框输入大写 DELETE 后再执行")
        else:
            try:
                result = purge_import_data(
                    客户ID, 项目ID, 账期,
                    include_project_tables=include_proj,
                    delete_raw_files=delete_raw,
                    delete_output_files=delete_output,
                )
                st.cache_data.clear()
                st.success(f"已删除 {scope_label} 共 {result['total_rows']} 行")
                if result["deleted_rows"]:
                    st.dataframe(
                        pd.DataFrame([
                            {"表名": k, "已删除行数": v}
                            for k, v in result["deleted_rows"].items()
                        ]),
                        use_container_width=True,
                        hide_index=True,
                    )
                if result.get("removed_raw_paths"):
                    st.markdown("**已删除 raw 目录：**")
                    for p in result["removed_raw_paths"]:
                        st.code(p)
                if result.get("removed_output_paths"):
                    st.markdown("**已删除 output 文件：**")
                    for p in result["removed_output_paths"]:
                        st.code(p)
                st.info("可回到 **数据导入** 页重新上传并导入。")
                st.rerun()
            except PurgeError as e:
                st.error(str(e))

with tab_client:
    st.subheader("删除整个客户")
    st.warning(
        f"将删除所选客户下 **所有项目、所有账期** 的导入数据，"
        f"包括 raw_*、fact_tem_monthly、meta_import_report、meta_project_diff。"
    )

    db_clients = sorted(client_summary["客户ID"].astype(str).tolist()) if not client_summary.empty else []
    client_tab_labels = labels[:]
    client_tab_values = values[:]
    for cid in db_clients:
        if cid not in client_tab_values:
            client_tab_labels.append(cid)
            client_tab_values.append(cid)

    purge_client_id = client_tab_values[
        client_tab_labels.index(st.selectbox("客户", client_tab_labels, key="purge_client_all"))
    ]

    if not client_summary.empty:
        row = client_summary[client_summary["客户ID"] == purge_client_id]
        if not row.empty:
            r = row.iloc[0]
            st.markdown(
                f"**{purge_client_id}** · {r.get('客户名称', '')} — "
                f"{int(r['项目数'])} 个项目，{int(r['账期数'])} 个账期，"
                f"{int(r['号码记录数'])} 条 fact 记录"
            )

    try:
        client_preview = preview_purge_client(purge_client_id)
        if client_preview:
            st.markdown(f"**将删除 `{purge_client_id}` 共 {sum(client_preview.values())} 行**")
    except PurgeError:
        client_preview = {}

    with st.form("purge_client_form"):
        delete_raw_client = st.checkbox(
            "同时删除 data/raw/ 下该客户全部归档",
            value=False,
        )
        delete_output_client = st.checkbox(
            "同时删除 data/output/ 下该客户全部 TEM 月报 Excel",
            value=False,
        )
        confirm_client = st.text_input(
            f"输入客户 ID `{purge_client_id}` 确认执行",
            placeholder=f"请输入 {purge_client_id}",
        )
        preview_client_btn = st.form_submit_button("预览将删除的行数")
        purge_client_btn = st.form_submit_button("执行客户删除", type="primary")

    if preview_client_btn:
        try:
            preview = preview_purge_client(purge_client_id)
            if preview:
                st.warning(f"预览 · 客户 {purge_client_id}（全部项目）")
                st.dataframe(
                    pd.DataFrame([{"表名": k, "将删除行数": v} for k, v in preview.items()]),
                    use_container_width=True,
                    hide_index=True,
                )
                st.caption(f"合计 {sum(preview.values())} 行")
            else:
                st.info("该客户没有匹配数据。")
        except PurgeError as e:
            st.error(str(e))

    if purge_client_btn:
        if confirm_client.strip() != purge_client_id:
            st.error(f"请在确认框输入客户 ID `{purge_client_id}` 后再执行")
        else:
            try:
                result = purge_client_data(
                    purge_client_id,
                    delete_raw_files=delete_raw_client,
                    delete_output_files=delete_output_client,
                )
                st.cache_data.clear()
                st.success(f"已删除客户 {purge_client_id} 共 {result['total_rows']} 行")
                if result["deleted_rows"]:
                    st.dataframe(
                        pd.DataFrame([
                            {"表名": k, "已删除行数": v}
                            for k, v in result["deleted_rows"].items()
                        ]),
                        use_container_width=True,
                        hide_index=True,
                    )
                if result.get("removed_raw_paths"):
                    st.markdown("**已删除 raw 目录：**")
                    for p in result["removed_raw_paths"]:
                        st.code(p)
                if result.get("removed_output_paths"):
                    st.markdown("**已删除 output 文件：**")
                    for p in result["removed_output_paths"]:
                        st.code(p)
                st.rerun()
            except PurgeError as e:
                st.error(str(e))

st.divider()
st.caption(
    "说明：删除仅影响 DuckDB 业务表与可选 raw/output 文件；"
    "按客户删除时会一并清除 meta_project_diff 中该客户的规则记录。"
    "不会删除 EMOS 知识库、账号、config/project_diff.yaml 源文件。"
)
