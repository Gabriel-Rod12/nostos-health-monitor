"""NOSTOS Streamlit application entry point."""

from __future__ import annotations

import streamlit as st

from src.telemetry import append_update, generate_initial_history, simulate_update
from src.ui_components import ASTRONAUT_IDS, METRICS, render_crew_overview, render_metric_groups, render_trend


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

# Keep a separate session history per environment. Switching environments
# restores its previous readings instead of resetting the chart history.
if environment not in st.session_state.telemetry_history_by_environment:
    st.session_state.telemetry_history_by_environment[environment] = generate_initial_history(
        environment=environment,
    )

selected_astronaut = st.selectbox("Consultar tripulante", ASTRONAUT_IDS)
selected_metric = st.selectbox(
    "Indicador para la tendencia",
    tuple(METRICS),
    format_func=lambda key: METRICS[key][0],
)


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
    history = append_update(history, update)
    st.session_state.telemetry_history_by_environment[environment] = history

    readings = update
    st.caption("Telemetría simulada actualizada automáticamente; los valores no son mediciones clínicas.")
    render_crew_overview(st, readings)
    st.divider()
    selected_rows = readings.loc[readings["astronaut_id"] == selected_astronaut]
    current_reading = selected_rows.iloc[-1] if not selected_rows.empty else None
    render_metric_groups(st, current_reading)
    render_trend(st, history, selected_astronaut, selected_metric)
    st.subheader("Centro de alertas")
    st.info("Las lecturas se están generando. El centro de alertas se activará al integrar el motor de diagnóstico.")


render_live_dashboard()

st.caption("NOSTOS es una simulación educativa; no es un dispositivo médico ni sustituye al personal médico.")
