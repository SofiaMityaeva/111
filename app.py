"""ТикетРоутер — точка входа. Запуск: streamlit run app.py"""

from __future__ import annotations

import streamlit as st

st.set_page_config(page_title="ТикетРоутер", page_icon="📨", layout="wide")

pages = [
    st.Page("views/home.py", title="Старт", icon="🏠", default=True),
    st.Page("views/new_ticket.py", title="Новое обращение", icon="✉️"),
    st.Page("views/queue.py", title="Очередь", icon="📋"),
    st.Page("views/dashboard.py", title="Дашборд SLA", icon="📊"),
    st.Page("views/model_page.py", title="Модель", icon="🧠"),
]

st.navigation(pages).run()
