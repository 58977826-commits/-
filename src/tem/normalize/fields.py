"""字段别名映射 - §13.1。

来源 Excel 的列名口径不一，集中在这里维护别名字典；ingest 层通过
``apply_aliases(df, table)`` 把任意来源列名重命名为统一字段名。

真实数据接入后，按实际列名补充各 alias 列表即可，无需改动其它代码。
"""
from __future__ import annotations

from typing import Dict, List

import pandas as pd


# ---------------------------------------------------------------------------
# 服务号码别名 - §7/§8/§9/§11 & §13.1
# 第一项始终是统一字段名，其后是各来源已知的列名
# ---------------------------------------------------------------------------
SERVICE_NUMBER_ALIASES: Dict[str, List[str]] = {
    "usage": [
        "服务号码", "设备号", "号码", "手机号码", "手机号", "Phone Number", "MSISDN",
    ],
    "billing_list": [
        "服务号码", "号码", "手机号码", "手机号", "Phone Number",
    ],
    "billing_detail": [
        "服务号码", "号码", "手机号码", "Phone Number",
    ],
    "asset": [
        "服务号码", "Phone number", "Phone Number", "phone_number", "号码", "手机号", "手机号码",
    ],
    "event_original": [
        "原始服务号码", "原始号码", "原号码", "服务号码", "号码",
    ],
    "event_new": [
        "新服务号码", "变更号码", "新号码",
    ],
    "event_assistant": [
        "副卡号码",
    ],
}


ACCOUNT_PERIOD_ALIASES: List[str] = [
    "账期", "月账期", "账单月份", "数据月份", "Period", "billing_period",
]


EMPLOYEE_ID_ALIASES: List[str] = [
    "员工ID", "员工 ID", "员工编号", "Employee ID", "EmployeeId",
    "WWID", "使用人WWID", "使用人 WWID", "内部用户编号",
]


EMAIL_ALIASES: List[str] = [
    "邮箱", "Email", "E-mail", "企业邮箱", "Email Address", "邮件",
]


EMPLOYEE_NAME_ALIASES: List[str] = [
    "员工姓名", "Employee Name", "姓名", "联系人", "当前使用人",
]


# 五张原始表内部业务字段的统一别名（除上述跨表共用字段外）
TABLE_ALIASES: Dict[str, Dict[str, List[str]]] = {
    "usage": {
        "总短信条数": ["总短信条数", "短信条数", "短信总数"],
        "总通话时长_秒": ["总通话时长_秒", "总通话时长(秒)", "通话时长_秒", "通话总时长(秒)"],
        "总通话分钟": ["总通话分钟", "总通话时长_分钟", "通话总时长(分钟)"],
        "总流量_M": ["总流量_M", "总流量(M)", "总流量MB", "总流量(MB)"],
        "总流量_GB": ["总流量_GB", "总流量(GB)"],
        "主叫通话时长": ["主叫通话时长", "主叫时长"],
        "被叫通话时长": ["被叫通话时长", "被叫时长"],
        "国内漫游流量": ["国内漫游流量"],
        "港澳台漫游流量": ["港澳台漫游流量", "港澳台流量"],
        "国际漫游流量": ["国际漫游流量"],
    },
    "billing_list": {
        "用户状态": ["用户状态", "状态"],
        "计费应收": ["计费应收"],
        "账务优惠": ["账务优惠", "优惠金额"],
        "实际应收": ["实际应收", "应收金额"],
        "账户标识": ["账户标识", "账户ID"],
        "账户名称": ["账户名称"],
        "用户标识": ["用户标识", "用户ID"],
    },
    "billing_detail": {
        "一级科目": ["一级科目", "费用大类"],
        "二级科目": ["二级科目", "费用中类"],
        "三级科目": ["三级科目", "费用明细项"],
        "明细科目编码": ["明细科目编码", "费用科目编码"],
        "账户标识": ["账户标识", "账户ID", "账户编码"],
        "计费应收": ["计费应收"],
        "账务优惠": ["账务优惠", "优惠金额"],
        "实际应收": ["实际应收"],
    },
    "asset": {
        "联系人": ["联系人", "使用人姓名", "使用人"],
        "员工编号": ["员工编号", "员工ID", "Employee ID"],
        "内部用户编号": ["内部用户编号"],
        "组织名称": ["组织名称", "Organization Name", "Organization->Name"],
        "资产状态": ["资产状态", "Asset Status", "状态"],
        "品牌": ["品牌", "Brand"],
        "型号": ["型号", "Model"],
        "IMEI": ["IMEI", "imei"],
        "序列号": ["序列号", "Serial Number", "SN"],
        "采购日期": ["采购日期", "Purchase date", "Purchase Date"],
        "投产日期": ["投产日期", "Move to production date", "MoveToProductionDate"],
        "保修到期日": ["保修到期日", "End of warranty", "Warranty End"],
        "标准套餐金额": ["标准套餐金额", "套餐金额", "Standard Fee", "合约价"],
    },
    "employee": {
        "员工状态": ["员工状态", "Status", "在职状态"],
        "法人主体": ["法人主体", "Legal Entity"],
        "BU": ["BU", "Function", "BU/Function", "BU / Function"],
        "Department": ["Department", "部门"],
        "CostCenter": ["CostCenter", "Cost Center", "成本中心"],
        "LineManager": ["LineManager", "Line Manager", "直属主管"],
        "ManagerEmail": ["ManagerEmail", "Manager Email", "主管邮箱"],
        "Location": ["Location", "Region", "Location/Region", "区域"],
        "生效日期": ["生效日期", "Effective Date"],
        "离职日期": ["离职日期", "Termination Date", "Leave Date"],
    },
    "event": {
        "事件类型": ["事件类型"],
        "事件动作": ["事件动作"],
        "开始时间": ["开始时间", "时间", "时间/开始时间", "时间 / 开始时间"],
        "完成时间": ["完成时间", "完工时间"],
        "事件状态": ["事件状态", "目前状态", "当前状态"],
        "原使用人": ["原使用人", "旧使用人"],
        "当前使用人": ["当前使用人", "使用人"],
        "部门": ["部门", "Department"],
        "系统流水号": ["系统流水号", "ITSM流水号", "工单号"],
        "当前设备序列号": ["当前设备序列号", "Serial Number"],
        "旧设备序列号": ["旧设备序列号", "Old Serial Number"],
        "备注": ["备注", "Remark"],
    },
}


