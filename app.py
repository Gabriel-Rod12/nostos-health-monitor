"""NOSTOS Streamlit application entry point."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.ui_components import ASTRONAUT_IDS, METRICS, render_alerts, render_crew_overview, render_metric_groups, render_trend


st.set_page_config(page_title="NOSTOS | Salud de la tripulación", page_icon="🛰️", layout="wide")
st.title("NOSTOS")
st.caption("Sistema de monitoreo de salud para misiones espaciales · Simulación asistencial")

with st.sidebar:
    st.header("Configuración de misión")
    environment_label = st.selectbox("Ambiente", ("Estación espacial", "Base en Marte"))
    environment = "station" if environment_label == "Estación espacial" else "mars"
    scenario_label = st.selectbox("Escenario", ("Reposo", "Actividad física / EVA", "Emergencia simulada"))
    scenario = {"Reposo": "rest", "Actividad física / EVA": "activity", "Emergencia simulada": "emergency"}[scenario_label]
    refresh_seconds = st.selectbox("Frecuencia de actualización", (5, 15, 30, 60), index=2, format_func=lambda value: f"Cada {value} s")
    st.caption(f"Configuración: `{environment}` · `{scenario}` · {refresh_seconds} s")

# These frames are the interface boundary for telemetry and diagnostics. Their
# columns follow the shared data contract; the owning modules can populate them.
readings = pd.DataFrame(columns=["timestamp", "astronaut_id", "environment", "scenario", *METRICS.keys()])
history = readings.copy()
events = pd.DataFrame(columns=[
    "event_id", "timestamp", "astronaut_id", "health_area", "parameter", "value",
    "unit", "severity", "reference_criterion", "message", "recommended_action",
])

st.caption("Las lecturas y alertas se conectarán al integrarse telemetría y diagnóstico.")
render_crew_overview(st, readings)

st.divider()
selected_astronaut = st.selectbox("Consultar tripulante", ASTRONAUT_IDS)
selected_rows = readings.loc[readings["astronaut_id"] == selected_astronaut]
current_reading = selected_rows.iloc[-1] if not selected_rows.empty else None
render_metric_groups(st, current_reading)

selected_metric = st.selectbox(
    "Indicador para la tendencia",
    tuple(METRICS),
    format_func=lambda key: METRICS[key][0],
)
render_trend(st, history, selected_astronaut, selected_metric)
render_alerts(st, events)

st.caption("NOSTOS es una simulación educativa; no es un dispositivo médico ni sustituye al personal médico.")
