"""TC-16: качество модели на отложенной синтетической выборке."""

from __future__ import annotations

from core.classifier import predict, train_and_evaluate
from core.data_gen import generate_training_set


def test_tc16_model_quality():
    data = generate_training_set()
    model, metrics = train_and_evaluate(data["text"], data["category"])
    assert metrics["accuracy"] >= 0.80
    assert metrics["macro_f1"] >= 0.75
    category, confidence = predict(model, "Второй день не работает интернет, роутер мигает красным")
    assert category == "tech"
    assert 0 < confidence <= 1


def test_synthetic_data_is_reproducible():
    assert generate_training_set(50, seed=1).equals(generate_training_set(50, seed=1))
