"""账号管理 - 仅管理员可见。"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

_APP = Path(__file__).resolve().parents[1]
if str(_APP) not in sys.path:
    sys.path.insert(0, str(_APP))

from _shared import get_current_user, init_page, section_tag  # noqa: E402
from tem.auth import AuthError, create_user, delete_user, list_users  # noqa: E402


init_page("账号管理", admin_only=True)
section_tag("系统管理")
st.title("👥 账号管理")
st.caption("管理员可新增、删除应用登录账号，并指定是否具有管理员权限。")

current = get_current_user()
current_username = current["username"] if current else None

users = list_users()
st.subheader("现有账号")
if users:
    df = pd.DataFrame([
        {
            "用户名": u.username,
            "管理员": "是" if u.is_admin else "否",
            "状态": "启用" if u.is_active else "停用",
            "创建时间": u.created_at.strftime("%Y-%m-%d %H:%M") if u.created_at else "—",
        }
        for u in users
    ])
    st.dataframe(df, use_container_width=True, hide_index=True)
else:
    st.info("暂无账号。请运行 `tem init-db` 初始化默认管理员。")

st.divider()
st.subheader("新增账号")
with st.form("create_user_form", clear_on_submit=True):
    new_username = st.text_input("用户名", placeholder="登录用户名")
    new_password = st.text_input("密码", type="password", placeholder="至少 4 位")
    new_password2 = st.text_input("确认密码", type="password")
    new_is_admin = st.checkbox("管理员权限", help="勾选后可访问本页并管理其他账号")
    create_submitted = st.form_submit_button("创建账号", type="primary")

if create_submitted:
    if new_password != new_password2:
        st.error("两次输入的密码不一致")
    else:
        try:
            user = create_user(new_username, new_password, is_admin=new_is_admin)
            st.success(f"已创建账号：{user.username}" + ("（管理员）" if user.is_admin else ""))
            st.rerun()
        except AuthError as e:
            st.error(str(e))

st.divider()
st.subheader("删除账号")
deletable = [u.username for u in users if u.username != current_username]
if not deletable:
    st.caption("没有可删除的其他账号。")
else:
    with st.form("delete_user_form"):
        del_username = st.selectbox("选择要删除的账号", deletable)
        confirm = st.checkbox(f"确认删除账号「{del_username}」")
        delete_submitted = st.form_submit_button("删除账号")
    if delete_submitted:
        if not confirm:
            st.warning("请勾选确认后再删除")
        else:
            try:
                delete_user(del_username, current_username=current_username)
                st.success(f"已删除账号：{del_username}")
                st.rerun()
            except AuthError as e:
                st.error(str(e))

st.caption("默认管理员账号为 admin / admin，首次 `tem init-db` 时自动创建（仅当库中无任何账号时）。")
