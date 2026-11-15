"""Pruebas del flujo conjunto telemetría → diagnóstico → historial."""

import pandas as pd

from src.diagnostics import EVENT_COLUMNS, evaluate_readings
from src.telemetry import append_update, generate_initial_history, simulate_update


def test_telemetry_diagnostics_and_history_flow():
    history = generate_initial_history(
        periods=3, end_time="2026-11-15T11:00:00Z", seed=21
    )
    update = simulate_update(
        history,
        environment="station",
        scenario="emergency",
        timestamp="2026-11-15T11:30:00Z",
        seed=22,
    )

    diagnostic_result = evaluate_readings(update, history=history, environment="station")
    updated_history = append_update(history, update)

    assert not diagnostic_result.astronaut_status.empty
    assert tuple(diagnostic_result.events.columns) == EVENT_COLUMNS
    assert len(updated_history) == len(history) + len(update)
    assert set(updated_history["astronaut_id"]) == {"AST-01", "AST-02", "AST-03"}
    assert pd.to_datetime(updated_history["timestamp"], utc=True).is_monotonic_increasing


def test_continuing_alert_keeps_event_id_stable():
    history = generate_initial_history(
        periods=1, end_time="2026-11-15T10:00:00Z", seed=31
    )
    first = simulate_update(
        history, "station", "rest",
        timestamp="2026-11-15T10:30:00Z", seed=32,
    )
    first.loc[first.index[0], "spo2_pct"] = 88
    first_result = evaluate_readings(first, history=history)
    updated_history = append_update(history, first)

    second = simulate_update(
        updated_history, "station", "rest",
        timestamp="2026-11-15T11:00:00Z", seed=33,
    )
    second.loc[second.index[0], "spo2_pct"] = 88
    second_result = evaluate_readings(second, history=updated_history)

    first_id = first_result.events.loc[first_result.events["parameter"] == "spo2_pct", "event_id"].iloc[0]
    second_id = second_result.events.loc[second_result.events["parameter"] == "spo2_pct", "event_id"].iloc[0]
    assert first_id == second_id
