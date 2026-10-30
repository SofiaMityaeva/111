"""Модель: качество классификатора, порог уверенности и переобучение (US-07)."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from core.classifier import load_metrics, save_model, top_words, train_and_evaluate
from core.config import SYNTHETIC_PATH, get_threshold, set_threshold
from core.pipeline import training_data_from_tickets
from ui_helpers import get_model, reference, require_setup

require_setup()
groups, names, rules = reference()
model = get_model()
metrics = load_metrics()

st.title("Модель")
st.write(
    "Классификатор — TF-IDF + логистическая регрессия. Метрики посчитаны на 20% данных, "
    "которые модель не видела при обучении."
)

if metrics:
    previous = metrics.get("previous")
    c1, c2, c3 = st.columns(3)
    pct = lambda v: f"{v:.1%}".replace(".", ",")
    c1.metric(
        "Accuracy", pct(metrics["accuracy"]),
        delta=f"{(metrics['accuracy'] - previous['accuracy']) * 100:+.1f} п. п.".replace(".", ",", 1) if previous else None,
    )
    c2.metric(
        "Macro F1", pct(metrics["macro_f1"]),
        delta=f"{(metrics['macro_f1'] - previous['macro_f1']) * 100:+.1f} п. п.".replace(".", ",", 1) if previous else None,
    )
    c3.metric("Примеров в обучении", metrics["n_train"] + metrics["n_test"])
    st.caption(
        f"Обучена {metrics['trained_at']}. Правок диспетчеров в обучении: {metrics.get('n_corrections_used', 0)}. "
        "Цель из бизнес-постановки: accuracy ≥ 80%, macro F1 ≥ 75%."
    )

    left, right = st.columns([3, 2])
    with left:
        labels = [names.get(code, code) for code in metrics["labels"]]
        fig = px.imshow(
            metrics["confusion_matrix"], x=labels, y=labels, text_auto=True,
            color_continuous_scale=["#F4F8F8", "#1D6A72"],
            labels={"x": "Предсказано", "y": "На самом деле", "color": "Обращений"},
            title="Матрица ошибок",
        )
        fig.update_layout(margin=dict(t=48, b=8), coloraxis_showscale=False)
        st.plotly_chart(fig)
    with right:
        f1_table = pd.DataFrame(
            {
                "Категория": [names.get(c, c) for c in metrics["f1_by_class"]],
                "F1": [f"{v:.0%}" for v in metrics["f1_by_class"].values()],
            }
        )
        st.write("Качество по категориям")
        st.dataframe(f1_table, hide_index=True)
        st.caption("Диагональ матрицы — верные ответы, всё вне её — ошибки модели.")

with st.expander("Какие слова модель считает главными"):
    for code in model.classes_:
        st.markdown(f"**{names.get(code, code)}:** {', '.join(top_words(model, code, 8))}")

st.subheader("Порог уверенности")
threshold = st.slider(
    "Ниже этого порога обращение уходит на проверку диспетчеру",
    min_value=0.3, max_value=0.95, value=float(get_threshold()), step=0.05, format="%.2f",
)
if st.button("Сохранить порог"):
    set_threshold(threshold)
    st.success(f"Порог {threshold:.0%} сохранён. Он применяется к новым обращениям.")

st.subheader("Переобучение")
confirmed = training_data_from_tickets()
st.write(
    f"Обращений, категорию которых подтвердил диспетчер: **{len(confirmed)}**. "
    "При переобучении они добавятся к синтетическому набору."
)
if st.button("Переобучить", type="primary"):
    if not SYNTHETIC_PATH.exists():
        st.error("Не найден синтетический набор. Сгенерируйте демо-данные на стартовой странице.")
        st.stop()
    training = pd.concat([pd.read_csv(SYNTHETIC_PATH, encoding="utf-8"), confirmed], ignore_index=True)
    with st.spinner("Обучаю модель…"):
        try:
            new_model, new_metrics = train_and_evaluate(training["text"], training["category"])
        except ValueError as exc:
            st.error(f"Не удалось обучить модель: {exc}")
            st.stop()
        new_metrics["n_corrections_used"] = len(confirmed)
        save_model(new_model, new_metrics)
    st.success("Модель переобучена.")
    st.rerun()
