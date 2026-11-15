"""Pruebas del motor de evaluación diagnóstica no clínica."""

import pytest

from src.diagnostics import EVENT_COLUMNS, STATUS_COLUMNS, evaluate_readings


def test_normal_readings_return_status_and_expected_columns(telemetry_update):
    result = evaluate_readings(telemetry_update)

    assert tuple(result.astronaut_status.columns) == STATUS_COLUMNS
    assert tuple(result.events.columns) == EVENT_COLUMNS
    assert len(result.astronaut_status) == len(telemetry_update)
    assert set(result.astronaut_status["status"]).issubset(
        {"normal", "precaution", "critical", "unassessed"}
    )


def test_low_spo2_creates_critical_event(telemetry_update):
    readings = telemetry_update.copy()
    readings.loc[readings.index[0], "spo2_pct"] = 88

    result = evaluate_readings(readings)
    event = result.events.loc[result.events["parameter"] == "spo2_pct"].iloc[0]

    assert event["severity"] == "critical"
    assert event["astronaut_id"] == readings.iloc[0]["astronaut_id"]
    assert result.astronaut_status.iloc[0]["status"] == "critical"


def test_duplicate_current_astronaut_is_rejected(telemetry_update):
    duplicate = telemetry_update.iloc[[0, 0]].copy()

    with pytest.raises(ValueError, match="at most one current row"):
        evaluate_readings(duplicate)


def test_mismatched_environment_argument_is_rejected(telemetry_update):
    with pytest.raises(ValueError, match="does not match"):
        evaluate_readings(telemetry_update, environment="mars")


def test_current_reading_older_than_history_is_rejected(telemetry_update):
    history = telemetry_update.copy()
    current = telemetry_update.copy()
    current["timestamp"] = "2026-11-15T11:00:00Z"

    with pytest.raises(ValueError, match="predates the supplied history"):
        evaluate_readings(current, history=history)
