"""Очередь: фильтры, разбор «На проверку» (US-04) и работа специалиста (US-05)."""

from __future__ import annotations

import streamlit as st

from core.config import STATUS_RESOLVED, STATUS_REVIEW, STATUSES
from core.db import get_corrections, get_tickets
from core.pipeline import NEXT_STATUSES, change_status, confirm_category
from ui_helpers import TABLE_CONFIG, now, reference, require_tickets, tickets_table

require_tickets()
groups, names, rules = reference()
current = now()

st.title("Очередь обращений")

tickets = get_tickets()
table = tickets_table(tickets, current, names)

# ---------- Фильтры ----------
col1, col2, col3 = st.columns(3)
statuses = col1.multiselect(
    "Статус", STATUSES, default=[s for s in STATUSES if s != STATUS_RESOLVED]
)
group_options = sorted(set(groups.values()))
selected_groups = col2.multiselect("Группа", group_options, default=group_options)
light_options = sorted(table["SLA"].unique())
lights = col3.multiselect("SLA", light_options, default=light_options)
search = st.text_input("Поиск по тексту", placeholder="Например: роутер")

filtered = table[
    table["Статус"].isin(statuses)
    & table["Группа"].isin(selected_groups)
    & table["SLA"].isin(lights)
]
if search.strip():
    filtered = filtered[filtered["Текст"].str.contains(search.strip(), case=False, regex=False)]
filtered = filtered.sort_values("Дедлайн")

st.caption(f"Показано {len(filtered)} из {len(table)} обращений, срочные сверху.")
st.dataframe(filtered, hide_index=True, column_config=TABLE_CONFIG)

# ---------- Работа с обращением ----------
st.subheader("Работа с обращением")
if filtered.empty:
    st.info("Под фильтры не попало ни одного обращения — измените фильтры выше.")
    st.stop()

ticket_ids = filtered["№"].tolist()
ticket_id = st.selectbox(
    "Обращение",
    ticket_ids,
    format_func=lambda i: f"№{i} · {filtered.set_index('№').loc[i, 'Категория']} · {filtered.set_index('№').loc[i, 'Статус']}",
)
ticket = tickets.set_index("id").loc[ticket_id]

with st.container(border=True):
    st.write(ticket["text"])
    st.caption(
        f"Модель: {names[ticket['predicted_category']]} ({ticket['confidence']:.0%}) · "
        f"сейчас: {names[ticket['category']]}, группа «{ticket['group_name']}», статус «{ticket['status']}»"
    )

    if ticket["status"] == STATUS_RESOLVED:
        st.info("Обращение решено, изменить его нельзя.")
    else:
        left, right = st.columns(2)
        with left:
            codes = list(names)
            new_category = st.selectbox(
                "Категория", codes, index=codes.index(ticket["category"]), format_func=names.get
            )
            label = "Подтвердить категорию" if ticket["status"] == STATUS_REVIEW else "Изменить категорию"
            if st.button(label, type="primary" if ticket["status"] == STATUS_REVIEW else "secondary"):
                try:
                    updated = confirm_category(int(ticket_id), new_category, now(), groups, rules)
                except ValueError as exc:
                    st.error(str(exc))
                else:
                    st.success(
                        f"Сохранено: группа «{updated['group_name']}», "
                        f"дедлайн {updated['deadline']:%d.%m.%Y %H:%M}, статус «{updated['status']}»."
                    )
                    st.rerun()
        with right:
            next_statuses = NEXT_STATUSES[ticket["status"]]
            if next_statuses:
                new_status = st.selectbox("Новый статус", next_statuses)
                if st.button("Сменить статус"):
                    try:
                        change_status(int(ticket_id), new_status, now())
                    except ValueError as exc:
                        st.error(str(exc))
                    else:
                        st.rerun()
            else:
                st.caption("Сначала подтвердите категорию — потом можно менять статус.")

with st.expander("Журнал правок диспетчеров"):
    corrections = get_corrections()
    if corrections.empty:
        st.write("Правок пока нет.")
    else:
        st.dataframe(
            corrections.assign(
                old_category=corrections["old_category"].map(names),
                new_category=corrections["new_category"].map(names),
            ).rename(
                columns={
                    "ticket_id": "Обращение",
                    "old_category": "Было",
                    "new_category": "Стало",
                    "corrected_at": "Когда",
                }
            )[["Обращение", "Было", "Стало", "Когда"]],
            hide_index=True,
        )
