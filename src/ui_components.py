"""Reusable Streamlit components for the NOSTOS monitoring dashboard."""

from __future__ import annotations

from typing import Any

import pandas as pd


ASTRONAUT_IDS = ("AST-01", "AST-02", "AST-03")
METRICS = {
    "heart_rate_bpm": ("Frecuencia cardíaca", " bpm"),
    "spo2_pct": ("SpO₂", "%"),
    "temperature_c": ("Temperatura", " °C"),
    "systolic_bp_mmhg": ("Presión sistólica", " mmHg"),
    "diastolic_bp_mmhg": ("Presión diastólica", " mmHg"),
    "activity_score_0_100": ("Actividad", " / 100"),
    "exercise_minutes_24h": ("Ejercicio", " min"),
    "resistance_training_minutes_24h": ("Resistencia", " min"),
    "muscle_mass_kg": ("Masa muscular estimada", " kg"),
    "body_fat_pct": ("Grasa corporal", "%"),
    "sleep_hours_24h": ("Sueño", " h"),
    "stress_score_0_10": ("Estrés percibido", " / 10"),
    "mood_score_0_10": ("Estado de ánimo", " / 10"),
}


def _format_value(value: Any, suffix: str) -> str:
    if pd.isna(value):
        return "—"
    if isinstance(value, (int, float)):
        return f"{value:.1f}{suffix}" if isinstance(value, float) else f"{value}{suffix}"
    return f"{value}{suffix}"


def render_crew_overview(st: Any, readings: pd.DataFrame) -> None:
    """Render the current status cards for the three crew members."""
    st.subheader("Estado de la tripulación")
    if readings.empty:
        st.info("Aún no hay lecturas. El panel se completará cuando esté conectado el módulo de telemetría.")
        return

    columns = st.columns(3)
    for column, astronaut_id in zip(columns, ASTRONAUT_IDS):
        member = readings.loc[readings["astronaut_id"] == astronaut_id]
        with column:
            st.markdown(f"**{astronaut_id}**")
            if member.empty:
                st.caption("Sin lectura disponible")
                continue
            row = member.iloc[-1]
            st.metric("Frecuencia cardíaca", _format_value(row.get("heart_rate_bpm"), " bpm"))
            st.metric("SpO₂", _format_value(row.get("spo2_pct"), "%"))
            st.caption(f"Actualizado: {row.get('timestamp', '—')}")


def render_metric_groups(st: Any, reading: pd.Series | None) -> None:
    """Render all contract metrics for one astronaut, without clinical interpretation."""
    groups = {
        "Sistema cardiovascular": (
            "heart_rate_bpm", "spo2_pct", "temperature_c", "systolic_bp_mmhg", "diastolic_bp_mmhg"
        ),
        "Actividad y composición corporal": (
            "activity_score_0_100", "exercise_minutes_24h", "resistance_training_minutes_24h",
            "muscle_mass_kg", "body_fat_pct"
        ),
        "Bienestar autoinformado": ("sleep_hours_24h", "stress_score_0_10", "mood_score_0_10"),
    }
    for title, keys in groups.items():
        st.markdown(f"#### {title}")
        columns = st.columns(len(keys))
        for column, key in zip(columns, keys):
            label, suffix = METRICS[key]
            value = reading.get(key) if reading is not None else None
            column.metric(label, _format_value(value, suffix))
    st.caption("Masa muscular y grasa corporal son estimaciones simuladas. Estrés y ánimo son autopercepciones; no constituyen diagnósticos.")


def render_trend(st: Any, history: pd.DataFrame, astronaut_id: str, metric: str) -> None:
    """Render an available time series, or an explicit empty state."""
    st.markdown("#### Tendencia")
    if history.empty or metric not in history.columns:
        st.info("La tendencia aparecerá cuando exista historial para este indicador.")
        return

    member_history = history.loc[history["astronaut_id"] == astronaut_id].copy()
    if member_history.empty:
        st.info("No hay historial disponible para este tripulante.")
        return

    import plotly.express as px

    figure = px.line(member_history, x="timestamp", y=metric, markers=True, title=METRICS[metric][0])
    figure.update_layout(margin=dict(l=10, r=10, t=45, b=10), height=300)
    st.plotly_chart(figure, use_container_width=True)


def render_alerts(st: Any, events: pd.DataFrame) -> None:
    """Render diagnostic events supplied by the diagnostics module."""
    st.subheader("Centro de alertas")
    if events.empty:
        st.info("Sin eventos disponibles. Las alertas se mostrarán cuando el motor de diagnóstico esté conectado.")
        return
    st.dataframe(events, use_container_width=True, hide_index=True)

