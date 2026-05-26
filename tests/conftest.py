"""pytest 共享 fixture：临时数据库、配置缓存重置。

注意：所有调用方都通过 `tem.config.get_settings()` 拿配置（内部缓存），
所以只需修改 `cfg_module._settings_cache` 即可全局生效。
"""
from __future__ import annotations

from pathlib import Path

import pytest

from tem import config as cfg_module


@pytest.fixture(autouse=True)
def _reset_config_cache():
    cfg_module.reset_cache()
    yield
    cfg_module.reset_cache()


@pytest.fixture
def tmp_db(tmp_path: Path):
    """提供一个独立 DuckDB 库 + 隔离的 raw/output 根目录。"""
    from tem import db as db_module

    s = cfg_module.Settings.load()
    s.db_path = tmp_path / "tem.duckdb"
    s.raw_root = tmp_path / "raw"
    s.output_root = tmp_path / "output"
    s.samples_root = tmp_path / "samples"
    s.raw_root.mkdir(parents=True, exist_ok=True)
    s.output_root.mkdir(parents=True, exist_ok=True)

    cfg_module._settings_cache = s
    db_module.init_db(verbose=False)

    yield s.db_path

    cfg_module._settings_cache = None
    if s.db_path.exists():
        try:
            s.db_path.unlink()
        except OSError:
            pass
