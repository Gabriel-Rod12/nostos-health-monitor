"""Fixtures compartidas para las pruebas de NOSTOS."""

import pandas as pd
import pytest

from src.telemetry import simulate_update


@pytest.fixture
def telemetry_update():
    return simulate_update(
        history=None,
        environment="station",
        scenario="rest",
        timestamp=pd.Timestamp("2026-11-15T12:00:00Z"),
        seed=123,
    )
