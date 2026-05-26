"""生成 Mock 数据，便于在真实账单到位前验证端到端管道。

覆盖场景（每个号码对应一种典型情况）：
  P01: 正常使用 + 标准套餐
  P02: 零用量但仍计费 (Z02)
  P03: 超套 50% + 上网费过高 (C05)
  P04: 高流量 (P95 / hard cap)
  P05: 漫游使用 + 国际漫游费
  P06: 增值业务异常 (B05)
  P07: 离职员工但仍计费
  P08: 资产无对应人员（人员缺失）
  P09: 账单有号码但无资产（资产缺失）
  P10: 当月改号事件（套餐变更/改号）
  P11: 副卡申请事件
  P12: 离职归还 On-Boarding 未闭环

使用方法：
  python scripts/generate_mock_data.py
  tem run --客户 demo --项目 mock --账期 202604
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"

CLIENT = "demo"
PROJECT = "mock"
PERIOD = "202604"


def write(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(path, index=False)
    print(f"[mock] write {path.relative_to(ROOT)}")


def main() -> None:
    # ---------------- usage ----------------
    usage = pd.DataFrame({
        "服务号码": [f"P{i:03d}" for i in range(1, 13)],
        "账期": [PERIOD] * 12,
        "总短信条数":   [10,  0,   5,   2,   0,   1,   3,   0,   0,   8,   4,   0],
        "总通话时长_秒": [1200, 0, 600, 7200, 1800, 300, 900, 0, 0, 1200, 1500, 0],
        "总流量_M":     [2048, 0, 4096, 81920, 3072, 1024, 2048, 0, 0, 1500, 1200, 0],
        "国际漫游流量": [0, 0, 0, 0, 5120, 0, 0, 0, 0, 0, 0, 0],
        "港澳台漫游流量": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    })
    write(usage, RAW / "usage" / CLIENT / PROJECT / PERIOD / "usage.xlsx")

    # ---------------- billing list ----------------
    actual = [187, 50, 281, 350, 280, 220, 187, 187, 187, 250, 220, 0]
    billing_list = pd.DataFrame({
        "服务号码": [f"P{i:03d}" for i in range(1, 13)],
        "账期": [PERIOD] * 12,
        "用户状态": ["在网"] * 11 + ["停机"],
        "计费应收": actual,
        "账务优惠": [0] * 12,
        "实际应收": actual,
        "账户标识": [f"ACCT_{i // 4}" for i in range(12)],
    })
    write(billing_list, RAW / "billing" / CLIENT / PROJECT / PERIOD / "billing_list.xlsx")

    # ---------------- billing detail ----------------
    rows = []
    # P01: 月固定费 187
    rows.append({"服务号码": "P001", "一级科目": "月固定费", "实际应收": 187})
    # P02: 月固定费 50
    rows.append({"服务号码": "P002", "一级科目": "月固定费", "实际应收": 50})
    # P03: 月固定费 187 + 上网费 94
    rows.append({"服务号码": "P003", "一级科目": "月固定费", "实际应收": 187})
    rows.append({"服务号码": "P003", "一级科目": "上网费",   "实际应收": 94})
    # P04: 月固定费 187 + 上网费 163
    rows.append({"服务号码": "P004", "一级科目": "月固定费", "实际应收": 187})
    rows.append({"服务号码": "P004", "一级科目": "上网费",   "实际应收": 163})
    # P05: 月固定费 187 + 国际漫游费 93
    rows.append({"服务号码": "P005", "一级科目": "月固定费", "实际应收": 187})
    rows.append({"服务号码": "P005", "一级科目": "国际漫游费", "实际应收": 93})
    # P06: 月固定费 187 + 增值业务费 33
    rows.append({"服务号码": "P006", "一级科目": "月固定费", "实际应收": 187})
    rows.append({"服务号码": "P006", "一级科目": "增值业务费", "实际应收": 33, "二级科目": "彩铃"})
    # P07-P09: 仅月固定费
    for sn, amt in [("P007", 187), ("P008", 187), ("P009", 187)]:
        rows.append({"服务号码": sn, "一级科目": "月固定费", "实际应收": amt})
    # P10: 月固定费 187 + 上网费 63
    rows.append({"服务号码": "P010", "一级科目": "月固定费", "实际应收": 187})
    rows.append({"服务号码": "P010", "一级科目": "上网费",   "实际应收": 63})
    # P11: 月固定费 187 + 副卡费 33
    rows.append({"服务号码": "P011", "一级科目": "月固定费", "实际应收": 187})
    rows.append({"服务号码": "P011", "一级科目": "副卡费",   "实际应收": 33})
    # P12: 全部为 0
    rows.append({"服务号码": "P012", "一级科目": "月固定费", "实际应收": 0})
    detail = pd.DataFrame(rows)
    detail["账期"] = PERIOD
    write(detail, RAW / "billing" / CLIENT / PROJECT / PERIOD / "billing_detail.xlsx")

    # ---------------- asset ----------------
    asset = pd.DataFrame({
        "服务号码": [f"P{i:03d}" for i in range(1, 13) if i != 9],  # P09 故意没有资产
        "联系人":   ["张三", "李四", "王五", "赵六", "钱七", "孙八", "周九", "吴十",
                     "郑十一", "孔十二", "韩十三"],
        "邮箱":     [f"u{i}@demo.com" for i in [1,2,3,4,5,6,7,8,10,11,12]],
        "员工编号": [f"E{i:03d}" for i in [1,2,3,4,5,6,7,8,10,11,12]],
        "组织名称": ["MT"] * 11,
        "资产状态": ["在用"] * 10 + ["停用"],
        "型号":     ["iPhone 16"] * 11,
        "标准套餐金额": [187.0] * 11,
    })
    write(asset, RAW / "asset" / CLIENT / PROJECT / "asset.xlsx")

    # ---------------- employee ----------------
    # P08 故意不在人员表 -> 人员缺失
    emp = pd.DataFrame({
        "员工ID": [f"E{i:03d}" for i in [1,2,3,4,5,6,7,10,11,12]],
        "员工姓名": ["张三", "李四", "王五", "赵六", "钱七", "孙八", "周九",
                     "孔十二", "韩十三", "吴十四"],
        "邮箱": [f"u{i}@demo.com" for i in [1,2,3,4,5,6,7,10,11,12]],
        "员工状态": ["在职"] * 6 + ["离职"] + ["在职"] * 3,   # E007 离职
        "BU": ["MT"] * 10,
        "Department": ["销售一部"] * 5 + ["销售二部"] * 5,
        "CostCenter": ["CC001"] * 5 + ["CC002"] * 5,
        "LineManager": ["mgrA"] * 5 + ["mgrB"] * 5,
        "ManagerEmail": ["mgrA@demo.com"] * 5 + ["mgrB@demo.com"] * 5,
        "离职日期": [None] * 6 + [date(2026, 3, 15)] + [None] * 3,
    })
    write(emp, RAW / "employee" / CLIENT / PROJECT / "employee.xlsx")

    # ---------------- event ----------------
    events = pd.DataFrame({
        "原始号码": ["P010", "P011", "P012"],
        "变更号码": ["P099", "/", "/"],
        "副卡号码": ["", "P011A", ""],
        "事件类型": ["套餐变更", "套餐变更", "离职归还"],
        "事件动作": ["改号", "副卡申请", "设备归还"],
        "时间":     [date(2026, 4, 5), date(2026, 4, 10), date(2026, 4, 20)],
        "目前状态": ["Completed", "Completed", "On-Boarding"],
        "使用人WWID": ["E010", "E011", "E012"],
        "当前使用人": ["孔十二", "韩十三", "吴十四"],
        "部门": ["销售二部"] * 3,
    })
    write(events, RAW / "event" / CLIENT / PROJECT / "events.xlsx")

    print()
    print("Mock 数据生成完毕。运行:")
    print(f"  tem run --客户 {CLIENT} --项目 {PROJECT} --账期 {PERIOD}")
    print(f"  streamlit run app/streamlit_app.py")


if __name__ == "__main__":
    sys.exit(main())
