"""TC-15: исправление категории и связанные сценарии работы с базой."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from core import db
from core.config import STATUS_IN_PROGRESS, STATUS_NEW, STATUS_RESOLVED, STATUS_REVIEW
from core.pipeline import change_status, confirm_category
from core.routing import category_groups, load_categories
from core.sla import load_sla_rules

GROUPS = category_groups(load_categories())
RULES = load_sla_rules()
CREATED = datetime(2026, 10, 30, 9, 0)


def make_ticket(db_path, status=STATUS_REVIEW, category="complaint"):
    return db.insert_ticket(
        {
            "created_at": CREATED, "channel": "Чат", "priority": "Средний",
            "text": "Списали деньги два раза", "predicted_category": category,
            "confidence": 0.45, "category": category, "group_name": GROUPS[category],
            "status": status, "auto_assigned": 0, "assigned_at": None,
            "deadline": CREATED + timedelta(hours=24), "resolved_at": None, "is_synthetic": 0,
        },
        db_path,
    )


def test_tc15_correction(tmp_path):
    path = tmp_path / "test.db"
    ticket_id = make_ticket(path)
    now = datetime(2026, 10, 30, 9, 30)
    updated = confirm_category(ticket_id, "billing", now, GROUPS, RULES, path)
    assert updated["group_name"] == "Биллинг"
    assert updated["deadline"] == CREATED + timedelta(hours=24)  # billing × Средний = 24 ч
    assert updated["status"] == STATUS_NEW
    assert updated["assigned_at"] == now
    corrections = db.get_corrections(path)
    assert len(corrections) == 1
    assert corrections.iloc[0]["old_category"] == "complaint"


def test_confirm_without_change_logs_nothing(tmp_path):
    path = tmp_path / "test.db"
    ticket_id = make_ticket(path, category="tech")
    updated = confirm_category(ticket_id, "tech", CREATED, GROUPS, RULES, path)
    assert updated["status"] == STATUS_NEW
    assert db.get_corrections(path).empty


def test_status_flow(tmp_path):
    path = tmp_path / "test.db"
    ticket_id = make_ticket(path, status=STATUS_NEW, category="tech")
    with pytest.raises(ValueError):
        change_status(ticket_id, STATUS_REVIEW, CREATED, path)
    change_status(ticket_id, STATUS_IN_PROGRESS, CREATED, path)
    resolved = change_status(ticket_id, STATUS_RESOLVED, CREATED + timedelta(hours=2), path)
    assert resolved["resolved_at"] == CREATED + timedelta(hours=2)


def test_review_ticket_needs_confirmation(tmp_path):
    path = tmp_path / "test.db"
    ticket_id = make_ticket(path)
    with pytest.raises(ValueError, match="подтвердите категорию"):
        change_status(ticket_id, STATUS_IN_PROGRESS, CREATED, path)
