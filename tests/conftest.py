"""
conftest.py — Shared test fixtures
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Provides reusable test data and helper functions for all test modules.
Uses the deterministic synthetic data generator so every test run
produces identical data.
"""

import io
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from apexmotion.config import QualityThresholds
from apexmotion.synthetic import (
    generate_clean_lap,
    generate_corrupted_lap,
    generate_minimal_lap,
)


# ---------------------------------------------------------------------------
# DataFrame fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def clean_df() -> pd.DataFrame:
    """A clean, valid lap dataset with 500 samples."""
    return generate_clean_lap()


@pytest.fixture
def corrupted_df() -> pd.DataFrame:
    """A lap dataset with deliberate quality issues."""
    return generate_corrupted_lap()


@pytest.fixture
def minimal_df() -> pd.DataFrame:
    """A very small but valid dataset (5 samples)."""
    return generate_minimal_lap()


@pytest.fixture
def empty_df() -> pd.DataFrame:
    """An empty DataFrame with correct columns."""
    return pd.DataFrame(columns=["time_s", "distance_m", "speed_kmh", "throttle_pct", "brake_pct"])


@pytest.fixture
def default_thresholds() -> QualityThresholds:
    """Default quality thresholds."""
    return QualityThresholds()


# ---------------------------------------------------------------------------
# CSV byte fixtures (for loader tests)
# ---------------------------------------------------------------------------

@pytest.fixture
def clean_csv_bytes() -> bytes:
    """Clean lap data as raw CSV bytes."""
    df = generate_clean_lap()
    return df.to_csv(index=False).encode("utf-8")


@pytest.fixture
def corrupted_csv_bytes() -> bytes:
    """Corrupted lap data as raw CSV bytes."""
    df = generate_corrupted_lap()
    return df.to_csv(index=False).encode("utf-8")


@pytest.fixture
def empty_csv_bytes() -> bytes:
    """Empty file (0 bytes)."""
    return b""


@pytest.fixture
def header_only_csv_bytes() -> bytes:
    """CSV with headers but no data rows."""
    return b"time_s,distance_m,speed_kmh\n"


@pytest.fixture
def malformed_csv_bytes() -> bytes:
    """Malformed CSV that can't be parsed cleanly."""
    return b"a,b,c\n1,2\n3,4,5,6\n"


@pytest.fixture
def missing_columns_csv_bytes() -> bytes:
    """CSV that's missing required columns."""
    return b"temperature,pressure,altitude\n20.5,1013,500\n21.0,1012,502\n"


@pytest.fixture
def renamed_columns_csv_bytes() -> bytes:
    """CSV with non-standard but mappable column names."""
    df = generate_clean_lap(n_samples=20)
    df = df.rename(columns={
        "time_s": "elapsed",
        "distance_m": "lap_distance",
        "speed_kmh": "velocity",
        "throttle_pct": "tps",
        "brake_pct": "brake_pressure",
    })
    return df.to_csv(index=False).encode("utf-8")


@pytest.fixture
def speed_in_ms_csv_bytes() -> bytes:
    """CSV with speed in m/s instead of km/h."""
    df = generate_clean_lap(n_samples=20)
    df["speed_kmh"] = df["speed_kmh"] / 3.6  # Convert to m/s
    df = df.rename(columns={"speed_kmh": "speed"})
    return df.to_csv(index=False).encode("utf-8")


@pytest.fixture
def nan_heavy_df() -> pd.DataFrame:
    """DataFrame with many NaN values."""
    df = generate_clean_lap(n_samples=50)
    rng = np.random.default_rng(42)
    nan_indices = rng.choice(50, 15, replace=False)
    df.loc[nan_indices, "speed_kmh"] = np.nan
    return df


@pytest.fixture
def inf_df() -> pd.DataFrame:
    """DataFrame with infinity values."""
    df = generate_clean_lap(n_samples=50)
    df.loc[10, "speed_kmh"] = np.inf
    df.loc[20, "brake_pct"] = -np.inf
    return df


@pytest.fixture
def duplicate_time_df() -> pd.DataFrame:
    """DataFrame with duplicate timestamps."""
    df = generate_clean_lap(n_samples=50)
    df.loc[10, "time_s"] = df.loc[9, "time_s"]
    df.loc[20, "time_s"] = df.loc[19, "time_s"]
    df.loc[21, "time_s"] = df.loc[19, "time_s"]
    return df


@pytest.fixture
def reversed_time_df() -> pd.DataFrame:
    """DataFrame with reversed timestamps."""
    df = generate_clean_lap(n_samples=50)
    # Swap two time values to create reversal
    df.loc[25, "time_s"] = df.loc[20, "time_s"] - 1.0
    return df


@pytest.fixture
def distance_reversal_df() -> pd.DataFrame:
    """DataFrame with distance going backwards."""
    df = generate_clean_lap(n_samples=50)
    df.loc[30, "distance_m"] = df.loc[25, "distance_m"]
    return df


@pytest.fixture
def large_gap_df() -> pd.DataFrame:
    """DataFrame with a large time gap."""
    df = generate_clean_lap(n_samples=50)
    # Add 10 seconds to all times from row 25 onward
    df.loc[25:, "time_s"] = df.loc[25:, "time_s"] + 10.0
    return df


@pytest.fixture
def flat_signal_df() -> pd.DataFrame:
    """DataFrame where all signals are constant (flat)."""
    df = generate_clean_lap(n_samples=50)
    df["speed_kmh"] = 200.0
    df["throttle_pct"] = 75.0
    df["brake_pct"] = 0.0
    return df


@pytest.fixture
def out_of_range_df() -> pd.DataFrame:
    """DataFrame with values outside plausible ranges."""
    df = generate_clean_lap(n_samples=50)
    df.loc[5, "speed_kmh"] = -50.0
    df.loc[10, "speed_kmh"] = 500.0
    df.loc[15, "throttle_pct"] = 150.0
    df.loc[20, "brake_pct"] = -10.0
    return df


@pytest.fixture
def suspicious_jump_df() -> pd.DataFrame:
    """DataFrame with sudden suspicious value jumps."""
    df = generate_clean_lap(n_samples=50)
    # Insert a sudden 200 km/h speed spike
    df.loc[25, "speed_kmh"] = df.loc[24, "speed_kmh"] + 200.0
    return df


@pytest.fixture
def tmp_csv_file(clean_csv_bytes, tmp_path) -> Path:
    """Write clean CSV to a temporary file and return the path."""
    p = tmp_path / "test_lap.csv"
    p.write_bytes(clean_csv_bytes)
    return p
