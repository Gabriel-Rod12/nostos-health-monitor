"""
Módulo: src/diagnostics.py
Proyecto: NOSTOS — Astronaut Health Monitoring System (NASA Space Apps Challenge 2026)
Responsable: Integrante 2 — Motor de Diagnóstico

Descripción:
    - Evalúa indicadores individuales frente a rangos clínicos (AHA, OMS, NIH, AASM)
      y criterios operativos simulados para Estación Espacial ('station') y Marte ('mars').
    - Analiza historial individual (Z-score, línea base muscular/emocional y deuda de sueño).
    - Cruza variables fisiológicas y conductuales para detectar patrones compuestos.
    - Despliega Protocolos de Acción Rápida paso a paso inmediatamente al activarse una alerta.

Nota metodológica:
    Herramienta de apoyo asistencial y monitoreo simulado. No emite diagnósticos clínicos
    definitivos (ni trastornos psicológicos) ni prescripciones farmacológicas.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd



# ==============================================================================
# 1. CONTRATO DE DATOS Y CONSTANTES
# ==============================================================================

REQUIRED_INPUT_COLUMNS: List[str] = [
    "timestamp",
    "astronaut_id",
    "environment",
    "scenario",
    "heart_rate_bpm",
    "spo2_pct",
    "temperature_c",
    "systolic_bp_mmhg",
    "diastolic_bp_mmhg",
    "activity_score_0_100",
    "exercise_minutes_24h",
    "resistance_training_minutes_24h",
    "muscle_mass_kg",
    "body_fat_pct",
    "sleep_hours_24h",
    "stress_score_0_10",
    "mood_score_0_10",
]

EVENT_COLUMNS: tuple = (
    "event_id",
    "timestamp",
    "astronaut_id",
    "health_area",
    "parameter",
    "detected_value",
    "unit",
    "severity",
    "reference_criteria",
    "explanation",
    "recommended_action",
)

# Columnas del DataFrame de estado por astronauta devuelto por evaluate_readings.
STATUS_COLUMNS: tuple = (
    "astronaut_id",
    "timestamp",
    "environment",
    "scenario",
    "status",
    "overall_status_es",
    "bone_risk_index_simulated",
    "muscle_mass_change_pct",
    "psychological_load_index_simulated",
)

# Mapeo de etiquetas de severidad en español a valores canónicos en inglés.
_SEVERITY_EN: Dict[str, str] = {
    "Verde": "normal",
    "Amarillo": "precaution",
    "Rojo": "critical",
}

SEVERITY_PRIORITY: Dict[str, int] = {
    "Verde": 0,
    "Amarillo": 1,
    "Rojo": 2,
}


@dataclass
class DiagnosticResult:
    """Resultado estructurado de evaluate_readings().

    Attributes:
        astronaut_status: DataFrame con una fila por astronauta y columnas STATUS_COLUMNS.
        events: DataFrame con un evento por alerta y columnas EVENT_COLUMNS.
        crew_summary: Resumen general del estado de la tripulación.
    """

    astronaut_status: pd.DataFrame
    events: pd.DataFrame
    crew_summary: Dict[str, Any]



# ==============================================================================
# 2. BIBLIOTECA DE PROTOCOLOS RÁPIDOS DE ACCIÓN (ASISTENCIALES / OPERATIVOS)
# ==============================================================================

RAPID_ACTION_PROTOCOLS: Dict[str, Dict[str, Any]] = {
    "TAQUICARDIA_REPOSO": {
        "protocol_id": "PROT-CV-01",
        "titulo": "Protocolo Rápido: Frecuencia Cardíaca Elevada en Reposo",
        "area": "Sistema Cardiovascular",
        "pasos_inmediatos": [
            "1. Permanecer en reposo y evitar cambios bruscos de postura.",
            "2. Ingerir 500 ml de agua con electrolitos en los próximos 20 minutos.",
            "3. Verificar temperatura y niveles de CO2 de la cabina; repetir medición en 10 minutos.",
        ],
        "escalamiento": "Si supera 110 lpm durante más de 20 min o hay mareo/molestia torácica, notificar al Flight Surgeon en Tierra.",
    },
    "BRADICARDIA_REPOSO": {
        "protocol_id": "PROT-CV-02",
        "titulo": "Protocolo Rápido: Frecuencia Cardíaca Baja en Reposo",
        "area": "Sistema Cardiovascular",
        "pasos_inmediatos": [
            "1. Verificar correcta colocación y contacto del sensor óptico.",
            "2. Evaluar presencia de mareo, debilidad o fatiga extrema.",
            "3. Repetir lectura en reposo tras 5 minutos.",
        ],
        "escalamiento": "Si es < 45 lpm acompañada de síntomas, reportar de inmediato al Oficial Médico de la Tripulación (CMO).",
    },
    "FLUID_SHIFT_HIPOVOLEMIA": {
        "protocol_id": "PROT-CV-03",
        "titulo": "Protocolo Rápido: Redistribución de Fluidos / Posible Deshidratación",
        "area": "Sistema Cardiovascular",
        "pasos_inmediatos": [
            "1. Aunque no exista sensación de sed, iniciar protocolo de rehidratación oral (500 ml con electrolitos).",
            "2. Evitar movimientos cefálicos rápidos o incorporaciones bruscas.",
            "3. Monitorear pulso y presión arterial cada 15 minutos hasta estabilizar.",
        ],
        "escalamiento": "Reportar en bitácora médica si la presión sistólica permanece < 95 mmHg.",
    },
    "HIPOXEMIA_OXIGENACION": {
        "protocol_id": "PROT-CV-04",
        "titulo": "Protocolo Rápido: Descenso de Saturación de Oxígeno (SpO2)",
        "area": "Sistema Cardiovascular",
        "pasos_inmediatos": [
            "1. Suspender inmediatamente cualquier esfuerzo físico o tarea EVA en curso.",
            "2. Verificar suministro de O2, presión parcial y niveles de CO2 en cabina o traje.",
            "3. Realizar respiraciones lentas y profundas durante 5 minutos y reevaluar SpO2.",
        ],
        "escalamiento": "Si SpO2 <= 90%, activar alerta prioritaria de soporte vital y contactar a control de misión.",
    },
    "ALTERACION_TERMICA": {
        "protocol_id": "PROT-CV-05",
        "titulo": "Protocolo Rápido: Elevación Térmica / Estrés Térmico",
        "area": "Sistema Cardiovascular",
        "pasos_inmediatos": [
            "1. Detener actividad física y regular ventilación/refrigeración del módulo o traje.",
            "2. Si temperatura >= 38.0 °C en reposo, aplicar aislamiento preventivo en módulo asignado.",
            "3. Mantener hidratación fraccionada constante y registrar síntomas asociados.",
        ],
        "escalamiento": "Transmitir telemetría médica prioritaria al médico de vuelo en Tierra.",
    },
    "ALTERACION_PRESION_ARTERIAL": {
        "protocol_id": "PROT-CV-06",
        "titulo": "Protocolo Rápido: Variación de Presión Arterial (PPG)",
        "area": "Sistema Cardiovascular",
        "pasos_inmediatos": [
            "1. Permanecer sentado/sujeto en reposo durante 5 minutos y repetir medición.",
            "2. Confirmar calibración del sensor PPG con tensiómetro de referencia si está disponible.",
            "3. Asegurar hidratación adecuada y evitar esfuerzos intensos hasta normalizar.",
        ],
        "escalamiento": "Escalar al equipo médico si sistólica >= 140 mmHg o < 90 mmHg de forma sostenida.",
    },
    "DEFICIT_CONTRAMEDIDAS_OSEAS": {
        "protocol_id": "PROT-OS-01",
        "titulo": "Protocolo Rápido: Baja Adherencia a Contramedidas Óseas y Musculares",
        "area": "Sistema Óseo",
        "pasos_inmediatos": [
            "1. Programar bloque prioritario de ejercicio resistivo (carga mecánica en tren inferior).",
            "2. Verificar cumplimiento de ingesta calórica, proteica y suplementación nutricional de misión.",
            "3. Registrar sesión completada para actualizar el índice estimado de riesgo.",
        ],
        "escalamiento": "Revisar plan semanal de acondicionamiento físico si el déficit persiste 3 días seguidos.",
    },
    "FATIGA_CIRCADIANA_SUENO": {
        "protocol_id": "PROT-PS-01",
        "titulo": "Protocolo Rápido: Fatiga Cognitiva y Disrupción Circadiana",
        "area": "Salud Mental y Psicológica",
        "pasos_inmediatos": [
            "1. Posponer maniobras críticas o tareas de alta precisión fuera de este turno.",
            "2. Aplicar iluminación enriquecida en azul al inicio de jornada y bloquear luz azul 1 h antes de dormir.",
            "3. Programar bloque protegido de descanso reparador (mínimo 7.5–8.5 h) y siesta breve si es viable.",
        ],
        "escalamiento": "Notificar a control de misión para redistribuir guardias si la deuda de sueño supera 3 días.",
    },
    "ESTRES_OPERATIVO_AGUDO": {
        "protocol_id": "PROT-PS-02",
        "titulo": "Protocolo Rápido: Sobrecarga de Estrés Operativo y Tensión Autonómica",
        "area": "Salud Mental y Psicológica",
        "pasos_inmediatos": [
            "1. Ejecutar pausa de descompresión de 10 minutos con respiración táctica pausada (4s inhalar / 6s exhalar).",
            "2. Revisar y priorizar lista de tareas del turno delegando actividades no esenciales.",
            "3. Verificar hidratación y evitar estimulantes (cafeína) durante las próximas 6 horas.",
        ],
        "escalamiento": "Habilitar consulta privada con el equipo de soporte conductual de misión.",
    },
    "AISLAMIENTO_ANIMO_BAJO": {
        "protocol_id": "PROT-PS-03",
        "titulo": "Protocolo Rápido: Desgaste por Aislamiento, Monotonía y Descenso Emocional",
        "area": "Salud Mental y Psicológica",
        "pasos_inmediatos": [
            "1. Programar actividad recreativa o comida compartida con la tripulación para reforzar cohesión.",
            "2. Habilitar envío/recepción de mensajes multimedia asíncronos con familiares y equipo de apoyo en Tierra.",
            "3. Asignar 30 minutos de autonomía personal y variar estímulos ambientales (música, iluminación, lectura).",
        ],
        "escalamiento": "Seguimiento diario prioritario por el Oficial Médico de la Tripulación (CMO) y soporte en Tierra.",
    },
}


# ==============================================================================
# 3. FUNCIONES AUXILIARES
# ==============================================================================

def _normalize_environment(env: Optional[str]) -> str:
    if not env or not isinstance(env, str):
        return "station"
    clean = env.strip().lower()
    return "mars" if ("mars" in clean or "marte" in clean) else "station"


def _normalize_scenario(scenario: Optional[str]) -> str:
    if not scenario or not isinstance(scenario, str):
        return "reposo"
    clean = scenario.strip().lower()
    if "eva" in clean or "actividad" in clean or "ejercicio" in clean:
        return "actividad_eva"
    if "emergencia" in clean or "emergency" in clean:
        return "emergencia"
    return "reposo"


def _max_severity(current: str, candidate: str) -> str:
    if SEVERITY_PRIORITY.get(candidate, 0) > SEVERITY_PRIORITY.get(current, 0):
        return candidate
    return current


def _build_event(
    timestamp: str,
    astronaut_id: str,
    health_area: str,
    parameter: str,
    detected_value: Any,
    unit: str,
    severity: str,
    reference_criteria: str,
    explanation: str,
    recommended_action: str,
) -> Dict[str, Any]:
    event_id = f"EVT-{astronaut_id}-{parameter.upper()}"
    return {
        "event_id": event_id,
        "timestamp": str(timestamp),
        "astronaut_id": str(astronaut_id),
        "health_area": health_area,
        "parameter": parameter,
        "detected_value": detected_value,
        "unit": unit,
        "severity": severity,
        "reference_criteria": reference_criteria,
        "explanation": explanation,
        "recommended_action": recommended_action,
    }


def validate_input_dataframe(df: pd.DataFrame) -> None:
    if df is None or not isinstance(df, pd.DataFrame):
        raise ValueError("La entrada 'current_df' debe ser un pandas.DataFrame válido.")
    missing = [col for col in REQUIRED_INPUT_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"Faltan columnas obligatorias del contrato de datos: {missing}")


# ==============================================================================
# 4. EVALUACIÓN POR ÁREA DE MONITOREO
# ==============================================================================

def evaluate_cardiovascular(
    row: pd.Series,
    astro_history: pd.DataFrame,
    scenario_type: str,
    environment: str,
) -> Tuple[str, List[Dict[str, Any]], List[str], List[str]]:
    """Evalúa Sistema Cardiovascular y devuelve (estado, eventos, recomendaciones, claves_protocolo)."""
    area = "Sistema Cardiovascular"
    area_status = "Verde"
    events: List[Dict[str, Any]] = []
    recommendations: List[str] = []
    protocol_keys: List[str] = []

    ts = row["timestamp"]
    astro_id = row["astronaut_id"]
    hr = float(row["heart_rate_bpm"])
    spo2 = float(row["spo2_pct"])
    temp = float(row["temperature_c"])
    sys_bp = float(row["systolic_bp_mmhg"])
    dia_bp = float(row["diastolic_bp_mmhg"])

    # 1. Frecuencia cardíaca (AHA + ajuste simulado en Actividad/EVA)
    if scenario_type == "actividad_eva":
        if hr > 175 or hr < 75:
            sev = "Rojo"
            ref = "75–175 lpm en Actividad/EVA [Criterio operativo simulado]"
            exp = f"Frecuencia cardíaca fuera de rango seguro durante esfuerzo físico/EVA ({hr:.0f} lpm)."
            rec = "Suspender temporalmente el esfuerzo físico/EVA, reposar y reevaluar en 5 minutos."
            protocol_keys.append("TAQUICARDIA_REPOSO" if hr > 175 else "BRADICARDIA_REPOSO")
        elif hr > 155 or hr < 90:
            sev = "Amarillo"
            ref = "90–155 lpm óptimo en Actividad/EVA [Criterio simulado]"
            exp = f"Respuesta cardíaca fuera de zona óptima durante actividad ({hr:.0f} lpm)."
            rec = "Modular ritmo de trabajo físico, hidratarse con electrolitos y controlar respiración."
            protocol_keys.append("TAQUICARDIA_REPOSO" if hr > 155 else "BRADICARDIA_REPOSO")
        else:
            sev, ref, exp, rec = "Verde", "", "", ""
    else:
        if hr > 110 or hr < 45:
            sev = "Rojo"
            ref = "50–90 lpm en reposo [Respaldo clínico: AHA]"
            exp = f"Frecuencia cardíaca crítica en reposo ({hr:.0f} lpm)."
            rec = "Permanecer en reposo, ingerir 500 ml de agua con electrolitos y notificar al médico de vuelo."
            protocol_keys.append("TAQUICARDIA_REPOSO" if hr > 110 else "BRADICARDIA_REPOSO")
        elif hr > 90 or hr < 50:
            sev = "Amarillo"
            ref = "50–90 lpm en reposo [Respaldo clínico: AHA]"
            exp = (
                f"Frecuencia cardíaca en precaución ({hr:.0f} lpm). "
                + ("En microgravedad puede asociarse a redistribución de fluidos (fluid shift)." if environment == "station" else "Vigilar hidratación y fatiga.")
            )
            rec = "Completar protocolo de hidratación oral y repetir lectura en reposo tras 10 minutos."
            protocol_keys.append("TAQUICARDIA_REPOSO" if hr > 90 else "BRADICARDIA_REPOSO")
        else:
            sev, ref, exp, rec = "Verde", "", "", ""

    if sev != "Verde":
        area_status = _max_severity(area_status, sev)
        recommendations.append(rec)
        events.append(_build_event(ts, astro_id, area, "heart_rate_bpm", round(hr, 1), "bpm", sev, ref, exp, rec))
    elif scenario_type == "reposo" and len(astro_history) >= 5:
        resting_hist = astro_history[
            astro_history["scenario"].astype(str).str.lower().str.contains("reposo")
        ]["heart_rate_bpm"].dropna()
        if len(resting_hist) >= 5:
            mean_hr = float(resting_hist.mean())
            std_hr = float(resting_hist.std(ddof=1))
            if std_hr > 0.5:
                z_score = (hr - mean_hr) / std_hr
                if z_score >= 2.0:
                    area_status = _max_severity(area_status, "Amarillo")
                    rec = "Incrementar ingesta hídrica preventiva y monitorear evolución en los próximos ciclos."
                    recommendations.append(rec)
                    protocol_keys.append("TAQUICARDIA_REPOSO")
                    events.append(
                        _build_event(
                            ts,
                            astro_id,
                            area,
                            "heart_rate_bpm",
                            round(hr, 1),
                            "bpm",
                            "Amarillo",
                            f"Línea base personal: {mean_hr:.1f} ± {std_hr:.1f} bpm (Z={z_score:.2f} >= 2.0) [Estadístico simulado]",
                            f"Aunque {hr:.0f} bpm está en rango general, supera en {z_score:.1f}σ el promedio histórico del astronauta.",
                            rec,
                        )
                    )

    # 2. Saturación de oxígeno SpO2 (OMS)
    if spo2 <= 90.0:
        sev = "Rojo"
        ref = "95–100% [Respaldo clínico: OMS]"
        exp = f"Hipoxemia crítica detectada (SpO2: {spo2:.1f}%)."
        rec = "Verificar inmediatamente suministro de O2 de cabina/traje, colocarse en reposo y alertar a control de misión."
        protocol_keys.append("HIPOXEMIA_OXIGENACION")
    elif spo2 <= 94.0:
        sev = "Amarillo"
        ref = "95–100% [Respaldo clínico: OMS]"
        exp = f"Saturación de oxígeno reducida (SpO2: {spo2:.1f}%)."
        rec = "Revisar ventilación/CO2 del módulo, realizar respiraciones profundas y reevaluar en 5 minutos."
        protocol_keys.append("HIPOXEMIA_OXIGENACION")
    else:
        sev, ref, exp, rec = "Verde", "", "", ""

    if sev != "Verde":
        area_status = _max_severity(area_status, sev)
        recommendations.append(rec)
        events.append(_build_event(ts, astro_id, area, "spo2_pct", round(spo2, 1), "%", sev, ref, exp, rec))

    # 3. Temperatura corporal (NIH / MedlinePlus)
    upper_green_temp = 37.6 if scenario_type == "actividad_eva" else 37.2
    if temp >= 38.0 or temp < 35.5:
        sev = "Rojo"
        ref = "36.1–37.2 °C [Respaldo clínico: NIH]"
        exp = f"Alteración térmica crítica ({temp:.1f} °C)."
        rec = "Aplicar aislamiento preventivo en módulo asignado, controlar hidratación y reportar telemetría médica."
        protocol_keys.append("ALTERACION_TERMICA")
    elif temp > upper_green_temp or temp < 36.1:
        sev = "Amarillo"
        ref = f"36.1–{upper_green_temp:.1f} °C [NIH + ajuste simulado]"
        exp = f"Temperatura corporal fuera de rango óptimo ({temp:.1f} °C)."
        rec = "Regular carga térmica/ventilación del traje o cabina, hidratarse y repetir medición en 15 minutos."
        protocol_keys.append("ALTERACION_TERMICA")
    else:
        sev, ref, exp, rec = "Verde", "", "", ""

    if sev != "Verde":
        area_status = _max_severity(area_status, sev)
        recommendations.append(rec)
        events.append(_build_event(ts, astro_id, area, "temperature_c", round(temp, 1), "°C", sev, ref, exp, rec))

    # 4. Presión arterial sistólica y diastólica (AHA)
    upper_green_sys = 160.0 if scenario_type == "actividad_eva" else 120.0
    if (sys_bp >= 140.0 and scenario_type != "actividad_eva") or sys_bp >= 180.0 or sys_bp < 90.0:
        sev = "Rojo"
        ref = "90–120 mmHg normal / >=140 o <90 crítico [Respaldo clínico: AHA]"
        exp = f"Presión arterial sistólica crítica ({sys_bp:.0f} mmHg)."
        rec = "Permanecer en reposo, verificar sensor PPG y notificar al médico de vuelo."
        protocol_keys.append("ALTERACION_PRESION_ARTERIAL")
    elif sys_bp > upper_green_sys:
        sev = "Amarillo"
        ref = f"90–{upper_green_sys:.0f} mmHg [Respaldo clínico: AHA]"
        exp = f"Presión arterial sistólica elevada ({sys_bp:.0f} mmHg)."
        rec = "Evitar cambios posturales bruscos, mantener hidratación y reevaluar en 15 minutos."
        protocol_keys.append("ALTERACION_PRESION_ARTERIAL")
    else:
        sev, ref, exp, rec = "Verde", "", "", ""

    if sev != "Verde":
        area_status = _max_severity(area_status, sev)
        recommendations.append(rec)
        events.append(_build_event(ts, astro_id, area, "systolic_bp_mmhg", round(sys_bp, 0), "mmHg", sev, ref, exp, rec))

    if dia_bp >= 90.0 or dia_bp < 55.0:
        sev = "Rojo"
        ref = "60–80 mmHg normal / >=90 crítico [Respaldo clínico: AHA]"
        exp = f"Presión arterial diastólica crítica ({dia_bp:.0f} mmHg)."
        rec = "Suspender actividad física, mantener reposo y solicitar evaluación médica remota."
        protocol_keys.append("ALTERACION_PRESION_ARTERIAL")
    elif dia_bp > 80.0 or dia_bp < 60.0:
        sev = "Amarillo"
        ref = "60–80 mmHg [Respaldo clínico: AHA]"
        exp = f"Presión arterial diastólica en precaución ({dia_bp:.0f} mmHg)."
        rec = "Monitorear tendencia hemodinámica y asegurar descanso e hidratación adecuados."
        protocol_keys.append("ALTERACION_PRESION_ARTERIAL")
    else:
        sev, ref, exp, rec = "Verde", "", "", ""

    if sev != "Verde":
        area_status = _max_severity(area_status, sev)
        recommendations.append(rec)
        events.append(_build_event(ts, astro_id, area, "diastolic_bp_mmhg", round(dia_bp, 0), "mmHg", sev, ref, exp, rec))

    return area_status, events, recommendations, protocol_keys


def calculate_bone_risk_index(
    row: pd.Series,
    astro_history: pd.DataFrame,
    environment: str,
) -> float:
    """Calcula el Índice Estimado de Riesgo de Deterioro Óseo (0–100, estimación simulada)."""
    target_total = 90.0 if environment == "station" else 60.0
    target_res = 45.0 if environment == "station" else 30.0
    gravity_factor = 1.0 if environment == "station" else 0.65

    if len(astro_history) >= 3:
        recent = astro_history.tail(10)
        ex_min = float(recent["exercise_minutes_24h"].mean())
        res_min = float(recent["resistance_training_minutes_24h"].mean())
        act_score = float(recent["activity_score_0_100"].mean())
    else:
        ex_min = float(row["exercise_minutes_24h"])
        res_min = float(row["resistance_training_minutes_24h"])
        act_score = float(row["activity_score_0_100"])

    deficit_res = np.clip((target_res - res_min) / target_res, 0.0, 1.0)
    deficit_ex = np.clip((target_total - ex_min) / target_total, 0.0, 1.0)
    deficit_act = np.clip((75.0 - act_score) / 75.0, 0.0, 1.0)

    raw_risk = (0.50 * deficit_res + 0.30 * deficit_ex + 0.20 * deficit_act) * 100.0
    return round(float(np.clip(raw_risk * gravity_factor, 0.0, 100.0)), 1)


def evaluate_bone_health(
    row: pd.Series,
    astro_history: pd.DataFrame,
    environment: str,
) -> Tuple[str, List[Dict[str, Any]], List[str], List[str], float]:
    """Evalúa Sistema Óseo mediante adherencia a ejercicio de resistencia y actividad diaria."""
    area = "Sistema Óseo"
    area_status = "Verde"
    events: List[Dict[str, Any]] = []
    recommendations: List[str] = []
    protocol_keys: List[str] = []

    ts = row["timestamp"]
    astro_id = row["astronaut_id"]
    ex_min = float(row["exercise_minutes_24h"])
    res_min = float(row["resistance_training_minutes_24h"])

    min_res_green = 45.0 if environment == "station" else 30.0
    min_res_yellow = 20.0 if environment == "station" else 15.0
    min_ex_green = 90.0 if environment == "station" else 60.0
    min_ex_yellow = 45.0 if environment == "station" else 30.0

    if res_min < min_res_yellow:
        sev = "Rojo"
        ref = f">= {min_res_green:.0f} min/24h en {environment} [NASA HRP ARED + umbral simulado]"
        exp = f"Adherencia crítica a ejercicios de resistencia ({res_min:.0f} min/24h)."
        rec = "Priorizar sesión de ejercicio resistivo en el próximo bloque de rutina."
        protocol_keys.append("DEFICIT_CONTRAMEDIDAS_OSEAS")
    elif res_min < min_res_green:
        sev = "Amarillo"
        ref = f">= {min_res_green:.0f} min/24h en {environment} [Criterio simulado]"
        exp = f"Entrenamiento resistivo por debajo de la meta diaria ({res_min:.0f} min/24h)."
        rec = "Completar 15–20 minutos adicionales de ejercicios de fuerza resistiva."
        protocol_keys.append("DEFICIT_CONTRAMEDIDAS_OSEAS")
    else:
        sev, ref, exp, rec = "Verde", "", "", ""

    if sev != "Verde":
        area_status = _max_severity(area_status, sev)
        recommendations.append(rec)
        events.append(
            _build_event(ts, astro_id, area, "resistance_training_minutes_24h", round(res_min, 1), "min", sev, ref, exp, rec)
        )

    if ex_min < min_ex_yellow:
        sev = "Rojo"
        ref = f">= {min_ex_green:.0f} min/24h en {environment} [Criterio simulado]"
        exp = f"Déficit severo de ejercicio físico diario ({ex_min:.0f} min/24h)."
        rec = "Reprogramar bloque obligatorio de ejercicio aeróbico y resistivo."
        protocol_keys.append("DEFICIT_CONTRAMEDIDAS_OSEAS")
    elif ex_min < min_ex_green:
        sev = "Amarillo"
        ref = f">= {min_ex_green:.0f} min/24h en {environment} [Criterio simulado]"
        exp = f"Tiempo de ejercicio diario inferior al objetivo recomendado ({ex_min:.0f} min/24h)."
        rec = "Incrementar actividad física para alcanzar la meta diaria."
        protocol_keys.append("DEFICIT_CONTRAMEDIDAS_OSEAS")
    else:
        sev, ref, exp, rec = "Verde", "", "", ""

    if sev != "Verde":
        area_status = _max_severity(area_status, sev)
        recommendations.append(rec)
        events.append(_build_event(ts, astro_id, area, "exercise_minutes_24h", round(ex_min, 1), "min", sev, ref, exp, rec))

    bone_risk_index = calculate_bone_risk_index(row, astro_history, environment)
    if bone_risk_index > 60.0:
        area_status = _max_severity(area_status, "Rojo")
        protocol_keys.append("DEFICIT_CONTRAMEDIDAS_OSEAS")
    elif bone_risk_index >= 30.0:
        area_status = _max_severity(area_status, "Amarillo")

    return area_status, events, recommendations, protocol_keys, bone_risk_index


def evaluate_muscular_density(
    row: pd.Series,
    astro_history: pd.DataFrame,
) -> Tuple[str, List[Dict[str, Any]], List[str], List[str], float]:
    """Evalúa Densidad Muscular comparando BIA actual frente a la línea base inicial del astronauta."""
    area = "Densidad Muscular"
    area_status = "Verde"
    events: List[Dict[str, Any]] = []
    recommendations: List[str] = []
    protocol_keys: List[str] = []

    ts = row["timestamp"]
    astro_id = row["astronaut_id"]
    muscle_kg = float(row["muscle_mass_kg"])
    body_fat = float(row["body_fat_pct"])

    if len(astro_history) > 0:
        baseline_slice = astro_history.head(3)
        baseline_muscle = float(baseline_slice["muscle_mass_kg"].mean())
        baseline_fat = float(baseline_slice["body_fat_pct"].mean())
    else:
        baseline_muscle = muscle_kg
        baseline_fat = body_fat

    muscle_delta_pct = ((muscle_kg - baseline_muscle) / baseline_muscle * 100.0) if baseline_muscle > 0 else 0.0
    fat_delta_pct = body_fat - baseline_fat

    if muscle_delta_pct <= -5.0:
        sev = "Rojo"
        ref = f"Caída < 2.0% vs. línea base ({baseline_muscle:.1f} kg) [Criterio simulado]"
        exp = f"Atrofia muscular progresiva crítica: pérdida de {abs(muscle_delta_pct):.1f}% respecto al inicio."
        rec = "Aumentar carga en ejercicios de resistencia de tren inferior y ajustar aporte proteico."
        protocol_keys.append("DEFICIT_CONTRAMEDIDAS_OSEAS")
    elif muscle_delta_pct <= -2.0:
        sev = "Amarillo"
        ref = f"Caída < 2.0% vs. línea base ({baseline_muscle:.1f} kg) [Criterio simulado]"
        exp = f"Descenso moderado de masa muscular estimada ({muscle_delta_pct:+.1f}% vs. inicio)."
        rec = "Reforzar rutina de fuerza en pantorrillas, cuádriceps y musculatura postural."
        protocol_keys.append("DEFICIT_CONTRAMEDIDAS_OSEAS")
    else:
        sev, ref, exp, rec = "Verde", "", "", ""

    if sev != "Verde":
        area_status = _max_severity(area_status, sev)
        recommendations.append(rec)
        events.append(_build_event(ts, astro_id, area, "muscle_mass_kg", round(muscle_kg, 2), "kg", sev, ref, exp, rec))

    if abs(fat_delta_pct) >= 5.0 or body_fat < 8.0 or body_fat > 30.0:
        sev = "Rojo"
        ref = f"Variación ±2.5% vs. base ({baseline_fat:.1f}%) y rango 8–30% [ACSM + simulado]"
        exp = f"Variación crítica de grasa corporal ({body_fat:.1f}%, cambio de {fat_delta_pct:+.1f}%)."
        rec = "Auditar ingesta calórica diaria frente al gasto energético de la misión."
    elif abs(fat_delta_pct) > 2.5:
        sev = "Amarillo"
        ref = f"Variación ±2.5% vs. base ({baseline_fat:.1f}%) [Criterio simulado]"
        exp = f"Desviación gradual en grasa corporal ({body_fat:.1f}%, {fat_delta_pct:+.1f}%)."
        rec = "Ajustar balance nutricional y proporción de ejercicio aeróbico/resistivo."
    else:
        sev, ref, exp, rec = "Verde", "", "", ""

    if sev != "Verde":
        area_status = _max_severity(area_status, sev)
        recommendations.append(rec)
        events.append(_build_event(ts, astro_id, area, "body_fat_pct", round(body_fat, 1), "%", sev, ref, exp, rec))

    return area_status, events, recommendations, protocol_keys, round(muscle_delta_pct, 2)


def calculate_psychological_load_index(
    sleep_h: float,
    stress: float,
    mood: float,
    environment: str,
) -> float:
    """
    Calcula un Índice Estimado de Carga Psicológica y Fatiga (0–100, modelo simulado).
    En 'mars' aplica un factor de aislamiento prolongado (+10%) ante sobrecarga sostenida.
    """
    sleep_deficit = np.clip((8.0 - sleep_h) / 4.0, 0.0, 1.0)
    stress_load = np.clip(stress / 10.0, 0.0, 1.0)
    mood_deficit = np.clip((10.0 - mood) / 10.0, 0.0, 1.0)

    raw_load = (0.40 * sleep_deficit + 0.35 * stress_load + 0.25 * mood_deficit) * 100.0
    env_factor = 1.10 if environment == "mars" else 1.0
    return round(float(np.clip(raw_load * env_factor, 0.0, 100.0)), 1)


def evaluate_psychological_wellbeing(
    row: pd.Series,
    astro_history: pd.DataFrame,
    environment: str,
) -> Tuple[str, List[Dict[str, Any]], List[str], List[str], float]:
    """
    Evalúa Salud Mental y Psicológica (autopercepción, descanso e historial longitudinal):
    - Evalúa valores puntuales (sleep_hours_24h, stress_score_0_10, mood_score_0_10).
    - Detecta deuda acumulada de sueño y caídas respecto a la línea base emocional del astronauta.
    - Adapta recomendaciones al contexto operativo ('station' vs. 'mars').
    """
    area = "Salud Mental y Psicológica"
    area_status = "Verde"
    events: List[Dict[str, Any]] = []
    recommendations: List[str] = []
    protocol_keys: List[str] = []

    ts = row["timestamp"]
    astro_id = row["astronaut_id"]
    sleep_h = float(row["sleep_hours_24h"])
    stress = float(row["stress_score_0_10"])
    mood = float(row["mood_score_0_10"])

    # 1. Horas de sueño en 24h + Detección de deuda acumulada en historial
    recent_sleep_low = False
    if len(astro_history) >= 3 and "sleep_hours_24h" in astro_history.columns:
        last_3_sleep = astro_history["sleep_hours_24h"].dropna().tail(3)
        if len(last_3_sleep) == 3 and (last_3_sleep < 6.5).all() and sleep_h < 6.5:
            recent_sleep_low = True

    if sleep_h < 5.5 or recent_sleep_low:
        sev = "Rojo"
        ref = "7.0–9.0 h/24h (o >=3 ciclos < 6.5h) [Respaldo: AASM / NASA Sleep Countermeasures]"
        exp = (
            f"Deuda acumulada de sueño detectada ({sleep_h:.1f} h en el último ciclo y < 6.5 h sostenido)."
            if recent_sleep_low and sleep_h >= 5.5
            else f"Déficit crítico de sueño ({sleep_h:.1f} h); alto riesgo de fatiga cognitiva."
        )
        rec = (
            "Posponer maniobras críticas, aplicar terapia de luz circadiana y asegurar bloque de sueño de 8 h."
            if environment == "station"
            else "Reprogramar tareas de precisión, ajustar ciclo sol marciano y priorizar descanso reparador."
        )
        protocol_keys.append("FATIGA_CIRCADIANA_SUENO")
    elif sleep_h < 7.0 or sleep_h > 9.5:
        sev = "Amarillo"
        ref = "7.0–9.0 h/24h [Respaldo: AASM / NASA Sleep Countermeasures]"
        exp = f"Duración de sueño fuera de ventana óptima ({sleep_h:.1f} h)."
        rec = "Reducir exposición a pantallas/luz azul 1 hora antes de dormir y mantener horario fijo."
        protocol_keys.append("FATIGA_CIRCADIANA_SUENO")
    else:
        sev, ref, exp, rec = "Verde", "", "", ""

    if sev != "Verde":
        area_status = _max_severity(area_status, sev)
        recommendations.append(rec)
        events.append(_build_event(ts, astro_id, area, "sleep_hours_24h", round(sleep_h, 1), "h", sev, ref, exp, rec))

    # 2. Estrés percibido (0 a 10) + Persistencia en historial
    sustained_stress = False
    if len(astro_history) >= 3 and "stress_score_0_10" in astro_history.columns:
        last_3_stress = astro_history["stress_score_0_10"].dropna().tail(3)
        if len(last_3_stress) == 3 and (last_3_stress >= 5.0).all() and stress >= 5.0:
            sustained_stress = True

    if stress >= 7.0:
        sev = "Rojo"
        ref = "0–3 óptimo / 4–6 precaución (escala 0–10) [Criterio operativo simulado]"
        exp = f"Nivel elevado de estrés percibido ({stress:.1f}/10)."
        rec = "Ejecutar pausa de descompresión de 10 min, redistribuir carga del turno y activar apoyo conductual."
        protocol_keys.append("ESTRES_OPERATIVO_AGUDO")
    elif stress >= 4.0 or sustained_stress:
        sev = "Amarillo"
        ref = "0–3 óptimo (escala 0–10) [Criterio operativo simulado]"
        exp = (
            f"Estrés percibido sostenido ({stress:.1f}/10 durante múltiples ciclos)"
            if sustained_stress
            else f"Estrés percibido moderado ({stress:.1f}/10)"
        ) + (" en entorno de aislamiento prolongado en Marte." if environment == "mars" else ".")
        rec = "Incorporar respiración táctica guiada (10 min) y revisar priorización de tareas."
        protocol_keys.append("ESTRES_OPERATIVO_AGUDO")
    else:
        sev, ref, exp, rec = "Verde", "", "", ""

    if sev != "Verde":
        area_status = _max_severity(area_status, sev)
        recommendations.append(rec)
        events.append(_build_event(ts, astro_id, area, "stress_score_0_10", round(stress, 1), "pts (0-10)", sev, ref, exp, rec))

    # 3. Estado de ánimo percibido (0 a 10) + Caída respecto a línea base individual
    mood_drop_alert = False
    baseline_mood = mood
    if len(astro_history) >= 3 and "mood_score_0_10" in astro_history.columns:
        baseline_mood = float(astro_history["mood_score_0_10"].dropna().head(3).mean())
        if (baseline_mood - mood) >= 2.5:
            mood_drop_alert = True

    if mood <= 3.0:
        sev = "Rojo"
        ref = "7–10 óptimo / 4–6 precaución (escala 0–10) [Criterio operativo simulado]"
        exp = f"Descenso marcado en bienestar emocional autopercibido ({mood:.1f}/10)."
        rec = (
            "Fomentar cohesión con la tripulación, habilitar mensajes asíncronos con familiares y tiempo de autonomía."
            if environment == "mars"
            else "Fomentar actividad recreativa grupal y habilitar comunicación privada con soporte en Tierra."
        )
        protocol_keys.append("AISLAMIENTO_ANIMO_BAJO")
    elif mood <= 6.0 or mood_drop_alert:
        sev = "Amarillo"
        ref = f"7–10 óptimo / caída < 2.5 pts vs. base ({baseline_mood:.1f}) [Criterio simulado]"
        exp = (
            f"Descenso significativo de ánimo ({mood:.1f}/10 frente a línea base personal de {baseline_mood:.1f}/10)."
            if mood_drop_alert and mood > 6.0
            else f"Estado de ánimo en nivel intermedio ({mood:.1f}/10); requiere seguimiento preventivo."
        )
        rec = "Programar pausa social con la tripulación, variedad sensorial y seguimiento diario."
        protocol_keys.append("AISLAMIENTO_ANIMO_BAJO")
    else:
        sev, ref, exp, rec = "Verde", "", "", ""

    if sev != "Verde":
        area_status = _max_severity(area_status, sev)
        recommendations.append(rec)
        events.append(_build_event(ts, astro_id, area, "mood_score_0_10", round(mood, 1), "pts (0-10)", sev, ref, exp, rec))

    psych_load = calculate_psychological_load_index(sleep_h, stress, mood, environment)
    if psych_load > 65.0:
        area_status = _max_severity(area_status, "Rojo")
    elif psych_load >= 35.0:
        area_status = _max_severity(area_status, "Amarillo")

    return area_status, events, recommendations, protocol_keys, psych_load


# ==============================================================================
# 5. MOTOR DE CORRELACIÓN DE VARIABLES (PATRONES COMPUESTOS)
# ==============================================================================

def evaluate_cross_variable_patterns(
    row: pd.Series,
    scenario_type: str,
    environment: str,
    muscle_delta_pct: float,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[str]]:
    """
    Cruza múltiples variables simultáneamente para generar interpretaciones
    fisiológicas y conductuales compuestas, activando su protocolo rápido al instante.
    """
    ts = str(row["timestamp"])
    astro_id = str(row["astronaut_id"])
    hr = float(row["heart_rate_bpm"])
    spo2 = float(row["spo2_pct"])
    temp = float(row["temperature_c"])
    sys_bp = float(row["systolic_bp_mmhg"])
    sleep_h = float(row["sleep_hours_24h"])
    stress = float(row["stress_score_0_10"])
    mood = float(row["mood_score_0_10"])
    res_min = float(row["resistance_training_minutes_24h"])
    act_score = float(row["activity_score_0_100"])

    patterns: List[Dict[str, Any]] = []
    pattern_events: List[Dict[str, Any]] = []
    protocol_keys: List[str] = []

    # Patrón 1: Taquicardia + Presión sistólica baja en reposo -> Redistribución de fluidos / Deshidratación
    if scenario_type != "actividad_eva" and hr > 90.0 and sys_bp < 100.0:
        sev = "Rojo" if (hr > 110.0 or sys_bp < 90.0) else "Amarillo"
        interp = (
            f"Patrón compatible con redistribución de fluidos (fluid shift) o depleción de volumen plasmático: "
            f"pulso elevado ({hr:.0f} bpm) combinado con presión sistólica baja ({sys_bp:.0f} mmHg)."
        )
        rec = "Ejecutar Protocolo PROT-CV-03: Ingerir 500 ml de agua con electrolitos y mantener reposo postural."
        patterns.append({"pattern_code": "FLUID_SHIFT_PATTERN", "severity": sev, "interpretation": interp})
        protocol_keys.append("FLUID_SHIFT_HIPOVOLEMIA")
        pattern_events.append(
            _build_event(
                ts, astro_id, "Sistema Cardiovascular", "patron_hr_presion",
                f"HR:{hr:.0f} / SYS:{sys_bp:.0f}", "bpm/mmHg", sev,
                "HR > 90 bpm + Sistólica < 100 mmHg [Modelo fisiológico espacial]", interp, rec
            )
        )

    # Patrón 2: Elevación térmica + Taquicardia en reposo -> Estrés térmico / Respuesta inmune
    if scenario_type != "actividad_eva" and temp >= 37.5 and hr > 95.0:
        sev = "Rojo" if (temp >= 38.0 or hr > 110.0) else "Amarillo"
        interp = (
            f"Patrón compatible con estrés térmico sistémico o posible respuesta inmune activa en cabina cerrada: "
            f"temperatura de {temp:.1f} °C acompañada de pulso de {hr:.0f} bpm."
        )
        rec = "Ejecutar Protocolo PROT-CV-05: Aislamiento preventivo, revisar ventilación de cabina y reportar telemetría."
        patterns.append({"pattern_code": "THERMAL_IMMUNE_PATTERN", "severity": sev, "interpretation": interp})
        protocol_keys.append("ALTERACION_TERMICA")
        pattern_events.append(
            _build_event(
                ts, astro_id, "Sistema Cardiovascular", "patron_temp_hr",
                f"Temp:{temp:.1f} / HR:{hr:.0f}", "°C/bpm", sev,
                "Temp >= 37.5 °C + HR > 95 bpm [Criterio clínico operativo]", interp, rec
            )
        )

    # Patrón 3: SpO2 reducida + Taquicardia -> Compromiso cardiorrespiratorio / Hipoxia
    if spo2 <= 94.0 and (hr > 95.0 or (scenario_type == "actividad_eva" and hr > 160.0)):
        sev = "Rojo" if spo2 <= 90.0 else "Amarillo"
        interp = (
            f"Patrón de compensación cardiorrespiratoria: descenso de oxigenación ({spo2:.1f}%) "
            f"con elevación cardíaca ({hr:.0f} bpm)."
        )
        rec = "Ejecutar Protocolo PROT-CV-04: Detener actividad/EVA y verificar suministro de O2 y niveles de CO2."
        patterns.append({"pattern_code": "CARDIORESPIRATORY_PATTERN", "severity": sev, "interpretation": interp})
        protocol_keys.append("HIPOXEMIA_OXIGENACION")
        pattern_events.append(
            _build_event(
                ts, astro_id, "Sistema Cardiovascular", "patron_spo2_hr",
                f"SpO2:{spo2:.1f}% / HR:{hr:.0f}", "%/bpm", sev,
                "SpO2 <= 94% + Elevación cardíaca [Criterio clínico operativo]", interp, rec
            )
        )

    # Patrón 4: Déficit de sueño + Estrés alto o Ánimo bajo -> Fatiga cognitiva y sobrecarga
    if sleep_h < 6.5 and (stress >= 6.0 or mood <= 4.0):
        sev = "Rojo" if (sleep_h < 5.5 or stress >= 7.0 or mood <= 3.0) else "Amarillo"
        interp = (
            f"Patrón de fatiga cognitiva y sobrecarga operativa: sueño insuficiente ({sleep_h:.1f} h) "
            f"combinado con estrés ({stress:.0f}/10) y ánimo ({mood:.0f}/10)."
        )
        rec = "Ejecutar Protocolo PROT-PS-01: Posponer maniobras críticas y priorizar bloque de descanso circadiano."
        patterns.append({"pattern_code": "COGNITIVE_OVERLOAD_PATTERN", "severity": sev, "interpretation": interp})
        protocol_keys.append("FATIGA_CIRCADIANA_SUENO")
        pattern_events.append(
            _build_event(
                ts, astro_id, "Salud Mental y Psicológica", "patron_sueno_estres",
                f"Sueño:{sleep_h:.1f}h / Estrés:{stress:.0f}", "h/pts", sev,
                "Sueño < 6.5h + Estrés >= 6 o Ánimo <= 4 [Criterio operativo simulado]", interp, rec
            )
        )

    # Patrón 5: Estrés percibido alto + Pulso elevado en reposo (sin fiebre) -> Tensión autonómica por estrés
    if scenario_type == "reposo" and stress >= 6.0 and hr > 85.0 and temp < 37.3:
        sev = "Rojo" if (stress >= 8.0 and hr > 100.0) else "Amarillo"
        interp = (
            f"Patrón de respuesta autonómica por sobrecarga de estrés: estrés percibido ({stress:.0f}/10) "
            f"reflejado en aceleración cardíaca en reposo ({hr:.0f} bpm) sin signos térmicos de infección."
        )
        rec = "Ejecutar Protocolo PROT-PS-02: Pausa de descompresión de 10 min con respiración táctica y ajuste de carga."
        patterns.append({"pattern_code": "AUTONOMIC_STRESS_PATTERN", "severity": sev, "interpretation": interp})
        protocol_keys.append("ESTRES_OPERATIVO_AGUDO")
        pattern_events.append(
            _build_event(
                ts, astro_id, "Salud Mental y Psicológica", "patron_estres_pulso",
                f"Estrés:{stress:.0f} / HR:{hr:.0f}", "pts/bpm", sev,
                "Estrés >= 6 + HR > 85 bpm en reposo sin fiebre [Modelo psicofisiológico simulado]", interp, rec
            )
        )

    # Patrón 6: Ánimo bajo + Baja actividad física -> Retraimiento conductual / monotonía
    if mood <= 5.0 and act_score < 50.0:
        sev = "Rojo" if (mood <= 3.0 and act_score < 35.0) else "Amarillo"
        interp = (
            f"Patrón de retraimiento conductual y baja energía: descenso emocional ({mood:.0f}/10) "
            f"acompañado de caída en actividad física diaria ({act_score:.0f}/100)."
        )
        rec = "Ejecutar Protocolo PROT-PS-03: Fomentar cohesión grupal, contacto asíncrono con Tierra y actividad activa."
        patterns.append({"pattern_code": "BEHAVIORAL_WITHDRAWAL_PATTERN", "severity": sev, "interpretation": interp})
        protocol_keys.append("AISLAMIENTO_ANIMO_BAJO")
        pattern_events.append(
            _build_event(
                ts, astro_id, "Salud Mental y Psicológica", "patron_animo_actividad",
                f"Ánimo:{mood:.0f} / Act:{act_score:.0f}", "pts/score", sev,
                "Ánimo <= 5 + Actividad < 50 [Criterio conductual operativo]", interp, rec
            )
        )

    # Patrón 7: Baja adherencia resistiva + Caída muscular -> Desacondicionamiento acelerado
    min_res = 30.0 if environment == "station" else 20.0
    if res_min < min_res and (muscle_delta_pct <= -2.0 or act_score < 50.0):
        sev = "Rojo" if muscle_delta_pct <= -5.0 else "Amarillo"
        interp = (
            f"Patrón de desacondicionamiento musculoesquelético acelerado: bajo ejercicio resistivo "
            f"({res_min:.0f} min/24h) con variación muscular de {muscle_delta_pct:+.1f}%."
        )
        rec = "Ejecutar Protocolo PROT-OS-01: Priorizar sesión de resistencia y auditar aporte proteico."
        patterns.append({"pattern_code": "DECONDITIONING_PATTERN", "severity": sev, "interpretation": interp})
        protocol_keys.append("DEFICIT_CONTRAMEDIDAS_OSEAS")
        pattern_events.append(
            _build_event(
                ts, astro_id, "Sistema Óseo", "patron_resistencia_musculo",
                f"Res:{res_min:.0f}m / Musc:{muscle_delta_pct:+.1f}%", "min/%", sev,
                "Déficit resistivo + Descenso masa muscular [Modelo simulado NASA HRP]", interp, rec
            )
        )

    return patterns, pattern_events, protocol_keys


# ==============================================================================
# 6. EVALUACIÓN INTEGRAL POR ASTRONAUTA Y TRIPULACIÓN (INTERFAZ PÚBLICA)
# ==============================================================================

def evaluate_astronaut(
    current_row: pd.Series,
    astro_history: Optional[pd.DataFrame] = None,
    environment: Optional[str] = None,
) -> Dict[str, Any]:
    """Evalúa el estado integral de un astronauta, sus patrones cruzados y protocolos activos."""
    if astro_history is None or not isinstance(astro_history, pd.DataFrame):
        astro_history = pd.DataFrame(columns=REQUIRED_INPUT_COLUMNS)

    env = _normalize_environment(environment if environment else current_row.get("environment"))
    scenario = _normalize_scenario(current_row.get("scenario"))
    astro_id = str(current_row["astronaut_id"])

    cardio_st, cardio_ev, cardio_rec, cardio_prot = evaluate_cardiovascular(
        current_row, astro_history, scenario, env
    )
    bone_st, bone_ev, bone_rec, bone_prot, bone_risk = evaluate_bone_health(
        current_row, astro_history, env
    )
    musc_st, musc_ev, musc_rec, musc_prot, musc_delta = evaluate_muscular_density(
        current_row, astro_history
    )
    psych_st, psych_ev, psych_rec, psych_prot, psych_load = evaluate_psychological_wellbeing(
        current_row, astro_history, env
    )

    # Evaluación cruzada entre múltiples variables
    patterns, pattern_ev, pattern_prot = evaluate_cross_variable_patterns(
        current_row, scenario, env, musc_delta
    )

    all_events = pattern_ev + cardio_ev + bone_ev + musc_ev + psych_ev

    overall_status = "Verde"
    for st in [cardio_st, bone_st, musc_st, psych_st]:
        overall_status = _max_severity(overall_status, st)
    for pat in patterns:
        overall_status = _max_severity(overall_status, pat["severity"])

    # Deduplicar protocolos rápidos activos en el orden en que se dispararon
    all_prot_keys = pattern_prot + cardio_prot + bone_prot + musc_prot + psych_prot
    active_protocols: List[Dict[str, Any]] = []
    seen_prot = set()
    for key in all_prot_keys:
        if key in RAPID_ACTION_PROTOCOLS and key not in seen_prot:
            seen_prot.add(key)
            active_protocols.append(RAPID_ACTION_PROTOCOLS[key])

    unique_recommendations: List[str] = []
    for rec in [ev["recommended_action"] for ev in pattern_ev] + cardio_rec + bone_rec + musc_rec + psych_rec:
        if rec and rec not in unique_recommendations:
            unique_recommendations.append(rec)

    if not unique_recommendations:
        unique_recommendations.append("Parámetros dentro de rangos nominales. Continuar protocolo estándar de misión.")

    return {
        "astronaut_id": astro_id,
        "timestamp": str(current_row["timestamp"]),
        "environment": env,
        "scenario": scenario,
        "overall_status": overall_status,
        "areas": {
            "Sistema Cardiovascular": cardio_st,
            "Sistema Óseo": bone_st,
            "Densidad Muscular": musc_st,
            "Salud Mental y Psicológica": psych_st,
        },
        "derived_metrics": {
            "bone_risk_index_simulated": bone_risk,
            "bone_risk_disclaimer": "Estimación simulada basada en actividad física y ejercicio (no medición clínica).",
            "muscle_mass_change_pct": musc_delta,
            "psychological_load_index_simulated": psych_load,
            "psychological_disclaimer": "Indicador operativo simulado de bienestar y fatiga (no diagnóstico clínico).",
        },
        "detected_patterns": patterns,
        "rapid_protocols": active_protocols,
        "flagged_parameters": [ev["parameter"] for ev in all_events],
        "recommendations": unique_recommendations,
        "events": all_events,
    }


def evaluate_crew_health(
    current_df: pd.DataFrame,
    history_df: Optional[pd.DataFrame] = None,
    environment: Optional[str] = None,
) -> Dict[str, Any]:
    """Punto de entrada principal para app.py y ui_components.py."""
    validate_input_dataframe(current_df)

    if current_df.empty:
        return {
            "crew_summary": {
                "overall_status": "Verde",
                "total_astronauts": 0,
                "active_alerts_count": 0,
                "critical_astronauts": [],
            },
            "astronaut_status": {},
            "events": [],
            "events_df": pd.DataFrame(columns=EVENT_COLUMNS),
        }

    if history_df is None or not isinstance(history_df, pd.DataFrame) or history_df.empty:
        history_df = pd.DataFrame(columns=REQUIRED_INPUT_COLUMNS)

    astronaut_status: Dict[str, Any] = {}
    all_events: List[Dict[str, Any]] = []
    crew_overall = "Verde"
    critical_astronauts: List[str] = []

    for _, row in current_df.iterrows():
        astro_id = str(row["astronaut_id"])
        if not history_df.empty and "astronaut_id" in history_df.columns:
            astro_hist = history_df[history_df["astronaut_id"] == astro_id].copy()
        else:
            astro_hist = pd.DataFrame(columns=REQUIRED_INPUT_COLUMNS)

        result = evaluate_astronaut(row, astro_hist, environment=environment)
        astronaut_status[astro_id] = result
        all_events.extend(result["events"])

        crew_overall = _max_severity(crew_overall, result["overall_status"])
        if result["overall_status"] == "Rojo":
            critical_astronauts.append(astro_id)

    events_df = pd.DataFrame(all_events, columns=list(EVENT_COLUMNS)) if all_events else pd.DataFrame(columns=list(EVENT_COLUMNS))

    return {
        "crew_summary": {
            "overall_status": crew_overall,
            "total_astronauts": len(astronaut_status),
            "active_alerts_count": len(all_events),
            "critical_astronauts": critical_astronauts,
        },
        "astronaut_status": astronaut_status,
        "events": all_events,
        "events_df": events_df,
    }


# ==============================================================================
# 7. NUEVA INTERFAZ PÚBLICA — evaluate_readings()
#    Requerida por tests/test_diagnostics.py y tests/test_integration.py.
#    Envuelve evaluate_crew_health() y convierte su salida al contrato de datos
#    tipado que esperan las pruebas de integración.
# ==============================================================================

def evaluate_readings(
    current_df: pd.DataFrame,
    history: Optional[pd.DataFrame] = None,
    environment: Optional[str] = None,
) -> DiagnosticResult:
    """Interfaz principal orientada a pruebas e integración.

    Valida las entradas, delega en ``evaluate_crew_health`` y convierte la
    salida en un ``DiagnosticResult`` tipado con:

    * ``astronaut_status`` — DataFrame con columnas ``STATUS_COLUMNS``.
    * ``events``           — DataFrame con columnas ``EVENT_COLUMNS``.
    * ``crew_summary``     — dict con métricas globales de la tripulación.

    Raises:
        ValueError: Si algún astronauta aparece más de una vez en current_df.
        ValueError: Si el argumento ``environment`` no coincide con el valor de
                    la columna ``environment`` del DataFrame.
        ValueError: Si el timestamp de alguna lectura actual es anterior al
                    timestamp más reciente del historial.
    """
    # --- Validación 1: sin filas duplicadas por astronauta -------------------------
    if not current_df.empty and "astronaut_id" in current_df.columns:
        duplicates = current_df["astronaut_id"].value_counts()
        duplicated_ids = duplicates[duplicates > 1].index.tolist()
        if duplicated_ids:
            raise ValueError(
                f"evaluate_readings recibió at most one current row por astronauta, "
                f"pero encontró duplicados: {duplicated_ids}."
            )

    # --- Validación 2: coherencia del argumento environment -----------------------
    if (
        environment is not None
        and not current_df.empty
        and "environment" in current_df.columns
    ):
        df_envs = current_df["environment"].unique().tolist()
        norm_arg = _normalize_environment(environment)
        for df_env in df_envs:
            if _normalize_environment(df_env) != norm_arg:
                raise ValueError(
                    f"El argumento environment='{environment}' does not match "
                    f"el valor '{df_env}' encontrado en el DataFrame."
                )

    # --- Validación 3: timestamp actual no anterior al historial ------------------
    if (
        history is not None
        and not history.empty
        and "timestamp" in history.columns
        and not current_df.empty
        and "timestamp" in current_df.columns
    ):
        hist_max = pd.to_datetime(history["timestamp"], utc=True, errors="coerce").max()
        curr_min = pd.to_datetime(current_df["timestamp"], utc=True, errors="coerce").min()
        if pd.notna(hist_max) and pd.notna(curr_min) and curr_min < hist_max:
            raise ValueError(
                f"El timestamp de la lectura actual ({curr_min}) predates the supplied history "
                f"(máximo histórico: {hist_max})."
            )

    # --- Delegación en la lógica existente ----------------------------------------
    raw = evaluate_crew_health(
        current_df=current_df,
        history_df=history,
        environment=environment,
    )

    # --- Conversión a DiagnosticResult -------------------------------------------
    astro_rows: List[Dict[str, Any]] = []
    for astro_id, astro_result in raw["astronaut_status"].items():
        overall_es = astro_result.get("overall_status", "Verde")
        status_en = _SEVERITY_EN.get(overall_es, "unassessed")
        derived = astro_result.get("derived_metrics", {})
        astro_rows.append({
            "astronaut_id": astro_id,
            "timestamp": astro_result.get("timestamp", ""),
            "environment": astro_result.get("environment", ""),
            "scenario": astro_result.get("scenario", ""),
            "status": status_en,
            "overall_status_es": overall_es,
            "bone_risk_index_simulated": derived.get("bone_risk_index_simulated"),
            "muscle_mass_change_pct": derived.get("muscle_mass_change_pct"),
            "psychological_load_index_simulated": derived.get("psychological_load_index_simulated"),
        })

    astronaut_status_df = (
        pd.DataFrame(astro_rows, columns=list(STATUS_COLUMNS))
        if astro_rows
        else pd.DataFrame(columns=list(STATUS_COLUMNS))
    )

    # Mapear severity de los eventos de español a inglés para coherencia de la API.
    events_df: pd.DataFrame = raw["events_df"].copy()
    if not events_df.empty and "severity" in events_df.columns:
        events_df["severity"] = events_df["severity"].map(
            lambda s: _SEVERITY_EN.get(s, s)
        )
    # Garantizar el orden de columnas exacto que esperan los tests.
    events_df = events_df.reindex(columns=list(EVENT_COLUMNS))

    crew_summary = raw.get("crew_summary", {})

    return DiagnosticResult(
        astronaut_status=astronaut_status_df,
        events=events_df,
        crew_summary=crew_summary,
    )