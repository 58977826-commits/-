"""Import Gate：写库前校验主键、必填项、账期一致性与列映射。"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any

import pandas as pd

from ..config import get_field_maps
from .common import IngestContext


RAW_TO_INGEST_TABLE: dict[str, str] = {
    "raw_usage": "usage",
    "raw_billing_list": "billing_list",
    "raw_billing_detail": "billing_detail",
    "raw_asset": "asset",
    "raw_employee": "employee",
    "raw_event": "event",
}

PLATFORM_COLUMNS = {
    "客户ID", "客户名称", "项目ID", "项目名称", "数据月份",
    "数据来源", "导入批次号", "数据更新时间",
}


@dataclass
class GateIssue:
    level: str  # error | warning | info
    code: str
    message: str


@dataclass
class GateReport:
    target_table: str
    ingest_table: str
    passed: bool
    blocked: bool
    row_count: int
    renamed_columns: dict[str, str] = field(default_factory=dict)
    unmapped_source_columns: list[str] = field(default_factory=list)
    missing_required: list[str] = field(default_factory=list)
    missing_required_any_groups: list[list[str]] = field(default_factory=list)
    duplicate_pk_count: int = 0
    duplicate_pk_samples: list[str] = field(default_factory=list)
    period_values: list[str] = field(default_factory=list)
    period_mismatch: bool = False
    issues: list[GateIssue] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["issues"] = [asdict(i) for i in self.issues]
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, default=str)


class IngestGateError(RuntimeError):
    """Import Gate 在 strict 模式下阻断写库。"""

    def __init__(self, report: GateReport):
        self.report = report
        msgs = [i.message for i in report.issues if i.level == "error"]
        super().__init__("; ".join(msgs) or "Import Gate 校验未通过")


def _table_spec(ingest_table: str) -> dict[str, Any]:
    fm = get_field_maps()
    return fm.table_spec(ingest_table)


def validate_before_write(
    df: pd.DataFrame,
    target_table: str,
    ctx: IngestContext,
    *,
    renamed_columns: dict[str, str] | None = None,
    source_columns: list[str] | None = None,
    source_file: str | None = None,
) -> GateReport:
    """对即将写入 DuckDB 的 DataFrame 做 Import Gate 校验。"""
    ingest_table = RAW_TO_INGEST_TABLE.get(target_table, target_table)
    spec = _table_spec(ingest_table)
    fm = get_field_maps()

    report = GateReport(
        target_table=target_table,
        ingest_table=ingest_table,
        passed=True,
        blocked=False,
        row_count=len(df),
        renamed_columns=dict(renamed_columns or {}),
    )

    if df.empty:
        report.issues.append(GateIssue("warning", "EMPTY", "DataFrame 为空，跳过写库"))
        report.passed = True
        return report

    src_cols = source_columns or list(renamed_columns.keys()) if renamed_columns else list(df.columns)
    mapped_targets = set(report.renamed_columns.values())
    report.unmapped_source_columns = [
        c for c in src_cols
        if c not in report.renamed_columns and str(c).strip() not in PLATFORM_COLUMNS
    ]
    if report.unmapped_source_columns:
        preview = ", ".join(report.unmapped_source_columns[:8])
        suffix = "..." if len(report.unmapped_source_columns) > 8 else ""
        report.issues.append(GateIssue(
            "warning", "UNMAPPED_COLUMNS",
            f"以下源列未映射到标准字段（写入时将丢弃）: {preview}{suffix}",
        ))

    # 必填字段
    for col in spec.get("required", []):
        if col not in df.columns or df[col].isna().all():
            report.missing_required.append(col)
            report.issues.append(GateIssue(
                "error", "MISSING_REQUIRED",
                f"缺少必填列或全部为空: {col}",
            ))

    # 至少满足一组「任选其一」字段（required_any 可为扁平列表或列表的列表）
    raw_any = spec.get("required_any", [])
    any_groups: list[list[str]] = []
    if raw_any:
        if isinstance(raw_any[0], list):
            any_groups = [list(g) for g in raw_any]
        else:
            any_groups = [list(raw_any)]

    for group in any_groups:
        if not any(c in df.columns and df[c].notna().any() for c in group):
            report.missing_required_any_groups.append(group)
            report.issues.append(GateIssue(
                "error", "MISSING_REQUIRED_ANY",
                f"以下列至少需要一列有值: {' / '.join(group)}",
            ))

    # 账期一致性
    period_col = spec.get("period_column")
    if period_col and period_col in df.columns and ctx.账期:
        periods = sorted({str(v).strip() for v in df[period_col].dropna().unique() if str(v).strip()})
        report.period_values = periods
        bad = [p for p in periods if p != str(ctx.账期)]
        if bad:
            report.period_mismatch = True
            report.issues.append(GateIssue(
                "error", "PERIOD_MISMATCH",
                f"文件账期 {bad} 与导入上下文账期 {ctx.账期} 不一致",
            ))

    # 主键重复（平台字段应已注入）
    pk = spec.get("primary_key", [])
    pk_present = [c for c in pk if c in df.columns]
    if len(pk_present) == len(pk) and pk:
        dup = df.duplicated(subset=pk, keep=False)
        n_dup_groups = df.loc[dup].groupby(pk_present, dropna=False).ngroups if dup.any() else 0
        report.duplicate_pk_count = int(dup.sum())
        if report.duplicate_pk_count > 0:
            sample = df.loc[dup, pk_present].head(3).astype(str).agg("|".join, axis=1).tolist()
            report.duplicate_pk_samples = sample
            report.issues.append(GateIssue(
                "warning", "DUPLICATE_PK",
                f"主键 {pk} 存在 {report.duplicate_pk_count} 行重复（写库前建议在 ingest 层聚合）",
            ))

    # 应用项目差异规则中的提示（info）
    try:
        from ..meta.project_diff import list_project_diffs

        diffs = list_project_diffs(ctx.客户ID, ctx.项目ID)
        for _, row in diffs.iterrows():
            if row.get("规则类别") == "字段映射":
                report.issues.append(GateIssue(
                    "info", f"DIFF_{row.get('规则ID')}",
                    f"{row.get('标准规则')} → {row.get('本项目规则')}",
                ))
    except Exception:  # noqa: BLE001
        pass

    has_error = any(i.level == "error" for i in report.issues)
    report.passed = not has_error
    mode = fm.gate_mode()
    report.blocked = has_error and mode == "strict"

    if source_file:
        report.issues.insert(0, GateIssue("info", "SOURCE", f"源文件: {source_file}"))

    return report


def save_import_report(report: GateReport, ctx: IngestContext, *, source_file: str | None = None) -> None:
    """持久化 Gate 报告到 meta_import_report。"""
    from ..db import connect

    status = "blocked" if report.blocked else ("warned" if any(i.level == "warning" for i in report.issues) else "passed")
    with connect() as con:
        con.execute(
            """
            INSERT INTO meta_import_report (
                导入批次号, 客户ID, 项目ID, 账期, 目标表, 源文件,
                行数, 状态, 报告JSON, 数据更新时间
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ctx.导入批次号, ctx.客户ID, ctx.项目ID, ctx.账期,
                report.target_table, source_file, report.row_count, status,
                report.to_json(), ctx.数据更新时间,
            ],
        )
