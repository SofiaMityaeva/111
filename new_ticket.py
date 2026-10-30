"""Новое обращение: ввод одного обращения (US-02) и загрузка CSV (US-03)."""

from __future__ import annotations

import streamlit as st

from core.config import CHANNELS, DEFAULT_PRIORITY, PRIORITIES, STATUS_REVIEW, get_threshold
from core.pipeline import analyze_ticket, confirm_category, save_ticket
from core.sla import sla_light
from core.validation import read_csv, validate_text, validate_tickets_df
from ui_helpers import get_model, light_label, now, reference, require_setup

require_setup()
model = get_model()
groups, names, rules = reference()
threshold = get_threshold()

st.title("Новое обращение")
single_tab, csv_tab = st.tabs(["Одно обращение", "Загрузить CSV"])

# ---------- Одно обращение ----------
with single_tab:
    with st.form("ticket_form"):
        text = st.text_area(
            "Текст обращения",
            height=120,
            placeholder="Например: второй день не работает интернет, роутер мигает красным",
        )
        col1, col2 = st.columns(2)
        channel = col1.selectbox("Канал", CHANNELS, index=CHANNELS.index("Чат"))
        priority = col2.selectbox("Приоритет", PRIORITIES, index=PRIORITIES.index(DEFAULT_PRIORITY))
        submitted = st.form_submit_button("Определить", type="primary")

    if submitted:
        error = validate_text(text)
        if error:
            st.error(error)
            st.session_state.pop("analysis", None)
        else:
            st.session_state["analysis"] = analyze_ticket(
                text, channel, priority, now(), model, groups, rules, threshold
            )

    ticket = st.session_state.get("analysis")
    if ticket:
        with st.container(border=True):
            st.subheader("Результат")
            left, right = st.columns([1, 2])
            left.markdown("Категория")
            right.markdown(f"**{names[ticket['category']]}**")
            left.markdown("Уверенность")
            right.progress(ticket["confidence"], text=f"{ticket['confidence']:.0%}")
            left.markdown("Группа")
            right.markdown(ticket["group_name"])
            left.markdown("Дедлайн")
            light = sla_light(ticket["created_at"], ticket["deadline"], now())
            right.markdown(f"{ticket['deadline']:%d.%m.%Y, %H:%M} · {light_label(light)}")

            if ticket["status"] == STATUS_REVIEW:
                st.warning(
                    f"Уверенность ниже порога {threshold:.0%}: обращение уйдёт на проверку диспетчеру. "
                    "Можно сразу выбрать правильную категорию ниже."
                )

            if st.button("Сохранить", type="primary"):
                ticket_id = save_ticket(ticket)
                st.session_state.pop("analysis")
                st.success(f"Обращение №{ticket_id} сохранено со статусом «{ticket['status']}».")

            with st.expander("Изменить категорию"):
                codes = list(names)
                new_category = st.selectbox(
                    "Правильная категория",
                    codes,
                    index=codes.index(ticket["category"]),
                    format_func=names.get,
                )
                if st.button("Сохранить с этой категорией"):
                    ticket_id = save_ticket(ticket)
                    saved = confirm_category(ticket_id, new_category, now(), groups, rules)
                    st.session_state.pop("analysis")
                    st.success(
                        f"Обращение №{ticket_id} сохранено: {names[saved['category']]}, "
                        f"группа «{saved['group_name']}», статус «{saved['status']}»."
                    )

# ---------- Загрузка CSV ----------
with csv_tab:
    st.write(
        "Обязательная колонка — `text`. Необязательные: `channel` (Почта, Сайт, Чат), "
        "`priority` (Высокий, Средний, Низкий), `created_at` (например, 2026-10-30 14:00). "
        "Разделитель — запятая или точка с запятой, кодировка UTF-8."
    )
    template = (
        "text,channel,priority,created_at\n"
        "Не работает интернет с утра,Чат,Высокий,2026-10-30 09:15\n"
        "Списали деньги два раза за октябрь,Почта,Средний,\n"
    )
    st.download_button("Скачать пример файла", template.encode("utf-8-sig"), "пример_обращений.csv", "text/csv")

    uploaded = st.file_uploader("CSV-файл с обращениями", type=["csv"])
    if uploaded is not None:
        try:
            df = read_csv(uploaded)
        except ValueError as exc:
            st.error(str(exc))
            st.stop()

        st.caption(f"Строк в файле: {len(df)}. Первые строки:")
        st.dataframe(df.head(5), hide_index=True)

        if st.button(f"Загрузить обращения ({len(df)})", type="primary"):
            try:
                rows, errors = validate_tickets_df(df, now())
            except ValueError as exc:
                st.error(str(exc))
                st.stop()

            auto_count = review_count = 0
            with st.spinner("Классифицирую обращения…"):
                for row in rows:
                    ticket = analyze_ticket(
                        row["text"], row["channel"], row["priority"], row["created_at"],
                        model, groups, rules, threshold,
                    )
                    save_ticket(ticket)
                    if ticket["auto_assigned"]:
                        auto_count += 1
                    else:
                        review_count += 1

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Загружено", len(rows))
            c2.metric("Назначено автоматически", auto_count)
            c3.metric("На проверку", review_count)
            c4.metric("Строк с ошибками", len(errors))
            if errors:
                st.warning("Эти строки не загружены — исправьте их в файле и загрузите снова:")
                st.dataframe(errors, hide_index=True)
            elif rows:
                st.success("Все строки загружены.")
