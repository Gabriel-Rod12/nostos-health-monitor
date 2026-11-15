"""Rule-based, non-clinical health signal evaluation for NOSTOS.

This module evaluates synthetic telemetry against a small set of documented
adult reference values. These rules are not astronaut medical standards, are
not validated for microgravity, EVA, or Mars, and must not be used to diagnose
or treat a person. During EVA, heart rate and blood pressure are not compared
with resting references. Bone-risk and body-composition estimates are left
unclassified because this project has no validated individual baselines or
mission-specific thresholds for them.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from math import isfinite
from typing import Any, Literal

import pandas as pd

from src.telemetry import ASTRONAUT_IDS, VITAL_COLUMNS, validate_telemetry


Severity = Literal["precaution", "critical"]

EVENT_COLUMNS: tuple[str, ...] = (
    "event_id",
    "timestamp",
    "astronaut_id",
    "environment",
    "scenario",
    "health_area",
    "parameter",
    "value",
    "unit",
    "severity",
    "reference",
    "message",
    "recommendation",
    "source_url",
    "experimental",
)

STATUS_COLUMNS: tuple[str, ...] = (
    "astronaut_id",
    "environment",
    "status",
    "status_label",
    "active_event_count",
    "attention_parameters",
    "evaluated_parameters",
    "unassessed_parameters",
    "missing_parameters",
    "assessment_coverage",
)

SOURCE_URLS: dict[str, str] = {
    "heart_rate": "https://medlineplus.gov/ency/article/003399.htm",
    "spo2": "https://www.medlineplus.gov/lab-tests/pulse-oximetry/",
    "blood_pressure": "https://www.heart.org/en/health-topics/high-blood-pressure/understanding-blood-pressure-readings/",
    "temperature": "https://www.nhs.uk/symptoms/fever-in-adults/",
    "sleep": "https://www.cdc.gov/sleep/about/",
    "space_context": "https://www.nasa.gov/ochmo/hsa-standards/",
}

_UNASSESSED_PARAMETERS: tuple[str, ...] = (
    "activity_score_0_100",
    "exercise_minutes_24h",
    "resistance_training_minutes_24h",
    "muscle_mass_kg",
    "body_fat_pct",
    "bone_density_or_bone_risk",
)

_STATUS_LABELS = {
    "normal": "Normal en indicadores evaluados",
    "precaution": "Precaución",
    "critical": "Crítico",
    "unassessed": "Sin datos evaluables",
}


@dataclass(frozen=True)
class DiagnosticResult:
    """Structured output for the dashboard and event-history integration."""

    astronaut_status: pd.DataFrame
    events: pd.DataFrame
    scope_notes: tuple[str, ...]


def _empty_result() -> DiagnosticResult:
    return DiagnosticResult(
        astronaut_status=pd.DataFrame(columns=STATUS_COLUMNS),
        events=pd.DataFrame(columns=EVENT_COLUMNS),
        scope_notes=_scope_notes(),
    )


def _scope_notes() -> tuple[str, ...]:
    return (
        f"Las referencias clínicas incluidas son generales para adultos; NASA publica estándares médicos específicos de misión ({SOURCE_URLS['space_context']}). Este motor no está validado para microgravedad, EVA ni Marte.",
        "Una lectura aislada no establece un diagnóstico. Confirmar mediciones y seguir el protocolo de la misión y la orientación del personal médico.",
        "Los umbrales de estrés y ánimo son reglas experimentales de autopercepción, no escalas clínicas ni diagnósticos psicológicos.",
        "No se emiten alertas de riesgo óseo, adherencia al ejercicio ni composición corporal: faltan mediciones y referencias individuales validadas.",
        "Todas las lecturas evaluadas por esta versión son datos simulados; no proceden de sensores ni de astronautas reales.",
    )


def _numeric_value(row: pd.Series, parameter: str) -> float | None:
    value = row.get(parameter)
    if value is None or pd.isna(value):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{parameter} must contain numeric values or missing data.") from exc
    if not isfinite(parsed):
        raise ValueError(f"{parameter} must contain finite numeric values.")
    return parsed


def _event_id(
    timestamp: pd.Timestamp,
    astronaut_id: str,
    parameter: str,
    severity: Severity,
) -> str:
    identity = f"{timestamp.isoformat()}|{astronaut_id}|{parameter}|{severity}"
    return sha256(identity.encode("utf-8")).hexdigest()[:16]


def _append_event(
    events: list[dict[str, Any]],
    row: pd.Series,
    *,
    timestamp: pd.Timestamp,
    health_area: str,
    parameter: str,
    value: float | str,
    unit: str,
    severity: Severity,
    reference: str,
    message: str,
    recommendation: str,
    source_url: str,
    experimental: bool = False,
) -> None:
    astronaut_id = str(row["astronaut_id"])
    events.append({
        "event_id": _event_id(timestamp, astronaut_id, parameter, severity),
        "timestamp": timestamp.isoformat(),
        "astronaut_id": astronaut_id,
        "environment": str(row["environment"]),
        "scenario": str(row["scenario"]),
        "health_area": health_area,
        "parameter": parameter,
        "value": value,
        "unit": unit,
        "severity": severity,
        "reference": reference,
        "message": message,
        "recommendation": recommendation,
        "source_url": source_url,
        "experimental": experimental,
    })


def _evaluate_heart_rate(
    row: pd.Series, timestamp: pd.Timestamp, events: list[dict[str, Any]],
) -> bool:
    value = _numeric_value(row, "heart_rate_bpm")
    if value is None:
        return False
    if value > 100:
        _append_event(
            events,
            row,
            timestamp=timestamp,
            health_area="cardiovascular",
            parameter="heart_rate_bpm",
            value=value,
            unit="bpm",
            severity="precaution",
            reference="Adult resting pulse is commonly 60–100 bpm; this comparison is applied only outside EVA.",
            message="La frecuencia cardíaca supera el intervalo general de referencia en una lectura no-EVA.",
            recommendation="Repetir después de al menos 10 minutos de reposo y comunicar al personal médico si permanece elevada o hay síntomas.",
            source_url=SOURCE_URLS["heart_rate"],
        )
    elif value < 40:
        _append_event(
            events,
            row,
            timestamp=timestamp,
            health_area="cardiovascular",
            parameter="heart_rate_bpm",
            value=value,
            unit="bpm",
            severity="precaution",
            reference="MedlinePlus reports 40–60 bpm for well-trained athletes and 60–100 bpm as a general adult resting range; values below 40 bpm are outside those reference values.",
            message="La frecuencia cardíaca está por debajo de los intervalos generales citados; el contexto y el estado individual importan.",
            recommendation="Confirmar la lectura y comunicarla al personal médico de la misión, especialmente si persiste o hay síntomas.",
            source_url=SOURCE_URLS["heart_rate"],
        )
    return True


def _evaluate_spo2(
    row: pd.Series, timestamp: pd.Timestamp, events: list[dict[str, Any]],
) -> bool:
    value = _numeric_value(row, "spo2_pct")
    if value is None:
        return False
    if value <= 88:
        severity: Severity = "critical"
        reference = "MedlinePlus: 88% or lower warrants immediate medical attention in at-home guidance; this is not a spaceflight protocol."
        message = "SpO₂ igual o inferior al umbral de atención inmediata de la referencia general consultada."
        recommendation = "Confirmar el sensor y avisar de inmediato al personal médico; seguir el protocolo aprobado de la misión."
    elif value <= 92:
        severity = "precaution"
        reference = "MedlinePlus: contact a health care provider at 92% or lower; normal values for most healthy people are 95–100%."
        message = "SpO₂ baja respecto al intervalo general; el resultado de un oxímetro puede variar varios puntos porcentuales."
        recommendation = "Repetir la medición verificando el sensor y avisar al personal médico de la misión."
    elif value < 95:
        severity = "precaution"
        reference = "MedlinePlus reports 95–100% for most healthy people; individual and environmental context can change interpretation."
        message = "SpO₂ por debajo del intervalo habitual citado para la mayoría de adultos sanos."
        recommendation = "Repetir la medición, revisar la calidad de la señal y comparar con el protocolo y la línea base de la misión."
    else:
        return True
    _append_event(
        events,
        row,
        timestamp=timestamp,
        health_area="cardiovascular",
        parameter="spo2_pct",
        value=value,
        unit="%",
        severity=severity,
        reference=reference,
        message=message,
        recommendation=recommendation,
        source_url=SOURCE_URLS["spo2"],
    )
    return True


def _evaluate_blood_pressure(
    row: pd.Series, timestamp: pd.Timestamp, events: list[dict[str, Any]],
) -> bool:
    systolic = _numeric_value(row, "systolic_bp_mmhg")
    diastolic = _numeric_value(row, "diastolic_bp_mmhg")
    if systolic is None or diastolic is None:
        return False

    value = f"{systolic:g}/{diastolic:g}"
    if systolic > 180 or diastolic > 120:
        reference = "AHA adult categories: >180 mmHg systolic and/or >120 mmHg diastolic is severe; a single reading is not a diagnosis."
        message = "La lectura supera el umbral general de presión arterial severamente elevada."
        recommendation = "Repetir la medición al cabo de 1 minuto. Si sigue elevada, contactar al personal médico; ante síntomas nuevos o preocupantes, activar el protocolo de emergencia de la misión."
    elif systolic >= 140 or diastolic >= 90:
        reference = "AHA adult categories: stage 2 begins at ≥140 mmHg systolic or ≥90 mmHg diastolic; categories do not diagnose from one reading."
        message = "La lectura cae en la categoría general de presión arterial etapa 2."
        recommendation = "Repetir con técnica correcta en reposo y comunicar el resultado confirmado al personal médico de la misión."
    elif systolic >= 130 or diastolic >= 80:
        reference = "AHA adult categories: stage 1 begins at 130–139 mmHg systolic or 80–89 mmHg diastolic."
        message = "La lectura cae en la categoría general de presión arterial etapa 1."
        recommendation = "Repetir con técnica correcta en reposo y revisar la tendencia con el personal médico; una lectura aislada no diagnostica hipertensión."
    elif systolic >= 120 and diastolic < 80:
        reference = "AHA adult categories: elevated blood pressure is 120–129 mmHg systolic and <80 mmHg diastolic."
        message = "La lectura cae en la categoría general de presión arterial elevada."
        recommendation = "Confirmar la medición en reposo y revisar la tendencia con el personal médico de la misión."
    else:
        return True

    severity: Severity = "critical" if systolic > 180 or diastolic > 120 else "precaution"
    _append_event(
        events,
        row,
        timestamp=timestamp,
        health_area="cardiovascular",
        parameter="blood_pressure",
        value=value,
        unit="mmHg",
        severity=severity,
        reference=reference,
        message=message,
        recommendation=recommendation,
        source_url=SOURCE_URLS["blood_pressure"],
    )
    return True


def _evaluate_temperature(
    row: pd.Series, timestamp: pd.Timestamp, events: list[dict[str, Any]],
) -> bool:
    value = _numeric_value(row, "temperature_c")
    if value is None:
        return False
    if value >= 38:
        _append_event(
            events,
            row,
            timestamp=timestamp,
            health_area="thermoregulation",
            parameter="temperature_c",
            value=value,
            unit="°C",
            severity="precaution",
            reference="NHS: 38 °C or above is usually considered a high temperature in adults; not a mission-specific threshold.",
            message="La temperatura alcanza el umbral general que suele considerarse fiebre en adultos.",
            recommendation="Confirmar la medición y comunicarla al personal médico si persiste o aparecen síntomas.",
            source_url=SOURCE_URLS["temperature"],
        )
    return True


def _evaluate_sleep(
    row: pd.Series, timestamp: pd.Timestamp, events: list[dict[str, Any]],
) -> bool:
    value = _numeric_value(row, "sleep_hours_24h")
    if value is None:
        return False
    if value < 7:
        _append_event(
            events,
            row,
            timestamp=timestamp,
            health_area="sleep_and_recovery",
            parameter="sleep_hours_24h",
            value=value,
            unit="h/24 h",
            severity="precaution",
            reference="CDC: adults aged 18–60 are generally recommended 7 or more hours per day; individual mission plans may differ.",
            message="El sueño autoinformado está por debajo de la recomendación general diaria para adultos.",
            recommendation="Revisar la oportunidad de descanso y la planificación del sueño con el equipo; considerar el patrón y el plan de sueño de la misión.",
            source_url=SOURCE_URLS["sleep"],
        )
    return True


def _evaluate_self_report(
    row: pd.Series,
    timestamp: pd.Timestamp,
    events: list[dict[str, Any]],
    parameter: str,
    *,
    threshold: float,
    high_is_concern: bool,
    label: str,
) -> bool:
    value = _numeric_value(row, parameter)
    if value is None:
        return False
    flagged = value >= threshold if high_is_concern else value <= threshold
    if flagged:
        criterion = f">={threshold:g}" if high_is_concern else f"<={threshold:g}"
        _append_event(
            events,
            row,
            timestamp=timestamp,
            health_area="mental_wellbeing",
            parameter=parameter,
            value=value,
            unit="/10",
            severity="precaution",
            reference=f"Regla experimental NOSTOS: {label} {criterion} en escala 0–10; umbral no validado clínicamente.",
            message=f"La autopercepción de {label.lower()} alcanza el umbral exploratorio configurado.",
            recommendation="Ofrecer un check-in de bienestar y acceso al apoyo psicosocial o médico disponible, respetando la privacidad. Esto no es un diagnóstico.",
            source_url="",
            experimental=True,
        )
    return True


def evaluate_readings(
    readings: pd.DataFrame,
    history: pd.DataFrame | None = None,
    environment: str | None = None,
) -> DiagnosticResult:
    """Evaluate one telemetry update and return crew status plus alert events.

    ``readings`` uses the exact shared telemetry schema and may contain one or
    more astronaut rows, with at most one row per astronaut. ``history`` is
    optional and is used to keep an event ID stable while the same alert
    continues without interruption. It is also validated for schema and
    chronological consistency. The environment is inferred from the readings
    unless provided explicitly.
    Thresholds remain the same for ``station`` and ``mars`` because this
    version has no validated environment-specific medical reference values.
    """
    if not isinstance(readings, pd.DataFrame):
        raise TypeError("readings must be a pandas DataFrame.")
    if readings.empty:
        if len(readings.columns) == 0:
            raise ValueError("readings must include the shared telemetry columns, even when empty.")
        validate_telemetry(readings)
        return _empty_result()

    validate_telemetry(readings)
    if readings["astronaut_id"].duplicated().any():
        raise ValueError("readings must contain at most one current row per astronaut.")

    reading_environments = set(readings["environment"].dropna().astype(str))
    if len(reading_environments) != 1:
        raise ValueError("All current readings must use the same environment.")
    inferred_environment = next(iter(reading_environments))
    if environment is not None:
        if environment not in {"station", "mars"}:
            raise ValueError("environment must be 'station' or 'mars'.")
        if environment != inferred_environment:
            raise ValueError("environment does not match the current telemetry readings.")

    current = readings.copy()
    current["timestamp"] = pd.to_datetime(current["timestamp"], utc=True, errors="raise")
    if current["timestamp"].isna().any():
        raise ValueError("timestamp cannot be missing.")

    if history is None:
        previous = pd.DataFrame(columns=VITAL_COLUMNS)
    else:
        if not isinstance(history, pd.DataFrame):
            raise TypeError("history must be a pandas DataFrame or None.")
        previous = history.copy()
        if previous.empty and len(previous.columns) == 0:
            previous = pd.DataFrame(columns=VITAL_COLUMNS)
        validate_telemetry(previous)
        if not previous.empty:
            previous["timestamp"] = pd.to_datetime(previous["timestamp"], utc=True, errors="raise")
            if previous["timestamp"].isna().any():
                raise ValueError("history timestamps cannot be missing.")
            latest_by_astronaut = previous.groupby("astronaut_id")["timestamp"].max()
            for _, row in current.iterrows():
                last_timestamp = latest_by_astronaut.get(row["astronaut_id"])
                if last_timestamp is not None and row["timestamp"] < last_timestamp:
                    raise ValueError(
                        f"Current reading for {row['astronaut_id']} predates the supplied history."
                    )

    events: list[dict[str, Any]] = []
    statuses: list[dict[str, Any]] = []

    # Respect the common update order while still allowing a single-astronaut query.
    order = {astronaut_id: index for index, astronaut_id in enumerate(ASTRONAUT_IDS)}
    current = current.assign(_order=current["astronaut_id"].map(order)).sort_values("_order")

    for _, row in current.iterrows():
        timestamp = row["timestamp"]
        scenario = str(row["scenario"])
        before = len(events)
        evaluated: list[str] = []
        missing: list[str] = []
        unassessed = list(_UNASSESSED_PARAMETERS)

        # Heart rate and blood pressure values rise with physical effort, so
        # resting references are deliberately suppressed during EVA scenarios.
        if scenario == "eva":
            unassessed.extend(("heart_rate_bpm (EVA context)", "blood_pressure (EVA context)"))
            if _evaluate_spo2(row, timestamp, events):
                evaluated.append("spo2_pct")
            else:
                missing.append("spo2_pct")
            if _evaluate_temperature(row, timestamp, events):
                evaluated.append("temperature_c")
            else:
                missing.append("temperature_c")
        else:
            if _evaluate_heart_rate(row, timestamp, events):
                evaluated.append("heart_rate_bpm")
            else:
                missing.append("heart_rate_bpm")
            if _evaluate_spo2(row, timestamp, events):
                evaluated.append("spo2_pct")
            else:
                missing.append("spo2_pct")
            if _evaluate_blood_pressure(row, timestamp, events):
                evaluated.append("blood_pressure")
            elif (
                _numeric_value(row, "systolic_bp_mmhg") is None
                or _numeric_value(row, "diastolic_bp_mmhg") is None
            ):
                missing.append("blood_pressure")
            if _evaluate_temperature(row, timestamp, events):
                evaluated.append("temperature_c")
            else:
                missing.append("temperature_c")

        if _evaluate_sleep(row, timestamp, events):
            evaluated.append("sleep_hours_24h")
        else:
            missing.append("sleep_hours_24h")
        if _evaluate_self_report(
            row,
            timestamp,
            events,
            "stress_score_0_10",
            threshold=8,
            high_is_concern=True,
            label="estrés percibido",
        ):
            evaluated.append("stress_score_0_10")
        else:
            missing.append("stress_score_0_10")
        if _evaluate_self_report(
            row,
            timestamp,
            events,
            "mood_score_0_10",
            threshold=3,
            high_is_concern=False,
            label="ánimo autoinformado",
        ):
            evaluated.append("mood_score_0_10")
        else:
            missing.append("mood_score_0_10")

        astronaut_events = events[before:]
        for event in astronaut_events:
            episode_start = _episode_start_timestamp(
                previous,
                astronaut_id=str(row["astronaut_id"]),
                environment=str(row["environment"]),
                current_timestamp=timestamp,
                event=event,
            )
            event["event_id"] = _event_id(
                episode_start,
                str(row["astronaut_id"]),
                str(event["parameter"]),
                event["severity"],
            )
        severities = {event["severity"] for event in astronaut_events}
        if "critical" in severities:
            status = "critical"
        elif "precaution" in severities:
            status = "precaution"
        elif not evaluated:
            status = "unassessed"
        else:
            status = "normal"

        statuses.append({
            "astronaut_id": str(row["astronaut_id"]),
            "environment": str(row["environment"]),
            "status": status,
            "status_label": _STATUS_LABELS[status],
            "active_event_count": len(astronaut_events),
            "attention_parameters": tuple(dict.fromkeys(event["parameter"] for event in astronaut_events)),
            "evaluated_parameters": tuple(evaluated),
            "unassessed_parameters": tuple(unassessed),
            "missing_parameters": tuple(missing),
            "assessment_coverage": "partial",
        })

    return DiagnosticResult(
        astronaut_status=pd.DataFrame(statuses, columns=STATUS_COLUMNS),
        events=pd.DataFrame(events, columns=EVENT_COLUMNS),
        scope_notes=_scope_notes(),
    )


def _historical_event_severity(row: pd.Series, parameter: str) -> str | None:
    """Return the matching alert severity for one prior telemetry row."""
    timestamp = pd.to_datetime(row["timestamp"], utc=True)
    scenario = str(row["scenario"])
    historical_events: list[dict[str, Any]] = []

    if parameter == "heart_rate_bpm" and scenario != "eva":
        _evaluate_heart_rate(row, timestamp, historical_events)
    elif parameter == "spo2_pct":
        _evaluate_spo2(row, timestamp, historical_events)
    elif parameter == "blood_pressure" and scenario != "eva":
        _evaluate_blood_pressure(row, timestamp, historical_events)
    elif parameter == "temperature_c":
        _evaluate_temperature(row, timestamp, historical_events)
    elif parameter == "sleep_hours_24h":
        _evaluate_sleep(row, timestamp, historical_events)
    elif parameter == "stress_score_0_10":
        _evaluate_self_report(
            row, timestamp, historical_events, parameter,
            threshold=8, high_is_concern=True, label="estrés percibido",
        )
    elif parameter == "mood_score_0_10":
        _evaluate_self_report(
            row, timestamp, historical_events, parameter,
            threshold=3, high_is_concern=False, label="ánimo autoinformado",
        )

    for historical_event in historical_events:
        if historical_event["parameter"] == parameter:
            return str(historical_event["severity"])
    return None


def _episode_start_timestamp(
    history: pd.DataFrame,
    *,
    astronaut_id: str,
    environment: str,
    current_timestamp: pd.Timestamp,
    event: dict[str, Any],
) -> pd.Timestamp:
    """Find the start of the current uninterrupted alert in telemetry history."""
    if history.empty:
        return current_timestamp
    member_history = history.loc[
        (history["astronaut_id"] == astronaut_id)
        & (history["environment"] == environment)
    ].sort_values("timestamp", ascending=False)
    episode_start = current_timestamp
    for _, previous_row in member_history.iterrows():
        previous_timestamp = pd.to_datetime(previous_row["timestamp"], utc=True)
        if previous_timestamp >= current_timestamp:
            continue
        previous_severity = _historical_event_severity(previous_row, str(event["parameter"]))
        if previous_severity == event["severity"]:
            episode_start = previous_timestamp
        else:
            break
    return episode_start

