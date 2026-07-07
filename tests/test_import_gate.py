"""Import Gate 单元测试。"""
from __future__ import annotations

import pandas as pd
import pytest

from tem.config import get_settings, reset_field_maps_cache
from tem.db import connect
from tem.ingest.common import IngestContext, write_dataframe
from tem.ingest.gate import IngestGateError, validate_before_write
from tem.ingest.preview import prevalidate_files
from tem.normalize import apply_aliases_with_report


@pytest.fixture
def ctx() -> IngestContext:
    return IngestContext(客户ID="johnson", 项目ID="work-phone", 账期="202604").resolve_meta()


def test_yaml_alias_月费应收(tmp_db, ctx):
    reset_field_maps_cache()
    df = pd.DataFrame({
        "号码": ["13800001234"],
        "月费应收": [100.0],
        "实际应收": [90.0],
        "账期": ["202604"],
    })
    out, rename = apply_aliases_with_report(df, "billing_list")
    assert "服务号码" in out.columns
    assert "计费应收" in out.columns
    assert rename.get("月费应收") == "计费应收"


def test_gate_blocks_period_mismatch(tmp_db, ctx):
    df = pd.DataFrame({
        "服务号码": ["13800001234"],
        "账期": ["202603"],
        "实际应收": [100.0],
        "客户ID": [ctx.客户ID],
        "项目ID": [ctx.项目ID],
    })
    report = validate_before_write(df, "raw_billing_list", ctx)
    assert report.period_mismatch is True
    assert not report.passed


def test_gate_blocks_missing_service_number(tmp_db, ctx):
    df = pd.DataFrame({
        "账期": ["202604"],
        "实际应收": [100.0],
        "客户ID": [ctx.客户ID],
        "项目ID": [ctx.项目ID],
    })
    report = validate_before_write(df, "raw_billing_list", ctx)
    assert not report.passed
    assert "服务号码" in report.missing_required


def test_write_dataframe_raises_on_strict_gate(tmp_db, ctx):
    df = pd.DataFrame({
        "服务号码": ["13800001234"],
        "账期": ["202603"],
        "实际应收": [100.0],
    })
    df["客户ID"] = ctx.客户ID
    df["客户名称"] = ctx.客户名称
    df["项目ID"] = ctx.项目ID
    df["项目名称"] = ctx.项目名称
    df["数据月份"] = ctx.账期
    df["数据来源"] = ctx.数据来源
    df["导入批次号"] = ctx.导入批次号
    df["数据更新时间"] = ctx.数据更新时间

    with pytest.raises(IngestGateError) as exc:
        write_dataframe(df, "raw_billing_list", ctx)
    assert exc.value.report.period_mismatch


def test_write_dataframe_passes_valid_billing(tmp_db, ctx):
    df = pd.DataFrame({
        "服务号码": ["13800001234"],
        "账期": ["202604"],
        "实际应收": [100.0],
        "计费应收": [100.0],
    })
    df["客户ID"] = ctx.客户ID
    df["客户名称"] = ctx.客户名称
    df["项目ID"] = ctx.项目ID
    df["项目名称"] = ctx.项目名称
    df["数据月份"] = ctx.账期
    df["数据来源"] = ctx.数据来源
    df["导入批次号"] = ctx.导入批次号
    df["数据更新时间"] = ctx.数据更新时间

    n = write_dataframe(df, "raw_billing_list", ctx, alias_map={"号码": "服务号码"})
    assert n == 1
    assert len(ctx.gate_reports) == 1
    assert ctx.gate_reports[0].passed


def test_prevalidate_passes_without_db_write(tmp_path, tmp_db, ctx):
    reset_field_maps_cache()
    p = tmp_path / "billing_list.csv"
    pd.DataFrame({
        "号码": ["13800001234"],
        "账期": ["202604"],
        "实际应收": [100.0],
        "计费应收": [100.0],
    }).to_csv(p, index=False)

    result = prevalidate_files([p], ctx)
    assert result["summary"]["passed"]
    assert not result["summary"]["would_block"]
    assert result["summary"]["row_count"] == 1

    with connect(read_only=True) as con:
        n = con.execute("SELECT COUNT(*) FROM raw_billing_list").fetchone()[0]
    assert n == 0
    assert not any(f.is_file() for f in get_settings().raw_root.rglob("*"))


def test_prevalidate_catches_period_mismatch(tmp_path, tmp_db, ctx):
    reset_field_maps_cache()
    p = tmp_path / "billing_list.csv"
    pd.DataFrame({
        "号码": ["13800001234"],
        "账期": ["202603"],
        "实际应收": [100.0],
    }).to_csv(p, index=False)

    result = prevalidate_files([p], ctx)
    assert result["summary"]["would_block"]
    assert not result["summary"]["passed"]
