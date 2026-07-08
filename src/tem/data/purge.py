"""按客户/项目/账期删除已导入的 TEM 数据（及可选 raw 归档文件）。"""
from __future__ import annotations

import gc
import shutil
import time
from pathlib import Path
from typing import Any

import pandas as pd

from ..config import get_settings
from ..db import connect

# 带账期粒度的业务表
PERIOD_TABLES = (
    "raw_usage",
    "raw_billing_list",
    "raw_billing_detail",
    "fact_tem_monthly",
)

# 项目级全量表（通常不按单月覆盖）
PROJECT_TABLES = (
    "raw_asset",
    "raw_employee",
    "raw_event",
)

META_PERIOD_TABLE = "meta_import_report"
META_CLIENT_TABLES = ("meta_project_diff",)

ALL_DATA_TABLES = PERIOD_TABLES + PROJECT_TABLES + (META_PERIOD_TABLE,)


class PurgeError(ValueError):
    """删除范围无效或执行失败。"""


def _table_has_column(table: str, column: str) -> bool:
    with connect(read_only=True) as con:
        cols = [r[1] for r in con.execute(f"PRAGMA table_info('{table}')").fetchall()]
    return column in cols


def _delete_rows(table: str, *, 客户ID: str, 项目ID: str, 账期: str | None = None) -> int:
    where = ["客户ID = ?", "项目ID = ?"]
    params: list[Any] = [客户ID, 项目ID]

    if 账期:
        if _table_has_column(table, "账期"):
            where.append("账期 = ?")
            params.append(账期)
        elif table == "raw_event" and _table_has_column(table, "事件月份"):
            where.append("事件月份 = ?")
            params.append(账期)
        elif _table_has_column(table, "数据月份"):
            where.append("数据月份 = ?")
            params.append(账期)
        else:
            return 0

    where_sql = " AND ".join(where)
    with connect() as con:
        n = con.execute(
            f"SELECT COUNT(*) FROM {table} WHERE {where_sql}",
            params,
        ).fetchone()[0]
        con.execute(f"DELETE FROM {table} WHERE {where_sql}", params)
    return int(n)


def _delete_client_rows(table: str, 客户ID: str) -> int:
    if not _table_has_column(table, "客户ID"):
        return 0
    with connect() as con:
        n = con.execute(
            f"SELECT COUNT(*) FROM {table} WHERE 客户ID = ?",
            [客户ID],
        ).fetchone()[0]
        con.execute(f"DELETE FROM {table} WHERE 客户ID = ?", [客户ID])
    return int(n)


def _count_client_rows(table: str, 客户ID: str) -> int:
    if not _table_has_column(table, "客户ID"):
        return 0
    with connect(read_only=True) as con:
        try:
            return int(con.execute(
                f"SELECT COUNT(*) FROM {table} WHERE 客户ID = ?",
                [客户ID],
            ).fetchone()[0])
        except Exception:  # noqa: BLE001
            return 0


def list_clients_in_db() -> pd.DataFrame:
    """汇总库内各客户的数据量（跨项目）。"""
    with connect(read_only=True) as con:
        try:
            return con.execute(
                """
                SELECT 客户ID,
                       MAX(客户名称) AS 客户名称,
                       COUNT(DISTINCT 项目ID) AS 项目数,
                       COUNT(DISTINCT 账期) AS 账期数,
                       COUNT(*) AS 号码记录数,
                       SUM(实际应收) AS 实际应收合计
                FROM fact_tem_monthly
                GROUP BY 客户ID
                ORDER BY 客户ID
                """
            ).fetchdf()
        except Exception:  # noqa: BLE001
            return pd.DataFrame()


def list_import_scopes() -> pd.DataFrame:
    """列出库内已有导入范围（以 fact_tem_monthly 为主）。"""
    with connect(read_only=True) as con:
        try:
            return con.execute(
                """
                SELECT 客户ID, 客户名称, 项目ID, 项目名称, 账期,
                       COUNT(*) AS 号码数,
                       SUM(实际应收) AS 实际应收合计
                FROM fact_tem_monthly
                GROUP BY 客户ID, 客户名称, 项目ID, 项目名称, 账期
                ORDER BY 客户ID, 项目ID, 账期 DESC
                """
            ).fetchdf()
        except Exception:  # noqa: BLE001
            return pd.DataFrame()


def preview_purge_client(客户ID: str) -> dict[str, int]:
    """预览将删除的客户全量数据（含其下所有项目）。"""
    if not 客户ID:
        raise PurgeError("客户ID 不能为空")

    counts: dict[str, int] = {}
    for table in ALL_DATA_TABLES + META_CLIENT_TABLES:
        n = _count_client_rows(table, 客户ID)
        if n:
            counts[table] = n
    return counts


def preview_purge(
    客户ID: str,
    项目ID: str,
    账期: str | None = None,
    *,
    include_project_tables: bool = False,
) -> dict[str, int]:
    """预览将删除的行数（不执行删除）。"""
    if not 客户ID or not 项目ID:
        raise PurgeError("客户ID 与 项目ID 不能为空")

    counts: dict[str, int] = {}
    tables = list(PERIOD_TABLES)
    if include_project_tables or not 账期:
        tables.extend(PROJECT_TABLES)
    if _table_has_column(META_PERIOD_TABLE, "客户ID"):
        tables.append(META_PERIOD_TABLE)

    for table in tables:
        where = ["客户ID = ?", "项目ID = ?"]
        params: list[Any] = [客户ID, 项目ID]
        if 账期 and (table in PERIOD_TABLES or table == META_PERIOD_TABLE):
            if _table_has_column(table, "账期"):
                where.append("账期 = ?")
                params.append(账期)
        elif 账期 and table == "raw_event":
            where.append("事件月份 = ?")
            params.append(账期)
        elif 账期 and table in PROJECT_TABLES:
            continue
        elif 账期 and _table_has_column(table, "数据月份"):
            where.append("数据月份 = ?")
            params.append(账期)

        with connect(read_only=True) as con:
            try:
                n = con.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE {' AND '.join(where)}",
                    params,
                ).fetchone()[0]
            except Exception:  # noqa: BLE001
                n = 0
        if n:
            counts[table] = int(n)
    return counts


