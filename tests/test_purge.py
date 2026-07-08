"""导入数据删除测试。"""
from __future__ import annotations

import pandas as pd

from tem.build import build_fact_tem_monthly
from tem.data.purge import (
    list_import_scopes,
    preview_purge,
    preview_purge_client,
    purge_client_data,
    purge_import_data,
)
from tem.db import connect
from tem.ingest import IngestContext, ingest_billing, ingest_usage


def _ctx(账期: str = "202604") -> IngestContext:
    return IngestContext(
        客户ID="johnson",
        项目ID="work-phone",
        账期=账期,
        客户名称="强生",
        项目名称="工作手机项目",
    )


def _seed_period(settings, 账期: str = "202604") -> None:
    usage_path = settings.raw_root / "usage" / "johnson" / "work-phone" / 账期 / "usage.xlsx"
    usage_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({
        "服务号码": ["13800000001"],
        "账期": [账期],
        "总短信条数": [10],
        "总通话时长_秒": [1200],
        "总流量_M": [2048],
    }).to_excel(usage_path, index=False)

    billing_path = settings.raw_root / "billing" / "johnson" / "work-phone" / 账期 / "billing_list.xlsx"
    billing_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({
        "服务号码": ["13800000001"],
        "账期": [账期],
        "用户状态": ["在网"],
        "计费应收": [187],
        "账务优惠": [0],
        "实际应收": [187],
    }).to_excel(billing_path, index=False)

    ctx = _ctx(账期)
    ingest_usage(ctx)
    ingest_billing(ctx)
    build_fact_tem_monthly("johnson", "work-phone", 账期)


def test_purge_single_period(tmp_db):
    from tem import config as cfg_module

    settings = cfg_module.get_settings()
    _seed_period(settings, 账期="202604")

    preview = preview_purge("johnson", "work-phone", "202604")
    assert preview.get("fact_tem_monthly", 0) >= 1

    result = purge_import_data("johnson", "work-phone", "202604")
    assert result["total_rows"] >= 1

    with connect(read_only=True) as con:
        n = con.execute(
            "SELECT COUNT(*) FROM fact_tem_monthly "
            "WHERE 客户ID='johnson' AND 项目ID='work-phone' AND 账期='202604'"
        ).fetchone()[0]
    assert n == 0

    scopes = list_import_scopes()
    assert scopes.empty or "202604" not in scopes["账期"].astype(str).tolist()


def test_purge_with_raw_files(tmp_db):
    from tem import config as cfg_module

    settings = cfg_module.get_settings()
    _seed_period(settings, 账期="202605")
    raw_dir = settings.raw_root / "usage" / "johnson" / "work-phone" / "202605"
    assert raw_dir.exists()

    result = purge_import_data(
        "johnson", "work-phone", "202605",
        delete_raw_files=True,
    )
    assert result["total_rows"] >= 1
    assert any("202605" in p for p in result["removed_raw_paths"])
    assert not raw_dir.exists()


def test_purge_client_all_projects(tmp_db):
    from tem import config as cfg_module

    settings = cfg_module.get_settings()
    _seed_period(settings, 账期="202606")

    preview = preview_purge_client("johnson")
    assert preview.get("fact_tem_monthly", 0) >= 1

    result = purge_client_data("johnson", delete_raw_files=True)
    assert result["total_rows"] >= 1

    with connect(read_only=True) as con:
        n = con.execute(
            "SELECT COUNT(*) FROM fact_tem_monthly WHERE 客户ID='johnson'"
        ).fetchone()[0]
    assert n == 0

    raw_client = settings.raw_root / "usage" / "johnson"
    assert not raw_client.exists()
