"""规则引擎核心单元测试 - C01-C06 / Z01-Z04 / H01-H04 / 异常聚合。"""
from __future__ import annotations

import pandas as pd
import pytest

from tem.rules import (
    aggregate_anomaly_summary,
    apply_high_usage,
    apply_overpackage,
    apply_post_termination,
    apply_roaming,
    apply_value_added,
    apply_zero_usage,
)


# ---------------------------------------------------------------------------
# 超套规则 C01-C06
# ---------------------------------------------------------------------------
class TestOverpackage:
    def test_c02_basic(self, tmp_db):
        """C02: 超套金额 = 实际应收 - 标准套餐金额。"""
        df = pd.DataFrame({
            "服务号码": ["A", "B"],
            "标准套餐金额": [100.0, 200.0],
            "实际应收": [150.0, 180.0],
        })
        out = apply_overpackage(df)
        assert out.loc[0, "超套金额"] == 50.0
        # C03: 实际 < 标准 时超套金额 = 0
        assert out.loc[1, "超套金额"] == 0.0

    def test_c04_rate(self, tmp_db):
        df = pd.DataFrame({
            "服务号码": ["A"],
            "标准套餐金额": [100.0],
            "实际应收": [150.0],
        })
        out = apply_overpackage(df)
        assert out.loc[0, "超套率"] == 0.5

    def test_c05_warning(self, tmp_db):
        """C05: 实际应收 > 标准套餐 * 1.05 -> 是否超套 = True。"""
        df = pd.DataFrame({
            "服务号码": ["A", "B"],
            "标准套餐金额": [100.0, 100.0],
            "实际应收": [104.0, 110.0],   # 4% / 10%
        })
        out = apply_overpackage(df)
        assert bool(out.loc[0, "是否超套"]) is False
        assert bool(out.loc[1, "是否超套"]) is True

    def test_no_standard_fee_no_warning(self, tmp_db):
        """标准套餐金额缺失 -> 不判超套。"""
        df = pd.DataFrame({
            "服务号码": ["A"],
            "标准套餐金额": [None],
            "实际应收": [9999.0],
        })
        out = apply_overpackage(df)
        assert bool(out.loc[0, "是否超套"]) is False


# ---------------------------------------------------------------------------
# 零用量规则 Z01-Z04
# ---------------------------------------------------------------------------
class TestZeroUsage:
    def test_z01_zero_usage(self, tmp_db):
        df = pd.DataFrame({
            "服务号码": ["A", "B"],
            "总通话分钟": [0, 10],
            "总流量GB": [0, 0.5],
            "短信条数": [0, 0],
            "实际应收": [50, 100],
            "客户ID": ["c1", "c1"],
            "项目ID": ["p1", "p1"],
        })
        out = apply_zero_usage(df)
        assert bool(out.loc[0, "是否零用量"]) is True
        assert bool(out.loc[1, "是否零用量"]) is False

    def test_z02_zero_billed(self, tmp_db):
        """Z02: 零用量 + 实际应收 > 0 -> 零用量但计费。"""
        df = pd.DataFrame({
            "服务号码": ["A"],
            "总通话分钟": [0],
            "总流量GB": [0],
            "短信条数": [0],
            "实际应收": [50],
            "客户ID": ["c1"],
            "项目ID": ["p1"],
        })
        out = apply_zero_usage(df)
        assert bool(out.loc[0, "是否零用量但计费"]) is True


