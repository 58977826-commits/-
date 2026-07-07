"""配置加载层。

读取 ``config/settings.yaml`` 与 ``config/rules.yaml``。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO_ROOT / "config"


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"配置文件不存在: {path}")
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_yaml(path: Path) -> dict[str, Any]:
    """加载 YAML 配置文件（供 meta 等模块使用）。"""
    return _load_yaml(path)


@dataclass
class ClientProject:
    客户ID: str
    客户名称: str
    项目ID: str
    项目名称: str


@dataclass
class Settings:
    """settings.yaml 的强类型视图。"""

    db_path: Path
    raw_root: Path
    output_root: Path
    samples_root: Path
    default_客户ID: str
    default_客户名称: str
    default_项目ID: str
    default_项目名称: str
    default_数据来源: str
    clients: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def load(cls, path: Path | None = None) -> "Settings":
        path = path or CONFIG_DIR / "settings.yaml"
        cfg = _load_yaml(path)
        db_path = REPO_ROOT / cfg["database"]["path"]
        paths = cfg.get("paths", {})
        default = cfg.get("default", {})
        return cls(
            db_path=db_path,
            raw_root=REPO_ROOT / paths.get("raw_root", "data/raw"),
            output_root=REPO_ROOT / paths.get("output_root", "data/output"),
            samples_root=REPO_ROOT / paths.get("samples_root", "data/samples"),
            default_客户ID=default.get("客户ID", "default"),
            default_客户名称=default.get("客户名称", "默认客户"),
            default_项目ID=default.get("项目ID", "default"),
            default_项目名称=default.get("项目名称", "默认项目"),
            default_数据来源=default.get("数据来源", "联通账单"),
            clients=cfg.get("clients", []),
        )

    def lookup_project(self, 客户ID: str, 项目ID: str) -> ClientProject:
        """按客户ID + 项目ID 查找客户/项目元数据；缺失时回退到默认值。"""
        for c in self.clients:
            if c.get("客户ID") == 客户ID:
                客户名称 = c.get("客户名称", 客户ID)
                for p in c.get("projects", []):
                    if p.get("项目ID") == 项目ID:
                        return ClientProject(
                            客户ID=客户ID,
                            客户名称=客户名称,
                            项目ID=项目ID,
                            项目名称=p.get("项目名称", 项目ID),
                        )
                return ClientProject(
                    客户ID=客户ID,
                    客户名称=客户名称,
                    项目ID=项目ID,
                    项目名称=项目ID,
                )
        return ClientProject(
            客户ID=客户ID or self.default_客户ID,
            客户名称=self.default_客户名称,
            项目ID=项目ID or self.default_项目ID,
            项目名称=self.default_项目名称,
        )


@dataclass
class Rules:
    """rules.yaml 的强类型视图。"""

    raw: dict[str, Any]

    @classmethod
    def load(cls, path: Path | None = None) -> "Rules":
        path = path or CONFIG_DIR / "rules.yaml"
        return cls(raw=_load_yaml(path))

    @property
    def overpackage_warn_ratio(self) -> float:
        return float(self.raw.get("overpackage", {}).get("warn_ratio", 0.05))

    @property
    def overpackage_default_standard_fee(self) -> float | None:
        v = self.raw.get("overpackage", {}).get("default_standard_fee")
        return None if v is None else float(v)

    @property
    def zero_usage_consecutive_months(self) -> int:
        return int(self.raw.get("zero_usage", {}).get("consecutive_months", 3))

    @property
    def low_usage_voice_min(self) -> float:
        return float(self.raw.get("low_usage", {}).get("voice_min_threshold", 5))

    @property
    def low_usage_data_gb(self) -> float:
        return float(self.raw.get("low_usage", {}).get("data_gb_threshold", 0.1))

    @property
    def high_usage_use_percentile(self) -> bool:
        return bool(self.raw.get("high_usage", {}).get("use_percentile", True))

    @property
    def high_usage_data_gb_p95_default(self) -> float | None:
        v = self.raw.get("high_usage", {}).get("data_gb_p95_default")
        return None if v is None else float(v)

    @property
    def high_usage_voice_min_p95_default(self) -> float | None:
        v = self.raw.get("high_usage", {}).get("voice_min_p95_default")
        return None if v is None else float(v)

    @property
    def high_usage_data_gb_hard_cap(self) -> float:
        return float(self.raw.get("high_usage", {}).get("data_gb_hard_cap", 50))

    @property
    def high_usage_voice_min_hard_cap(self) -> float:
        return float(self.raw.get("high_usage", {}).get("voice_min_hard_cap", 1500))

    @property
    def roaming_bill_keywords(self) -> list[str]:
        return list(self.raw.get("roaming", {}).get("bill_keywords", []))

    @property
    def value_added_bill_keywords(self) -> list[str]:
        return list(self.raw.get("value_added_service", {}).get("bill_keywords", []))

    @property
    def value_added_whitelist(self) -> list[str]:
        return list(self.raw.get("value_added_service", {}).get("whitelist_subjects", []))

    @property
    def post_termination_tolerance_days(self) -> int:
        return int(self.raw.get("post_termination", {}).get("tolerance_days", 0))

    @property
    def event_open_states(self) -> list[str]:
        return list(self.raw.get("event", {}).get("open_states", ["On-Boarding"]))

    @property
    def event_closed_states(self) -> list[str]:
        return list(self.raw.get("event", {}).get("closed_states", ["Completed"]))

    @property
    def event_cancelled_states(self) -> list[str]:
        return list(self.raw.get("event", {}).get("cancelled_states", ["Canceled"]))

    @property
    def report_top_n(self) -> int:
        return int(self.raw.get("report", {}).get("top_n", 20))


@dataclass
class FieldMaps:
    """field_maps.yaml：Import Gate + 增量字段别名。"""

    raw: dict[str, Any]

    @classmethod
    def load(cls, path: Path | None = None) -> "FieldMaps":
        path = path or CONFIG_DIR / "field_maps.yaml"
        if not path.exists():
            return cls(raw={"import_gate": {"mode": "warn", "tables": {}}, "field_aliases": {}})
        return cls(raw=_load_yaml(path))

    def gate_mode(self) -> str:
        return str(self.raw.get("import_gate", {}).get("mode", "strict"))

    def table_spec(self, ingest_table: str) -> dict[str, Any]:
        return dict(self.raw.get("import_gate", {}).get("tables", {}).get(ingest_table, {}))

    def extra_field_aliases(self, ingest_table: str) -> dict[str, list[str]]:
        return dict(self.raw.get("field_aliases", {}).get(ingest_table, {}) or {})

    def extra_service_number_aliases(self, ingest_table: str) -> list[str]:
        return list(self.raw.get("service_number_aliases", {}).get(ingest_table, []) or [])

    def extra_account_period_aliases(self) -> list[str]:
        return list(self.raw.get("account_period_aliases", []) or [])


_settings_cache: Settings | None = None
_rules_cache: Rules | None = None
_field_maps_cache: FieldMaps | None = None


def get_settings() -> Settings:
    global _settings_cache
    if _settings_cache is None:
        _settings_cache = Settings.load()
    return _settings_cache


def get_rules() -> Rules:
    global _rules_cache
    if _rules_cache is None:
        _rules_cache = Rules.load()
    return _rules_cache


def get_field_maps() -> FieldMaps:
    global _field_maps_cache
    if _field_maps_cache is None:
        _field_maps_cache = FieldMaps.load()
    return _field_maps_cache


def reset_cache() -> None:
    """单元测试 / 切换配置时使用。"""
    global _settings_cache, _rules_cache, _field_maps_cache
    _settings_cache = None
    _rules_cache = None
    _field_maps_cache = None


def reset_field_maps_cache() -> None:
    """仅刷新 field_maps.yaml 缓存（不影响 Settings / DB 路径）。"""
    global _field_maps_cache
    _field_maps_cache = None
