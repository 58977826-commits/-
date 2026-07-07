"""自动识别 Excel 表类型并入库。

工作流程：
  1. detect_table_type(columns)：根据列名集合判断 usage / billing / asset / employee / event
  2. detect_excel_file(path)：扫描 Excel 全部 sheet，给出每个 sheet 的识别结果
  3. auto_ingest_files(files, ctx)：按识别结果把文件复制到 data/raw/{type}/...
     再调用对应的 ingest_* 函数入库

设计原则：
  - 列名匹配为主信号（强信号），文件名为次级信号（兜底）
  - 检测优先级 event > billing > usage > asset > employee
    （保证有 "事件类型" 列的文件优先归到事件表）
  - 不修改用户上传的原始文件；落地到 raw/ 目录留档便于复算

落地路径约定：
  usage / billing                       -> data/raw/{type}/{客户}/{项目}/{账期}/
  asset / employee / event              -> data/raw/{type}/{客户}/{项目}/
"""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import pandas as pd

from ..config import get_settings
from .asset import ingest_asset
from .billing import ingest_billing
from .common import IngestContext
from .employee import ingest_employee
from .event import ingest_event
from .usage import ingest_usage


# ---------------------------------------------------------------------------
# 表类型识别：列名信号
# ---------------------------------------------------------------------------

# 各表的"强信号列"：命中其中一个就基本可以确定是这类
_EVENT_SIGNALS = {"事件类型", "事件动作", "原始号码", "原始服务号码", "使用人WWID", "使用人 WWID"}

_BILLING_SIGNALS = {
    "实际应收", "应收金额", "计费应收", "账务优惠",
    "一级科目", "费用大类", "二级科目", "三级科目", "明细科目编码", "用户状态",
}

_USAGE_SIGNALS = {
    "总流量_M", "总流量(M)", "总流量MB", "总流量(MB)",
    "总通话时长_秒", "总通话时长(秒)",
    "国际漫游流量", "港澳台漫游流量", "国内漫游流量",
    "主叫通话时长", "被叫通话时长",
    "总短信条数", "短信总数",
}

_ASSET_SIGNALS = {
    "IMEI", "标准套餐金额", "资产状态", "Asset Status",
    "Phone number", "Phone Number",
    "序列号", "Serial Number", "SN",
    "投产日期", "Move to production date",
    "保修到期日", "End of warranty",
    "采购日期", "Purchase date",
}

_EMPLOYEE_SIGNALS = {
    "员工 ID", "员工ID", "Employee ID", "EmployeeId",
    "WWID",
    "Cost Center", "CostCenter", "成本中心",
    "BU / Function", "BU/Function",
    "Department",
    "Line Manager", "LineManager",
    "Manager Email", "ManagerEmail",
    "员工状态",
    "法人主体", "Legal Entity",
}


# 文件名兜底关键字（仅在列名识别失败时启用）
_FILENAME_HINTS: dict[str, tuple[str, ...]] = {
    "usage":     ("raw_usage", "用量"),
    "billing":   ("raw_billing", "账单"),
    "asset":     ("raw_asset", "资产"),
    "employee":  ("raw_employee", "人员", "员工"),
    "event":     ("raw_event", "事件"),
}

# 应跳过的辅助 sheet（事件字典 / 下拉选项 等）
_SKIP_SHEET_KEYWORDS = ("事件字典", "字典", "_下拉", "下拉选项", "Dropdown", "dropdown")


def detect_table_type(columns: list[str]) -> str | None:
    """根据列名集合判断表类型。

    返回 "usage" / "billing" / "asset" / "employee" / "event" / None
    （billing 不再细分 list / detail，sheet 级粒度由 ingest_billing 内部处理）
    """
    cols = {str(c).strip() for c in columns if c is not None and str(c).strip()}

    # 1) 事件表：列里出现"事件类型"等独有信号 -> 一票通过
    if cols & _EVENT_SIGNALS:
        return "event"

    # 2) 账单：列里出现账单独有信号，且不像资产/人员
    if cols & _BILLING_SIGNALS:
        # 排除：资产/人员/用量/事件不会同时含 实际应收 / 一级科目 等
        if not (cols & _ASSET_SIGNALS) and not (cols & _USAGE_SIGNALS):
            return "billing"

    # 3) 用量：流量/通话时长信号
    if cols & _USAGE_SIGNALS:
        return "usage"

    # 4) 资产：IMEI / 标准套餐金额 / 资产状态 / 序列号 等设备特征
    if cols & _ASSET_SIGNALS:
        return "asset"

    # 5) 人员：员工 ID + Cost Center / Department 等组织特征
    if cols & _EMPLOYEE_SIGNALS:
        # 人员表不应包含服务号码相关列
        phone_cols = {"服务号码", "Phone number", "Phone Number", "号码"}
        if not (cols & phone_cols):
            return "employee"

    return None


def detect_table_type_by_filename(name: str) -> str | None:
    """兜底：仅根据文件名识别表类型。"""
    s = (name or "").lower()
    for t, hints in _FILENAME_HINTS.items():
        if any(h.lower() in s for h in hints):
            return t
    return None


# ---------------------------------------------------------------------------
# 文件 / sheet 级扫描
# ---------------------------------------------------------------------------


