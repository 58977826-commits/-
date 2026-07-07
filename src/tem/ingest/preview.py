"""Import Gate 预检：解析 + 标准化，不写库。"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from .asset import _normalize_asset_df
from .billing import (
    _classify_file_name,
    _classify_sheet_name,
    _normalize_billing_df,
)
from .common import IngestContext, read_any
from .employee import _normalize_employee_df
from .event import _is_skip_sheet, _is_total_sheet, _normalize_event_df
from .gate import GateReport, validate_before_write
from .usage import _normalize_usage_df
from .auto import detect_excel_file
from .gate import RAW_TO_INGEST_TABLE, GateIssue


def _empty_gate_report(raw_table: str, message: str, source_file: str | None = None) -> GateReport:

    report = GateReport(
        target_table=raw_table,
        ingest_table=RAW_TO_INGEST_TABLE.get(raw_table, raw_table),
        passed=True,
        blocked=False,
        row_count=0,
    )
    report.issues.append(GateIssue("warning", "EMPTY", message))
    if source_file:
        report.issues.insert(0, GateIssue("info", "SOURCE", f"源文件: {source_file}"))
    return report


def _validate_usage_file(p: Path, ctx: IngestContext) -> list[GateReport]:
    reports: list[GateReport] = []
    frames: list[pd.DataFrame] = []
    alias_map: dict[str, str] = {}
    source_columns: list[str] = []

    df = read_any(p)
    sheets = df.values() if isinstance(df, dict) else [df]
    for sheet_df in sheets:
        norm, rename, src_cols = _normalize_usage_df(sheet_df, ctx)
        if not norm.empty:
            frames.append(norm)
        alias_map.update(rename)
        source_columns = src_cols

    merged = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if merged.empty:
        reports.append(_empty_gate_report("raw_usage", "无有效用量行", p.name))
    else:
        reports.append(
            validate_before_write(
                merged, "raw_usage", ctx,
                renamed_columns=alias_map,
                source_columns=source_columns,
                source_file=p.name,
            )
        )
    return reports


def _validate_billing_file(p: Path, ctx: IngestContext) -> list[GateReport]:
    reports: list[GateReport] = []
    list_frames: list[pd.DataFrame] = []
    detail_frames: list[pd.DataFrame] = []
    list_meta: dict[str, Any] = {"alias_map": {}, "source_columns": []}
    detail_meta: dict[str, Any] = {"alias_map": {}, "source_columns": []}

    suffix = p.suffix.lower()
    if suffix == ".csv":
        kind = _classify_file_name(p) or "billing_list"
        df = read_any(p)
        norm, rename, src_cols = _normalize_billing_df(df, ctx, kind)
        meta = list_meta if kind == "billing_list" else detail_meta
        meta["alias_map"] = rename
        meta["source_columns"] = src_cols
        (list_frames if kind == "billing_list" else detail_frames).append(norm)
    else:
        xl = pd.ExcelFile(p)
        file_kind = _classify_file_name(p)
        for sheet in xl.sheet_names:
            kind = _classify_sheet_name(sheet) or file_kind
            if kind not in {"billing_list", "billing_detail"}:
                kind = "billing_list"
            sheet_df = pd.read_excel(p, sheet_name=sheet, dtype=object)
            norm, rename, src_cols = _normalize_billing_df(sheet_df, ctx, kind)
            if norm.empty:
                continue
            meta = list_meta if kind == "billing_list" else detail_meta
            meta["alias_map"] = {**meta.get("alias_map", {}), **rename}
            meta["source_columns"] = src_cols
            (list_frames if kind == "billing_list" else detail_frames).append(norm)

    if list_frames:
        merged = pd.concat(list_frames, ignore_index=True)
        if merged.empty:
            reports.append(_empty_gate_report("raw_billing_list", "清单 sheet 无有效行", p.name))
        else:
            reports.append(
                validate_before_write(
                    merged, "raw_billing_list", ctx,
                    renamed_columns=list_meta.get("alias_map") or None,
                    source_columns=list_meta.get("source_columns") or None,
                    source_file=p.name,
                )
            )
    if detail_frames:
        merged = pd.concat(detail_frames, ignore_index=True)
        if merged.empty:
            reports.append(_empty_gate_report("raw_billing_detail", "明细 sheet 无有效行", p.name))
        else:
            reports.append(
                validate_before_write(
                    merged, "raw_billing_detail", ctx,
                    renamed_columns=detail_meta.get("alias_map") or None,
                    source_columns=detail_meta.get("source_columns") or None,
                    source_file=p.name,
                )
            )
    if not list_frames and not detail_frames:
        reports.append(_empty_gate_report("raw_billing_list", "未读到任何账单 sheet", p.name))
    return reports


def _validate_asset_file(p: Path, ctx: IngestContext) -> list[GateReport]:
    frames: list[pd.DataFrame] = []
    df = read_any(p)
    sheets = df.values() if isinstance(df, dict) else [df]
    for sheet_df in sheets:
        norm = _normalize_asset_df(sheet_df, ctx)
        if not norm.empty:
            frames.append(norm)
    merged = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if merged.empty:
        return [_empty_gate_report("raw_asset", "无有效资产行", p.name)]
    return [validate_before_write(merged, "raw_asset", ctx, source_file=p.name)]


def _validate_employee_file(p: Path, ctx: IngestContext) -> list[GateReport]:
    frames: list[pd.DataFrame] = []
    df = read_any(p)
    sheets = df.values() if isinstance(df, dict) else [df]
    for sheet_df in sheets:
        norm = _normalize_employee_df(sheet_df, ctx)
        if not norm.empty:
            frames.append(norm)
    merged = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if merged.empty:
        return [_empty_gate_report("raw_employee", "无有效人员行", p.name)]
    return [validate_before_write(merged, "raw_employee", ctx, source_file=p.name)]


def _validate_event_file(p: Path, ctx: IngestContext) -> list[GateReport]:
    frames: list[pd.DataFrame] = []
    suffix = p.suffix.lower()
    if suffix == ".csv":
        frames.append(_normalize_event_df(read_any(p), ctx))
    else:
        xl = pd.ExcelFile(p)
        total_sheets = [s for s in xl.sheet_names if _is_total_sheet(s)]
        target_sheets = total_sheets if total_sheets else [
            s for s in xl.sheet_names if not _is_skip_sheet(s)
        ]
        for sheet in target_sheets:
            sheet_df = pd.read_excel(p, sheet_name=sheet, dtype=object)
            norm = _normalize_event_df(sheet_df, ctx)
            if not norm.empty:
                frames.append(norm)
    merged = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if merged.empty:
        return [_empty_gate_report("raw_event", "无有效事件行", p.name)]
    return [validate_before_write(merged, "raw_event", ctx, source_file=p.name)]


_VALIDATORS = {
    "usage": _validate_usage_file,
    "billing": _validate_billing_file,
    "asset": _validate_asset_file,
    "employee": _validate_employee_file,
    "event": _validate_event_file,
}


def prevalidate_files(files: list[Path], ctx: IngestContext) -> dict[str, Any]:
    """Import Gate 预检：走与 ingest 相同的标准化流程，但不写库、不复制 raw 目录。

    返回:
        {
            "file_reports": [...],
            "gate_reports": [GateReport.to_dict(), ...],
            "summary": { passed, would_block, error_count, warning_count, row_count },
        }
    """
    ctx.resolve_meta()
    file_reports: list[dict[str, Any]] = []
    gate_reports: list[GateReport] = []

    for p in files:
        info = detect_excel_file(p)
        primary = info["primary_type"]
        report: dict[str, Any] = {
            "file": p.name,
            "primary_type": primary,
            "from_filename": info.get("from_filename", False),
            "sheets": info["sheets"],
        }
        if info.get("error"):
            report["error"] = info["error"]
            file_reports.append(report)
            continue

        if primary not in _VALIDATORS:
            report["error"] = report.get("error") or "无法识别表类型"
            file_reports.append(report)
            continue

        try:
            reports = _VALIDATORS[primary](p, ctx)
            gate_reports.extend(reports)
            report["precheck_passed"] = all(r.passed for r in reports)
            report["precheck_blocked"] = any(r.blocked for r in reports)
        except Exception as e:  # noqa: BLE001
            report["error"] = str(e)
            report["precheck_passed"] = False

        file_reports.append(report)

    error_count = sum(1 for r in gate_reports for i in r.issues if i.level == "error")
    warning_count = sum(1 for r in gate_reports for i in r.issues if i.level == "warning")

    return {
        "file_reports": file_reports,
        "gate_reports": [r.to_dict() for r in gate_reports],
        "summary": {
            "passed": all(r.passed for r in gate_reports) if gate_reports else False,
            "would_block": any(r.blocked for r in gate_reports),
            "error_count": error_count,
            "warning_count": warning_count,
            "row_count": sum(r.row_count for r in gate_reports),
            "file_count": len(files),
        },
    }
