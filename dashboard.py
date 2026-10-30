"""Дашборд SLA для руководителя поддержки (US-06)."""

from __future__ import annotations

from datetime import timedelta

import plotly.express as px
import streamlit as st

from core.config import (
    LIGHT_AT_RISK,
    LIGHT_ON_TIME,
    LIGHT_OVERDUE,
    LIGHT_RESOLVED_LATE,
    LIGHT_RESOLVED_ON_TIME,
)
from core.db import get_tickets
from core.kpi import at_risk, compute_kpis, light_by_group, violations_by_day
from ui_helpers import TABLE_CONFIG, now, reference, require_tickets, tickets_table

LIGHT_COLORS = {
    LIGHT_RESOLVED_ON_TIME: "#6FA8AE",
    LIGHT_ON_TIME: "#1D6A72",
    LIGHT_AT_RISK: "#E0A526",
    LIGHT_OVERDUE: "#C8473B",
    LIGHT_RESOLVED_LATE: "#E58A7F",
}

require_tickets()
groups, names, rules = reference()
current = now()

st.title("Дашборд SLA")
tickets = get_tickets()

# ---------- Фильтры ----------
first_day = tickets["created_at"].min().date()
today = current.date()
col1, col2 = st.columns([1, 2])
period = col1.date_input(
    "Период поступления",
    value=(max(first_day, today - timedelta(days=13)), today),
    min_value=first_day,
    max_value=today,
    format="DD.MM.YYYY",
)
group_options = sorted(set(groups.values()))
selected_groups = col2.multiselect("Группы", group_options, default=group_options)

if not isinstance(period, tuple) or len(period) != 2:
    st.info("Выберите в календаре начало и конец периода.")
    st.stop()
start, end = period
mask = (
    (tickets["created_at"].dt.date >= start)
    & (tickets["created_at"].dt.date <= end)
    & tickets["group_name"].isin(selected_groups)
)
data = tickets[mask]
if data.empty:
    st.info("За этот период и по этим группам обращений нет — измените фильтры.")
    st.stop()

# ---------- KPI ----------
kpi = compute_kpis(data, current)


def fmt(value, suffix="%"):
    """Число с запятой, как принято в русском тексте: 84,4%."""
    return "—" if value is None else f"{value:g}".replace(".", ",") + suffix


row1 = st.columns(3)
row1[0].metric("Решено в срок", fmt(kpi["share_on_time"]), help="Решённые не позже дедлайна / все решённые")
row1[1].metric("Нарушения SLA", fmt(kpi["violation_share"]), help="Решённые с опозданием + открытые просроченные / все обращения")
row1[2].metric("Среднее время до назначения", fmt(kpi["avg_assign_minutes"], " мин"))
row2 = st.columns(3)
row2[0].metric("Назначено автоматически", fmt(kpi["auto_share"]))
row2[1].metric("Переназначения", fmt(kpi["reassign_share"]), help="Автоназначенные, у которых потом сменилась категория")
row2[2].metric("Исправления модели диспетчером", fmt(kpi["correction_share"]), help="Среди обращений, проверенных диспетчером")
st.caption(f"Обращений за период: {kpi['total']}, из них решено: {kpi['resolved']}.")

# ---------- Графики ----------
left, right = st.columns(2)
with left:
    daily = violations_by_day(data, current)
    fig = px.line(
        daily, x="day", y="violation_share", markers=True,
        labels={"day": "День поступления", "violation_share": "Нарушения SLA, %"},
        title="Доля нарушений SLA по дням",
    )
    fig.update_traces(line_color="#C8473B")
    fig.update_layout(yaxis_rangemode="tozero", margin=dict(t=48, b=8))
    st.plotly_chart(fig)
with right:
    by_group = light_by_group(data, current)
    fig = px.bar(
        by_group, x="count", y="group_name", color="sla_light", orientation="h",
        color_discrete_map=LIGHT_COLORS,
        labels={"count": "Обращений", "group_name": "", "sla_light": "SLA"},
        title="Обращения по группам и состоянию SLA",
    )
    fig.update_layout(margin=dict(t=48, b=8), legend_title_text="")
    st.plotly_chart(fig)

# ---------- Под угрозой ----------
st.subheader("Под угрозой")
risky = at_risk(data, current)
if risky.empty:
    st.write("Сейчас нет открытых обращений, у которых осталось меньше 20% времени.")
else:
    st.dataframe(tickets_table(risky, current, names), hide_index=True, column_config=TABLE_CONFIG)

# ---------- Выгрузка ----------
export = tickets_table(data, current, names)
csv = export.to_csv(index=False).encode("utf-8-sig")  # utf-8-sig — чтобы Excel открыл кириллицу
st.download_button(
    "Выгрузить CSV", csv, f"обращения_{start:%Y%m%d}-{end:%Y%m%d}.csv", "text/csv"
)
