"""Общие функции для страниц Streamlit: загрузка модели и справочников, оформление таблиц."""

from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

from core.classifier import load_model
from core.config import (
    LIGHT_AT_RISK,
    LIGHT_ON_TIME,
    LIGHT_OVERDUE,
    LIGHT_RESOLVED_LATE,
    LIGHT_RESOLVED_ON_TIME,
    MODEL_PATH,
)
from core.db import count_tickets
from core.kpi import add_sla_light
from core.routing import category_groups, category_names, load_categories
from core.sla import load_sla_rules

LIGHT_ICONS = {
    LIGHT_ON_TIME: "🟢",
    LIGHT_AT_RISK: "🟡",
    LIGHT_OVERDUE: "🔴",
    LIGHT_RESOLVED_ON_TIME: "✅",
    LIGHT_RESOLVED_LATE: "⚠️",
}


def now() -> datetime:
    return datetime.now().replace(microsecond=0)


@st.cache_data
def reference():
    """Справочники: (группы по категориям, названия категорий, матрица SLA)."""
    categories = load_categories()
    return category_groups(categories), category_names(categories), load_sla_rules()


@st.cache_resource
def _cached_model(mtime: float):
    return load_model()


def get_model():
    """Модель из файла; после переобучения файл меняется и кэш обновляется сам."""
    if not MODEL_PATH.exists():
        return None
    return _cached_model(MODEL_PATH.stat().st_mtime)


def require_setup() -> None:
    """Останавливает страницу с подсказкой, если модель ещё не обучена."""
    if get_model() is None:
        st.info("Модель ещё не обучена. На стартовой странице нажмите «Сгенерировать демо-данные и обучить модель».")
        st.page_link("views/home.py", label="Перейти на стартовую страницу", icon="🏠")
        st.stop()


def require_tickets() -> None:
    if count_tickets() == 0:
        st.info("В базе пока нет обращений. Добавьте их на странице «Новое обращение» или сгенерируйте демо-данные.")
        st.page_link("views/home.py", label="Перейти на стартовую страницу", icon="🏠")
        st.stop()


def light_label(light: str) -> str:
    return f"{LIGHT_ICONS.get(light, '')} {light}".strip()


def tickets_table(df: pd.DataFrame, current: datetime, names: dict) -> pd.DataFrame:
    """Таблица обращений с понятными колонками для показа пользователю."""
    marked = add_sla_light(df, current)
    view = pd.DataFrame(
        {
            "№": marked["id"],
            "SLA": marked["sla_light"].map(light_label),
            "Статус": marked["status"],
            "Категория": marked["category"].map(names),
            "Группа": marked["group_name"],
            "Приоритет": marked["priority"],
            "Поступило": marked["created_at"],
            "Дедлайн": marked["deadline"],
            "Уверенность": (marked["confidence"] * 100).round(0),
            "Канал": marked["channel"],
            "Текст": marked["text"],
        }
    )
    return view


TABLE_CONFIG = {
    "Поступило": st.column_config.DatetimeColumn(format="DD.MM.YYYY HH:mm"),
    "Дедлайн": st.column_config.DatetimeColumn(format="DD.MM.YYYY HH:mm"),
    "Уверенность": st.column_config.NumberColumn(format="%d%%"),
    "Текст": st.column_config.TextColumn(width="large"),
}
