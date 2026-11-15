"""NOSTOS Streamlit application entry point."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.diagnostics import EVENT_COLUMNS, evaluate_crew_health
from src.telemetry import append_update, generate_initial_history, simulate_update
from src.ui_components import METRICS, render_alerts, render_astronaut_cards, render_metric_groups, render_trend


st.set_page_config(page_title="NOSTOS | Salud de la tripulación", page_icon="🛰️", layout="wide")
st.title("NOSTOS")
st.caption("Sistema de monitoreo de salud para misiones espaciales · Simulación asistencial")

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

if "active_view" not in st.session_state:
    st.session_state.active_view = "dashboard"
if "selected_astronaut" not in st.session_state:
    st.session_state.selected_astronaut = None


@st.fragment(run_every=refresh_seconds)
def render_live_dashboard() -> None:
    history = st.session_state.telemetry_history_by_environment[environment]
    st.session_state.telemetry_update_number += 1
    update = simulate_update(
        history,
        environment=environment,
        scenario=scenario,
        seed=st.session_state.telemetry_update_number,
    )
    diagnostic_result = evaluate_crew_health(update, history, environment)
    event_history = st.session_state.diagnostic_events_by_environment[environment]
    current_events = diagnostic_result["events_df"]
    if not current_events.empty:
        event_history = pd.concat(
            [event_history, current_events], ignore_index=True,
        )
        event_history = event_history.drop_duplicates(subset=["event_id"], keep="last")
    st.session_state.diagnostic_events_by_environment[environment] = event_history
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
    st.caption("Telemetría simulada actualizada automáticamente; los valores no son mediciones clínicas.")
    status = st.session_state.diagnostic_status_by_environment[environment]
    if st.session_state.active_view == "dashboard":
        selected = render_astronaut_cards(st, readings, status)
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
        selected_rows = readings.loc[readings["astronaut_id"] == selected_astronaut]
        current_reading = selected_rows.iloc[-1] if not selected_rows.empty else None
        selected_status = status.loc[status["astronaut_id"] == selected_astronaut]
        if not selected_status.empty:
            current_status = selected_status.iloc[-1]
            if current_status["status"] == "critical":
                st.error(f"Estado: {current_status['status_label']}")
            elif current_status["status"] == "precaution":
                st.warning(f"Estado: {current_status['status_label']}")
            else:
                st.success(f"Estado: {current_status['status_label']}")

        render_metric_groups(st, current_reading)
        selected_metric = st.selectbox(
            "Indicador para la tendencia",
            tuple(METRICS),
            format_func=lambda key: METRICS[key][0],
        )
        render_trend(st, history, selected_astronaut, selected_metric)
        astronaut_events = event_history.loc[event_history["astronaut_id"] == selected_astronaut]
        render_alerts(st, astronaut_events)


render_live_dashboard()

st.caption("NOSTOS es una simulación educativa; no es un dispositivo médico ni sustituye al personal médico.")
