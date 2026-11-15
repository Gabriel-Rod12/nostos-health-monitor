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
TELEMETRY_SIMULATION_VERSION = 3


@st.dialog("Estado de la tripulación", width="large")
def show_crew_status_dialog(events: pd.DataFrame, statuses: pd.DataFrame) -> None:
    if events.empty:
        attention = statuses.loc[statuses["status"] != "normal"] if not statuses.empty else statuses
        if attention.empty and len(statuses) == 3:
            st.success("No hay alertas activas. Todos los tripulantes están en nivel nominal.")
            return
        if attention.empty:
            st.info("No hay alertas activas en este momento.")
            return
        st.caption("Estado actual de los tripulantes que requieren seguimiento:")
        for _, astronaut in attention.iterrows():
            message = f"{astronaut['astronaut_id']} · {astronaut['status_label']}"
            if astronaut["status"] == "critical":
                st.error(message)
            else:
                st.warning(message)
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
        elif parameter == "support_request":
            parameter_label = "Solicitud de apoyo"
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


@st.dialog("Check-in de bienestar psicológico", width="large")
def show_psychological_checkin() -> None:
    st.caption("Responde según cómo te has sentido durante las últimas 24 horas. No hay respuestas correctas o incorrectas.")
    st.info("Es una autoevaluación de bienestar; no es un diagnóstico ni sustituye una consulta profesional. Una solicitud para hablar ahora se mostrará como petición de apoyo.")
    with st.form("psychological_checkin_form", clear_on_submit=True):
        astronaut_id = st.selectbox("Tripulante", ("AST-01", "AST-02", "AST-03"))
        left, right = st.columns(2)
        with left:
            mood = st.slider("1. ¿Cómo describirías tu estado de ánimo?", 0, 10, 7, help="0 = muy bajo · 10 = muy bueno")
            sleep_quality = st.slider("3. ¿Qué tan reparador fue tu sueño?", 0, 10, 7, help="0 = nada reparador · 10 = muy reparador")
            concentration = st.slider("5. ¿Qué tan fácil te resultó concentrarte?", 0, 10, 7, help="0 = muy difícil · 10 = muy fácil")
            crew_connection = st.slider("7. ¿Qué tan conectado/a te sentiste con la tripulación?", 0, 10, 7, help="0 = muy aislado/a · 10 = muy conectado/a")
            recovery = st.slider("9. Después de un momento difícil, ¿qué tan bien pudiste recuperarte?", 0, 10, 7, help="0 = todavía no me recupero · 10 = me recuperé bien")
        with right:
            stress = st.slider("2. ¿Cuánto estrés has sentido?", 0, 10, 2, help="0 = ninguno · 10 = muy alto")
            energy = st.slider("4. ¿Cuánta energía o descanso sientes que tienes?", 0, 10, 7, help="0 = agotado/a · 10 = muy descansado/a")
            workload = st.slider("6. ¿Qué tan manejable te pareció la carga de trabajo?", 0, 10, 7, help="0 = nada manejable · 10 = totalmente manejable")
            support = st.slider("8. ¿Cuánto apoyo sentiste que tenías disponible?", 0, 10, 7, help="0 = ninguno · 10 = mucho")
        support_request = st.radio(
            "10. ¿Te gustaría hablar con alguien del equipo médico o psicosocial?",
            ("No por ahora", "Sí, en el próximo contacto", "Sí, me gustaría hablar ahora"),
            index=0,
        )
        submitted = st.form_submit_button("Guardar check-in", type="primary", use_container_width=True)

    if submitted:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "astronaut_id": astronaut_id,
            "mood_score_0_10": mood,
            "stress_score_0_10": stress,
            "sleep_quality_0_10": sleep_quality,
            "energy_0_10": energy,
            "concentration_0_10": concentration,
            "workload_manageable_0_10": workload,
            "crew_connection_0_10": crew_connection,
            "support_available_0_10": support,
            "recovery_0_10": recovery,
            "support_request": support_request,
        }
        checkins = st.session_state.psychological_checkins_by_astronaut
        checkins.setdefault(astronaut_id, []).append(entry)
        st.session_state.psychological_checkins_by_astronaut = checkins
        st.success(f"Check-in guardado para {astronaut_id}.")
        st.rerun()


