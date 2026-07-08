"""项目画像 → 服务项/组件/风险 推荐。"""
from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

import pandas as pd

from ..db import connect
from ..meta.project_diff import list_project_diffs
from .load_data import load_components, load_match_rules, load_service_items


@dataclass
class ProjectProfile:
    客户名称: str
    行业: str = ""
    项目类型: list[str] = field(default_factory=list)
    用户规模: str = ""
    参考样板项目: str = ""
    涉及终端: bool = False
    涉及号卡: bool = False
    涉及账务: bool = False
    涉及库存: bool = False
    涉及事件: bool = False
    涉及服务台: bool = False
    涉及驻场: bool = False
    特殊说明: str = ""
    画像ID: str = ""

    def __post_init__(self) -> None:
        if not self.画像ID:
            self.画像ID = f"PF-{uuid.uuid4().hex[:10]}"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def flags(self) -> dict[str, bool]:
        return {
            "has_terminal": self.涉及终端,
            "has_sim": self.涉及号卡,
            "has_billing": self.涉及账务,
            "has_inventory": self.涉及库存,
            "has_event": self.涉及事件,
            "has_helpdesk": self.涉及服务台,
            "has_onsite": self.涉及驻场,
        }


@dataclass
class RecommendationItem:
    kind: str  # service | component | risk
    item_id: str
    name: str
    reason: str
    rule_id: str = ""
    source_project: str = ""
    priority: int = 100


@dataclass
class MatchResult:
    profile: ProjectProfile
    service_items: list[RecommendationItem] = field(default_factory=list)
    components: list[RecommendationItem] = field(default_factory=list)
    risks: list[RecommendationItem] = field(default_factory=list)
    pending_diffs: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile": self.profile.to_dict(),
            "service_items": [asdict(x) for x in self.service_items],
            "components": [asdict(x) for x in self.components],
            "risks": [asdict(x) for x in self.risks],
            "pending_diffs": self.pending_diffs,
        }


def _eval_condition(expr: str, profile: ProjectProfile) -> bool:
    expr = (expr or "").strip()
    if not expr or expr == "always":
        return True
    if expr.startswith("project_type:"):
        target = expr.split(":", 1)[1]
        return target in profile.项目类型
    if expr.startswith("source:"):
        target = expr.split(":", 1)[1]
        return profile.参考样板项目 == target
    flags = profile.flags()
    return bool(flags.get(expr))


def _lookup_service(service_id: str) -> dict[str, Any] | None:
    for s in load_service_items():
        if s.get("服务项ID") == service_id:
            return s
    return None


def _lookup_component(component_id: str) -> dict[str, Any] | None:
    for c in load_components():
        if c.get("组件编号") == component_id:
            return c
    return None


def match_profile(profile: ProjectProfile) -> MatchResult:
    """规则匹配：条件 → 服务项 → 组件 → 风险。"""
    result = MatchResult(profile=profile)
    seen_services: set[str] = set()
    seen_components: set[str] = set()
    seen_risks: set[str] = set()

    rules = sorted(load_match_rules(), key=lambda r: int(r.get("优先级", 100)))

    for rule in rules:
        if not _eval_condition(str(rule.get("条件表达式", "")), profile):
            continue
        rule_id = str(rule.get("规则ID", ""))
        priority = int(rule.get("优先级", 100))
        reason = str(rule.get("推荐理由", ""))

        for sid in str(rule.get("推荐服务项", "")).split(","):
            sid = sid.strip()
            if not sid or sid in seen_services:
                continue
            svc = _lookup_service(sid)
            if svc:
                seen_services.add(sid)
                result.service_items.append(RecommendationItem(
                    kind="service",
                    item_id=sid,
                    name=str(svc.get("服务项名称", sid)),
                    reason=reason,
                    rule_id=rule_id,
                    priority=priority,
                ))

        for cid in str(rule.get("推荐组件", "")).split(","):
            cid = cid.strip()
            if not cid or cid in seen_components:
                continue
            comp = _lookup_component(cid)
            if comp:
                seen_components.add(cid)
                result.components.append(RecommendationItem(
                    kind="component",
                    item_id=cid,
                    name=str(comp.get("组件名称", cid)),
                    reason=reason,
                    rule_id=rule_id,
                    source_project=str(comp.get("来源项目", "")),
                    priority=priority,
                ))

        risk = str(rule.get("关联风险", "")).strip()
        if risk and risk not in seen_risks:
            seen_risks.add(risk)
            result.risks.append(RecommendationItem(
                kind="risk",
                item_id=f"RISK-{rule_id}",
                name=risk,
                reason=reason,
                rule_id=rule_id,
                priority=priority,
            ))

    # 关联 TEM 项目差异作为待确认项
    try:
        diffs = list_project_diffs()
        if not diffs.empty:
            result.pending_diffs = diffs.head(20).to_dict(orient="records")
    except Exception:  # noqa: BLE001
        pass

    return result


def save_profile(profile: ProjectProfile, created_by: str | None = None) -> None:
    ts = datetime.now()
    with connect() as con:
        con.execute(
            """
            INSERT OR REPLACE INTO meta_emos_project_profile
            (画像ID, 客户名称, 行业, 项目类型, 用户规模, 画像JSON, 创建人, 数据更新时间)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                profile.画像ID,
                profile.客户名称,
                profile.行业,
                ",".join(profile.项目类型),
                profile.用户规模,
                json.dumps(profile.to_dict(), ensure_ascii=False),
                created_by,
                ts,
            ],
        )


def save_recommendation(profile_id: str, result: MatchResult) -> str:
    rec_id = f"REC-{uuid.uuid4().hex[:10]}"
    ts = datetime.now()
    with connect() as con:
        con.execute(
            """
            INSERT INTO meta_emos_recommendation (推荐ID, 画像ID, 推荐JSON, 数据更新时间)
            VALUES (?, ?, ?, ?)
            """,
            [rec_id, profile_id, json.dumps(result.to_dict(), ensure_ascii=False, default=str), ts],
        )
    return rec_id


def list_profiles(limit: int = 50) -> pd.DataFrame:
    with connect(read_only=True) as con:
        return con.execute(
            """
            SELECT 画像ID, 客户名称, 行业, 项目类型, 用户规模, 创建人, 数据更新时间
            FROM meta_emos_project_profile
            ORDER BY 数据更新时间 DESC
            LIMIT ?
            """,
            [limit],
        ).fetchdf()


def match_result_from_dict(profile_dict: dict, result_dict: dict) -> MatchResult:
    profile = ProjectProfile(**profile_dict)
    return MatchResult(
        profile=profile,
        service_items=[RecommendationItem(**x) for x in result_dict.get("service_items", [])],
        components=[RecommendationItem(**x) for x in result_dict.get("components", [])],
        risks=[RecommendationItem(**x) for x in result_dict.get("risks", [])],
        pending_diffs=result_dict.get("pending_diffs", []),
    )


def get_latest_recommendation(profile_id: str) -> dict[str, Any] | None:
    with connect(read_only=True) as con:
        row = con.execute(
            """
            SELECT 推荐JSON FROM meta_emos_recommendation
            WHERE 画像ID = ? ORDER BY 数据更新时间 DESC LIMIT 1
            """,
            [profile_id],
        ).fetchone()
    if not row:
        return None
    return json.loads(row[0])
