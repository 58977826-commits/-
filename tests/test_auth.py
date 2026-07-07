"""应用登录与账号管理单元测试。"""
from __future__ import annotations

import pytest

from tem.auth import (
    AuthError,
    authenticate,
    count_admins,
    create_user,
    delete_user,
    ensure_default_admin,
    list_users,
    user_exists,
)
from tem.auth.users import verify_password, hash_password


def test_hash_and_verify_password():
    salt, digest = hash_password("secret")
    assert verify_password("secret", salt, digest)
    assert not verify_password("wrong", salt, digest)


def test_ensure_default_admin(tmp_db):
    # init_db fixture 已执行 ensure_default_admin，再次调用应为幂等
    assert ensure_default_admin() is False
    assert user_exists("admin")
    assert authenticate("admin", "admin") is not None
    assert authenticate("admin", "wrong") is None


def test_create_and_delete_user(tmp_db):
    ensure_default_admin()
    user = create_user("viewer", "pass1234", is_admin=False)
    assert user.username == "viewer"
    assert not user.is_admin
    assert authenticate("viewer", "pass1234") is not None

    delete_user("viewer", current_username="admin")
    assert not user_exists("viewer")


def test_cannot_delete_only_admin(tmp_db):
    ensure_default_admin()
    with pytest.raises(AuthError, match="唯一的管理员"):
        delete_user("admin", current_username="other")


def test_cannot_delete_self(tmp_db):
    ensure_default_admin()
    with pytest.raises(AuthError, match="当前登录"):
        delete_user("admin", current_username="admin")


def test_create_admin_user(tmp_db):
    ensure_default_admin()
    create_user("ops", "ops1234", is_admin=True)
    assert count_admins() == 2
    users = list_users()
    assert {u.username for u in users} == {"admin", "ops"}
