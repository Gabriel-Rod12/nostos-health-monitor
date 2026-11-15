"""Reusable Streamlit components for the NOSTOS monitoring dashboard."""

from __future__ import annotations

from typing import Any

import pandas as pd
from src.diagnostics import COUNTERMEASURE_TARGETS


ASTRONAUT_IDS = ("AST-01", "AST-02", "AST-03")
METRICS = {
    "heart_rate_bpm": ("Frecuencia cardíaca", " bpm"),
    "spo2_pct": ("SpO₂", "%"),
    "temperature_c": ("Temperatura", " °C"),
    "systolic_bp_mmhg": ("Presión sistólica", " mmHg"),
    "diastolic_bp_mmhg": ("Presión diastólica", " mmHg"),
    "activity_score_0_100": ("Actividad", " / 100"),
    "exercise_minutes_24h": ("Ejercicio", " min"),
    "resistance_training_minutes_24h": ("Entrenamiento resistivo", " min"),
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


def _format_telemetry_time(value: Any) -> str:
    timestamp = pd.to_datetime(value, utc=True, errors="coerce")
    if pd.isna(timestamp):
        return "Sin datos"
    now = pd.Timestamp.now(tz="UTC")
    age_seconds = max(0, int((now - timestamp).total_seconds()))
    if age_seconds < 2:
        age = "ahora"
    elif age_seconds < 60:
        age = f"hace {age_seconds}s"
    elif age_seconds < 3_600:
        age = f"hace {age_seconds // 60}m"
    else:
        age = f"hace {age_seconds // 3_600}h"
    return f"Última telemetría: {timestamp.strftime('%H:%M:%S')} UTC ({age})"


def _metric_range(metric: str, scenario: str) -> str:
    if metric == "heart_rate_bpm":
        return "Rango EVA: 75–175 bpm (operativo)" if scenario == "eva" else "Rango reposo: 50–90 bpm"
    if metric == "spo2_pct":
        return "Rango de referencia: 95–100%"
    if metric == "temperature_c":
        upper = "37.6" if scenario == "eva" else "37.2"
        return f"Rango: 36.1–{upper} °C"
    if metric == "systolic_bp_mmhg":
        return "Rango EVA: 90–160 mmHg (operativo)" if scenario == "eva" else "Rango reposo: 90–120 mmHg"
    if metric == "diastolic_bp_mmhg":
        return "Rango de referencia: 60–80 mmHg"
    return ""


def _metric_trend(history: pd.DataFrame, astronaut_id: str, metric: str) -> str:
    series = history.loc[history["astronaut_id"] == astronaut_id, metric].dropna().tail(2)
    if len(series) < 2:
        return "● Sin tendencia"
    change = float(series.iloc[-1]) - float(series.iloc[-2])
    if abs(change) < 0.05:
        return "● Estable"
    arrow = "▲" if change > 0 else "▼"
    return f"{arrow} {change:+.1f}"


def _render_card_metric(
    st: Any,
    *,
    label: str,
    value: Any,
    suffix: str,
    trend: str,
    reference: str,
    severity: str | None,
) -> None:
    color = {"Rojo": "#ff4b4b", "Amarillo": "#f4b942"}.get(severity, "#e8edf7")
    formatted = _format_value(value, suffix)
    trend_display = f"{trend} {suffix.strip()}" if trend.startswith(("▲", "▼")) else trend
    trend_color = "#36c98f" if trend.startswith("▲") else "#ff4b4b" if trend.startswith("▼") else "#bdc8d6"
    st.markdown(
        f"""
        <div style="padding: 0.2rem 0 0.45rem 0; min-height: 5.1rem;">
          <div style="font-size: 0.78rem; color: #aab7c8;">{label}</div>
          <div style="font-size: 1.55rem; line-height: 1.8rem; font-weight: 650; color: {color};">{formatted}</div>
          <div style="font-size: 0.72rem; color: {trend_color};">{trend_display}</div>
          <div style="font-size: 0.68rem; color: #8493a7;">{reference}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


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
    history: pd.DataFrame,
    current_events: pd.DataFrame,
) -> str | None:
    """Render a three-column crew overview and return the opened profile ID."""
    st.subheader("Tripulación")
    card_columns = st.columns(3)
    for card_column, astronaut_id in zip(card_columns, ASTRONAUT_IDS):
        member = readings.loc[readings["astronaut_id"] == astronaut_id]
        row = member.iloc[-1] if not member.empty else None
        status_rows = astronaut_status.loc[astronaut_status["astronaut_id"] == astronaut_id]
        status = status_rows.iloc[-1] if not status_rows.empty else None
        alerts = current_events.loc[current_events["astronaut_id"] == astronaut_id] if not current_events.empty else current_events

        with card_column, st.container(border=True):
            heading, state = st.columns([3, 2])
            with heading:
                st.markdown(f"### {astronaut_id}")
                st.caption(_format_telemetry_time(row.get("timestamp")) if row is not None else "Última telemetría: Sin datos")
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
                ("diastolic_bp_mmhg", "Presión diastólica", " mmHg"),
            )
            metric_columns = st.columns(2)
            for index, (key, label, suffix) in enumerate(quick_metrics):
                matching_alert = alerts.loc[alerts["parameter"] == key] if not alerts.empty else alerts
                severity = matching_alert.iloc[-1]["severity"] if not matching_alert.empty else None
                value = row.get(key) if row is not None else None
                target_column = metric_columns[index % 2]
                with target_column:
                    _render_card_metric(
                        st,
                        label=label,
                        value=value,
                        suffix=suffix,
                        trend=_metric_trend(history, astronaut_id, key),
                        reference=_metric_range(key, str(row.get("scenario", "rest")) if row is not None else "rest"),
                        severity=severity,
                    )

            bpm_history = history.loc[
                history["astronaut_id"] == astronaut_id,
                ["timestamp", "heart_rate_bpm"],
            ].tail(24)
            if not bpm_history.empty:
                import plotly.graph_objects as go

                figure = go.Figure(
                    go.Scatter(
                        x=bpm_history["timestamp"],
                        y=bpm_history["heart_rate_bpm"],
                        mode="lines+markers",
                        line={"color": "#42c7d9", "width": 2},
                        marker={"size": 4},
                        hovertemplate="%{x|%d/%m %H:%M}<br>%{y:.0f} bpm<extra></extra>",
                    )
                )
                latest = bpm_history.iloc[-1]
                figure.add_trace(
                    go.Scatter(
                        x=[latest["timestamp"]],
                        y=[latest["heart_rate_bpm"]],
                        mode="markers+text",
                        marker={"color": "#f4b942", "size": 8},
                        text=[f"{latest['heart_rate_bpm']:.0f} BPM"],
                        textposition="middle right",
                        textfont={"color": "#f4b942", "size": 11},
                        hovertemplate="Última lectura: %{y:.0f} bpm<extra></extra>",
                        showlegend=False,
                    )
                )
                figure.update_layout(
                    title={"text": "Tendencia de BPM · últimas 24 lecturas", "font": {"size": 12}},
                    height=125,
                    margin={"l": 4, "r": 58, "t": 30, "b": 4},
                    showlegend=False,
                )
                figure.update_xaxes(visible=False, showgrid=False)
                figure.update_yaxes(visible=False, showgrid=False, zeroline=False)
                st.plotly_chart(figure, use_container_width=True, config={"displayModeBar": False})

            if st.button("Abrir ficha completa", key=f"open_profile_{astronaut_id}", use_container_width=True):
                return astronaut_id
    return None


def _detail_metric_reference(metric: str, environment: str, scenario: str) -> str:
    references = {
        "activity_score_0_100": "Indicador 0–100; sin rango clínico validado",
        "muscle_mass_kg": "Estimación BIA; comparar con línea base individual",
        "body_fat_pct": "Referencia operativa simulada: 8–30%",
        "sleep_hours_24h": "Referencia general: 7–9 h/24 h",
        "stress_score_0_10": "Autoinforme; 0–3 óptimo (criterio simulado)",
        "mood_score_0_10": "Autoinforme; 7–10 óptimo (criterio simulado)",
    }
    if metric in references:
        return references[metric]
    if metric == "exercise_minutes_24h":
        target = COUNTERMEASURE_TARGETS[environment][metric]
        return f"Objetivo operativo simulado: ≥{target:g} min/24 h"
    if metric == "resistance_training_minutes_24h":
        target = COUNTERMEASURE_TARGETS[environment][metric]
        return f"Objetivo operativo simulado: ≥{target:g} min/24 h"
    return _metric_range(metric, scenario)


def render_metric_groups(
    st: Any,
    reading: pd.Series | None,
    events: pd.DataFrame | None = None,
    environment: str = "station",
) -> None:
    """Render contract metrics in bordered groups with diagnostic context."""
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
        with st.container(border=True):
            st.markdown(f"#### {title}")
            columns = st.columns(len(keys))
            for column, key in zip(columns, keys):
                label, suffix = METRICS[key]
                value = reading.get(key) if reading is not None else None
                column.metric(label, _format_value(value, suffix))
                scenario = str(reading.get("scenario", "rest")) if reading is not None else "rest"
                reference = _detail_metric_reference(key, environment, scenario)
                matching = (
                    events.loc[events["parameter"] == key]
                    if events is not None and not events.empty and "parameter" in events.columns
                    else pd.DataFrame()
                )
                if not matching.empty:
                    severity = str(matching.iloc[-1]["severity"])
                    if severity == "Rojo":
                        color, state = "#ff4b4b", "Crítico"
                    else:
                        color, state = "#f4b942", "Precaución"
                    subtitle = f"{state} · {reference}"
                elif key in {"activity_score_0_100", "muscle_mass_kg"}:
                    color, subtitle = "#aab7c8", reference
                else:
                    color, subtitle = "#36c98f", f"Normal · {reference}"
                column.markdown(
                    f'<div style="font-size:0.72rem;color:{color};margin-top:-0.55rem;">{subtitle}</div>',
                    unsafe_allow_html=True,
                )
    st.caption("Masa muscular y grasa corporal son estimaciones simuladas. Estrés y ánimo son autopercepciones; no constituyen diagnósticos.")


def render_trend(
    st: Any,
    history: pd.DataFrame,
    astronaut_id: str,
    metric: str,
    scenario: str | None = None,
) -> None:
    """Render an available time series, or an explicit empty state."""
    st.markdown("#### Tendencia")
    if history.empty or metric not in history.columns:
        st.info("La tendencia aparecerá cuando exista historial para este indicador.")
        return

    member_history = history.loc[history["astronaut_id"] == astronaut_id].copy()
    if metric == "heart_rate_bpm" and scenario is not None:
        member_history = member_history.loc[member_history["scenario"] == scenario]
    if member_history.empty:
        st.info("No hay historial disponible para este tripulante.")
        return

    import plotly.express as px

    figure = px.line(member_history, x="timestamp", y=metric, markers=True, title=METRICS[metric][0])
    range_data = _chart_reference_band(member_history, metric, scenario or "rest", str(member_history["environment"].iloc[-1]))
    if range_data is not None:
        lower, upper, range_label, band_color = range_data
        figure.add_hrect(
            y0=lower,
            y1=upper,
            fillcolor=band_color,
            opacity=0.11,
            line_width=0,
            layer="below",
        )
        figure.add_hline(y=lower, line_dash="dot", line_color=band_color, opacity=0.9)
        figure.add_hline(y=upper, line_dash="dot", line_color=band_color, opacity=0.9)
        figure.update_layout(title=f"{METRICS[metric][0]} · {range_label}")
    elif metric == "muscle_mass_kg":
        baseline = float(member_history["muscle_mass_kg"].head(3).mean())
        lower = baseline * 0.98
        upper = baseline * 1.02
        caution = baseline * 0.98
        critical = baseline * 0.95
        figure.add_hrect(y0=lower, y1=upper, fillcolor="#36c98f", opacity=0.10, line_width=0, layer="below")
        figure.add_hline(y=upper, line_dash="dot", line_color="#36c98f", opacity=0.9)
        figure.add_hline(y=baseline, line_dash="dot", line_color="#36c98f", opacity=0.9)
        figure.add_hline(y=caution, line_dash="dot", line_color="#f4b942", opacity=0.9)
        figure.add_hline(y=critical, line_dash="dot", line_color="#ff4b4b", opacity=0.9)
        figure.update_layout(title=f"{METRICS[metric][0]} · base y umbrales personales simulados")
    else:
        figure.update_layout(title=f"{METRICS[metric][0]} · sin rango seguro validado")
    figure.update_layout(margin=dict(l=10, r=10, t=45, b=10), height=300)
    st.plotly_chart(figure, use_container_width=True)


def _chart_reference_band(
    history: pd.DataFrame,
    metric: str,
    scenario: str,
    environment: str,
) -> tuple[float, float, str, str] | None:
    """Return the visualization band and label for an existing project criterion."""
    if metric == "heart_rate_bpm":
        low, high = (75, 175) if scenario == "eva" else (50, 90)
        label = "rango EVA operativo simulado" if scenario == "eva" else "rango operativo en reposo"
        return low, high, f"{label}: {low}–{high} bpm", "#36c98f"
    if metric == "spo2_pct":
        return 95, 100, "referencia: 95–100%", "#36c98f"
    if metric == "temperature_c":
        high = 37.6 if scenario == "eva" else 37.2
        return 36.1, high, f"referencia: 36.1–{high:.1f} °C", "#36c98f"
    if metric == "systolic_bp_mmhg":
        high = 160 if scenario == "eva" else 120
        label = "objetivo EVA simulado" if scenario == "eva" else "referencia en reposo"
        return 90, high, f"{label}: 90–{high} mmHg", "#36c98f"
    if metric == "diastolic_bp_mmhg":
        return 60, 80, "referencia: 60–80 mmHg", "#36c98f"
    if metric == "activity_score_0_100":
        return 0, 100, "escala 0–100 · no es un rango seguro", "#8292a6"
    if metric == "exercise_minutes_24h":
        target = COUNTERMEASURE_TARGETS[environment][metric]
        return target, 180, f"meta operativa simulada: ≥{target:g} min/24 h", "#36c98f"
    if metric == "resistance_training_minutes_24h":
        target = COUNTERMEASURE_TARGETS[environment][metric]
        return target, 120, f"meta operativa simulada: ≥{target:g} min/24 h", "#36c98f"
    if metric == "body_fat_pct":
        baseline = float(history["body_fat_pct"].head(3).mean())
        low = max(8.0, baseline - 2.5)
        high = min(30.0, baseline + 2.5)
        return low, high, f"ventana personal simulada: {low:.1f}–{high:.1f}%", "#36c98f"
    if metric == "sleep_hours_24h":
        return 7, 9.5, "rango de evaluación: 7–9.5 h/24 h", "#36c98f"
    if metric == "stress_score_0_10":
        return 0, 3, "óptimo operativo simulado: 0–3/10", "#36c98f"
    if metric == "mood_score_0_10":
        return 7, 10, "óptimo operativo simulado: 7–10/10", "#36c98f"
    return None


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

