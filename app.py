"""NOSTOS Streamlit application entry point."""

from __future__ import annotations

from datetime import datetime, timezone
from time import perf_counter

import pandas as pd
import streamlit as st

from src.diagnostics import EVENT_COLUMNS, evaluate_crew_health
from src.telemetry import append_update, generate_initial_history, simulate_update
from src.ui_components import METRICS, render_alerts, render_astronaut_cards, render_metric_groups, render_trend


st.set_page_config(page_title="NOSTOS | Salud de la tripulación", page_icon="🛰️", layout="wide")


@st.dialog("Estado de la tripulación", width="large")
def show_crew_status_dialog(events: pd.DataFrame, statuses: pd.DataFrame) -> None:
    if events.empty:
        nominal = int((statuses["status"] == "normal").sum()) if not statuses.empty else 0
        if nominal == 3:
            st.success("No hay alertas activas. Todos los tripulantes están en nivel nominal.")
        else:
            st.info("No hay alertas activas en este momento.")
        return
    st.caption(f"{len(events)} alerta(s) activa(s)")
    alert_columns = st.columns(2)
    for index, (_, event) in enumerate(events.iterrows()):
        severity = str(event.get("severity", ""))
        astronaut_id = event.get("astronaut_id", "Tripulante desconocido")
        area = event.get("health_area", "Área sin especificar")
        parameter = str(event.get("parameter", "Parámetro sin especificar"))
        detected_value = event.get("detected_value", "—")
        unit = event.get("unit", "")
        value_text = f"{detected_value} {unit}".strip()
        if parameter == "patron_resistencia_musculo":
            parameter_label = "Ejercicio resistivo y masa muscular estimada"
            raw_value = str(detected_value)
            resistance_part, _, muscle_part = raw_value.partition("/")
            resistance_minutes = resistance_part.replace("Res:", "").replace("m", "").strip()
            muscle_change = muscle_part.replace("Musc:", "").replace("%", "").strip()
            value_text = (
                f"{resistance_minutes} min/24 h de ejercicio resistivo · "
                f"cambio muscular: {muscle_change}%"
            )
        else:
            parameter_label = METRICS.get(parameter, (parameter.replace("_", " ").capitalize(), ""))[0]
        with alert_columns[index % 2], st.container(border=True):
            st.markdown(f"**{astronaut_id}**")
            st.caption(f"Área: {area}")
            st.caption(f"Parámetro: {parameter_label} · Valor: {value_text}")
            if severity == "Rojo":
                st.error("🔴 Gravedad: Crítica")
            elif severity == "Amarillo":
                st.warning("🟡 Gravedad: Precaución")
            else:
                st.info(f"Gravedad: {severity or 'Sin especificar'}")

with st.sidebar:
    st.header("Configuración de misión")
    environment_label = st.selectbox("Ambiente", ("Estación espacial", "Base en Marte"))
    environment = "station" if environment_label == "Estación espacial" else "mars"
    scenario_label = st.selectbox("Escenario", ("Reposo", "Actividad física / EVA", "Emergencia simulada"))
    scenario = {"Reposo": "rest", "Actividad física / EVA": "eva", "Emergencia simulada": "emergency"}[scenario_label]
    refresh_seconds = st.selectbox("Frecuencia de actualización", (5, 15, 30, 60), index=2, format_func=lambda value: f"Cada {value} s")
    st.caption(f"Configuración: `{environment}` · `{scenario}` · {refresh_seconds} s")

if "telemetry_history_by_environment" not in st.session_state:
    st.session_state.telemetry_history_by_environment = {}
if "telemetry_update_number" not in st.session_state:
    st.session_state.telemetry_update_number = 0
if "diagnostic_events_by_environment" not in st.session_state:
    st.session_state.diagnostic_events_by_environment = {}
if "diagnostic_status_by_environment" not in st.session_state:
    st.session_state.diagnostic_status_by_environment = {}
