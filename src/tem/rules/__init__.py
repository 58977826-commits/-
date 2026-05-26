"""规则引擎 - 设计文档第 13 章。

规则编号 -> 代码位置：
  C01-C06     overpackage.py
  Z01-Z04     zero_usage.py
  H01-H04     high_usage.py
  漫游        anomalies.apply_roaming
  增值业务    anomalies.apply_value_added
  离职后计费  anomalies.apply_post_termination
  事件未闭环  event_rules.apply_event_status
  改号 / 副卡 event_rules.apply_event_change
"""
from .overpackage import apply_overpackage
from .zero_usage import apply_zero_usage
from .high_usage import apply_high_usage
from .anomalies import (
    apply_roaming,
    apply_value_added,
    apply_post_termination,
    aggregate_anomaly_summary,
)
from .event_rules import apply_event_status, apply_event_change

__all__ = [
    "apply_overpackage",
    "apply_zero_usage",
    "apply_high_usage",
    "apply_roaming",
    "apply_value_added",
    "apply_post_termination",
    "aggregate_anomaly_summary",
    "apply_event_status",
    "apply_event_change",
]