# ---------------------------------------------------------------------------
# 高用量规则 H01-H04
# ---------------------------------------------------------------------------
class TestHighUsage:
    def test_h01_hard_cap_data(self, tmp_db):
        """H01: 流量 > hard_cap (50GB) -> 高流量。"""
        df = pd.DataFrame({
            "服务号码": [f"P{i}" for i in range(6)],
            "总通话分钟": [10] * 6,
            "总流量GB": [1, 2, 3, 4, 5, 60],   # 最后一个超过 hard cap
        })
        out = apply_high_usage(df)
        assert bool(out.loc[5, "是否高流量"]) is True
        # P95 阈值在 5 ≥ 5 数据点的情况下也会触发，但其它 5 个不应该都被标
        assert bool(out.loc[0, "是否高流量"]) is False

    def test_h02_p95(self, tmp_db):
        """H02: P95 触发判定。"""
        df = pd.DataFrame({
            "服务号码": [f"P{i}" for i in range(20)],
            "总通话分钟": [10] * 20,
            "总流量GB": list(range(1, 20)) + [200],   # 最后一个 200，p95 触发
        })
        out = apply_high_usage(df)
        assert bool(out.loc[19, "是否高流量"]) is True

    def test_h03_voice(self, tmp_db):
        """H03: 通话 hard cap 1500 分钟。"""
        df = pd.DataFrame({
            "服务号码": ["A", "B"],
            "总通话分钟": [200, 2000],
            "总流量GB": [1.0, 2.0],
        })
        out = apply_high_usage(df)
        assert bool(out.loc[0, "是否高通话"]) is False
        assert bool(out.loc[1, "是否高通话"]) is True


# ---------------------------------------------------------------------------
# 漫游
# ---------------------------------------------------------------------------
class TestRoaming:
    def test_roaming_by_usage(self, tmp_db):
        df = pd.DataFrame({
            "服务号码": ["A", "B"],
            "国际漫游流量": [0, 100],
            "港澳台漫游流量": [0, 0],
        })
        out = apply_roaming(df, billing_detail=None)
        assert bool(out.loc[0, "是否漫游"]) is False
        assert bool(out.loc[1, "是否漫游"]) is True

    def test_roaming_by_billing(self, tmp_db):
        df = pd.DataFrame({"服务号码": ["A", "B"]})
        billing_detail = pd.DataFrame({
            "服务号码": ["A", "B"],
            "一级科目": ["国际漫游费", "上网费"],
            "实际应收": [100, 50],
        })
        out = apply_roaming(df, billing_detail=billing_detail)
        assert bool(out.loc[0, "是否漫游"]) is True
        assert bool(out.loc[1, "是否漫游"]) is False


# ---------------------------------------------------------------------------
# 增值业务
# ---------------------------------------------------------------------------
class TestValueAdded:
    def test_value_added(self, tmp_db):
        df = pd.DataFrame({"服务号码": ["A", "B"]})
        billing_detail = pd.DataFrame({
            "服务号码": ["A", "A", "B"],
            "一级科目": ["增值业务费", "上网费", "上网费"],
            "实际应收": [30, 50, 80],
        })
        out = apply_value_added(df, billing_detail=billing_detail)
        assert bool(out.loc[0, "是否增值业务异常"]) is True
        assert out.loc[0, "增值业务金额"] == 30
        assert bool(out.loc[1, "是否增值业务异常"]) is False


# ---------------------------------------------------------------------------
# 离职后计费
# ---------------------------------------------------------------------------
class TestPostTermination:
    def test_terminated_status(self, tmp_db):
        df = pd.DataFrame({
            "服务号码": ["A", "B"],
            "员工状态": ["在职", "离职"],
            "实际应收": [100, 50],
            "账期": ["202604", "202604"],
        })
        out = apply_post_termination(df)
        assert bool(out.loc[0, "是否离职后计费"]) is False
        assert bool(out.loc[1, "是否离职后计费"]) is True


# ---------------------------------------------------------------------------
# 异常聚合
# ---------------------------------------------------------------------------
class TestAnomalyAggregate:
    def test_aggregate_summary(self, tmp_db):
        df = pd.DataFrame({
            "服务号码": ["A", "B", "C"],
            "是否超套": [True, False, False],
            "是否零用量但计费": [False, True, False],
            "是否高流量": [False, False, True],
            "是否漫游": [False, False, False],
            "是否增值业务异常": [False, False, False],
            "是否离职后计费": [False, False, False],
            "超套金额": [50.0, 0.0, 0.0],
            "增值业务金额": [0.0, 0.0, 0.0],
            "实际应收": [150, 30, 100],
        })
        out = aggregate_anomaly_summary(df)
        assert "超套" in out.loc[0, "异常类型"]
        assert "零用量" in out.loc[1, "异常类型"]
        assert "高流量" in out.loc[2, "异常类型"]
        assert out.loc[0, "异常金额"] == 50.0
        assert out.loc[1, "异常金额"] == 30.0     # 零用量但计费 -> 异常金额=实际应收