if "current_events_by_environment" not in st.session_state:
    st.session_state.current_events_by_environment = {}
if "mission_start_utc" not in st.session_state:
    st.session_state.mission_start_utc = datetime.now(timezone.utc)
if "last_telemetry_at_utc" not in st.session_state:
    st.session_state.last_telemetry_at_utc = None
if "telemetry_latency_seconds" not in st.session_state:
    st.session_state.telemetry_latency_seconds = None

# Keep a separate session history per environment. Switching environments
# restores its previous readings instead of resetting the chart history.
if environment not in st.session_state.telemetry_history_by_environment:
    st.session_state.telemetry_history_by_environment[environment] = generate_initial_history(
        environment=environment,
    )
if environment not in st.session_state.diagnostic_events_by_environment:
    st.session_state.diagnostic_events_by_environment[environment] = pd.DataFrame(columns=EVENT_COLUMNS)
if environment not in st.session_state.diagnostic_status_by_environment:
    st.session_state.diagnostic_status_by_environment[environment] = pd.DataFrame(
        columns=["astronaut_id", "status", "status_label"]
    )
if environment not in st.session_state.current_events_by_environment:
    st.session_state.current_events_by_environment[environment] = pd.DataFrame(columns=EVENT_COLUMNS)

if "active_view" not in st.session_state:
    st.session_state.active_view = "dashboard"
if "selected_astronaut" not in st.session_state:
    st.session_state.selected_astronaut = None


@st.fragment(run_every=1)
def render_telemetry_header() -> None:
    now = datetime.now(timezone.utc)
    elapsed = int((now - st.session_state.mission_start_utc).total_seconds())
    days, remainder = divmod(elapsed, 86_400)
    hours, remainder = divmod(remainder, 3_600)
    minutes, seconds = divmod(remainder, 60)
    met = f"{days:02d}d {hours:02d}h {minutes:02d}m {seconds:02d}s"

    last_update = st.session_state.last_telemetry_at_utc
    is_online = last_update is not None and (now - last_update).total_seconds() <= max(refresh_seconds * 2.5, 10)
    link_text = "ONLINE 🟢" if is_online else "OFFLINE 🔴"
    latency = st.session_state.telemetry_latency_seconds
    latency_text = f"{latency:.2f}s" if latency is not None else "—"

    current_events = st.session_state.current_events_by_environment[environment]
    current_status = st.session_state.diagnostic_status_by_environment[environment]
    active_alerts = len(current_events)
    if active_alerts:
        alert_label = "ALERTA ACTIVA" if active_alerts == 1 else "ALERTAS ACTIVAS"
        crew_summary = f"{active_alerts} {alert_label}"
    else:
        nominal = int((current_status["status"] == "normal").sum()) if not current_status.empty else 0
        crew_summary = f"{nominal}/3 TRIPULANTES NOMINALES" if nominal else "EVALUANDO TRIPULACIÓN"

    with st.container(border=True):
        left, center, right = st.columns([2, 2, 2])
        with left:
            st.markdown("### 🛰️ NOSTOS")
            st.caption("Sistema de monitoreo de salud para misiones espaciales · Simulación asistencial")
            st.caption(f"TELEMETRY LINK: {link_text} · Latencia: {latency_text}")
        with center:
            st.markdown(f"**MISSION ELAPSED TIME**  \n`MET: {met}`")
            st.caption(f"{now.strftime('%H:%M:%S')} UTC")
        with right:
            st.markdown("**RESUMEN DE TRIPULACIÓN**")
            if active_alerts:
                button_label = f"{crew_summary} · VER DETALLE"
            elif current_status.empty:
                button_label = f"{crew_summary} · VER ESTADO"
            else:
                button_label = f"{crew_summary} · VER ESTADO"
            if st.button(button_label, key=f"crew_status_{environment}", type="primary", use_container_width=True):
                show_crew_status_dialog(current_events, current_status)


