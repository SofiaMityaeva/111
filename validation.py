"""Проверка пользовательского ввода: текст, приоритет, канал, дата и CSV-файл."""

from __future__ import annotations

from datetime import datetime

import pandas as pd

from core.config import (
    CHANNELS,
    DEFAULT_CHANNEL,
    DEFAULT_PRIORITY,
    MAX_TEXT_LENGTH,
    PRIORITIES,
)

DATETIME_INPUT_FORMATS = [
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M",
    "%d.%m.%Y %H:%M:%S",
    "%d.%m.%Y %H:%M",
    "%Y-%m-%d",
    "%d.%m.%Y",
]


def validate_text(text) -> str | None:
    """Возвращает текст ошибки или None, если текст корректен."""
    if text is None or not str(text).strip():
        return "Введите текст обращения"
    if len(str(text)) > MAX_TEXT_LENGTH:
        return f"Текст длиннее {MAX_TEXT_LENGTH} символов — сократите его"
    return None


def _normalize_choice(value, allowed: list[str]) -> str | None:
    """Ищет значение в списке без учёта регистра и пробелов по краям."""
    cleaned = str(value).strip().lower()
    for option in allowed:
        if option.lower() == cleaned:
            return option
    return None


def validate_priority(value) -> tuple[str | None, str | None]:
    """Возвращает (приоритет в правильном написании, ошибка)."""
    normalized = _normalize_choice(value, PRIORITIES)
    if normalized is None:
        return None, f"Неизвестный приоритет «{value}». Допустимо: {', '.join(PRIORITIES)}"
    return normalized, None


def validate_channel(value) -> tuple[str | None, str | None]:
    """Возвращает (канал в правильном написании, ошибка)."""
    normalized = _normalize_choice(value, CHANNELS)
    if normalized is None:
        return None, f"Неизвестный канал «{value}». Допустимо: {', '.join(CHANNELS)}"
    return normalized, None


def parse_datetime(value) -> datetime | None:
    """Разбирает дату в одном из поддерживаемых форматов, иначе None."""
    text = str(value).strip()
    for fmt in DATETIME_INPUT_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def read_csv(file) -> pd.DataFrame:
    """Читает CSV с разделителем «,» или «;». Ошибку чтения переводит в понятный текст."""
    try:
        df = pd.read_csv(
            file,
            sep=None,
            engine="python",
            encoding="utf-8-sig",
            dtype=str,
            keep_default_na=False,
        )
    except UnicodeDecodeError as exc:
        raise ValueError("Файл не в кодировке UTF-8. Сохраните CSV в UTF-8 и загрузите снова") from exc
    except (pd.errors.ParserError, pd.errors.EmptyDataError, ValueError) as exc:
        raise ValueError("Не удалось прочитать файл как CSV. Проверьте разделители и заголовок") from exc
    df.columns = [str(c).strip().lower() for c in df.columns]
    return df


def validate_tickets_df(df: pd.DataFrame, now: datetime) -> tuple[list[dict], list[dict]]:
    """Проверяет таблицу обращений построчно.

    Возвращает (корректные строки, ошибки). Номер строки в ошибке — номер строки
    в файле с учётом заголовка, чтобы его было легко найти в Excel.
    """
    if "text" not in df.columns:
        raise ValueError("Нет обязательной колонки text")

    valid_rows, errors = [], []
    for position, (_, row) in enumerate(df.iterrows()):
        line = position + 2  # +1 за заголовок, +1 потому что счёт строк с единицы
        reasons = []

        text = row.get("text", "")
        text_error = validate_text(text)
        if text_error:
            reasons.append(text_error)

        priority_raw = row.get("priority", "") or DEFAULT_PRIORITY
        priority, priority_error = validate_priority(priority_raw)
        if priority_error:
            reasons.append(priority_error)

        channel_raw = row.get("channel", "") or DEFAULT_CHANNEL
        channel, channel_error = validate_channel(channel_raw)
        if channel_error:
            reasons.append(channel_error)

        created_raw = row.get("created_at", "")
        if created_raw:
            created_at = parse_datetime(created_raw)
            if created_at is None:
                reasons.append(f"Не удалось разобрать дату «{created_raw}». Пример: 2026-10-30 14:00")
            elif created_at > now:
                reasons.append("Дата поступления в будущем")
        else:
            created_at = now

        if reasons:
            errors.append({"Строка": line, "Причина": "; ".join(reasons)})
        else:
            valid_rows.append(
                {
                    "text": str(text).strip(),
                    "priority": priority,
                    "channel": channel,
                    "created_at": created_at,
                }
            )
    return valid_rows, errors