@st.dialog("Respuestas del check-in", width="large")
def show_checkin_responses(entry: dict) -> None:
    timestamp = datetime.fromisoformat(entry["timestamp"].replace("Z", "+00:00"))
    st.caption(f"{entry['astronaut_id']} · {timestamp.strftime('%d/%m/%Y %H:%M:%S')} UTC")
    st.info("Autoinforme de bienestar; no es un diagnóstico clínico.")

    questions = (
        ("Estado de ánimo", "mood_score_0_10"),
        ("Estrés percibido", "stress_score_0_10"),
        ("Calidad del sueño", "sleep_quality_0_10"),
        ("Energía o descanso", "energy_0_10"),
        ("Concentración", "concentration_0_10"),
        ("Carga de trabajo manejable", "workload_manageable_0_10"),
        ("Conexión con la tripulación", "crew_connection_0_10"),
        ("Apoyo disponible", "support_available_0_10"),
        ("Recuperación tras un momento difícil", "recovery_0_10"),
    )
    columns = st.columns(2)
    for index, (label, key) in enumerate(questions):
        with columns[index % 2], st.container(border=True):
            st.caption(label)
            st.markdown(f"### {entry[key]} / 10")
    st.markdown("**¿Desea hablar con el equipo médico o psicosocial?**")
    st.write(entry["support_request"])


with st.sidebar:
    st.header("Configuración de misión")
    environment_label = st.selectbox("Ambiente", ("Estación espacial", "Base en Marte"))
    environment = "station" if environment_label == "Estación espacial" else "mars"
    scenario_label = st.selectbox("Escenario", ("Reposo", "Actividad física / EVA", "Emergencia simulada"))
    scenario = {"Reposo": "rest", "Actividad física / EVA": "eva", "Emergencia simulada": "emergency"}[scenario_label]
    refresh_seconds = st.selectbox("Frecuencia de actualización", (5, 15, 30, 60), index=2, format_func=lambda value: f"Cada {value} s")
    st.caption(f"Configuración: `{environment}` · `{scenario}` · {refresh_seconds} s")

# Discard session readings made by the previous simulator, where selecting
# rest reset 24-hour exercise totals to very low per-scenario values.
if st.session_state.get("telemetry_simulation_version") != TELEMETRY_SIMULATION_VERSION:
    st.session_state.telemetry_history_by_environment = {}
    st.session_state.telemetry_update_number = 0
    st.session_state.diagnostic_events_by_environment = {}
    st.session_state.diagnostic_status_by_environment = {}
    st.session_state.current_events_by_environment = {}
    st.session_state.last_telemetry_at_utc = None
    st.session_state.telemetry_latency_seconds = None
    st.session_state.telemetry_simulation_version = TELEMETRY_SIMULATION_VERSION

