"""DuckDB 连接与初始化。"""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

import duckdb

from .config import REPO_ROOT, get_settings


SQL_DIR = REPO_ROOT / "sql"
DDL_FILES = ["001_raw_tables.sql", "002_fact_tem_monthly.sql", "003_views.sql", "004_meta_tables.sql", "005_app_users.sql"]


def get_connection(read_only: bool = False) -> duckdb.DuckDBPyConnection:
    settings = get_settings()
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(settings.db_path), read_only=read_only)


@contextmanager
def connect(read_only: bool = False):
    con = get_connection(read_only=read_only)
    try:
        yield con
    finally:
        con.close()


def init_db(verbose: bool = True) -> None:
    """跑完所有 DDL 脚本，建表 + 视图（幂等）。"""
    with connect() as con:
        for fname in DDL_FILES:
            path = SQL_DIR / fname
            if not path.exists():
                raise FileNotFoundError(f"DDL 脚本缺失: {path}")
            sql = path.read_text(encoding="utf-8")
            con.execute(sql)
            if verbose:
                print(f"[init_db] executed {fname}")
    from .meta.project_diff import sync_project_diff_from_config
    sync_project_diff_from_config(verbose=verbose)
    from .auth.users import ensure_default_admin
    if ensure_default_admin() and verbose:
        print("[init_db] created default admin account (admin / admin)")


def list_tables() -> list[str]:
    with connect(read_only=True) as con:
        rows = con.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'main' ORDER BY table_name"
        ).fetchall()
    return [r[0] for r in rows]


def truncate(table: str, 客户ID: str | None = None, 项目ID: str | None = None,
             账期: str | None = None) -> int:
    """按客户/项目/账期清空指定表，便于重导。返回删除行数。"""
    where = []
    params: list = []
    if 客户ID:
        where.append("客户ID = ?")
        params.append(客户ID)
    if 项目ID:
        where.append("项目ID = ?")
        params.append(项目ID)
    if 账期:
        where.append("账期 = ?")
        params.append(账期)
    sql = f"DELETE FROM {table}"
    if where:
        sql += " WHERE " + " AND ".join(where)
    with connect() as con:
        before = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        con.execute(sql, params)
        after = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    return before - after
