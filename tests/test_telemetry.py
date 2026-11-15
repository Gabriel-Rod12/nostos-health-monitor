"""Pruebas del contrato y la generación de telemetría."""

import pandas as pd
import pytest

from src.telemetry import (
    ASTRONAUT_IDS,
    VITAL_COLUMNS,
    append_update,
    generate_initial_history,
    simulate_update,
    validate_telemetry,
)


def test_simulate_update_returns_one_row_per_astronaut():
    update = simulate_update(None, "station", "rest", timestamp="2026-11-15T12:00:00Z", seed=7)

    assert len(update) == len(ASTRONAUT_IDS)
    assert set(update["astronaut_id"]) == set(ASTRONAUT_IDS)
    assert tuple(update.columns) == VITAL_COLUMNS
    validate_telemetry(update, require_all_astronauts=True)


def test_simulation_is_reproducible_with_same_seed_and_timestamp():
    kwargs = {"timestamp": "2026-11-15T12:00:00Z", "seed": 99}

    first = simulate_update(None, "mars", "eva", **kwargs)
    second = simulate_update(None, "mars", "eva", **kwargs)

    pd.testing.assert_frame_equal(first, second)


def test_validate_telemetry_rejects_missing_column(telemetry_update):
    invalid = telemetry_update.drop(columns=["spo2_pct"])

    with pytest.raises(ValueError, match="Telemetry schema mismatch"):
        validate_telemetry(invalid)


def test_validate_telemetry_rejects_unsupported_environment(telemetry_update):
    invalid = telemetry_update.copy()
    invalid.loc[0, "environment"] = "moon"

    with pytest.raises(ValueError, match="environment"):
        validate_telemetry(invalid)


def test_validate_telemetry_rejects_infinite_numeric_value(telemetry_update):
    invalid = telemetry_update.copy()
    invalid.loc[0, "spo2_pct"] = float("inf")

    with pytest.raises(ValueError, match="finite numeric"):
        validate_telemetry(invalid)


def test_generate_initial_history_has_requested_number_of_updates():
    history = generate_initial_history(
        periods=4, end_time="2026-11-15T12:00:00Z", seed=10
    )

    assert len(history) == 4 * len(ASTRONAUT_IDS)
    validate_telemetry(history)
    timestamps = pd.to_datetime(history["timestamp"], utc=True)
    assert timestamps.is_monotonic_increasing


def test_append_update_preserves_all_rows_and_contract(telemetry_update):
    history = generate_initial_history(
        periods=2, end_time="2026-11-15T11:30:00Z", seed=10
    )

    combined = append_update(history, telemetry_update)

    assert len(combined) == len(history) + len(telemetry_update)
    validate_telemetry(combined)
    assert pd.to_datetime(combined["timestamp"], utc=True).is_monotonic_increasing
