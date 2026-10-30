"""Маршрутизация: категория → группа поддержки и решение «автоматически или на проверку»."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from core.config import CATEGORIES_PATH, STATUS_NEW, STATUS_REVIEW


def load_categories(path: Path = CATEGORIES_PATH) -> pd.DataFrame:
    """Читает справочник категорий: code, name, group_name."""
    df = pd.read_csv(path, encoding="utf-8")
    required = {"code", "name", "group_name"}
    if not required.issubset(df.columns):
        raise ValueError(f"В справочнике категорий нужны колонки: {', '.join(sorted(required))}")
    return df


def category_groups(categories: pd.DataFrame) -> dict[str, str]:
    """Словарь «код категории → группа»."""
    return dict(zip(categories["code"], categories["group_name"]))


def category_names(categories: pd.DataFrame) -> dict[str, str]:
    """Словарь «код категории → название для интерфейса»."""
    return dict(zip(categories["code"], categories["name"]))


def route(category: str, confidence: float, groups: dict[str, str], threshold: float) -> tuple[str, str, bool]:
    """Возвращает (группа, статус, назначено ли автоматически).

    Уверенность не ниже порога → автоназначение, статус «Новое».
    Ниже порога → статус «На проверку», группа предварительная.
    """
    if category not in groups:
        raise ValueError(f"Категории «{category}» нет в справочнике")
    auto = confidence >= threshold
    status = STATUS_NEW if auto else STATUS_REVIEW
    return groups[category], status, auto