render_telemetry_header()


@st.fragment(run_every=refresh_seconds)
def render_live_dashboard() -> None:
    history = st.session_state.telemetry_history_by_environment[environment]
    st.session_state.telemetry_update_number += 1
    started_at = perf_counter()
    update = simulate_update(
        history,
        environment=environment,
        scenario=scenario,
        seed=st.session_state.telemetry_update_number,
    )
    diagnostic_result = evaluate_crew_health(update, history, environment)
    st.session_state.telemetry_latency_seconds = perf_counter() - started_at
    st.session_state.last_telemetry_at_utc = datetime.now(timezone.utc)
    event_history = st.session_state.diagnostic_events_by_environment[environment]
    current_events = diagnostic_result["events_df"]
    if not current_events.empty:
        event_history = pd.concat(
            [event_history, current_events], ignore_index=True,
        )
        event_history = event_history.drop_duplicates(subset=["event_id"], keep="last")
    st.session_state.diagnostic_events_by_environment[environment] = event_history
    st.session_state.current_events_by_environment[environment] = current_events
    status_labels = {"Verde": ("normal", "Normal"), "Amarillo": ("precaution", "Precaución"), "Rojo": ("critical", "Crítico")}
    status_rows = []
    for astronaut_id, result in diagnostic_result["astronaut_status"].items():
        status, label = status_labels.get(result["overall_status"], ("unassessed", "Sin evaluación"))
        status_rows.append({"astronaut_id": astronaut_id, "status": status, "status_label": label})
    status_frame = pd.DataFrame(status_rows, columns=["astronaut_id", "status", "status_label"])
    st.session_state.diagnostic_status_by_environment[environment] = status_frame

    history = append_update(history, update)
    st.session_state.telemetry_history_by_environment[environment] = history

    readings = update
    status = st.session_state.diagnostic_status_by_environment[environment]
    if st.session_state.active_view == "dashboard":
        selected = render_astronaut_cards(st, readings, status, history, current_events)
        if selected is not None:
            st.session_state.selected_astronaut = selected
            st.session_state.active_view = "detail"
            st.rerun()
    else:
        selected_astronaut = st.session_state.selected_astronaut
        if st.button("← Volver al panel de tripulación"):
            st.session_state.active_view = "dashboard"
            st.rerun()

        st.title(f"Ficha de {selected_astronaut}")
        st.caption("Especialista de Misión | Módulo: Habitación Orbital | Días en microgravedad: 42")
        selected_rows = readings.loc[readings["astronaut_id"] == selected_astronaut]
        current_reading = selected_rows.iloc[-1] if not selected_rows.empty else None
        astronaut_events = current_events.loc[current_events["astronaut_id"] == selected_astronaut]
        selected_status = status.loc[status["astronaut_id"] == selected_astronaut]
        if not selected_status.empty:
            current_status = selected_status.iloc[-1]
            if current_status["status"] == "critical":
                st.error(f"Estado: {current_status['status_label']}")
            elif current_status["status"] == "precaution":
                st.warning(f"Estado: {current_status['status_label']}")
            else:
                st.success(f"Estado: {current_status['status_label']}")

        render_metric_groups(st, current_reading, astronaut_events, environment)
        selected_metric = st.selectbox(
            "Indicador para la tendencia",
            tuple(METRICS),
            format_func=lambda key: METRICS[key][0],
        )
        render_trend(st, history, selected_astronaut, selected_metric, scenario)
        astronaut_events = event_history.loc[event_history["astronaut_id"] == selected_astronaut]
        render_alerts(st, astronaut_events)


render_live_dashboard()

st.divider()
st.caption("Telemetría simulada actualizada automáticamente; los valores no son mediciones clínicas.")
st.caption("Las mediciones son simuladas. NOSTOS es una herramienta educativa y no sustituye al personal médico.")
