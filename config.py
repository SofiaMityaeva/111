"""Настройки приложения: пути к файлам, справочные значения и пороги.

Все значения, которые могут понадобиться поменять (пороги, списки),
собраны здесь, чтобы не искать их по коду.
"""

from __future__ import annotations

import json
from pathlib import Path

# --- Пути ---
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
MODELS_DIR = BASE_DIR / "models"

DB_PATH = BASE_DIR / "ticket_router.db"
CATEGORIES_PATH = DATA_DIR / "categories.csv"
SLA_RULES_PATH = DATA_DIR / "sla_rules.csv"
SYNTHETIC_PATH = DATA_DIR / "synthetic_tickets.csv"
MODEL_PATH = MODELS_DIR / "classifier.joblib"
METRICS_PATH = MODELS_DIR / "metrics.json"
SETTINGS_PATH = MODELS_DIR / "settings.json"

# --- Справочные значения ---
PRIORITIES = ["Высокий", "Средний", "Низкий"]
CHANNELS = ["Почта", "Сайт", "Чат"]
DEFAULT_CHANNEL = "Сайт"
DEFAULT_PRIORITY = "Средний"

STATUS_REVIEW = "На проверку"
STATUS_NEW = "Новое"
STATUS_IN_PROGRESS = "В работе"
STATUS_RESOLVED = "Решено"
STATUSES = [STATUS_REVIEW, STATUS_NEW, STATUS_IN_PROGRESS, STATUS_RESOLVED]

# Светофор SLA
LIGHT_ON_TIME = "В срок"
LIGHT_AT_RISK = "Под угрозой"
LIGHT_OVERDUE = "Просрочено"
LIGHT_RESOLVED_ON_TIME = "Решено в срок"
LIGHT_RESOLVED_LATE = "Решено с нарушением"

# --- Пороги ---
MAX_TEXT_LENGTH = 5000
DEFAULT_CONFIDENCE_THRESHOLD = 0.6  # ниже — обращение уходит на проверку диспетчеру
AT_RISK_SHARE = 0.2  # «под угрозой», если осталось меньше 20% норматива

DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"


def get_threshold(settings_path: Path = SETTINGS_PATH) -> float:
    """Возвращает сохранённый порог уверенности или значение по умолчанию."""
    try:
        with open(settings_path, encoding="utf-8") as f:
            value = float(json.load(f).get("confidence_threshold", DEFAULT_CONFIDENCE_THRESHOLD))
        return value if 0 < value < 1 else DEFAULT_CONFIDENCE_THRESHOLD
    except (OSError, ValueError, json.JSONDecodeError):
        return DEFAULT_CONFIDENCE_THRESHOLD


def set_threshold(value: float, settings_path: Path = SETTINGS_PATH) -> None:
    """Сохраняет порог уверенности в файл настроек."""
    if not 0 < value < 1:
        raise ValueError("Порог уверенности должен быть больше 0 и меньше 1")
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    with open(settings_path, "w", encoding="utf-8") as f:
        json.dump({"confidence_threshold": round(value, 2)}, f, ensure_ascii=False)


class Paths:
    """Набор путей к файлам; в тестах подменяется на временную папку."""

    def __init__(self, base: Path | None = None):
        if base is None:
            self.synthetic, self.model, self.metrics, self.db = SYNTHETIC_PATH, MODEL_PATH, METRICS_PATH, DB_PATH
        else:
            self.synthetic = base / "synthetic_tickets.csv"
            self.model = base / "classifier.joblib"
            self.metrics = base / "metrics.json"
            self.db = base / "ticket_router.db"
