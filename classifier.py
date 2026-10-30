"""Классификатор обращений: TF-IDF + логистическая регрессия.

TF-IDF превращает текст в вектор чисел: каждое слово и пара слов получают вес,
который выше, если слово часто встречается в этом тексте и редко в остальных.
Логистическая регрессия по этим весам считает вероятность каждой категории.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

from core.config import DATETIME_FORMAT, METRICS_PATH, MODEL_PATH


def normalize_text(text: str) -> str:
    """Нижний регистр, «ё» → «е», без лишних пробелов."""
    text = str(text).lower().replace("ё", "е")
    return re.sub(r"\s+", " ", text).strip()


def build_pipeline() -> Pipeline:
    return Pipeline(
        [
            (
                "tfidf",
                TfidfVectorizer(preprocessor=normalize_text, ngram_range=(1, 2), sublinear_tf=True),
            ),
            ("clf", LogisticRegression(max_iter=2000, class_weight="balanced")),
        ]
    )


def train_and_evaluate(texts, labels, test_size: float = 0.2, random_state: int = 42):
    """Обучает модель и честно оценивает её на отложенной выборке.

    1. Делим данные 80/20 с сохранением долей категорий.
    2. Обучаем на 80%, считаем метрики на 20%, которые модель не видела.
    3. Финальную модель переобучаем на всех данных — так она знает больше примеров,
       а метрики из шага 2 остаются честной оценкой качества.
    """
    texts, labels = list(texts), list(labels)
    if len(set(labels)) < 2:
        raise ValueError("Для обучения нужно хотя бы две категории")

    x_train, x_test, y_train, y_test = train_test_split(
        texts, labels, test_size=test_size, random_state=random_state, stratify=labels
    )
    model = build_pipeline().fit(x_train, y_train)
    predicted = model.predict(x_test)

    classes = sorted(set(labels))
    per_class_f1 = f1_score(y_test, predicted, labels=classes, average=None)
    metrics = {
        "accuracy": round(float(accuracy_score(y_test, predicted)), 4),
        "macro_f1": round(float(f1_score(y_test, predicted, average="macro")), 4),
        "labels": classes,
        "confusion_matrix": confusion_matrix(y_test, predicted, labels=classes).tolist(),
        "f1_by_class": {c: round(float(v), 4) for c, v in zip(classes, per_class_f1)},
        "n_train": len(x_train),
        "n_test": len(x_test),
        "trained_at": datetime.now().strftime(DATETIME_FORMAT),
    }

    final_model = build_pipeline().fit(texts, labels)
    return final_model, metrics


def predict(model: Pipeline, text: str) -> tuple[str, float]:
    """Возвращает (категория, уверенность от 0 до 1)."""
    probabilities = model.predict_proba([text])[0]
    best = int(np.argmax(probabilities))
    return str(model.classes_[best]), float(probabilities[best])


def predict_many(model: Pipeline, texts: list[str]) -> list[tuple[str, float]]:
    probabilities = model.predict_proba(texts)
    best = probabilities.argmax(axis=1)
    return [(str(model.classes_[i]), float(p[i])) for i, p in zip(best, probabilities)]


def top_words(model: Pipeline, category: str, n: int = 10) -> list[str]:
    """Слова и пары слов, которые сильнее всего указывают на категорию."""
    vectorizer = model.named_steps["tfidf"]
    clf = model.named_steps["clf"]
    index = list(clf.classes_).index(category)
    weights = clf.coef_[index]
    vocabulary = vectorizer.get_feature_names_out()
    return [str(vocabulary[i]) for i in np.argsort(weights)[::-1][:n]]


def save_model(model: Pipeline, metrics: dict, model_path: Path = MODEL_PATH, metrics_path: Path = METRICS_PATH) -> None:
    """Сохраняет модель и метрики; прошлые метрики остаются в поле previous."""
    model_path.parent.mkdir(parents=True, exist_ok=True)
    previous = load_metrics(metrics_path)
    if previous:
        previous.pop("previous", None)
        metrics = {**metrics, "previous": previous}
    joblib.dump(model, model_path)
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)


def load_model(model_path: Path = MODEL_PATH) -> Pipeline | None:
    if not Path(model_path).exists():
        return None
    try:
        return joblib.load(model_path)
    except Exception:  # повреждённый или несовместимый файл — считаем, что модели нет
        return None


def load_metrics(metrics_path: Path = METRICS_PATH) -> dict | None:
    try:
        with open(metrics_path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
