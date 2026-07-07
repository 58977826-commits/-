"""ingest 层 - 把五类原始 Excel/CSV 加载到 DuckDB raw_* 表。

文件投递目录约定：
    data/raw/{type}/{客户ID}/{项目ID}/{账期}/*.xlsx|*.csv

其中 type ∈ {usage, billing, asset, employee, event}。
account 维度为可选（asset / employee 表通常按当期/全量给）。
"""
from .common import IngestContext, build_batch_id, scan_files, write_dataframe
from .gate import GateReport, IngestGateError, validate_before_write
from .usage import ingest_usage
from .billing import ingest_billing
from .asset import ingest_asset
from .employee import ingest_employee
from .event import ingest_event
from .auto import (
    auto_ingest_files,
    detect_excel_file,
    detect_table_type,
    detect_table_type_by_filename,
)
from .preview import prevalidate_files

__all__ = [
    "IngestContext",
    "build_batch_id",
    "scan_files",
    "write_dataframe",
    "ingest_usage",
    "ingest_billing",
    "ingest_asset",
    "ingest_employee",
    "ingest_event",
    "auto_ingest_files",
    "detect_excel_file",
    "detect_table_type",
    "detect_table_type_by_filename",
    "GateReport",
    "IngestGateError",
    "validate_before_write",
    "prevalidate_files",
]