if "psychological_checkins_by_astronaut" not in st.session_state:
    st.session_state.psychological_checkins_by_astronaut = {}

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
    statuses = set(current_status["status"]) if not current_status.empty else set()
    severities = set(current_events["severity"].astype(str)) if not current_events.empty else set()
    if "critical" in statuses or "Rojo" in severities:
        button_state = "critical"
    elif "precaution" in statuses or "Amarillo" in severities:
        button_state = "precaution"
    else:
        button_state = "nominal"

    if active_alerts:
        alert_label = "ALERTA ACTIVA" if active_alerts == 1 else "ALERTAS ACTIVAS"
        crew_summary = f"{active_alerts} {alert_label}"
    elif button_state == "critical":
        crew_summary = "TRIPULACIÓN EN ESTADO CRÍTICO"
    elif button_state == "precaution":
        crew_summary = "TRIPULACIÓN EN PRECAUCIÓN"
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
            else:
                button_label = f"{crew_summary} · VER ESTADO"
            st.markdown(
                """
                <style>
                .st-key-crew-alert-nominal button {background:#168447!important;border-color:#168447!important;color:#fff!important}
                .st-key-crew-alert-precaution button {background:#c58a00!important;border-color:#c58a00!important;color:#fff!important}
                .st-key-crew-alert-critical button {background:#c93636!important;border-color:#c93636!important;color:#fff!important}
                </style>
                """,
                unsafe_allow_html=True,
            )
            with st.container(key=f"crew-alert-{button_state}"):
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
    latest_checkins = st.session_state.psychological_checkins_by_astronaut
    for index, reading in update.iterrows():
        astronaut_checkins = latest_checkins.get(str(reading["astronaut_id"]), [])
        if astronaut_checkins:
            latest_checkin = astronaut_checkins[-1]
            update.at[index, "mood_score_0_10"] = latest_checkin["mood_score_0_10"]
            update.at[index, "stress_score_0_10"] = latest_checkin["stress_score_0_10"]

    diagnostic_result = evaluate_crew_health(update, history, environment)
    st.session_state.telemetry_latency_seconds = perf_counter() - started_at
    st.session_state.last_telemetry_at_utc = datetime.now(timezone.utc)
    event_history = st.session_state.diagnostic_events_by_environment[environment]
    current_events = diagnostic_result["events_df"].copy()
    support_request_events = []
    for astronaut_id, astronaut_checkins in latest_checkins.items():
        if astronaut_checkins and astronaut_checkins[-1]["support_request"] == "Sí, me gustaría hablar ahora":
            checkin = astronaut_checkins[-1]
            support_request_events.append({
                "event_id": f"SUPPORT-{astronaut_id}-{checkin['timestamp']}",
                "timestamp": checkin["timestamp"],
                "astronaut_id": astronaut_id,
                "health_area": "Bienestar psicológico",
                "parameter": "support_request",
                "detected_value": checkin["support_request"],
                "unit": "",
                "severity": "Amarillo",
                "reference_criteria": "Solicitud directa del astronauta en el check-in; no es un diagnóstico.",
                "explanation": "El astronauta solicita hablar ahora con el equipo de apoyo.",
                "recommended_action": "Contactar al equipo médico o psicosocial disponible según el protocolo de la misión.",
            })
    if support_request_events:
        current_events = pd.concat(
            [current_events, pd.DataFrame(support_request_events, columns=EVENT_COLUMNS)],
            ignore_index=True,
        )
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
        with st.container(border=True):
            st.subheader("Check-in de bienestar psicológico")
            st.write("Registra cómo se siente un tripulante y si desea recibir apoyo.")
            st.caption("Las respuestas se conservan durante esta sesión. Estado de ánimo y estrés alimentan el motor de seguimiento como autoinforme.")
            if st.button("Iniciar check-in", key="open_psychological_checkin", use_container_width=True):
                show_psychological_checkin()
    else:
        selected_astronaut = st.session_state.selected_astronaut
        if st.button("← Volver al panel de tripulación"):
            st.session_state.active_view = "dashboard"
            st.rerun()

        st.title(f"Ficha de {selected_astronaut}")
        st.caption("Especialista de Misión | Módulo: Habitación Orbital | Días en microgravedad: 42")
        checkins = st.session_state.psychological_checkins_by_astronaut.get(selected_astronaut, [])
        with st.expander(f"Check-ins de bienestar · {len(checkins)}", expanded=False):
            if not checkins:
                st.caption("Este tripulante todavía no tiene check-ins registrados.")
            else:
                for checkin_index, checkin in reversed(list(enumerate(checkins))):
                    timestamp = datetime.fromisoformat(checkin["timestamp"].replace("Z", "+00:00"))
                    date_column, summary_column, button_column = st.columns([2, 2, 1])
                    date_column.write(timestamp.strftime("%d/%m/%Y · %H:%M UTC"))
                    summary_column.caption(
                        f"Ánimo {checkin['mood_score_0_10']}/10 · Estrés {checkin['stress_score_0_10']}/10"
                    )
                    if button_column.button("Ver", key=f"view_checkin_{selected_astronaut}_{checkin_index}"):
                        show_checkin_responses(checkin)

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
