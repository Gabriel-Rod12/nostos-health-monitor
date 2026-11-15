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


REPORT_GROUPS = {
    "Sistema cardiovascular": (
        "heart_rate_bpm", "spo2_pct", "temperature_c", "systolic_bp_mmhg", "diastolic_bp_mmhg"
    ),
    "Actividad y composición corporal": (
        "activity_score_0_100", "exercise_minutes_24h", "resistance_training_minutes_24h",
        "muscle_mass_kg", "body_fat_pct",
    ),
    "Bienestar autoinformado": ("sleep_hours_24h", "stress_score_0_10", "mood_score_0_10"),
}


def _alert_workflow_key(event: dict) -> str:
    return f"{event.get('event_id', 'EVENTO')}|{event.get('timestamp', '')}"


def _medical_escalation_report(event: dict, workflow: dict, environment: str) -> str:
    detected_value = f"{event.get('detected_value', '—')} {event.get('unit', '')}".strip()
    return "\n".join((
        "NOSTOS · SOLICITUD DE CONTACTO MÉDICO EN TIERRA",
        f"Generado (UTC): {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}",
        f"Tripulante: {event.get('astronaut_id', 'Sin identificar')}",
        f"Ambiente de misión: {environment}",
        f"Área: {event.get('health_area', 'Sin especificar')}",
        f"Parámetro: {event.get('parameter', 'Sin especificar')}",
        f"Valor detectado: {detected_value}",
        f"Gravedad: {event.get('severity', 'Sin especificar')}",
        f"Hora de la alerta (UTC): {event.get('timestamp', 'Sin especificar')}",
        f"Criterio: {event.get('reference_criteria', 'Sin especificar')}",
        f"Descripción: {event.get('explanation', 'Sin descripción')}",
        f"Acción recomendada: {event.get('recommended_action', 'Seguir el protocolo de misión.')}",
        f"Apoyo de tripulación: {workflow.get('crew_member', 'No registrado')}",
        f"Nota de seguimiento: {workflow.get('note', 'Se solicita contacto y evaluación del equipo médico en tierra.')}",
        "",
        "Este reporte se generó desde una simulación asistencial de NOSTOS y requiere revisión del equipo médico.",
    ))


