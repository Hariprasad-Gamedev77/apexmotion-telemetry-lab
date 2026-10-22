"""
synthetic.py — Deterministic synthetic data generator
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Generates realistic-looking (but entirely fake) telemetry data for
testing and demonstration. Uses a fixed random seed so output is
identical every time — good for tests and Git diffs.

IMPORTANT: All data is synthetic. This is NOT real Formula 1 or any
other real motorsport telemetry.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


# Fixed seed for reproducibility
_RNG_SEED = 42


def _make_rng(seed: int = _RNG_SEED) -> np.random.Generator:
    """Create a reproducible random number generator."""
    return np.random.default_rng(seed)


def generate_clean_lap(
    n_samples: int = 500,
    lap_distance_m: float = 5200.0,
    seed: int = _RNG_SEED,
) -> pd.DataFrame:
    """
    Generate a clean synthetic lap dataset.

    The lap simulates a circuit with acceleration zones, braking zones,
    and corners. All values are within plausible ranges, time is
    monotonically increasing, and distance is monotonically increasing.

    Args:
        n_samples: Number of data points to generate.
        lap_distance_m: Total lap distance in metres.
        seed: Random seed for reproducibility.

    Returns:
        DataFrame with columns: time_s, distance_m, speed_kmh,
        throttle_pct, brake_pct.
    """
    rng = _make_rng(seed)

    # Distance: evenly spaced with tiny noise
    distance = np.linspace(0, lap_distance_m, n_samples)

    # Create a speed profile that looks like a lap:
    # - Straights (high speed)
    # - Braking zones (speed drops)
    # - Corners (low speed)
    # - Acceleration (speed rises)
    #
    # We use a combination of sine waves to create this pattern.
    t_norm = np.linspace(0, 2 * np.pi * 3, n_samples)  # 3 "sectors"

    # Base speed profile: oscillates between ~80 and ~280 km/h
    base_speed = 180 + 100 * np.sin(t_norm)

    # Add some realistic variation
    noise = rng.normal(0, 2, n_samples)
    speed = np.clip(base_speed + noise, 60, 340)

    # Throttle: high when accelerating, low when braking
    speed_gradient = np.gradient(speed)
    throttle = np.clip(50 + speed_gradient * 15 + rng.normal(0, 2, n_samples), 0, 100)

    # Brake: inverse of throttle, only active during deceleration
    brake = np.clip(-speed_gradient * 12 + rng.normal(0, 1, n_samples), 0, 100)
    # Ensure brake is near zero when throttle is high
    brake[throttle > 60] = np.clip(rng.normal(0, 0.5, (throttle > 60).sum()), 0, 2)

    # Time: derived from speed to be physically consistent
    # dt = ds / v, where ds is distance increment and v is speed
    ds = np.diff(distance)
    v_ms = speed[:-1] / 3.6  # km/h → m/s
    v_ms = np.maximum(v_ms, 1.0)  # avoid division by zero
    dt = ds / v_ms
    time = np.concatenate([[0], np.cumsum(dt)])

    return pd.DataFrame({
        "time_s": np.round(time, 4),
        "distance_m": np.round(distance, 2),
        "speed_kmh": np.round(speed, 2),
        "throttle_pct": np.round(throttle, 2),
        "brake_pct": np.round(brake, 2),
    })


def generate_corrupted_lap(
    n_samples: int = 500,
    lap_distance_m: float = 5200.0,
    seed: int = _RNG_SEED,
) -> pd.DataFrame:
    """
    Generate a synthetic lap dataset with deliberate quality issues.

    The following defects are injected:
      1. Missing values (NaN) in speed and throttle columns.
      2. Duplicate timestamps.
      3. A non-monotonic time reversal.
      4. A distance reversal.
      5. Out-of-range speed values (negative and >380).
      6. Infinite values in brake column.
      7. A large time gap.
      8. A suspicious speed jump.

    This is used for testing the quality engine and for the
    Validation Bench demonstration.

    Args:
        n_samples: Number of data points to generate.
        lap_distance_m: Total lap distance in metres.
        seed: Random seed for reproducibility.

    Returns:
        DataFrame with injected defects.
    """
    # Start with a clean lap
    df = generate_clean_lap(n_samples, lap_distance_m, seed)

    # --- Inject defects ---

    # 1. Missing values: set some speed and throttle values to NaN
    df.loc[10, "speed_kmh"] = np.nan
    df.loc[11, "speed_kmh"] = np.nan
    df.loc[50, "throttle_pct"] = np.nan

    # 2. Duplicate timestamps: make rows 100 and 101 have the same time
    df.loc[101, "time_s"] = df.loc[100, "time_s"]

    # 3. Non-monotonic time: swap time values to create a reversal
    df.loc[200, "time_s"] = df.loc[198, "time_s"] - 0.5

    # 4. Distance reversal: make distance go backwards
    df.loc[300, "distance_m"] = df.loc[299, "distance_m"] - 10.0

    # 5. Out-of-range speed: one negative, one impossibly high
    df.loc[150, "speed_kmh"] = -25.0
    df.loc[350, "speed_kmh"] = 420.0

    # 6. Infinite values in brake
    df.loc[250, "brake_pct"] = np.inf

    # 7. Large time gap: add 5 seconds to all times from row 400 onward
    df.loc[400:, "time_s"] = df.loc[400:, "time_s"] + 5.0

    # 8. Suspicious speed jump: sudden 200 km/h change
    df.loc[450, "speed_kmh"] = df.loc[449, "speed_kmh"] + 200.0

    return df


def generate_minimal_lap(n_samples: int = 5, seed: int = _RNG_SEED) -> pd.DataFrame:
    """
    Generate a very small valid dataset for edge-case testing.

    Args:
        n_samples: Number of samples (default 5, very small).
        seed: Random seed.

    Returns:
        Small but valid DataFrame.
    """
    return generate_clean_lap(n_samples=n_samples, lap_distance_m=500.0, seed=seed)


def generate_second_lap(
    n_samples: int = 500,
    lap_distance_m: float = 5200.0,
    seed: int = 99,
) -> pd.DataFrame:
    """
    Generate a second clean lap for comparison testing.

    Uses a different seed to produce different (but still valid) data.
    The lap distance is the same as the first lap so they can be
    distance-aligned.

    Args:
        n_samples: Number of data points.
        lap_distance_m: Total lap distance (should match first lap).
        seed: Different seed for different data.

    Returns:
        Clean DataFrame with different values.
    """
    return generate_clean_lap(n_samples=n_samples, lap_distance_m=lap_distance_m, seed=seed)


def generate_different_coverage_lap(
    n_samples: int = 400,
    lap_distance_m: float = 4800.0,
    seed: int = 77,
) -> pd.DataFrame:
    """
    Generate a lap with different distance coverage for testing
    alignment edge cases.

    This lap covers a shorter distance, so when compared with a
    5200m lap, the shared coverage is limited.
    """
    return generate_clean_lap(n_samples=n_samples, lap_distance_m=lap_distance_m, seed=seed)


def generate_different_rate_lap(
    n_samples: int = 250,
    lap_distance_m: float = 5200.0,
    seed: int = 55,
) -> pd.DataFrame:
    """
    Generate a lap with a different sampling rate (fewer samples
    over the same distance) for testing alignment interpolation.
    """
    return generate_clean_lap(n_samples=n_samples, lap_distance_m=lap_distance_m, seed=seed)


def save_sample_data(output_dir: str | Path = "sample_data") -> dict[str, Path]:
    """
    Generate and save sample CSV files to disk.

    Returns:
        Dict mapping dataset name to file path.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    files = {}

    clean = generate_clean_lap()
    clean_path = output_dir / "clean_lap.csv"
    clean.to_csv(clean_path, index=False)
    files["clean_lap"] = clean_path

    corrupted = generate_corrupted_lap()
    corrupted_path = output_dir / "corrupted_lap.csv"
    corrupted.to_csv(corrupted_path, index=False)
    files["corrupted_lap"] = corrupted_path

    return files


# When run directly, generate sample data
if __name__ == "__main__":
    saved = save_sample_data()
    for name, path in saved.items():
        print(f"Generated: {path} ({name})")
