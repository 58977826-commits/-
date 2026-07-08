"""EMOS 配置加载。"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from ..config import CONFIG_DIR, load_yaml

EMOS_CONFIG_DIR = CONFIG_DIR / "emos"
REPO_ROOT = CONFIG_DIR.parent
COMPONENTS_MD_DIR = REPO_ROOT / "components_md"
TEMPLATES_DIR = REPO_ROOT / "templates" / "emos"
OUTPUT_EMOS_ROOT = REPO_ROOT / "data" / "output" / "emos"


def _load(name: str, key: str) -> list[dict[str, Any]]:
    path = EMOS_CONFIG_DIR / name
    if not path.exists():
        return []
    data = load_yaml(path)
    return list(data.get(key, []) or [])


def load_project_types() -> list[dict[str, Any]]:
    return _load("project_types.yaml", "project_types")


def load_service_items() -> list[dict[str, Any]]:
    return _load("service_items.yaml", "service_items")


def load_components() -> list[dict[str, Any]]:
    return _load("components.yaml", "components")


def load_match_rules() -> list[dict[str, Any]]:
    return _load("match_rules.yaml", "match_rules")


def load_knowledge_cards() -> list[dict[str, Any]]:
    return _load("knowledge_cards.yaml", "knowledge_cards")


def load_ai_prompts() -> list[dict[str, Any]]:
    return _load("ai_prompts.yaml", "prompts")


def get_component_by_id(component_id: str) -> dict[str, Any] | None:
    for c in load_components():
        if c.get("组件编号") == component_id:
            return c
    return None


def read_component_markdown(component_id: str) -> str | None:
    comp = get_component_by_id(component_id)
    if not comp:
        return None
    rel = comp.get("AI摘要文件")
    if not rel:
        return None
    path = REPO_ROOT / str(rel)
    if path.exists():
        return path.read_text(encoding="utf-8")
    return None
