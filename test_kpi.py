"""TC-14: KPI на контрольном наборе с известным результатом."""

from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd

from core.kpi import compute_kpis

NOW = datetime(2026, 10, 30, 12, 0)


def control_set() -> pd.DataFrame:
    rows = []
    for i in range(20):
        created = datetime(2026, 10, 29, 9, 0)
        deadline = created + timedelta(hours=8)
        late = i >= 15  # 15 в срок, 5 с нарушением
        rows.append(
            {
                "id": i + 1,
                "created_at": created,
                "assigned_at": created + timedelta(minutes=10),
                "deadline": deadline,
                "resolved_at": deadline + timedelta(hours=1) if late else deadline - timedelta(hours=1),
                "auto_assigned": 1 if i < 16 else 0,
                "predicted_category": "tech",
                "category": "billing" if i in (0, 19) else "tech",
                "group_name": "Техподдержка",
            }
        )
    return pd.DataFrame(rows)


def test_tc14_kpi_control_set():
    kpi = compute_kpis(control_set(), NOW)
    assert kpi["share_on_time"] == 75.0
    assert kpi["violation_share"] == 25.0
    assert kpi["avg_assign_minutes"] == 10.0
    assert kpi["auto_share"] == 80.0
    assert kpi["reassign_share"] == 5.0  # 1 из 20 автоназначенных сменил категорию
    assert kpi["correction_share"] == 25.0  # 1 из 4 проверенных диспетчером


def test_open_overdue_counts_as_violation():
    df = control_set().iloc[:1].copy()
    df["resolved_at"] = pd.NaT
    df["deadline"] = NOW - timedelta(minutes=5)
    kpi = compute_kpis(df, NOW)
    assert kpi["violation_share"] == 100.0
    assert kpi["share_on_time"] is None  # решённых нет — долю считать не из чего
