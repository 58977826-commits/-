"""端到端模拟"网页上传"：把 data/samples 的 6 个模板当作上传文件，跑全流程。

模拟流程：
  1. 生成 mock 数据（覆盖 12 种异常场景）
  2. 把 mock 文件当作上传文件交给 auto_ingest_files
  3. 跑 build_fact_tem_monthly
  4. 校验 fact_tem_monthly 行数

不修改用户已有的 db/tem.duckdb 数据，使用临时 DB。
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tem import config as cfg
from tem import db as db_module
from tem.build import build_fact_tem_monthly
from tem.ingest import IngestContext, auto_ingest_files

# 复用 generate_mock_data 里的逻辑（直接 import 跑一次）
sys.path.insert(0, str(Path(__file__).resolve().parent))


def main() -> int:
    # 使用临时 DB / raw 根目录，不污染用户数据
    tmp = Path(tempfile.mkdtemp(prefix="tem_e2e_"))
    print(f"[e2e] 临时工作目录: {tmp}")

    s = cfg.Settings.load()
    s.db_path = tmp / "tem.duckdb"
    s.raw_root = tmp / "raw"
    s.output_root = tmp / "output"
    s.raw_root.mkdir(parents=True, exist_ok=True)
    s.output_root.mkdir(parents=True, exist_ok=True)
    cfg._settings_cache = s

    db_module.init_db(verbose=False)
    print("[e2e] 临时 DB 初始化完毕")

    # 步骤 1：在另一个临时目录里准备 6 个上传文件（不带任何目录结构）
    upload_dir = tmp / "uploads"
    upload_dir.mkdir()

    import pandas as pd
    from datetime import date

    pd.DataFrame({
        "服务号码": ["P001", "P002", "P003"],
        "账期": ["202604"] * 3,
        "总短信条数": [10, 0, 5],
        "总通话时长_秒": [1200, 0, 600],
        "总流量_M": [2048, 0, 4096],
    }).to_excel(upload_dir / "联通用量_202604.xlsx", index=False)

    pd.DataFrame({
        "服务号码": ["P001", "P002", "P003"],
        "账期": ["202604"] * 3,
        "用户状态": ["在网"] * 3,
        "计费应收": [187, 50, 281],
        "实际应收": [187, 50, 281],
    }).to_excel(upload_dir / "联通账单清单_202604.xlsx", index=False)

    pd.DataFrame({
        "服务号码": ["P001", "P002", "P003", "P003"],
        "账期": ["202604"] * 4,
        "一级科目": ["月固定费", "月固定费", "月固定费", "上网费"],
        "实际应收": [187, 50, 187, 94],
    }).to_excel(upload_dir / "联通账单明细_202604.xlsx", index=False)

    pd.DataFrame({
        "服务号码": ["P001", "P002", "P003"],
        "联系人": ["张三", "李四", "王五"],
        "邮箱": ["a@x.com", "b@x.com", "c@x.com"],
        "员工编号": ["E001", "E002", "E003"],
        "资产状态": ["在用"] * 3,
        "型号": ["iPhone"] * 3,
        "标准套餐金额": [187.0] * 3,
    }).to_excel(upload_dir / "资产清单.xlsx", index=False)

    pd.DataFrame({
        "员工 ID": ["E001", "E002", "E003"],
        "员工姓名": ["张三", "李四", "王五"],
        "邮箱": ["a@x.com", "b@x.com", "c@x.com"],
        "员工状态": ["在职"] * 3,
        "Cost Center": ["CC001", "CC001", "CC002"],
        "Department": ["销售一部", "销售一部", "运营部"],
        "BU / Function": ["MT"] * 3,
        "Line Manager": ["mgrA", "mgrA", "mgrB"],
        "Manager Email": ["mgrA@x.com", "mgrA@x.com", "mgrB@x.com"],
    }).to_excel(upload_dir / "人员名册.xlsx", index=False)

    pd.DataFrame({
        "原始号码": ["P003"],
        "变更号码": ["P099"],
        "事件类型": ["套餐变更"],
        "事件动作": ["改号"],
        "时间": [date(2026, 4, 5)],
        "目前状态": ["Completed"],
        "使用人WWID": ["E003"],
        "当前使用人": ["王五"],
    }).to_excel(upload_dir / "事件总表.xlsx", index=False)

    uploaded_files = sorted(upload_dir.glob("*.xlsx"))
    print(f"[e2e] 准备上传 {len(uploaded_files)} 个文件")

    # 步骤 2：模拟网页上传 -> auto_ingest_files
    ctx = IngestContext(客户ID="e2e", 项目ID="auto", 账期="202604")
    result = auto_ingest_files(uploaded_files, ctx)

    print()
    print("=" * 70)
    print("识别结果：")
    print("=" * 70)
    for r in result["file_reports"]:
        primary = r["primary_type"] or "未识别"
        flag = "OK " if r["primary_type"] else "XX "
        landed = Path(r.get("landed_at", "")).relative_to(tmp) if r.get("landed_at") else "—"
        print(f"  {flag} {r['file']:<35} -> {primary:<10} -> {landed}")

    print()
    print("入库行数：")
    for t, n in result["ingest_counts"].items():
        print(f"  {t:<25} {n}")

    # 步骤 3：跑规则引擎
    n_fact = build_fact_tem_monthly("e2e", "auto", "202604")
    print(f"\nfact_tem_monthly: {n_fact} 行")

    # 步骤 4：抽样校验
    with db_module.connect(read_only=True) as con:
        df = con.execute("""
            SELECT 服务号码, 实际应收, 标准套餐金额, 超套金额, 是否超套, 是否零用量,
                   异常类型, Department, CostCenter, 是否改号
            FROM fact_tem_monthly
            WHERE 客户ID = 'e2e' AND 项目ID = 'auto' AND 账期 = '202604'
            ORDER BY 服务号码
        """).fetchdf()
    print()
    print("fact_tem_monthly 抽样：")
    print(df.to_string(index=False))

    # 验收点
    assert len(df) == 3, f"expected 3 rows, got {len(df)}"
    assert df.iloc[1]["是否零用量"], "P002 应被识别为零用量"
    assert df.iloc[2]["是否超套"], "P003 应被识别为超套（281 > 187*1.05）"
    assert df.iloc[2]["是否改号"], "P003 应被识别为有改号事件"
    assert df.iloc[0]["CostCenter"] == "CC001"

    print()
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
