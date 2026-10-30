"""TC-09 … TC-13: дедлайн и светофор SLA."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from core.config import LIGHT_AT_RISK, LIGHT_ON_TIME, LIGHT_OVERDUE, LIGHT_RESOLVED_LATE, LIGHT_RESOLVED_ON_TIME
from core.sla import compute_deadline, load_sla_rules, sla_light

RULES = load_sla_rules()


def test_tc09_deadline_same_day():
    created = datetime(2026, 10, 30, 10, 0)
    assert compute_deadline(created, "tech", "Высокий", RULES) == datetime(2026, 10, 30, 14, 0)


def test_tc10_deadline_several_days():
    created = datetime(2026, 10, 30, 18, 0)
    assert compute_deadline(created, "connect", "Низкий", RULES) == datetime(2026, 11, 2, 18, 0)


def test_tc11_at_risk():
    created = datetime(2026, 10, 30, 8, 0)
    deadline = created + timedelta(hours=10)
    now = deadline - timedelta(hours=1, minutes=59)
    assert sla_light(created, deadline, now) == LIGHT_AT_RISK


def test_on_time_when_enough_time_left():
    created = datetime(2026, 10, 30, 8, 0)
    deadline = created + timedelta(hours=10)
    assert sla_light(created, deadline, deadline - timedelta(hours=3)) == LIGHT_ON_TIME


def test_tc12_overdue():
    created = datetime(2026, 10, 30, 8, 0)
    deadline = created + timedelta(hours=4)
    assert sla_light(created, deadline, deadline + timedelta(minutes=1)) == LIGHT_OVERDUE


def test_tc13_resolved_late_and_on_time():
    created = datetime(2026, 10, 30, 8, 0)
    deadline = created + timedelta(hours=4)
    assert sla_light(created, deadline, deadline, deadline + timedelta(minutes=1)) == LIGHT_RESOLVED_LATE
    assert sla_light(created, deadline, deadline, deadline) == LIGHT_RESOLVED_ON_TIME


def test_missing_rule():
    with pytest.raises(ValueError):
        compute_deadline(datetime(2026, 10, 30), "tech", "Срочный", RULES)
