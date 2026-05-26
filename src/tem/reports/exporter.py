"""导出月度 Excel 报表。

输出文件：data/output/{客户ID}_{项目ID}_{账期}_TEM月报.xlsx
包含以下 sheet：
  - 月度首页（§15.1 核心指标）
  - 费用统计_部门（§15.2）
  - 费用统计_成本中心（§15.6）
  - 用量分析（§15.3）
  - 超套清单（§15.4）
  - 异常清单（§15.5）
  - 事件运营（§15.7）
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

from ..config import get_rules, get_settings
from ..db import connect


def _query(con, sql: str, params: list) -> pd.DataFrame:
    return con.execute(sql, params).fetchdf()


def export_monthly_reports(客户ID: str, 项目ID: str, 账期: str,
                           output_dir: Path | None = None) -> Path:
    settings = get_settings()
    output_dir = output_dir or settings.output_root
    output_dir.mkdir(parents=True, exist_ok=True)
    fname = f"{客户ID}_{项目ID}_{账期}_TEM月报_{datetime.now():%Y%m%d%H%M%S}.xlsx"
    out_path = output_dir / fname

    rules = get_rules()
    top_n = rules.report_top_n
    params = [客户ID, 项目ID, 账期]

    with connect(read_only=True) as con:
        # 月度首页（§15.1）
        summary = _query(con, "SELECT * FROM v_monthly_summary WHERE 客户ID = ? AND 项目ID = ? AND 账期 = ?", params)

        # 费用统计_部门（§15.2 之 BU/Department 维度）
        dept = _query(con, """
            SELECT BU, Department,
                   COUNT(*) AS 号码数,
                   COUNT(DISTINCT 员工ID) AS 员工数,
                   SUM(实际应收) AS 实际应收合计,
                   SUM(超套金额) AS 超套金额合计
            FROM fact_tem_monthly
            WHERE 客户ID = ? AND 项目ID = ? AND 账期 = ?
            GROUP BY BU, Department
            ORDER BY 实际应收合计 DESC NULLS LAST
        """, params)

        # 成本中心分摊（§15.6）
        cc = _query(con, "SELECT * FROM v_costcenter_allocation WHERE 客户ID = ? AND 项目ID = ? AND 账期 = ? ORDER BY 实际应收合计 DESC NULLS LAST", params)

        # 用量分析（§15.3）
        usage = _query(con, """
            SELECT 服务号码, 员工姓名, Department, CostCenter,
                   总流量GB, 总通话分钟, 短信条数,
                   是否零用量, 是否低用量, 是否高流量, 是否高通话
            FROM fact_tem_monthly
            WHERE 客户ID = ? AND 项目ID = ? AND 账期 = ?
            ORDER BY 总流量GB DESC NULLS LAST
        """, params)

        # 超套清单（§15.4）
        overpkg = _query(con, "SELECT * FROM v_overpackage_list WHERE 客户ID = ? AND 项目ID = ? AND 账期 = ? ORDER BY 超套金额 DESC NULLS LAST", params)

        # 异常清单（§15.5）
        anomalies = _query(con, "SELECT * FROM v_anomaly_list WHERE 客户ID = ? AND 项目ID = ? AND 账期 = ? ORDER BY 异常金额 DESC NULLS LAST", params)

        # 事件运营（§15.7）- 按客户/项目/数据月份过滤
        events = _query(con, """
            SELECT 事件类型, 事件动作, 事件状态, COUNT(*) AS 事件数
            FROM raw_event
            WHERE 客户ID = ? AND 项目ID = ? AND (数据月份 = ? OR 事件月份 = ?)
            GROUP BY 事件类型, 事件动作, 事件状态
            ORDER BY 事件数 DESC
        """, [客户ID, 项目ID, 账期, 账期])

        # TOP 流量 / 通话
        top_data = usage.head(top_n).copy()
        top_voice = usage.sort_values("总通话分钟", ascending=False).head(top_n).copy()

    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        if summary.empty:
            pd.DataFrame([{"提示": f"未找到 {客户ID}/{项目ID}/{账期} 的 fact_tem_monthly 记录"}]).to_excel(writer, sheet_name="月度首页", index=False)
        else:
            # 转置成卡片视图
            summary_view = summary.T.reset_index()
            summary_view.columns = ["指标", "值"]
            summary_view.to_excel(writer, sheet_name="月度首页", index=False)

        dept.to_excel(writer, sheet_name="费用统计_部门", index=False)
        cc.to_excel(writer, sheet_name="成本中心分摊", index=False)
        usage.to_excel(writer, sheet_name="用量分析", index=False)
        top_data.to_excel(writer, sheet_name=f"TOP{top_n}_流量", index=False)
        top_voice.to_excel(writer, sheet_name=f"TOP{top_n}_通话", index=False)
        overpkg.to_excel(writer, sheet_name="超套清单", index=False)
        anomalies.to_excel(writer, sheet_name="异常清单", index=False)
        events.to_excel(writer, sheet_name="事件运营", index=False)

    return out_path
