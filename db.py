"""Работа с базой SQLite: создание таблиц, чтение и запись обращений и правок."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

import pandas as pd

from core.config import DATETIME_FORMAT, DB_PATH

TICKET_FIELDS = [
    "created_at",
    "channel",
    "priority",
    "text",
    "predicted_category",
    "confidence",
    "category",
    "group_name",
    "status",
    "auto_assigned",
    "assigned_at",
    "deadline",
    "resolved_at",
    "is_synthetic",
]

DATETIME_FIELDS = ["created_at", "assigned_at", "deadline", "resolved_at"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    channel TEXT NOT NULL,
    priority TEXT NOT NULL,
    text TEXT NOT NULL,
    predicted_category TEXT NOT NULL,
    confidence REAL NOT NULL,
    category TEXT NOT NULL,
    group_name TEXT NOT NULL,
    status TEXT NOT NULL,
    auto_assigned INTEGER NOT NULL DEFAULT 0,
    assigned_at TEXT,
    deadline TEXT NOT NULL,
    resolved_at TEXT,
    is_synthetic INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS corrections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id INTEGER NOT NULL REFERENCES tickets(id),
    old_category TEXT NOT NULL,
    new_category TEXT NOT NULL,
    corrected_at TEXT NOT NULL
);
"""


def _to_db(value):
    """Даты храним строками в одном формате, остальное как есть."""
    if isinstance(value, datetime):
        return value.strftime(DATETIME_FORMAT)
    if isinstance(value, bool):
        return int(value)
    return value


@contextmanager
def connect(db_path: Path = DB_PATH):
    """Открывает соединение, после блока сохраняет изменения и всегда закрывает файл."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(db_path: Path = DB_PATH) -> None:
    with connect(db_path) as conn:
        conn.executescript(SCHEMA)


def reset_db(db_path: Path = DB_PATH) -> None:
    """Удаляет все обращения и правки, структура таблиц остаётся."""
    init_db(db_path)
    with connect(db_path) as conn:
        conn.execute("DELETE FROM corrections")
        conn.execute("DELETE FROM tickets")
        conn.execute("DELETE FROM sqlite_sequence WHERE name IN ('tickets', 'corrections')")


def insert_ticket(ticket: dict, db_path: Path = DB_PATH) -> int:
    init_db(db_path)
    values = [_to_db(ticket.get(field)) for field in TICKET_FIELDS]
    placeholders = ", ".join("?" for _ in TICKET_FIELDS)
    with connect(db_path) as conn:
        cursor = conn.execute(
            f"INSERT INTO tickets ({', '.join(TICKET_FIELDS)}) VALUES ({placeholders})", values
        )
        return int(cursor.lastrowid)


def insert_correction(ticket_id: int, old_category: str, new_category: str, corrected_at: datetime, db_path: Path = DB_PATH) -> None:
    with connect(db_path) as conn:
        conn.execute(
            "INSERT INTO corrections (ticket_id, old_category, new_category, corrected_at) VALUES (?, ?, ?, ?)",
            (ticket_id, old_category, new_category, _to_db(corrected_at)),
        )


def update_ticket(ticket_id: int, fields: dict, db_path: Path = DB_PATH) -> None:
    unknown = set(fields) - set(TICKET_FIELDS)
    if unknown:
        raise ValueError(f"Неизвестные поля: {', '.join(sorted(unknown))}")
    assignments = ", ".join(f"{name} = ?" for name in fields)
    values = [_to_db(v) for v in fields.values()] + [ticket_id]
    with connect(db_path) as conn:
        conn.execute(f"UPDATE tickets SET {assignments} WHERE id = ?", values)


def get_ticket(ticket_id: int, db_path: Path = DB_PATH) -> dict | None:
    init_db(db_path)
    with connect(db_path) as conn:
        row = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    if row is None:
        return None
    ticket = dict(row)
    for field in DATETIME_FIELDS:
        if ticket[field]:
            ticket[field] = datetime.strptime(ticket[field], DATETIME_FORMAT)
    return ticket


def get_tickets(db_path: Path = DB_PATH) -> pd.DataFrame:
    """Все обращения; даты сразу превращаются в datetime."""
    init_db(db_path)
    with connect(db_path) as conn:
        df = pd.read_sql_query("SELECT * FROM tickets ORDER BY id", conn)
    for field in DATETIME_FIELDS:
        df[field] = pd.to_datetime(df[field], format=DATETIME_FORMAT, errors="coerce")
    return df


def get_corrections(db_path: Path = DB_PATH) -> pd.DataFrame:
    init_db(db_path)
    with connect(db_path) as conn:
        return pd.read_sql_query("SELECT * FROM corrections ORDER BY id", conn)


def count_tickets(db_path: Path = DB_PATH) -> int:
    init_db(db_path)
    with connect(db_path) as conn:
        return int(conn.execute("SELECT COUNT(*) FROM tickets").fetchone()[0])
