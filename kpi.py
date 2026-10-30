"""Расчёт KPI из раздела 14 бизнес-постановки и данных для графиков дашборда."""

from __future__ import annotations

from datetime import datetime

import pandas as pd

from core.config import (
    LIGHT_AT_RISK,
    LIGHT_OVERDUE,
    LIGHT_RESOLVED_LATE,
)
from core.sla import sla_light


def _share(part: int, whole: int) -> float | None:
    """Доля в процентах; None, если делить не на что."""
    return round(part / whole * 100, 1) if whole else None


def add_sla_light(df: pd.DataFrame, now: datetime) -> pd.DataFrame:
    """Добавляет колонку sla_light с состоянием SLA на момент now."""
    df = df.copy()
    df["sla_light"] = [
        sla_light(
            row.created_at,
            row.deadline,
            now,
            None if pd.isna(row.resolved_at) else row.resolved_at,
        )
        for row in df.itertuples()
    ]
    return df


def compute_kpis(df: pd.DataFrame, now: datetime) -> dict:
    """Считает все KPI по таблице обращений (даты уже в формате datetime)."""
    total = len(df)
    resolved = df[df["resolved_at"].notna()]
    resolved_on_time = resolved[resolved["resolved_at"] <= resolved["deadline"]]
    resolved_late = len(resolved) - len(resolved_on_time)
    open_overdue = df[df["resolved_at"].isna() & (df["deadline"] < now)]

    assigned = df[df["assigned_at"].notna()]
    assign_minutes = (assigned["assigned_at"] - assigned["created_at"]).dt.total_seconds() / 60

    auto = df[df["auto_assigned"] == 1]
    auto_reassigned = auto[auto["category"] != auto["predicted_category"]]
    reviewed = assigned[assigned["auto_assigned"] == 0]
    reviewed_changed = reviewed[reviewed["category"] != reviewed["predicted_category"]]

    return {
        "total": total,
        "resolved": len(resolved),
        "share_on_time": _share(len(resolved_on_time), len(resolved)),
        "violations": resolved_late + len(open_overdue),
        "violation_share": _share(resolved_late + len(open_overdue), total),
        "avg_assign_minutes": round(float(assign_minutes.mean()), 1) if len(assigned) else None,
        "reassign_share": _share(len(auto_reassigned), len(assigned)),
        "auto_share": _share(len(auto), total),
        "correction_share": _share(len(reviewed_changed), len(reviewed)),
    }


def violations_by_day(df: pd.DataFrame, now: datetime) -> pd.DataFrame:
    """Доля нарушений SLA по дню поступления обращения."""
    if df.empty:
        return pd.DataFrame(columns=["day", "violation_share", "total"])
    marked = add_sla_light(df, now)
    marked["violated"] = marked["sla_light"].isin([LIGHT_OVERDUE, LIGHT_RESOLVED_LATE])
    marked["day"] = marked["created_at"].dt.normalize()
    daily = marked.groupby("day").agg(total=("id", "count"), violated=("violated", "sum")).reset_index()
    daily["violation_share"] = (daily["violated"] / daily["total"] * 100).round(1)
    return daily[["day", "violation_share", "total"]]


def light_by_group(df: pd.DataFrame, now: datetime) -> pd.DataFrame:
    """Число обращений по группам и состояниям SLA — для столбчатой диаграммы."""
    if df.empty:
        return pd.DataFrame(columns=["group_name", "sla_light", "count"])
    marked = add_sla_light(df, now)
    return marked.groupby(["group_name", "sla_light"]).size().reset_index(name="count")


def at_risk(df: pd.DataFrame, now: datetime) -> pd.DataFrame:
    """Открытые обращения «под угрозой» — самые срочные сверху."""
    marked = add_sla_light(df, now)
    return marked[marked["sla_light"] == LIGHT_AT_RISK].sort_values("deadline")