def apply_aliases(df: pd.DataFrame, table: str) -> pd.DataFrame:
    """把 df 中已知的来源列名重命名为统一字段名。

    table 取值（与 ingest 模块一一对应）：
      - usage / billing_list / billing_detail / asset / employee / event

    跨表共用字段（服务号码 / 账期 / 员工ID / 邮箱 / 员工姓名）按对应规则补加映射。
    """
    # 运营商 Excel 列名常带首尾空格（如同文件中的「 账期」「号码 」），先统一 strip
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]

    rename: Dict[str, str] = {}

    # 跨表共用字段
    if table in {"usage", "billing_list", "billing_detail", "asset"}:
        for src in df.columns:
            if src in SERVICE_NUMBER_ALIASES.get(table, []) and src != "服务号码":
                rename[src] = "服务号码"

    if table == "event":
        # 事件表的服务号码分三路：原始 / 新 / 副卡，三组别名互斥
        for src in df.columns:
            if src in SERVICE_NUMBER_ALIASES["event_original"] and src != "原始服务号码":
                rename[src] = "原始服务号码"
            elif src in SERVICE_NUMBER_ALIASES["event_new"] and src != "新服务号码":
                rename[src] = "新服务号码"
            elif src in SERVICE_NUMBER_ALIASES["event_assistant"] and src != "副卡号码":
                rename[src] = "副卡号码"

    # 账期
    if table in {"usage", "billing_list", "billing_detail"}:
        for src in df.columns:
            if src in ACCOUNT_PERIOD_ALIASES and src != "账期":
                rename[src] = "账期"

    # 员工ID
    if table in {"asset", "employee", "event"}:
        for src in df.columns:
            if src in EMPLOYEE_ID_ALIASES and src != "员工ID":
                # asset 第一阶段用"员工编号"作为来源字段保留，故不强制改名
                if table == "asset" and src == "员工编号":
                    continue
                rename[src] = "员工ID"

    # 邮箱
    if table in {"asset", "employee"}:
        for src in df.columns:
            if src in EMAIL_ALIASES and src != "邮箱":
                rename[src] = "邮箱"

    # 员工姓名（asset.联系人 / employee.员工姓名 / event.当前使用人 各自有独立字段，不强制改名）
    # 其他业务字段
    for unified, aliases in TABLE_ALIASES.get(table, {}).items():
        for src in df.columns:
            if src != unified and src in aliases:
                rename[src] = unified

    if rename:
        df = df.rename(columns=rename)
    return df


def normalize_phone(value) -> str | None:
    """统一服务号码：去空白、去前后空格、去 .0 浮点尾巴、去 +86。"""
    if value is None:
        return None
    if isinstance(value, float):
        if pd.isna(value):
            return None
        if value.is_integer():
            return str(int(value))
    s = str(value).strip().replace(" ", "")
    if not s:
        return None
    if s.endswith(".0") and s[:-2].isdigit():
        s = s[:-2]
    if s.startswith("+86"):
        s = s[3:]
    elif s.startswith("86") and len(s) == 13:
        s = s[2:]
    return s


def normalize_account_period(value) -> str | None:
    """账期统一为 YYYYMM 字符串。

    支持以下输入：
      - 202604 / "202604"
      - "2026-04" / "2026/04" / "2026年4月" / "2026年04月"
      - 日期对象（取 yyyymm）
    """
    import re

    if value is None:
        return None
    if isinstance(value, float) and pd.isna(value):
        return None
    if isinstance(value, (pd.Timestamp,)):
        return value.strftime("%Y%m")
    s = str(value).strip()
    if not s:
        return None
    # 形如 "YYYY年M月"
    m = re.match(r"^(\d{4})\D(\d{1,2})\D?$", s)
    if m:
        y, mo = m.group(1), m.group(2)
        return f"{y}{int(mo):02d}"
    digits = "".join(ch for ch in s if ch.isdigit())
    if len(digits) >= 6:
        return digits[:6]
    if len(digits) == 5:
        # "2026年4月" -> "20264" -> "202604"
        return digits[:4] + f"{int(digits[4]):02d}"
    return s
