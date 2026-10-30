"""Сквозная обработка обращения: собирает шаги из других модулей в один сценарий.

Страницы интерфейса вызывают только эти функции, поэтому порядок шагов
(классификация → маршрутизация → SLA → сохранение) описан в одном месте.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

from core import db
from core.classifier import predict
from core.config import (
    DB_PATH,
    STATUS_IN_PROGRESS,
    STATUS_NEW,
    STATUS_RESOLVED,
    STATUS_REVIEW,
)
from core.routing import route
from core.sla import compute_deadline

# Куда можно перевести обращение из каждого статуса
NEXT_STATUSES = {
    STATUS_REVIEW: [],  # сначала диспетчер подтверждает категорию
    STATUS_NEW: [STATUS_IN_PROGRESS, STATUS_RESOLVED],
    STATUS_IN_PROGRESS: [STATUS_RESOLVED],
    STATUS_RESOLVED: [],
}


def analyze_ticket(text, channel, priority, created_at, model, groups, sla_rules, threshold) -> dict:
    """Классифицирует обращение, назначает группу и считает дедлайн. Ничего не сохраняет."""
    category, confidence = predict(model, text)
    group, status, auto = route(category, confidence, groups, threshold)
    return {
        "created_at": created_at,
        "channel": channel,
        "priority": priority,
        "text": text.strip(),
        "predicted_category": category,
        "confidence": round(confidence, 4),
        "category": category,
        "group_name": group,
        "status": status,
        "auto_assigned": int(auto),
        "assigned_at": created_at if auto else None,
        "deadline": compute_deadline(created_at, category, priority, sla_rules),
        "resolved_at": None,
        "is_synthetic": 0,
    }


def save_ticket(ticket: dict, db_path: Path = DB_PATH) -> int:
    return db.insert_ticket(ticket, db_path)


def confirm_category(ticket_id: int, new_category: str, now: datetime, groups, sla_rules, db_path: Path = DB_PATH) -> dict:
    """Диспетчер подтверждает или исправляет категорию.

    Группа и дедлайн пересчитываются, «На проверку» превращается в «Новое».
    Если категория изменилась, в журнал правок пишется запись.
    """
    ticket = db.get_ticket(ticket_id, db_path)
    if ticket is None:
        raise ValueError(f"Обращение №{ticket_id} не найдено")
    if ticket["status"] == STATUS_RESOLVED:
        raise ValueError("Решённое обращение изменить нельзя")
    if new_category not in groups:
        raise ValueError(f"Категории «{new_category}» нет в справочнике")

    old_category = ticket["category"]
    fields = {
        "category": new_category,
        "group_name": groups[new_category],
        "deadline": compute_deadline(ticket["created_at"], new_category, ticket["priority"], sla_rules),
    }
    if ticket["status"] == STATUS_REVIEW:
        fields["status"] = STATUS_NEW
    if ticket["assigned_at"] is None or old_category != new_category:
        fields["assigned_at"] = now

    db.update_ticket(ticket_id, fields, db_path)
    if old_category != new_category:
        db.insert_correction(ticket_id, old_category, new_category, now, db_path)
    return db.get_ticket(ticket_id, db_path)


def change_status(ticket_id: int, new_status: str, now: datetime, db_path: Path = DB_PATH) -> dict:
    """Переводит обращение в следующий статус по правилам NEXT_STATUSES."""
    ticket = db.get_ticket(ticket_id, db_path)
    if ticket is None:
        raise ValueError(f"Обращение №{ticket_id} не найдено")
    allowed = NEXT_STATUSES[ticket["status"]]
    if new_status not in allowed:
        if ticket["status"] == STATUS_REVIEW:
            raise ValueError("Сначала подтвердите категорию обращения")
        raise ValueError(f"Из статуса «{ticket['status']}» нельзя перейти в «{new_status}»")
    fields = {"status": new_status}
    if new_status == STATUS_RESOLVED:
        fields["resolved_at"] = now
    db.update_ticket(ticket_id, fields, db_path)
    return db.get_ticket(ticket_id, db_path)


def training_data_from_tickets(db_path: Path = DB_PATH):
    """Обращения, категорию которых подтвердил человек: их можно добавить в обучение."""
    tickets = db.get_tickets(db_path)
    confirmed = tickets[(tickets["auto_assigned"] == 0) & tickets["assigned_at"].notna()]
    corrected_ids = set(db.get_corrections(db_path)["ticket_id"])
    corrected = tickets[tickets["id"].isin(corrected_ids)]
    columns = ["id", "text", "category"]
    rows = pd.concat([confirmed[columns], corrected[columns]]).drop_duplicates("id")
    return rows[["text", "category"]].reset_index(drop=True)