def _is_skip_sheet(name: str) -> bool:
    n = (name or "").strip()
    return not n or any(k in n for k in _SKIP_SHEET_KEYWORDS)


def detect_excel_file(path: Path) -> dict[str, Any]:
    """扫描整个 Excel 文件，返回每个 sheet 的识别结果。

    返回结构：
        {
            "file": "<filename>",
            "primary_type": "usage" / "billing" / ... / None,
            "from_filename": False,   # primary_type 是否仅由文件名兜底
            "sheets": [
                {"name": "Sheet1", "table_type": "usage", "columns": [...]},
                ...
            ],
            "error": "...",           # 若读取失败
        }
    """
    info: dict[str, Any] = {
        "file": path.name,
        "primary_type": None,
        "from_filename": False,
        "sheets": [],
    }

    suffix = path.suffix.lower()
    if suffix == ".csv":
        try:
            df = pd.read_csv(path, nrows=0, encoding_errors="ignore")
        except Exception as e:  # noqa: BLE001
            info["error"] = str(e)
            return info
        cols = [str(c) for c in df.columns]
        t = detect_table_type(cols)
        info["sheets"].append({"name": path.name, "table_type": t, "columns": cols})
        info["primary_type"] = t
    elif suffix in {".xlsx", ".xls"}:
        try:
            xl = pd.ExcelFile(path)
        except Exception as e:  # noqa: BLE001
            info["error"] = str(e)
            return info
        for sheet in xl.sheet_names:
            if _is_skip_sheet(sheet):
                info["sheets"].append({"name": sheet, "table_type": "skip", "columns": []})
                continue
            try:
                header = pd.read_excel(path, sheet_name=sheet, nrows=0, dtype=object)
            except Exception:  # noqa: BLE001
                info["sheets"].append({"name": sheet, "table_type": None, "columns": []})
                continue
            cols = [str(c) for c in header.columns]
            t = detect_table_type(cols)
            info["sheets"].append({"name": sheet, "table_type": t, "columns": cols})
            if t and not info["primary_type"]:
                info["primary_type"] = t
    else:
        info["error"] = f"不支持的文件类型: {suffix}"
        return info

    # 兜底：列识别失败时按文件名猜
    if not info["primary_type"]:
        fname_guess = detect_table_type_by_filename(path.name)
        if fname_guess:
            info["primary_type"] = fname_guess
            info["from_filename"] = True

    return info


# ---------------------------------------------------------------------------
# 自动入库
# ---------------------------------------------------------------------------


def _target_dir(bucket: str, ctx: IngestContext) -> Path:
    """按表类型决定落地目录。"""
    root = get_settings().raw_root / bucket / ctx.客户ID / ctx.项目ID
    if bucket in {"usage", "billing"} and ctx.账期:
        root = root / ctx.账期
    return root


def auto_ingest_files(files: list[Path], ctx: IngestContext) -> dict[str, Any]:
    """识别一批文件的类型并落地 + 入库。

    返回:
        {
            "file_reports": [ {file, primary_type, landed_at, sheets, error?}, ... ],
            "ingest_counts": { "raw_usage": N, "raw_billing_list": N, ... },
        }
    """
    ctx.resolve_meta()

    # 按桶分组（key = usage / billing / asset / employee / event）
    grouped: dict[str, list[Path]] = {
        "usage": [], "billing": [], "asset": [], "employee": [], "event": [],
    }
    file_reports: list[dict[str, Any]] = []

    for f in files:
        info = detect_excel_file(f)
        primary = info["primary_type"]
        report: dict[str, Any] = {
            "file": f.name,
            "primary_type": primary,
            "from_filename": info.get("from_filename", False),
            "sheets": info["sheets"],
        }
        if info.get("error"):
            report["error"] = info["error"]

        if primary in grouped:
            target_dir = _target_dir(primary, ctx)
            target_dir.mkdir(parents=True, exist_ok=True)
            target = target_dir / f.name
            try:
                if f.resolve() != target.resolve():
                    shutil.copy2(f, target)
            except (FileNotFoundError, OSError) as e:
                report["error"] = f"复制文件失败: {e}"
                file_reports.append(report)
                continue
            grouped[primary].append(target)
            report["landed_at"] = str(target)
        else:
            report.setdefault("error", "无法识别表类型")

        file_reports.append(report)

    # 调用对应 ingest 函数
    counts: dict[str, int] = {}
    if grouped["usage"]:
        counts["raw_usage"] = ingest_usage(ctx, files=grouped["usage"])
    if grouped["billing"]:
        c = ingest_billing(ctx, files=grouped["billing"])
        counts["raw_billing_list"] = c.get("billing_list", 0)
        counts["raw_billing_detail"] = c.get("billing_detail", 0)
    if grouped["asset"]:
        counts["raw_asset"] = ingest_asset(ctx, files=grouped["asset"])
    if grouped["employee"]:
        counts["raw_employee"] = ingest_employee(ctx, files=grouped["employee"])
    if grouped["event"]:
        counts["raw_event"] = ingest_event(ctx, files=grouped["event"])

    return {
        "file_reports": file_reports,
        "ingest_counts": counts,
        "gate_reports": [r.to_dict() for r in ctx.gate_reports],
    }
