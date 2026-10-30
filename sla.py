"""SLA: расчёт дедлайна и «светофора» по матрице «категория × приоритет»."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

from core.config import (
    AT_RISK_SHARE,
    LIGHT_AT_RISK,
    LIGHT_ON_TIME,
    LIGHT_OVERDUE,
    LIGHT_RESOLVED_LATE,
    LIGHT_RESOLVED_ON_TIME,
    SLA_RULES_PATH,
)


def load_sla_rules(path: Path = SLA_RULES_PATH) -> dict[tuple[str, str], float]:
    """Читает матрицу SLA в словарь {(категория, приоритет): часы}."""
    df = pd.read_csv(path, encoding="utf-8")
    required = {"category", "priority", "hours"}
    if not required.issubset(df.columns):
        raise ValueError(f"В матрице SLA нужны колонки: {', '.join(sorted(required))}")
    return {(row.category, row.priority): float(row.hours) for row in df.itertuples()}


def compute_deadline(created_at: datetime, category: str, priority: str, rules: dict) -> datetime:
    """Дедлайн = время поступления + норматив в часах. Считается календарное время."""
    key = (category, priority)
    if key not in rules:
        raise ValueError(f"Нет норматива SLA для категории «{category}» и приоритета «{priority}»")
    return created_at + timedelta(hours=rules[key])


def sla_light(
    created_at: datetime,
    deadline: datetime,
    now: datetime,
    resolved_at: datetime | None = None,
) -> str:
    """Возвращает состояние SLA для одного обращения."""
    if resolved_at is not None:
        return LIGHT_RESOLVED_ON_TIME if resolved_at <= deadline else LIGHT_RESOLVED_LATE
    if now > deadline:
        return LIGHT_OVERDUE
    total = deadline - created_at
    remaining = deadline - now
    if remaining < total * AT_RISK_SHARE:
        return LIGHT_AT_RISK
    return LIGHT_ON_TIME