def _rmtree_safe(path: Path, retries: int = 5) -> None:
    """Windows 下 Excel 可能短暂占用文件，删除时重试。"""
    if not path.exists():
        return

    for attempt in range(retries):
        try:
            shutil.rmtree(path)
            return
        except PermissionError:
            if attempt >= retries - 1:
                raise
            time.sleep(0.3)
            gc.collect()


def _purge_raw_files(客户ID: str, 项目ID: str, 账期: str | None) -> list[str]:
    """删除 data/raw 下归档文件，返回删除的路径列表。"""
    settings = get_settings()
    removed: list[str] = []
    type_dirs = ["usage", "billing", "asset", "employee", "event"]

    for t in type_dirs:
        base = settings.raw_root / t / 客户ID / 项目ID
        if not base.exists():
            continue
        if 账期 and t in {"usage", "billing"}:
            target = base / 账期
            if target.exists():
                _rmtree_safe(target)
                removed.append(str(target))
        elif not 账期:
            _rmtree_safe(base)
            removed.append(str(base))
        elif t in {"asset", "employee", "event"} and not 账期:
            pass
    return removed


def _purge_raw_files_client(客户ID: str) -> list[str]:
    """删除 data/raw 下该客户全部归档。"""
    settings = get_settings()
    removed: list[str] = []
    for t in ("usage", "billing", "asset", "employee", "event"):
        base = settings.raw_root / t / 客户ID
        if base.exists():
            _rmtree_safe(base)
            removed.append(str(base))
    return removed


def _purge_output_files_client(客户ID: str) -> list[str]:
    settings = get_settings()
    removed: list[str] = []
    for p in settings.output_root.glob(f"{客户ID}_*.xlsx"):
        p.unlink(missing_ok=True)
        removed.append(str(p))
    return removed


def purge_client_data(
    客户ID: str,
    *,
    delete_raw_files: bool = False,
    delete_output_files: bool = False,
) -> dict[str, Any]:
    """删除指定客户下全部导入数据（所有项目、所有账期）。"""
    if not 客户ID:
        raise PurgeError("客户ID 不能为空")

    deleted: dict[str, int] = {}
    for table in ALL_DATA_TABLES + META_CLIENT_TABLES:
        n = _delete_client_rows(table, 客户ID)
        if n:
            deleted[table] = n

    removed_raw: list[str] = []
    if delete_raw_files:
        removed_raw = _purge_raw_files_client(客户ID)

    removed_output: list[str] = []
    if delete_output_files:
        removed_output = _purge_output_files_client(客户ID)

    return {
        "deleted_rows": deleted,
        "total_rows": sum(deleted.values()),
        "removed_raw_paths": removed_raw,
        "removed_output_paths": removed_output,
    }


def purge_import_data(
    客户ID: str,
    项目ID: str,
    账期: str | None = None,
    *,
    include_project_tables: bool = False,
    delete_raw_files: bool = False,
    delete_output_files: bool = False,
) -> dict[str, Any]:
    """删除指定范围的导入数据。

    - 仅传 账期：删除该账期的用量/账单/fact 及 Gate 报告；默认不动 asset/employee/event。
    - 不传 账期：删除该客户+项目下所有账期数据；若 include_project_tables=True 一并删三张项目表。
    """
    if not 客户ID or not 项目ID:
        raise PurgeError("客户ID 与 项目ID 不能为空")

    deleted: dict[str, int] = {}

    for table in PERIOD_TABLES:
        n = _delete_rows(table, 客户ID=客户ID, 项目ID=项目ID, 账期=账期)
        if n:
            deleted[table] = n

    if _table_has_column(META_PERIOD_TABLE, "客户ID"):
        n = _delete_rows(META_PERIOD_TABLE, 客户ID=客户ID, 项目ID=项目ID, 账期=账期)
        if n:
            deleted[META_PERIOD_TABLE] = n

    if include_project_tables or not 账期:
        for table in PROJECT_TABLES:
            if 账期 and table == "raw_event":
                n = _delete_rows(table, 客户ID=客户ID, 项目ID=项目ID, 账期=账期)
            elif 账期:
                continue
            else:
                n = _delete_rows(table, 客户ID=客户ID, 项目ID=项目ID, 账期=None)
            if n:
                deleted[table] = n

    removed_raw: list[str] = []
    if delete_raw_files:
        removed_raw = _purge_raw_files(客户ID, 项目ID, 账期)

    removed_output: list[str] = []
    if delete_output_files and 账期:
        settings = get_settings()
        pattern = f"{客户ID}_{项目ID}_{账期}_TEM月报_*.xlsx"
        for p in settings.output_root.glob(pattern):
            p.unlink(missing_ok=True)
            removed_output.append(str(p))

    return {
        "deleted_rows": deleted,
        "total_rows": sum(deleted.values()),
        "removed_raw_paths": removed_raw,
        "removed_output_paths": removed_output,
    }
