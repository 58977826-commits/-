"""验证 mock 数据跑出的 fact_tem_monthly 是否覆盖了所有预期场景。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tem.db import connect


def main() -> None:
    with connect(read_only=True) as con:
        df = con.execute("""
            SELECT 服务号码, 实际应收, 标准套餐金额, 超套金额,
                   是否超套, 是否零用量, 是否零用量但计费, 是否高流量, 是否高通话, 是否漫游,
                   是否增值业务异常, 是否离职后计费, 是否资产缺失, 是否人员缺失,
                   是否存在当月事件, 当月事件类型, 是否事件未闭环,
                   是否改号, 新服务号码, 是否副卡申请, 副卡号码,
                   异常类型, 异常金额, 建议动作, Department, CostCenter
            FROM fact_tem_monthly
            WHERE 客户ID = 'demo' AND 项目ID = 'mock' AND 账期 = '202604'
            ORDER BY 服务号码
        """).fetchdf()

    print(df.to_string(max_colwidth=40))

    print()
    print("=" * 80)
    print("分项核对：")
    print("=" * 80)

    checks = [
        ("P001 正常 - 无异常", df.iloc[0], lambda r: not r["是否超套"] and not r["是否零用量"]),
        ("P002 零用量但计费", df.iloc[1], lambda r: r["是否零用量但计费"]),
        ("P003 超套预警", df.iloc[2], lambda r: r["是否超套"]),
        ("P004 高流量", df.iloc[3], lambda r: r["是否高流量"]),
        ("P005 漫游", df.iloc[4], lambda r: r["是否漫游"]),
        ("P006 增值业务异常", df.iloc[5], lambda r: r["是否增值业务异常"]),
        ("P007 离职后计费", df.iloc[6], lambda r: r["是否离职后计费"]),
        ("P008 人员缺失", df.iloc[7], lambda r: r["是否人员缺失"]),
        ("P009 资产缺失", df.iloc[8], lambda r: r["是否资产缺失"]),
        ("P010 改号事件", df.iloc[9], lambda r: r["是否改号"]),
        ("P011 副卡事件", df.iloc[10], lambda r: r["是否副卡申请"]),
        ("P012 离职归还 On-Boarding 未闭环", df.iloc[11], lambda r: r["是否事件未闭环"]),
    ]

    ok = True
    for name, row, check in checks:
        passed = check(row)
        flag = "OK " if passed else "XX "
        if not passed:
            ok = False
        print(f"  {flag} {name}  -> 异常类型: {row['异常类型'] or '(无)'}")

    print()
    print(f"结果: {'ALL PASS' if ok else 'SOME FAILED'}")


if __name__ == "__main__":
    main()
