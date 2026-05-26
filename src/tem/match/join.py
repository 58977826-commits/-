"""跨表匹配（§14.2）。

匹配顺序与主键：
  1. 账单清单 ⇔ 用量          客户ID + 项目ID + 账期 + 服务号码
  2. 账单清单 ⇔ 资产          客户ID + 项目ID + 服务号码
  3. 资产    ⇔ 人员           客户ID + 员工ID  ->  客户ID + 邮箱（A04 / E02-E04）
  4. 当月事件解释（结果表层面） 客户ID + 项目ID + 账期 + 服务号码 / 员工ID
  5. 事件费用解释               原始号码 / 变更号码 / 副卡号码 + 事件动作

本模块产出"号码 × 月度基底表"，规则引擎在此基础上打标签。
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from ..db import connect


@dataclass
class JoinResult:
    base: pd.DataFrame                    # 主底表：账单清单 + 用量 + 资产 + 人员
    billing_detail: pd.DataFrame          # 账单明细（按 客户ID+项目ID+账期+服务号码 分组的科目集合）
    events: pd.DataFrame                  # 当月事件（按 客户ID+项目ID+账期+各号码字段 关联）


def _read_table(con, table: str, 客户ID: str, 项目ID: str | None,
                账期: str | None) -> pd.DataFrame:
    cols = [r[1] for r in con.execute(f"PRAGMA table_info('{table}')").fetchall()]
    where = ["客户ID = ?"]
    params: list = [客户ID]
    if 项目ID and "项目ID" in cols:
        where.append("(项目ID = ? OR 项目ID IS NULL)")
        params.append(项目ID)
    if 账期 and "账期" in cols:
        where.append("账期 = ?")
        params.append(账期)
    sql = f"SELECT * FROM {table} WHERE " + " AND ".join(where)
    return con.execute(sql, params).fetchdf()


def build_monthly_base(客户ID: str, 项目ID: str, 账期: str) -> JoinResult:
    """组装月度基底宽表（不打异常标签，只做字段匹配）。"""
    with connect(read_only=True) as con:
        billing_list = _read_table(con, "raw_billing_list", 客户ID, 项目ID, 账期)
        usage = _read_table(con, "raw_usage", 客户ID, 项目ID, 账期)
        billing_detail = _read_table(con, "raw_billing_detail", 客户ID, 项目ID, 账期)
        asset = _read_table(con, "raw_asset", 客户ID, 项目ID, None)
        # 人员表通常按客户级别覆盖，项目ID 可能为空，因此 SELECT 项目ID 不做强约束
        employee = _read_table(con, "raw_employee", 客户ID, None, None)
        events = _read_table(con, "raw_event", 客户ID, 项目ID, None)

    # 1) 账单清单 ⇔ 用量（左连：以账单为主线，用量补充）
    base = _step1_billing_join_usage(billing_list, usage)

    # 没有账单时退化为以用量为主
    if base.empty and not usage.empty:
        base = usage.assign(实际应收=0.0, 计费应收=0.0, 账务优惠=0.0)
        base["客户ID"] = 客户ID
        base["项目ID"] = 项目ID
        base["账期"] = 账期

    # 2) 基底 ⇔ 资产
    base = _step2_join_asset(base, asset)

    # 3) 资产 ⇔ 人员（已经合并到 base 上）
    base = _step3_join_employee(base, employee)

    # 关键字段补齐（即使资产/人员未匹配也保留主键四元组）
    for col in ["客户ID", "项目ID", "账期", "服务号码"]:
        if col not in base.columns:
            base[col] = None

    base["客户ID"] = base["客户ID"].fillna(客户ID)
    base["项目ID"] = base["项目ID"].fillna(项目ID)
    base["账期"] = base["账期"].fillna(账期)

    # 4) & 5) 事件层在 build/fact_tem_monthly.py 中按账期 join，这里只返回原始事件 DataFrame
    return JoinResult(base=base, billing_detail=billing_detail, events=events)


# ---------------------------------------------------------------------------
# step 1: 账单清单 ⇔ 用量
# ---------------------------------------------------------------------------
def _step1_billing_join_usage(billing_list: pd.DataFrame, usage: pd.DataFrame) -> pd.DataFrame:
    if billing_list.empty and usage.empty:
        return pd.DataFrame()

    keys = ["客户ID", "项目ID", "账期", "服务号码"]
    bl = billing_list.copy()
    us = usage.copy()

    # 账单清单同号码多账户的情况：聚合实际应收
    if not bl.empty:
        agg = {
            "用户状态": "first",
            "计费应收": "sum",
            "账务优惠": "sum",
            "实际应收": "sum",
            "账户标识": lambda x: ",".join({str(v) for v in x if pd.notna(v)}),
            "账户名称": lambda x: ",".join({str(v) for v in x if pd.notna(v)}),
            "用户标识": lambda x: ",".join({str(v) for v in x if pd.notna(v)}),
            "客户名称": "first",
            "项目名称": "first",
            "数据月份": "first",
            "数据来源": "first",
            "导入批次号": "first",
            "数据更新时间": "first",
        }
        agg = {k: v for k, v in agg.items() if k in bl.columns}
        bl = bl.groupby(keys, dropna=False, as_index=False).agg(agg)

    if bl.empty:
        return us
    if us.empty:
        return bl

    # 用量列尽量保留，避免与账单冲突时使用 _usage 后缀
    return bl.merge(us, on=keys, how="outer", suffixes=("", "_usage"))


# ---------------------------------------------------------------------------
# step 2: 基底 ⇔ 资产
# ---------------------------------------------------------------------------
def _step2_join_asset(base: pd.DataFrame, asset: pd.DataFrame) -> pd.DataFrame:
    if asset.empty:
        # 标签：是否资产缺失
        base["是否资产缺失"] = True
        return base

    keys = ["客户ID", "项目ID", "服务号码"]
    asset_slim = asset.copy()
    # 资产表可能存在多条（历史 / 库存 / 在用），按 服务号码 取在用优先
    if "资产状态" in asset_slim.columns:
        priority = {"在用": 0, "正常": 0, "投产": 0, "Active": 0, "in_use": 0,
                    "库存": 5, "Stock": 5, "停用": 9, "停机": 9, "Inactive": 9}
        asset_slim["__pri"] = asset_slim["资产状态"].map(lambda x: priority.get(str(x), 3))
        asset_slim = asset_slim.sort_values("__pri").drop_duplicates(subset=keys, keep="first")
        asset_slim = asset_slim.drop(columns="__pri")

    keep_cols = keys + [
        "联系人", "邮箱", "员工编号", "内部用户编号", "组织名称",
        "资产状态", "品牌", "型号", "IMEI", "序列号",
        "采购日期", "投产日期", "保修到期日", "标准套餐金额",
    ]
    keep_cols = [c for c in keep_cols if c in asset_slim.columns]
    asset_slim = asset_slim[keep_cols]

    merged = base.merge(asset_slim, on=keys, how="left", suffixes=("", "_asset"))
    merged["是否资产缺失"] = merged.get("资产状态").isna() if "资产状态" in merged.columns else True
    return merged


# ---------------------------------------------------------------------------
# step 3: 基底 ⇔ 人员（员工ID > 邮箱 > 姓名）
# ---------------------------------------------------------------------------
def _step3_join_employee(base: pd.DataFrame, employee: pd.DataFrame) -> pd.DataFrame:
    if employee.empty:
        base["是否人员缺失"] = True
        return base

    emp_keep = [
        "客户ID", "员工ID", "员工姓名", "邮箱", "员工状态",
        "法人主体", "BU", "Department", "CostCenter",
        "LineManager", "ManagerEmail", "Location",
        "生效日期", "离职日期",
    ]
    emp_keep = [c for c in emp_keep if c in employee.columns]
    emp = employee[emp_keep].drop_duplicates(subset=["客户ID", "员工ID"]) if "员工ID" in employee.columns else employee[emp_keep]

    # 候选连接键：A04 优先级 -> 员工ID > 邮箱 > 姓名
    base["__match_key"] = "未匹配"

    # 资产表里的"员工编号"也算员工ID（A02/A04 等价）
    if "员工编号" in base.columns and ("员工ID" not in base.columns or base["员工ID"].isna().all()):
        base["员工ID"] = base["员工编号"]

    # 第一轮：按员工ID
    if "员工ID" in base.columns and "员工ID" in emp.columns:
        emp_by_id = emp.dropna(subset=["员工ID"]).drop_duplicates(subset=["客户ID", "员工ID"])
        merged = base.merge(
            emp_by_id,
            on=["客户ID", "员工ID"],
            how="left",
            suffixes=("", "_emp"),
        )
        # 标记本轮命中的行
        hit_id = merged.get("员工状态").notna() if "员工状态" in merged.columns else pd.Series([False] * len(merged))
        merged.loc[hit_id, "__match_key"] = "员工ID"
        base = merged

    # 第二轮：按邮箱（仅对未命中的行）
    unmatched = base["__match_key"] == "未匹配"
    if unmatched.any() and "邮箱" in base.columns and "邮箱" in emp.columns:
        emp_by_mail = emp.dropna(subset=["邮箱"]).drop_duplicates(subset=["客户ID", "邮箱"])
        # 选出只对未匹配行做合并
        sub = base.loc[unmatched, ["客户ID", "邮箱"]].drop_duplicates()
        joined = sub.merge(emp_by_mail, on=["客户ID", "邮箱"], how="left")
        # 把找到的字段反向覆盖到 base 上
        col_to_fill = [c for c in joined.columns if c not in {"客户ID", "邮箱"}]
        for col in col_to_fill:
            if col not in base.columns:
                base[col] = None
            mapper = joined.set_index(["客户ID", "邮箱"])[col]
            for idx in base.index[unmatched]:
                key = (base.at[idx, "客户ID"], base.at[idx, "邮箱"])
                if key in mapper.index and pd.notna(mapper.loc[key]) and pd.isna(base.at[idx, col]):
                    base.at[idx, col] = mapper.loc[key] if not isinstance(mapper.loc[key], pd.Series) else mapper.loc[key].iloc[0]
                    base.at[idx, "__match_key"] = "邮箱"

    # 是否人员缺失
    base["是否人员缺失"] = base["__match_key"] == "未匹配"
    base = base.drop(columns="__match_key", errors="ignore")
    return base
