"""端到端管道测试 - 用 mock 数据跑通 ingest -> build -> query。"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from tem.build import build_fact_tem_monthly
from tem.db import connect
from tem.ingest import (
    IngestContext,
    ingest_asset,
    ingest_billing,
    ingest_employee,
    ingest_event,
    ingest_usage,
)


def _ctx(账期: str = "202604") -> IngestContext:
    return IngestContext(
        客户ID="johnson",
        项目ID="work-phone",
        账期=账期,
        客户名称="强生",
        项目名称="工作手机项目",
        数据来源="联通账单",
    )


def _write(path: Path, df: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(path, index=False)


def test_e2e_minimal(tmp_path, tmp_db, monkeypatch):
    """落地一个微型样本：3 个号码，覆盖正常 / 超套 / 零用量但计费三种典型场景。"""
    from tem import config as cfg_module

    settings = cfg_module.get_settings()
    raw_root = settings.raw_root

    # 用量
    usage_path = raw_root / "usage" / "johnson" / "work-phone" / "202604" / "usage.xlsx"
    _write(usage_path, pd.DataFrame({
        "服务号码": ["13800000001", "13800000002", "13800000003"],
        "账期": ["202604", "202604", "202604"],
        "总短信条数": [10, 0, 5],
        "总通话时长_秒": [1200, 0, 600],
        "总流量_M": [2048, 0, 1024],
    }))

    # 账单清单
    billing_path = raw_root / "billing" / "johnson" / "work-phone" / "202604" / "billing_list.xlsx"
    _write(billing_path, pd.DataFrame({
        "服务号码": ["13800000001", "13800000002", "13800000003"],
        "账期": ["202604", "202604", "202604"],
        "用户状态": ["在网", "在网", "在网"],
        "计费应收": [187, 50, 250],
        "账务优惠": [0, 0, 0],
        "实际应收": [187, 50, 250],
    }))
    # 账单明细
    detail_path = raw_root / "billing" / "johnson" / "work-phone" / "202604" / "billing_detail.xlsx"
    _write(detail_path, pd.DataFrame({
        "服务号码": ["13800000001", "13800000002", "13800000003", "13800000003"],
        "账期": ["202604"] * 4,
        "一级科目": ["月固定费", "月固定费", "月固定费", "上网费"],
        "实际应收": [187, 50, 187, 63],
    }))

    # 资产
    asset_path = raw_root / "asset" / "johnson" / "work-phone" / "asset.xlsx"
    _write(asset_path, pd.DataFrame({
        "服务号码": ["13800000001", "13800000002", "13800000003"],
        "联系人": ["张三", "李四", "王五"],
        "邮箱": ["zhang@x.com", "li@x.com", "wang@x.com"],
        "员工编号": ["E001", "E002", "E003"],
        "组织名称": ["MT", "MT", "Vision"],
        "资产状态": ["在用", "在用", "在用"],
        "型号": ["iPhone 16", "iPhone 16", "iPhone 16"],
        "标准套餐金额": [187.0, 187.0, 187.0],
    }))

    # 人员
    employee_path = raw_root / "employee" / "johnson" / "work-phone" / "employee.xlsx"
    _write(employee_path, pd.DataFrame({
        "员工ID": ["E001", "E002", "E003"],
        "员工姓名": ["张三", "李四", "王五"],
        "邮箱": ["zhang@x.com", "li@x.com", "wang@x.com"],
        "员工状态": ["在职", "在职", "在职"],
        "BU": ["MT", "MT", "Vision"],
        "Department": ["销售一部", "销售一部", "运营部"],
        "CostCenter": ["CC001", "CC001", "CC002"],
        "LineManager": ["mgrA", "mgrA", "mgrB"],
        "ManagerEmail": ["mgrA@x.com", "mgrA@x.com", "mgrB@x.com"],
    }))

    # 事件（一个改号事件）
    event_path = raw_root / "event" / "johnson" / "work-phone" / "events.xlsx"
    _write(event_path, pd.DataFrame({
        "原始号码": ["13800000003"],
        "变更号码": ["13900000003"],
        "事件类型": ["套餐变更"],
        "事件动作": ["改号"],
        "时间": [date(2026, 4, 5)],
        "目前状态": ["Completed"],
        "使用人WWID": ["E003"],
        "当前使用人": ["王五"],
    }))

    ctx = _ctx()
    n_usage = ingest_usage(ctx)
    n_bill = ingest_billing(ctx)
    n_asset = ingest_asset(ctx)
    n_emp = ingest_employee(ctx)
    n_event = ingest_event(ctx)

    assert n_usage == 3
    assert n_bill["billing_list"] == 3
    assert n_bill["billing_detail"] == 4
    assert n_asset == 3
    assert n_emp == 3
    assert n_event == 1

    # 跑 fact 表
    n = build_fact_tem_monthly("johnson", "work-phone", "202604")
    assert n == 3

    with connect(read_only=True) as con:
        rows = con.execute("""
            SELECT 服务号码, 实际应收, 标准套餐金额, 超套金额, 是否超套, 是否零用量, 是否零用量但计费,
                   异常类型, Department, CostCenter, 当月事件类型, 是否改号
            FROM fact_tem_monthly
            WHERE 客户ID = 'johnson' AND 项目ID = 'work-phone' AND 账期 = '202604'
            ORDER BY 服务号码
        """).fetchdf()

    assert list(rows["服务号码"]) == ["13800000001", "13800000002", "13800000003"]

    # 号码1: 用量正常、账单 = 标准套餐 -> 不超套、无异常
    r1 = rows.iloc[0]
    assert float(r1["超套金额"]) == 0.0
    assert bool(r1["是否超套"]) is False
    assert r1["Department"] == "销售一部"
    assert r1["CostCenter"] == "CC001"

    # 号码2: 零用量，账单 50 -> 零用量但计费
    r2 = rows.iloc[1]
    assert bool(r2["是否零用量"]) is True
    assert bool(r2["是否零用量但计费"]) is True
    assert "零用量" in r2["异常类型"]

    # 号码3: 实际应收 250 > 标准 187 * 1.05 -> 超套；当月有改号事件
    r3 = rows.iloc[2]
    assert float(r3["超套金额"]) == 63.0
    assert bool(r3["是否超套"]) is True
    assert "超套" in r3["异常类型"]
    assert bool(r3["是否改号"]) is True


def test_views_callable(tmp_path, tmp_db):
    """视图可被查询，且字段可读。"""
    with connect(read_only=True) as con:
        # 三个视图 + raw_event 都应可查询
        for view in ["v_monthly_summary", "v_costcenter_allocation",
                     "v_anomaly_list", "v_overpackage_list", "v_event_overview"]:
            con.execute(f"SELECT * FROM {view} LIMIT 0").fetchdf()
