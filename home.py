"""Стартовая страница: что это за приложение и первый запуск (сценарий US-01)."""

from __future__ import annotations

import streamlit as st

from core.classifier import load_metrics
from core.config import Paths, get_threshold
from core.data_gen import create_demo_environment
from core.db import count_tickets, reset_db
from ui_helpers import get_model, now, reference

st.title("ТикетРоутер")
st.write(
    "Сервис определяет категорию обращения клиента по тексту, направляет его в нужную группу "
    "поддержки и следит, чтобы ответ уложился в срок по SLA."
)
st.caption(
    "Учебный проект. Компания «СетьПлюс» вымышленная, все обращения и цифры — синтетические "
    "и нужны только для демонстрации."
)

model = get_model()
metrics = load_metrics()
tickets = count_tickets()

col1, col2, col3 = st.columns(3)
col1.metric("Обращений в базе", tickets)
col2.metric("Модель", "обучена" if model else "не обучена")
col3.metric("Accuracy модели", f"{metrics['accuracy']:.0%}" if metrics else "—")

st.subheader("Демо-данные")
st.write(
    "Кнопка создаёт 1 500 синтетических размеченных обращений, обучает на них модель и "
    "заполняет базу историей из 300 обращений за последние 14 дней. Текущие обращения будут удалены."
)

if st.button("Сгенерировать демо-данные и обучить модель", type="primary"):
    groups, _, rules = reference()
    with st.spinner("Генерирую обращения и обучаю модель…"):
        try:
            result = create_demo_environment(now(), groups, rules, get_threshold(), Paths())
        except Exception as exc:  # показываем причину, а не падаем
            st.error(f"Не удалось подготовить демо-данные: {exc}")
        else:
            st.success(
                f"Готово: {result['tickets']} обращений, {result['corrections']} правок диспетчеров, "
                f"accuracy модели {result['metrics']['accuracy']:.0%}."
            )
            st.rerun()

with st.expander("Очистить базу"):
    st.write("Удаляет все обращения и журнал правок. Модель и справочники остаются.")
    if st.button("Удалить все обращения"):
        reset_db()
        st.success("База очищена.")
        st.rerun()

st.subheader("Как пользоваться")
st.markdown(
    "1. **Новое обращение** — введите текст или загрузите CSV и посмотрите категорию, группу и дедлайн.\n"
    "2. **Очередь** — разберите обращения «На проверку», меняйте статусы.\n"
    "3. **Дашборд SLA** — KPI, нарушения по дням и группам, обращения под угрозой.\n"
    "4. **Модель** — качество классификатора, порог уверенности и переобучение."
)
