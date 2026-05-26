"""Excel 表类型自动识别测试。"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from tem.ingest.auto import (
    auto_ingest_files,
    detect_excel_file,
    detect_table_type,
    detect_table_type_by_filename,
)
from tem.ingest.common import IngestContext


class TestDetectByColumns:
    """各表对应的真实模板列（来自 data/samples/*.xlsx）。"""

    def test_usage(self):
        cols = ["客户ID", "客户名称", "项目ID", "项目名称", "账期", "服务号码",
                "总短信条数", "总通话时长_秒", "总流量_M",
                "主叫通话时长", "被叫通话时长",
                "国内漫游流量", "港澳台漫游流量", "国际漫游流量"]
        assert detect_table_type(cols) == "usage"

    def test_billing_list(self):
        cols = ["客户ID", "客户名称", "项目ID", "项目名称", "账期", "服务号码",
                "用户状态", "计费应收", "账务优惠", "实际应收",
                "账户标识", "账户名称", "用户标识"]
        assert detect_table_type(cols) == "billing"

    def test_billing_detail(self):
        cols = ["客户ID", "项目ID", "账期", "服务号码",
                "一级科目", "二级科目", "三级科目", "明细科目编码",
                "计费应收", "账务优惠", "实际应收"]
        assert detect_table_type(cols) == "billing"

    def test_asset(self):
        cols = ["客户ID", "客户名称", "项目ID", "项目名称", "服务号码",
                "联系人", "邮箱", "员工编号", "组织名称",
                "资产状态", "品牌", "型号", "IMEI", "序列号", "标准套餐金额"]
        assert detect_table_type(cols) == "asset"

    def test_employee(self):
        cols = ["客户ID", "项目ID", "员工 ID", "员工姓名", "邮箱", "员工状态",
                "法人主体", "BU / Function", "Department", "Cost Center",
                "Line Manager", "Manager Email", "离职日期"]
        assert detect_table_type(cols) == "employee"

    def test_event(self):
        cols = ["客户ID", "项目ID", "原始号码", "变更号码", "事件类型", "事件动作",
                "开始时间", "目前状态", "完工时间", "副卡号码",
                "旧使用人", "当前使用人", "使用人WWID", "部门",
                "系统流水号", "备注"]
        assert detect_table_type(cols) == "event"

    def test_unknown(self):
        cols = ["foo", "bar", "baz"]
        assert detect_table_type(cols) is None

    def test_empty(self):
        assert detect_table_type([]) is None

    def test_event_wins_over_others(self):
        """事件表也常有"服务号码"列别名，事件信号应优先。"""
        cols = ["客户ID", "服务号码", "事件类型", "事件动作", "实际应收"]
        assert detect_table_type(cols) == "event"

    def test_employee_excluded_by_phone(self):
        """带服务号码 + Cost Center 的混合数据不应识别为人员表。"""
        cols = ["服务号码", "Cost Center", "实际应收"]
        # 因含"实际应收" -> billing 优先
        assert detect_table_type(cols) == "billing"


class TestDetectByFilename:
    @pytest.mark.parametrize("name,expected", [
        ("01_raw_usage_运营商用量.xlsx", "usage"),
        ("02_raw_billing_账单清单.xlsx", "billing"),
        ("03_raw_billing_账单明细.xlsx", "billing"),
        ("04_raw_asset_资产.xlsx", "asset"),
        ("05_raw_employee_人员.xlsx", "employee"),
        ("06_raw_event_事件总表.xlsx", "event"),
        ("用量.xlsx", "usage"),
        ("联通账单_202604.csv", "billing"),
        ("无规律名称.xlsx", None),
    ])
    def test_filename_hint(self, name, expected):
        assert detect_table_type_by_filename(name) == expected


class TestDetectExcelFile:
    def test_detect_xlsx_with_columns(self, tmp_path: Path):
        path = tmp_path / "usage_demo.xlsx"
        pd.DataFrame({
            "服务号码": ["13800001234"],
            "账期": ["202604"],
            "总短信条数": [5],
            "总通话时长_秒": [1200],
            "总流量_M": [512],
        }).to_excel(path, index=False)
        info = detect_excel_file(path)
        assert info["primary_type"] == "usage"
        assert info["from_filename"] is False
        assert info["sheets"][0]["table_type"] == "usage"

    def test_skip_dictionary_sheets(self, tmp_path: Path):
        """事件字典 / _下拉选项 sheet 应该被标为 skip。"""
        path = tmp_path / "event.xlsx"
        with pd.ExcelWriter(path, engine="openpyxl") as w:
            pd.DataFrame({
                "原始号码": ["138"],
                "事件类型": ["套餐变更"],
                "事件动作": ["改号"],
            }).to_excel(w, sheet_name="总表", index=False)
            pd.DataFrame({"trigger_scenario": ["A"]}).to_excel(w, sheet_name="事件字典", index=False)
            pd.DataFrame({"opt": ["x"]}).to_excel(w, sheet_name="_下拉选项", index=False)

        info = detect_excel_file(path)
        assert info["primary_type"] == "event"
        # 字典 / 下拉 应该标 skip
        skip_count = sum(1 for s in info["sheets"] if s["table_type"] == "skip")
        assert skip_count >= 2

    def test_filename_fallback(self, tmp_path: Path):
        """空内容 + 文件名含 'raw_asset' -> 文件名兜底。"""
        path = tmp_path / "raw_asset_2026.xlsx"
        # 写一个全是无关列的 Excel
        pd.DataFrame({"foo": [1], "bar": [2]}).to_excel(path, index=False)
        info = detect_excel_file(path)
        assert info["primary_type"] == "asset"
        assert info["from_filename"] is True

    def test_unknown_file(self, tmp_path: Path):
        path = tmp_path / "unrelated.xlsx"
        pd.DataFrame({"foo": [1], "bar": [2]}).to_excel(path, index=False)
        info = detect_excel_file(path)
        assert info["primary_type"] is None


class TestAutoIngest:
    """端到端：把 6 类文件丢进去，验证落地 + 入库行数。"""

    def _build_files(self, root: Path) -> list[Path]:
        files = []

        # usage
        p = root / "usage.xlsx"
        pd.DataFrame({
            "服务号码": ["P001", "P002"],
            "账期": ["202604", "202604"],
            "总短信条数": [10, 0],
            "总通话时长_秒": [1200, 0],
            "总流量_M": [2048, 0],
        }).to_excel(p, index=False)
        files.append(p)

        # billing 清单
        p = root / "billing_清单.xlsx"
        pd.DataFrame({
            "服务号码": ["P001", "P002"],
            "账期": ["202604", "202604"],
            "用户状态": ["在网", "在网"],
            "计费应收": [187, 50],
            "实际应收": [187, 50],
        }).to_excel(p, index=False)
        files.append(p)

        # billing 明细
        p = root / "billing_明细.xlsx"
        pd.DataFrame({
            "服务号码": ["P001", "P002"],
            "账期": ["202604", "202604"],
            "一级科目": ["月固定费", "月固定费"],
            "实际应收": [187, 50],
        }).to_excel(p, index=False)
        files.append(p)

        # asset
        p = root / "asset.xlsx"
        pd.DataFrame({
            "服务号码": ["P001", "P002"],
            "联系人": ["张三", "李四"],
            "邮箱": ["a@x.com", "b@x.com"],
            "员工编号": ["E001", "E002"],
            "资产状态": ["在用", "在用"],
            "型号": ["iPhone", "iPhone"],
            "IMEI": ["IMEI001", "IMEI002"],
            "标准套餐金额": [187.0, 187.0],
        }).to_excel(p, index=False)
        files.append(p)

        # employee
        p = root / "employee.xlsx"
        pd.DataFrame({
            "员工 ID": ["E001", "E002"],
            "员工姓名": ["张三", "李四"],
            "邮箱": ["a@x.com", "b@x.com"],
            "员工状态": ["在职", "在职"],
            "Cost Center": ["CC001", "CC002"],
            "Department": ["销售一部", "销售二部"],
            "BU / Function": ["MT", "MT"],
        }).to_excel(p, index=False)
        files.append(p)

        # event
        p = root / "event.xlsx"
        pd.DataFrame({
            "原始号码": ["P001"],
            "事件类型": ["套餐变更"],
            "事件动作": ["改号"],
            "时间": ["2026-04-05"],
            "目前状态": ["Completed"],
        }).to_excel(p, index=False)
        files.append(p)

        return files

    def test_auto_ingest_all_types(self, tmp_path: Path, tmp_db):
        # 准备 6 个文件
        upload_dir = tmp_path / "uploads"
        upload_dir.mkdir()
        files = self._build_files(upload_dir)

        ctx = IngestContext(
            客户ID="demo",
            项目ID="auto",
            账期="202604",
        )
        result = auto_ingest_files(files, ctx)

        # 6 个文件全部被识别
        types = {r["primary_type"] for r in result["file_reports"]}
        assert types == {"usage", "billing", "asset", "employee", "event"}

        # 入库行数
        counts = result["ingest_counts"]
        assert counts.get("raw_usage", 0) == 2
        assert counts.get("raw_billing_list", 0) == 2
        assert counts.get("raw_billing_detail", 0) == 2
        assert counts.get("raw_asset", 0) == 2
        assert counts.get("raw_employee", 0) == 2
        assert counts.get("raw_event", 0) == 1

        # 验证落地到 data/raw/
        for r in result["file_reports"]:
            assert "landed_at" in r
            assert Path(r["landed_at"]).exists()
