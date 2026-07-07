"""DuckDB 账号存储与校验。"""
from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from ..db import connect

DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "admin"
_PBKDF2_ITERATIONS = 100_000


class AuthError(ValueError):
    """账号操作失败。"""


@dataclass(frozen=True)
class AppUser:
    username: str
    is_admin: bool
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def to_session_dict(self) -> dict[str, Any]:
        return {
            "username": self.username,
            "is_admin": self.is_admin,
            "is_active": self.is_active,
        }


def _now() -> datetime:
    return datetime.now()


def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    if salt is None:
        salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        _PBKDF2_ITERATIONS,
    ).hex()
    return salt, digest


def verify_password(password: str, salt: str, password_hash: str) -> bool:
    _, digest = hash_password(password, salt)
    return secrets.compare_digest(digest, password_hash)


def _row_to_user(row: tuple) -> AppUser:
    return AppUser(
        username=row[0],
        is_admin=bool(row[1]),
        is_active=bool(row[2]),
        created_at=row[3],
        updated_at=row[4],
    )


def user_exists(username: str) -> bool:
    with connect(read_only=True) as con:
        row = con.execute(
            "SELECT 1 FROM meta_app_user WHERE username = ?",
            [username],
        ).fetchone()
    return row is not None


def count_admins() -> int:
    with connect(read_only=True) as con:
        row = con.execute(
            "SELECT COUNT(*) FROM meta_app_user WHERE is_admin = TRUE AND is_active = TRUE",
        ).fetchone()
    return int(row[0] if row else 0)


def list_users() -> list[AppUser]:
    with connect(read_only=True) as con:
        rows = con.execute(
            """
            SELECT username, is_admin, is_active, created_at, updated_at
            FROM meta_app_user
            ORDER BY is_admin DESC, username
            """
        ).fetchall()
    return [_row_to_user(r) for r in rows]


def authenticate(username: str, password: str) -> AppUser | None:
    username = username.strip()
    if not username or not password:
        return None
    with connect(read_only=True) as con:
        row = con.execute(
            """
            SELECT username, password_hash, password_salt, is_admin, is_active
            FROM meta_app_user
            WHERE username = ?
            """,
            [username],
        ).fetchone()
    if not row:
        return None
    if not bool(row[4]):
        return None
    if not verify_password(password, row[2], row[1]):
        return None
    return AppUser(username=row[0], is_admin=bool(row[3]), is_active=True)


def create_user(
    username: str,
    password: str,
    *,
    is_admin: bool = False,
) -> AppUser:
    username = username.strip()
    if not username:
        raise AuthError("用户名不能为空")
    if len(username) > 64:
        raise AuthError("用户名过长")
    if not password:
        raise AuthError("密码不能为空")
    if len(password) < 4:
        raise AuthError("密码至少 4 位")
    if user_exists(username):
        raise AuthError(f"用户名已存在：{username}")

    salt, password_hash = hash_password(password)
    ts = _now()
    with connect() as con:
        con.execute(
            """
            INSERT INTO meta_app_user (
                username, password_hash, password_salt, is_admin, is_active, created_at, updated_at
            ) VALUES (?, ?, ?, ?, TRUE, ?, ?)
            """,
            [username, password_hash, salt, is_admin, ts, ts],
        )
    return AppUser(username=username, is_admin=is_admin, is_active=True, created_at=ts, updated_at=ts)


def delete_user(username: str, *, current_username: str | None = None) -> None:
    username = username.strip()
    if not username:
        raise AuthError("用户名不能为空")
    if not user_exists(username):
        raise AuthError(f"用户不存在：{username}")
    if current_username and username == current_username:
        raise AuthError("不能删除当前登录账号")

    with connect(read_only=True) as con:
        row = con.execute(
            "SELECT is_admin FROM meta_app_user WHERE username = ?",
            [username],
        ).fetchone()
    if row and bool(row[0]) and count_admins() <= 1:
        raise AuthError("不能删除唯一的管理员账号")

    with connect() as con:
        con.execute("DELETE FROM meta_app_user WHERE username = ?", [username])


def ensure_default_admin() -> bool:
    """若库中无任何账号，创建默认 admin/admin。返回是否新建。"""
    try:
        with connect(read_only=True) as con:
            row = con.execute("SELECT COUNT(*) FROM meta_app_user").fetchone()
    except Exception:  # noqa: BLE001 — 表尚未创建
        return False
    if row and int(row[0]) > 0:
        return False
    create_user(DEFAULT_ADMIN_USERNAME, DEFAULT_ADMIN_PASSWORD, is_admin=True)
    return True