def render_alert_action_content(event: dict, environment: str) -> None:
    workflow_key = _alert_workflow_key(event)
    workflow_by_environment = st.session_state.alert_followups_by_environment
    workflow = workflow_by_environment[environment].setdefault(
        workflow_key, {"status": "open"}
    )
    severity = str(event.get("severity", ""))
    astronaut_id = str(event.get("astronaut_id", "Tripulante"))
    value = f"{event.get('detected_value', '—')} {event.get('unit', '')}".strip()

    st.markdown(f"**{astronaut_id} · {event.get('health_area', 'Área sin especificar')}**")
    st.caption(f"Parámetro: {event.get('parameter', 'Sin especificar')} · Valor: {value}")
    if severity in {"Rojo", "critical"}:
        st.error(f"Gravedad: crítica · {event.get('reference_criteria', '')}")
        st.warning("Sigue el protocolo de emergencia de la misión y solicita apoyo médico de inmediato; no esperes a resolver una alerta crítica por cuenta propia.")
    elif severity in {"Amarillo", "precaution"}:
        st.warning(f"Gravedad: precaución · {event.get('reference_criteria', '')}")
    else:
        st.info(f"Gravedad: {severity or 'Sin especificar'}")

    st.markdown("#### Qué puede hacer el astronauta")
    st.write(event.get("recommended_action") or "Seguir las indicaciones operativas de la misión.")
    if event.get("explanation"):
        st.caption(str(event["explanation"]))
    st.caption("NOSTOS ofrece orientación simulada; las decisiones clínicas corresponden al personal médico.")

    if workflow["status"] == "medical_report_ready":
        st.warning("Solicitud registrada. El informe está preparado para entregarlo al equipo médico en tierra; esta aplicación no tiene un canal conectado para transmitirlo automáticamente.")
        report_text = _medical_escalation_report(event, workflow, environment)
        safe_event_id = "".join(
            character if character.isalnum() or character in "-_" else "-"
            for character in str(event.get("event_id", "alerta"))
        )
        st.download_button(
            "Descargar informe para medicina en tierra",
            data=report_text,
            file_name=f"NOSTOS-{astronaut_id}-{safe_event_id}-medicina-tierra.txt",
            mime="text/plain",
            use_container_width=True,
        )
        return

    if workflow["status"] == "resolved":
        st.success("Seguimiento marcado como resuelto por la tripulación.")
        return

    if severity in {"Rojo", "critical"}:
        with st.form(f"critical_escalation_form_{workflow_key}"):
            note = st.text_area("Nota para medicina en tierra", placeholder="Describe la situación y el contacto solicitado.")
            escalate = st.form_submit_button("Preparar reporte médico urgente", type="primary", use_container_width=True)
        if escalate:
            workflow.update(
                status="medical_report_ready",
                note=note.strip() or "Alerta crítica: se solicita contacto médico inmediato.",
                updated_at=datetime.now(timezone.utc).isoformat(),
            )
            st.rerun(scope="fragment")
        return

    if workflow["status"] == "open":
        if st.button("Marcar resuelta por el astronauta", key=f"resolve_self_{workflow_key}", use_container_width=True):
            workflow.update(status="resolved", updated_at=datetime.now(timezone.utc).isoformat())
            st.rerun(scope="fragment")
        if st.button("No se resolvió · solicitar apoyo de la crew", key=f"request_crew_{workflow_key}", use_container_width=True):
            workflow.update(status="crew_needed", updated_at=datetime.now(timezone.utc).isoformat())
            st.rerun(scope="fragment")

    elif workflow["status"] == "crew_needed":
        crew_options = tuple(member for member in ("AST-01", "AST-02", "AST-03") if member != astronaut_id)
        crew_member = st.selectbox("Tripulante que apoyará", crew_options, key=f"crew_assignee_{workflow_key}")
        if st.button("Registrar solicitud de apoyo", key=f"assign_crew_{workflow_key}", type="primary", use_container_width=True):
            workflow.update(status="crew_assigned", crew_member=crew_member, updated_at=datetime.now(timezone.utc).isoformat())
            st.rerun(scope="fragment")

    elif workflow["status"] == "crew_assigned":
        st.info(f"Se registró apoyo de {workflow.get('crew_member', 'otro tripulante')}.")
        if st.button("La crew resolvió la alerta", key=f"resolve_crew_{workflow_key}", use_container_width=True):
            workflow.update(status="resolved", updated_at=datetime.now(timezone.utc).isoformat())
            st.rerun(scope="fragment")
        with st.form(f"ground_escalation_form_{workflow_key}"):
            note = st.text_area("Nota para el equipo médico en tierra", placeholder="Describe qué se intentó y qué apoyo se necesita.")
            escalate = st.form_submit_button("Escalar y preparar reporte médico", type="primary", use_container_width=True)
        if escalate:
            workflow.update(
                status="medical_report_ready",
                note=note.strip() or "No se resolvió con el apoyo de la tripulación; se solicita contacto médico.",
                updated_at=datetime.now(timezone.utc).isoformat(),
            )
            st.rerun(scope="fragment")


@st.dialog("Recomendaciones y seguimiento", width="large")
def show_alert_action_dialog(event: dict, environment: str) -> None:
    render_alert_action_content(event, environment)


@st.dialog("Estado de la tripulación", width="large")
def show_crew_status_dialog(
    events: pd.DataFrame,
    statuses: pd.DataFrame,
    environment: str,
) -> None:
    selected_alert = st.session_state.crew_status_selected_alert
    if selected_alert is not None:
        render_alert_action_content(selected_alert["event"], selected_alert["environment"])
        if st.button("← Volver a las alertas", key="back_to_crew_alerts", use_container_width=True):
            st.session_state.crew_status_selected_alert = None
            st.rerun(scope="fragment")
        return

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
            if st.button(
                "Ver recomendaciones",
                key=f"crew_alert_action_{_alert_workflow_key(event.to_dict())}",
                use_container_width=True,
            ):
                st.session_state.crew_status_selected_alert = {
                    "event": event.to_dict(),
                    "environment": environment,
                }
                st.rerun(scope="fragment")


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


