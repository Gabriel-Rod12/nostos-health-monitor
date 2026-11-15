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


def render_crew_overview(
    st: Any,
    readings: pd.DataFrame,
    astronaut_status: pd.DataFrame | None = None,
) -> None:
    """Render the current status cards for the three crew members."""
    st.subheader("Estado de la tripulación")
    if readings.empty:
        st.info("Aún no hay lecturas. El panel se completará cuando esté conectado el módulo de telemetría.")
        return

    columns = st.columns(3)
    for column, astronaut_id in zip(columns, ASTRONAUT_IDS):
        member = readings.loc[readings["astronaut_id"] == astronaut_id]
        status_row = None
        if astronaut_status is not None and not astronaut_status.empty:
            matches = astronaut_status.loc[astronaut_status["astronaut_id"] == astronaut_id]
            if not matches.empty:
                status_row = matches.iloc[-1]
        with column:
            st.markdown(f"**{astronaut_id}**")
            if status_row is not None:
                status = status_row["status"]
                label = status_row["status_label"]
                if status == "critical":
                    st.error(f"Estado: {label}")
                elif status == "precaution":
                    st.warning(f"Estado: {label}")
                elif status == "normal":
                    st.success(f"Estado: {label}")
                else:
                    st.info(f"Estado: {label}")
            if member.empty:
                st.caption("Sin lectura disponible")
                continue
            row = member.iloc[-1]
            st.metric("Frecuencia cardíaca", _format_value(row.get("heart_rate_bpm"), " bpm"))
            st.metric("SpO₂", _format_value(row.get("spo2_pct"), "%"))
            st.caption(f"Actualizado: {row.get('timestamp', '—')}")


def render_astronaut_cards(
    st: Any,
    readings: pd.DataFrame,
    astronaut_status: pd.DataFrame,
) -> str | None:
    """Render vertically stacked crew cards and return the opened profile ID."""
    st.subheader("Tripulación")
    for astronaut_id in ASTRONAUT_IDS:
        member = readings.loc[readings["astronaut_id"] == astronaut_id]
        row = member.iloc[-1] if not member.empty else None
        status_rows = astronaut_status.loc[astronaut_status["astronaut_id"] == astronaut_id]
        status = status_rows.iloc[-1] if not status_rows.empty else None

        with st.container(border=True):
            heading, state = st.columns([3, 2])
            with heading:
                st.markdown(f"### {astronaut_id}")
                st.caption(f"Lectura: {row.get('timestamp', '—') if row is not None else 'Sin datos'}")
            with state:
                if status is None:
                    st.info("Sin evaluación")
                elif status["status"] == "critical":
                    st.error(f"Estado: {status['status_label']}")
                elif status["status"] == "precaution":
                    st.warning(f"Estado: {status['status_label']}")
                else:
                    st.success(f"Estado: {status['status_label']}")

            quick_metrics = (
                ("heart_rate_bpm", "Frecuencia cardíaca", " bpm"),
                ("spo2_pct", "SpO₂", "%"),
                ("temperature_c", "Temperatura", " °C"),
                ("systolic_bp_mmhg", "Presión sistólica", " mmHg"),
            )
            metric_columns = st.columns(len(quick_metrics))
            for column, (key, label, suffix) in zip(metric_columns, quick_metrics):
                value = row.get(key) if row is not None else None
                column.metric(label, _format_value(value, suffix))

            if st.button("Abrir ficha completa", key=f"open_profile_{astronaut_id}", use_container_width=True):
                return astronaut_id
    return None


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
        st.success("No hay eventos de atención registrados en esta sesión.")
        return
    display = events.copy()
    if "timestamp" in display.columns:
        display = display.sort_values("timestamp", ascending=False, kind="stable")
    display["severity"] = display["severity"].map({
        "precaution": "Precaución", "critical": "Crítico",
        "Amarillo": "Precaución", "Rojo": "Crítico", "Verde": "Normal",
    }).fillna(display["severity"])
    display = display.rename(columns={
        "event_id": "ID de evento", "timestamp": "Fecha y hora", "astronaut_id": "Tripulante",
        "environment": "Ambiente", "scenario": "Escenario", "health_area": "Área",
        "parameter": "Parámetro", "value": "Valor", "detected_value": "Valor",
        "unit": "Unidad", "severity": "Gravedad", "reference": "Criterio de referencia",
        "reference_criteria": "Criterio de referencia", "message": "Descripción",
        "explanation": "Descripción", "recommendation": "Acción recomendada",
        "recommended_action": "Acción recomendada", "source_url": "Fuente", "experimental": "Experimental",
    })
    preferred = ["ID de evento", "Fecha y hora", "Tripulante", "Ambiente", "Escenario", "Área", "Parámetro", "Valor", "Unidad", "Gravedad", "Descripción", "Acción recomendada", "Criterio de referencia", "Fuente", "Experimental"]
    st.dataframe(display[[column for column in preferred if column in display.columns]], use_container_width=True, hide_index=True)

