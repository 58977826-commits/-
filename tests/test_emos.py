"""EMOS 模块单元测试。"""
from __future__ import annotations

from pathlib import Path

import pytest

from tem.config import CONFIG_DIR
from tem.emos import (
    ProjectProfile,
    build_ai_brief,
    build_ai_review_report,
    generate_landing_pack,
    load_components,
    match_profile,
    sync_emos_from_config,
)


@pytest.fixture
def emos_config_exists():
    assert (CONFIG_DIR / "emos" / "components.yaml").exists()


def test_components_seed_count(emos_config_exists):
    comps = load_components()
    assert len(comps) >= 50


def test_match_profile_work_phone(emos_config_exists):
    profile = ProjectProfile(
        客户名称="测试客户",
        行业="医药",
        项目类型=["工作手机"],
        用户规模="500-2000",
        参考样板项目="强生MT",
        涉及号卡=True,
        涉及账务=True,
        涉及终端=True,
        涉及事件=True,
    )
    result = match_profile(profile)
    assert len(result.service_items) >= 2
    assert len(result.components) >= 3
    assert len(result.risks) >= 1


def test_sync_and_generate(tmp_db, emos_config_exists):
    counts = sync_emos_from_config(verbose=False)
    assert counts.get("meta_emos_component", 0) >= 50

    profile = ProjectProfile(
        客户名称="礼来测试",
        项目类型=["工作手机"],
        涉及号卡=True,
        涉及账务=True,
    )
    result = match_profile(profile)
    pack = generate_landing_pack(profile, result)
    pack_path = Path(pack["pack_dir"])
    assert pack_path.exists()
    assert (pack_path / "AI_Brief.md").exists()
    assert (pack_path / "recommendation.json").exists()


def test_ai_brief_and_review(emos_config_exists):
    profile = ProjectProfile(客户名称="GE测试", 项目类型=["终端租赁"], 涉及终端=True, 涉及库存=True)
    result = match_profile(profile)
    brief = build_ai_brief(profile, result)
    review = build_ai_review_report(profile, result)
    assert "GE测试" in brief
    assert "审查" in review or "Prompt" in review