def render_astronaut_report(report: dict, astronaut_id: str) -> None:
    """Render a stored, point-in-time health report for one astronaut."""
    period_start = report["period_start"]
    period_end = report["period_end"]
    generated_at = report["generated_at"]
    readings = report["readings"]
    report_events = report["events"]
    period_label = report["period_label"]

    st.markdown(f"### Reporte de salud · {astronaut_id}")
    st.caption(
        f"Periodo: {period_label} · {period_start.strftime('%d/%m/%Y %H:%M')}–"
        f"{period_end.strftime('%d/%m/%Y %H:%M')} UTC · Generado: "
        f"{generated_at.strftime('%d/%m/%Y %H:%M:%S')} UTC"
    )
    summary_columns = st.columns(3)
    summary_columns[0].metric("Lecturas incluidas", len(readings))
    summary_columns[1].metric("Alertas del periodo", len(report_events))
    summary_columns[2].metric("Estado al generar", report["status_label"])

    if readings.empty:
        st.warning("No hay lecturas de telemetría disponibles para este periodo en la sesión actual.")
    else:
        latest_reading = readings.iloc[-1]
        st.caption(
            "Última lectura del periodo: "
            f"{latest_reading['timestamp'].strftime('%d/%m/%Y %H:%M:%S')} UTC · "
            f"Ambiente: {latest_reading['environment']} · Escenario: {latest_reading['scenario']}"
        )
        for group_name, metric_keys in REPORT_GROUPS.items():
            with st.container(border=True):
                st.markdown(f"#### {group_name}")
                summary_rows = []
                for key in metric_keys:
                    if key not in readings.columns:
                        continue
                    label, suffix = METRICS[key]
                    values = pd.to_numeric(readings[key], errors="coerce").dropna()
                    if values.empty:
                        continue
                    summary_rows.append({
                        "Indicador": label,
                        "Último": f"{values.iloc[-1]:.1f}{suffix}",
                        "Promedio": f"{values.mean():.1f}{suffix}",
                        "Mínimo": f"{values.min():.1f}{suffix}",
                        "Máximo": f"{values.max():.1f}{suffix}",
                    })
                if summary_rows:
                    st.dataframe(pd.DataFrame(summary_rows), use_container_width=True, hide_index=True)

        with st.expander("Detalle de todas las lecturas del periodo", expanded=False):
            for group_name, metric_keys in REPORT_GROUPS.items():
                available_keys = [key for key in metric_keys if key in readings.columns]
                st.markdown(f"**{group_name}**")
                detail = readings[["timestamp", "environment", "scenario", *available_keys]].copy()
                detail["timestamp"] = detail["timestamp"].dt.strftime("%d/%m/%Y %H:%M:%S UTC")
                detail = detail.rename(columns={
                    "timestamp": "Fecha UTC",
                    "environment": "Ambiente",
                    "scenario": "Escenario",
                    **{key: METRICS[key][0] for key in available_keys},
                })
                st.dataframe(detail, use_container_width=True, hide_index=True)

    with st.container(border=True):
        st.markdown("#### Alertas registradas en el periodo")
        if report_events.empty:
            st.success("No hay alertas registradas para este astronauta durante el periodo.")
        else:
            columns = [
                ("timestamp", "Fecha UTC"), ("health_area", "Sistema"),
                ("parameter", "Parámetro"), ("detected_value", "Valor"),
                ("severity", "Gravedad"), ("explanation", "Detalle"),
                ("recommended_action", "Acción recomendada"),
            ]
            alert_table = report_events[[key for key, _ in columns]].rename(
                columns=dict(columns)
            )
            st.dataframe(alert_table, use_container_width=True, hide_index=True)

    with st.container(border=True):
        st.markdown("#### Check-in más reciente")
        checkin = report["latest_checkin"]
        if checkin is None:
            st.caption("Este astronauta todavía no tiene check-ins registrados.")
        else:
            checkin_time = datetime.fromisoformat(checkin["timestamp"].replace("Z", "+00:00"))
            st.caption(f"Registrado: {checkin_time.strftime('%d/%m/%Y %H:%M:%S')} UTC")
            checkin_questions = (
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
            checkin_rows = [
                {"Pregunta": label, "Respuesta": f"{checkin[key]} / 10"}
                for label, key in checkin_questions
            ]
            checkin_rows.append({
                "Pregunta": "¿Desea hablar con el equipo médico o psicosocial?",
                "Respuesta": checkin["support_request"],
            })
            st.dataframe(pd.DataFrame(checkin_rows), use_container_width=True, hide_index=True)
            st.caption("El check-in es un autoinforme y no constituye un diagnóstico clínico.")


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
    st.session_state.alert_followups_by_environment = {}
    st.session_state.last_telemetry_at_utc = None
    st.session_state.telemetry_latency_seconds = None
    st.session_state.telemetry_simulation_version = TELEMETRY_SIMULATION_VERSION

if "psychological_checkins_by_astronaut" not in st.session_state:
    st.session_state.psychological_checkins_by_astronaut = {}
if "astronaut_reports" not in st.session_state:
    st.session_state.astronaut_reports = {}

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
if "alert_followups_by_environment" not in st.session_state:
    st.session_state.alert_followups_by_environment = {}
if "crew_status_selected_alert" not in st.session_state:
    st.session_state.crew_status_selected_alert = None
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
if environment not in st.session_state.alert_followups_by_environment:
    st.session_state.alert_followups_by_environment[environment] = {}

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
    link_text = "EN LÍNEA 🟢" if is_online else "FUERA DE LÍNEA 🔴"
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
            st.caption(f"ENLACE DE TELEMETRÍA: {link_text} · Latencia: {latency_text}")
        with center:
            st.markdown(f"**TIEMPO TRANSCURRIDO DE MISIÓN**  \n`MET: {met}`")
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
                    st.session_state.crew_status_selected_alert = None
                    show_crew_status_dialog(current_events, current_status, environment)


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
        selected_alert = render_alerts(
            st,
            astronaut_events,
            st.session_state.alert_followups_by_environment[environment],
        )
        if selected_alert is not None:
            show_alert_action_dialog(selected_alert, environment)

        st.divider()
        st.subheader("Reporte del astronauta")
        period_options = {
            "24 horas": pd.Timedelta(hours=24),
            "1 semana": pd.Timedelta(days=7),
            "1 mes": pd.Timedelta(days=30),
        }
        period_column, button_column = st.columns([2, 1])
        with period_column:
            selected_period = st.selectbox(
                "Periodo del reporte",
                tuple(period_options),
                key=f"report_period_{selected_astronaut}",
            )
        with button_column:
            st.write("")
            generate_report = st.button(
                "Generar reporte",
                key=f"generate_report_{selected_astronaut}",
                type="primary",
                use_container_width=True,
            )

        if generate_report:
            period_end = datetime.now(timezone.utc)
            period_start = period_end - period_options[selected_period]
            astronaut_history = history.loc[
                history["astronaut_id"] == selected_astronaut
            ].copy()
            astronaut_history["timestamp"] = pd.to_datetime(
                astronaut_history["timestamp"], utc=True, errors="coerce"
            )
            astronaut_history = astronaut_history.loc[
                astronaut_history["timestamp"].between(period_start, period_end)
            ].sort_values("timestamp")

            astronaut_report_events = event_history.loc[
                event_history["astronaut_id"] == selected_astronaut
            ].copy()
            if not astronaut_report_events.empty:
                astronaut_report_events["timestamp"] = pd.to_datetime(
                    astronaut_report_events["timestamp"], utc=True, errors="coerce"
                )
                astronaut_report_events = astronaut_report_events.loc[
                    astronaut_report_events["timestamp"].between(period_start, period_end)
                ].sort_values("timestamp", ascending=False)

            latest_status = (
                selected_status.iloc[-1]["status_label"]
                if not selected_status.empty
                else "Sin evaluación"
            )
            astronaut_checkins = st.session_state.psychological_checkins_by_astronaut.get(
                selected_astronaut, []
            )
            st.session_state.astronaut_reports[selected_astronaut] = {
                "period_label": selected_period,
                "period_start": period_start,
                "period_end": period_end,
                "generated_at": period_end,
                "readings": astronaut_history.copy(),
                "events": astronaut_report_events.copy(),
                "latest_checkin": dict(astronaut_checkins[-1]) if astronaut_checkins else None,
                "status_label": latest_status,
            }

        saved_report = st.session_state.astronaut_reports.get(selected_astronaut)
        if saved_report is not None:
            render_astronaut_report(saved_report, selected_astronaut)


render_live_dashboard()

st.divider()
st.caption("Telemetría simulada actualizada automáticamente; los valores no son mediciones clínicas.")
st.caption("Las mediciones son simuladas. NOSTOS es una herramienta educativa y no sustituye al personal médico.")
