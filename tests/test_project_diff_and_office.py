"""项目差异规则与 Office 落地包导出测试。"""
from __future__ import annotations

from pathlib import Path

import pytest

from tem.config import CONFIG_DIR
from tem.emos import ProjectProfile, generate_landing_pack, match_profile
from tem.meta.project_diff import (
    delete_diff_rule,
    load_project_diff_yaml,
    sync_project_diff_from_config,
    upsert_diff_rule,
)


@pytest.fixture
def diff_yaml_tmp(tmp_path, monkeypatch):
    """隔离 project_diff.yaml 到临时目录。"""
    cfg_dir = tmp_path / "config"
    cfg_dir.mkdir()
    target = cfg_dir / "project_diff.yaml"
    target.write_text("defaults: []\nprojects: []\n", encoding="utf-8")
    monkeypatch.setattr("tem.meta.project_diff.CONFIG_DIR", cfg_dir)
    return target


def test_upsert_and_delete_global_diff(tmp_db, diff_yaml_tmp):
    upsert_diff_rule(
        "TEST-001", "字段映射", "标准A", "项目A", "PM",
        客户ID="*", 项目ID="*",
    )
    cfg = load_project_diff_yaml()
    assert any(d["规则ID"] == "TEST-001" for d in cfg["defaults"])
    sync_project_diff_from_config(verbose=False)

    delete_diff_rule("TEST-001", 客户ID="*", 项目ID="*")
    cfg = load_project_diff_yaml()
    assert not any(d.get("规则ID") == "TEST-001" for d in cfg.get("defaults", []))


def test_upsert_project_scoped_diff(tmp_db, diff_yaml_tmp):
    upsert_diff_rule(
        "BILL-X-001", "账单结构", "标准双sheet", "客户特殊sheet", "运营",
        客户ID="demo", 项目ID="p1",
    )
    cfg = load_project_diff_yaml()
    proj = next(p for p in cfg["projects"] if p["客户ID"] == "demo")
    assert any(d["规则ID"] == "BILL-X-001" for d in proj["diffs"])


def test_landing_pack_office_files(tmp_db):
    assert (CONFIG_DIR / "emos" / "components.yaml").exists()
    profile = ProjectProfile(
        客户名称="Office测试",
        项目类型=["工作手机"],
        涉及号卡=True,
        涉及账务=True,
    )
    result = match_profile(profile)
    pack = generate_landing_pack(profile, result)
    pack_dir = Path(pack["pack_dir"])
    xlsx = pack_dir / f"{profile.客户名称}_落地包.xlsx"
    assert xlsx.exists()
    assert pack.get("office", {}).get("xlsx")
    docx_path = pack.get("office", {}).get("docx")
    if docx_path:
        assert Path(docx_path).exists()
