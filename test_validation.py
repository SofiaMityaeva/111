"""TC-01 … TC-05: проверка пользовательского ввода и CSV."""

from __future__ import annotations

import io
from datetime import datetime

import pytest

from core.validation import read_csv, validate_priority, validate_text, validate_tickets_df

NOW = datetime(2026, 10, 30, 12, 0)


def test_tc01_empty_text():
    assert validate_text("   ") == "Введите текст обращения"


def test_tc02_too_long_text():
    assert "длиннее" in validate_text("а" * 5001)
    assert validate_text("а" * 5000) is None


def test_tc03_unknown_priority():
    value, error = validate_priority("Срочный")
    assert value is None
    assert "Высокий" in error and "Низкий" in error


def test_priority_is_case_insensitive():
    assert validate_priority(" высокий ") == ("Высокий", None)


def test_tc04_csv_without_text_column():
    df = read_csv(io.StringIO("channel,priority\nЧат,Высокий\n"))
    with pytest.raises(ValueError, match="Нет обязательной колонки text"):
        validate_tickets_df(df, NOW)


def test_tc05_csv_with_bad_rows():
    lines = ["text;priority"] + [f"Обращение {i};Средний" for i in range(8)] + [";Средний", "  ;Низкий"]
    df = read_csv(io.StringIO("\n".join(lines)))
    rows, errors = validate_tickets_df(df, NOW)
    assert len(rows) == 8
    assert [e["Строка"] for e in errors] == [10, 11]
    assert all("Введите текст" in e["Причина"] for e in errors)


def test_csv_defaults_and_dates():
    df = read_csv(io.StringIO("text,created_at\nНе работает интернет,30.10.2026 09:15\nВопрос по оплате,\n"))
    rows, errors = validate_tickets_df(df, NOW)
    assert errors == []
    assert rows[0]["created_at"] == datetime(2026, 10, 30, 9, 15)
    assert rows[1]["created_at"] == NOW
    assert rows[1]["priority"] == "Средний" and rows[1]["channel"] == "Сайт"


def test_csv_future_date_rejected():
    df = read_csv(io.StringIO("text,created_at\nТекст,2030-01-01 10:00\n"))
    rows, errors = validate_tickets_df(df, NOW)
    assert rows == [] and "будущем" in errors[0]["Причина"]
