"""Simulación reproducible de telemetría biomédica para NOSTOS.

Los valores de este módulo son sintéticos; no representan mediciones clínicas ni
criterios médicos. El módulo solo produce telemetría que cumple el contrato de
datos compartido. La evaluación de alertas corresponde a ``diagnostics.py``.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable, Literal

import numpy as np
import pandas as pd

AstronautId = Literal["AST-01", "AST-02", "AST-03"]
Environment = Literal["station", "mars"]
Scenario = Literal["rest", "eva", "emergency"]

ASTRONAUT_IDS: tuple[AstronautId, ...] = ("AST-01", "AST-02", "AST-03")
ENVIRONMENTS: tuple[Environment, ...] = ("station", "mars")
SCENARIOS: tuple[Scenario, ...] = ("rest", "eva", "emergency")

VITAL_COLUMNS: tuple[str, ...] = (
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
)

NUMERIC_COLUMNS: tuple[str, ...] = tuple(
    column for column in VITAL_COLUMNS
    if column not in {"timestamp", "astronaut_id", "environment", "scenario"}
)
DEFAULT_HISTORY_PATH = Path(__file__).resolve().parents[1] / "data" / "astronaut_vitals.csv"

# Perfiles deliberadamente sintéticos. Mantienen diferencias individuales sin
# pretender describir a personas reales ni rangos de referencia médica.
_PROFILES: dict[AstronautId, dict[str, float]] = {
    "AST-01": {"heart_rate_bpm": 68, "spo2_pct": 98.0, "temperature_c": 36.7,
               "systolic_bp_mmhg": 116, "diastolic_bp_mmhg": 74,
               "exercise_minutes_24h": 75, "resistance_training_minutes_24h": 36,
               "muscle_mass_kg": 43.2, "body_fat_pct": 18.1, "sleep_hours_24h": 7.4,
               "stress_score_0_10": 3.2, "mood_score_0_10": 7.5},
    "AST-02": {"heart_rate_bpm": 72, "spo2_pct": 97.6, "temperature_c": 36.8,
               "systolic_bp_mmhg": 120, "diastolic_bp_mmhg": 77,
               "exercise_minutes_24h": 72, "resistance_training_minutes_24h": 34,
               "muscle_mass_kg": 39.8, "body_fat_pct": 22.4, "sleep_hours_24h": 7.1,
               "stress_score_0_10": 3.8, "mood_score_0_10": 7.0},
    "AST-03": {"heart_rate_bpm": 64, "spo2_pct": 98.2, "temperature_c": 36.6,
               "systolic_bp_mmhg": 112, "diastolic_bp_mmhg": 71,
               "exercise_minutes_24h": 78, "resistance_training_minutes_24h": 38,
               "muscle_mass_kg": 46.1, "body_fat_pct": 15.7, "sleep_hours_24h": 7.7,
               "stress_score_0_10": 2.7, "mood_score_0_10": 7.8},
}

_SCENARIO_EFFECTS: dict[Scenario, dict[str, float]] = {
    "rest": {"heart_rate_bpm": 0, "spo2_pct": 0, "temperature_c": 0,
             "systolic_bp_mmhg": 0, "diastolic_bp_mmhg": 0, "activity": 24,
             "exercise": 0, "resistance": 0, "stress": 0, "mood": 0},
    "eva": {"heart_rate_bpm": 24, "spo2_pct": -0.5, "temperature_c": 0.25,
            "systolic_bp_mmhg": 10, "diastolic_bp_mmhg": 6, "activity": 78,
            "exercise": 8, "resistance": 4, "stress": 1.1, "mood": -0.2},
    "emergency": {"heart_rate_bpm": 42, "spo2_pct": -3.0, "temperature_c": 0.6,
                  "systolic_bp_mmhg": 20, "diastolic_bp_mmhg": 12, "activity": 45,
                  "exercise": 0, "resistance": 0, "stress": 4.2, "mood": -1.6},
}

# Casos controlados para comprobar el flujo de alertas críticas. Estos valores
# son datos sintéticos de una emergencia de prueba, no protocolos médicos ni
# perfiles de astronautas reales.
_EMERGENCY_CRITICAL_OVERRIDES: dict[AstronautId, dict[str, float]] = {
    "AST-02": {"spo2_pct": 88.0},
    "AST-03": {"systolic_bp_mmhg": 185.0, "diastolic_bp_mmhg": 122.0},
}


def _validate_choice(value: str, choices: Iterable[str], name: str) -> None:
    if value not in choices:
        allowed = ", ".join(choices)
        raise ValueError(f"{name} must be one of: {allowed}. Received {value!r}.")


def _as_utc_timestamp(value: datetime | pd.Timestamp | None) -> pd.Timestamp:
    timestamp = pd.Timestamp.now(tz="UTC") if value is None else pd.Timestamp(value)
    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize("UTC")
    return timestamp.tz_convert("UTC")


def _previous_values(history: pd.DataFrame, astronaut_id: AstronautId) -> dict[str, float]:
    if history.empty:
        return _PROFILES[astronaut_id]
    astronaut_history = history.loc[history["astronaut_id"] == astronaut_id]
    if astronaut_history.empty:
        return _PROFILES[astronaut_id]
    last = astronaut_history.sort_values("timestamp").iloc[-1]
    return {column: float(last[column]) for column in _PROFILES[astronaut_id]}


def validate_telemetry(frame: pd.DataFrame, *, require_all_astronauts: bool = False) -> None:
    """Validate the shared telemetry schema and its categorical fields.

    This deliberately validates structure rather than medical normality, which
    is owned by the diagnostic engine.
    """
    missing = [column for column in VITAL_COLUMNS if column not in frame.columns]
    extra = [column for column in frame.columns if column not in VITAL_COLUMNS]
    if missing or extra:
        raise ValueError(f"Telemetry schema mismatch. Missing={missing}; extra={extra}.")
    if not frame["astronaut_id"].isin(ASTRONAUT_IDS).all():
        raise ValueError("astronaut_id contains an unsupported identifier.")
    if not frame["environment"].isin(ENVIRONMENTS).all():
        raise ValueError("environment must be 'station' or 'mars'.")
    if not frame["scenario"].isin(SCENARIOS).all():
        raise ValueError("scenario must be 'rest', 'eva', or 'emergency'.")
    try:
        timestamps = pd.to_datetime(frame["timestamp"], utc=True, errors="raise")
    except (TypeError, ValueError) as exc:
        raise ValueError("timestamp must contain valid UTC-convertible datetimes.") from exc
    if timestamps.isna().any():
        raise ValueError("timestamp cannot be missing.")
    for column in NUMERIC_COLUMNS:
        numeric = pd.to_numeric(frame[column], errors="coerce")
        invalid = frame[column].notna() & (numeric.isna() | ~np.isfinite(numeric))
        if invalid.any():
            raise ValueError(f"{column} must contain finite numeric values or missing data.")
    if require_all_astronauts:
        if len(frame) != len(ASTRONAUT_IDS) or set(frame["astronaut_id"]) != set(ASTRONAUT_IDS):
            raise ValueError("An update must contain exactly one reading for AST-01, AST-02, and AST-03.")


def simulate_update(
    history: pd.DataFrame | None,
    environment: Environment,
    scenario: Scenario,
    *,
    timestamp: datetime | pd.Timestamp | None = None,
    seed: int | None = None,
) -> pd.DataFrame:
    """Create one simultaneous reading for each astronaut.

    Pass a ``seed`` and a timestamp to obtain repeatable output. Slow-moving
    body-composition, sleep, and 24-hour exercise totals are bounded to small
    steps from each astronaut's latest historical reading. Selecting rest or
    emergency changes the current activity profile without resetting the
    rolling daily exercise totals.
    """
    _validate_choice(environment, ENVIRONMENTS, "environment")
    _validate_choice(scenario, SCENARIOS, "scenario")
    previous_history = pd.DataFrame(columns=VITAL_COLUMNS) if history is None else history.copy()
    if not previous_history.empty:
        validate_telemetry(previous_history)
        previous_history["timestamp"] = pd.to_datetime(previous_history["timestamp"], utc=True)

    rng = np.random.default_rng(seed)
    now = _as_utc_timestamp(timestamp)
    effect = _SCENARIO_EFFECTS[scenario]
    # These differences are simulation parameters, not clinical reference ranges.
    mars = {"heart_rate_bpm": 1.5, "stress": 0.4, "sleep": -0.2} if environment == "mars" else {}
    records: list[dict[str, object]] = []

    for astronaut_id in ASTRONAUT_IDS:
        previous = _previous_values(previous_history, astronaut_id)
        profile = _PROFILES[astronaut_id]
        activity = np.clip(effect["activity"] + rng.normal(0, 5), 0, 100)
        exercise_target = profile["exercise_minutes_24h"] + effect["exercise"]
        resistance_target = profile["resistance_training_minutes_24h"] + effect["resistance"]
        record: dict[str, object] = {
            "timestamp": now.isoformat(),
            "astronaut_id": astronaut_id,
            "environment": environment,
            "scenario": scenario,
            "heart_rate_bpm": round(max(35, previous["heart_rate_bpm"] * 0.35 + (_PROFILES[astronaut_id]["heart_rate_bpm"] + effect["heart_rate_bpm"] + mars.get("heart_rate_bpm", 0)) * 0.65 + rng.normal(0, 2.5))),
            "spo2_pct": round(float(np.clip(_PROFILES[astronaut_id]["spo2_pct"] + effect["spo2_pct"] + rng.normal(0, 0.25), 85, 100)), 1),
            "temperature_c": round(float(np.clip(_PROFILES[astronaut_id]["temperature_c"] + effect["temperature_c"] + rng.normal(0, 0.08), 34, 40)), 1),
            "systolic_bp_mmhg": round(max(70, _PROFILES[astronaut_id]["systolic_bp_mmhg"] + effect["systolic_bp_mmhg"] + rng.normal(0, 3))),
            "diastolic_bp_mmhg": round(max(40, _PROFILES[astronaut_id]["diastolic_bp_mmhg"] + effect["diastolic_bp_mmhg"] + rng.normal(0, 2))),
            "activity_score_0_100": round(float(activity), 1),
            "exercise_minutes_24h": round(float(np.clip(previous["exercise_minutes_24h"] * 0.85 + exercise_target * 0.15 + rng.normal(0, 0.6), 0, 180)), 1),
            "resistance_training_minutes_24h": round(float(np.clip(previous["resistance_training_minutes_24h"] * 0.85 + resistance_target * 0.15 + rng.normal(0, 0.3), 0, 120)), 1),
            "muscle_mass_kg": round(float(previous["muscle_mass_kg"] + rng.normal(0, 0.012)), 2),
            "body_fat_pct": round(float(np.clip(previous["body_fat_pct"] + rng.normal(0, 0.008), 5, 45)), 2),
            "sleep_hours_24h": round(float(np.clip(previous["sleep_hours_24h"] * 0.7 + (_PROFILES[astronaut_id]["sleep_hours_24h"] + mars.get("sleep", 0)) * 0.3 + rng.normal(0, 0.12), 0, 14)), 1),
            "stress_score_0_10": round(float(np.clip(previous["stress_score_0_10"] * 0.4 + (_PROFILES[astronaut_id]["stress_score_0_10"] + effect["stress"] + mars.get("stress", 0)) * 0.6 + rng.normal(0, 0.25), 0, 10)), 1),
            "mood_score_0_10": round(float(np.clip(previous["mood_score_0_10"] * 0.5 + (_PROFILES[astronaut_id]["mood_score_0_10"] + effect["mood"]) * 0.5 + rng.normal(0, 0.2), 0, 10)), 1),
        }
        if scenario == "emergency":
            record.update(_EMERGENCY_CRITICAL_OVERRIDES.get(astronaut_id, {}))
        records.append(record)

    update = pd.DataFrame(records, columns=VITAL_COLUMNS)
    validate_telemetry(update, require_all_astronauts=True)
    return update


def generate_initial_history(
    environment: Environment = "station",
    *,
    periods: int = 24,
    interval_minutes: int = 30,
    end_time: datetime | pd.Timestamp | None = None,
    seed: int = 42,
) -> pd.DataFrame:
    """Generate reproducible, chronological seed history for all three astronauts."""
    if periods < 1 or interval_minutes < 1:
        raise ValueError("periods and interval_minutes must be positive integers.")
    final_time = _as_utc_timestamp(end_time)
    start_time = final_time - timedelta(minutes=interval_minutes * (periods - 1))
    history = pd.DataFrame(columns=VITAL_COLUMNS)
    for index in range(periods):
        reading_time = start_time + timedelta(minutes=interval_minutes * index)
        # The mix gives charts varied but reproducible, non-emergency baseline data.
        scenario: Scenario = "eva" if index % 8 == 5 else "rest"
        update = simulate_update(history, environment, scenario, timestamp=reading_time, seed=seed + index)
        # Avoid concatenating against the all-object empty seed frame: recent
        # Pandas versions warn that its dtype inference will change.
        history = update.copy() if history.empty else pd.concat([history, update], ignore_index=True)
    return history


def load_history(path: str | Path) -> pd.DataFrame:
    """Load and validate a telemetry CSV while preserving UTC timestamps."""
    frame = pd.read_csv(path)
    validate_telemetry(frame)
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    return frame.loc[:, VITAL_COLUMNS]


def load_default_history() -> pd.DataFrame:
    """Load the versioned sample history shipped in ``data/astronaut_vitals.csv``.

    The dashboard may use this fixture for demos or tests. Live session history
    remains in memory and should be extended with :func:`append_update`.
    """
    return load_history(DEFAULT_HISTORY_PATH)


def append_update(history: pd.DataFrame, update: pd.DataFrame) -> pd.DataFrame:
    """Return chronological history with a valid three-astronaut update appended."""
    validate_telemetry(history)
    validate_telemetry(update, require_all_astronauts=True)
    combined = pd.concat([history, update], ignore_index=True)
    combined["timestamp"] = pd.to_datetime(combined["timestamp"], utc=True)
    return combined.sort_values(["timestamp", "astronaut_id"], kind="stable").reset_index(drop=True)
