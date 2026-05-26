"""字段标准化与单位换算层。

设计依据：§13.1 标准化字段规则。
"""
from .fields import (
    apply_aliases,
    normalize_account_period,
    normalize_phone,
    SERVICE_NUMBER_ALIASES,
    EMPLOYEE_ID_ALIASES,
    EMAIL_ALIASES,
    ACCOUNT_PERIOD_ALIASES,
)
from .units import (
    seconds_to_minutes,
    mb_to_gb,
    excel_serial_to_date,
    coerce_date,
    period_yyyymm,
)

__all__ = [
    "apply_aliases",
    "normalize_account_period",
    "normalize_phone",
    "SERVICE_NUMBER_ALIASES",
    "EMPLOYEE_ID_ALIASES",
    "EMAIL_ALIASES",
    "ACCOUNT_PERIOD_ALIASES",
    "seconds_to_minutes",
    "mb_to_gb",
    "excel_serial_to_date",
    "coerce_date",
    "period_yyyymm",
]
