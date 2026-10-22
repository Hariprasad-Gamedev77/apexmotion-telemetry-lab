"""
test_synthetic.py — Tests for synthetic data generator
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Covers:
  - Deterministic output (same seed → same data)
  - Clean data properties (monotonic time, monotonic distance, valid ranges)
  - Corrupted data has injected defects
  - Different seeds produce different data
  - Minimal lap edge cases
  - File saving works correctly
"""

import numpy as np
import pandas as pd
import pytest

from apexmotion.synthetic import (
    generate_clean_lap,
    generate_corrupted_lap,
    generate_minimal_lap,
    generate_second_lap,
    generate_different_coverage_lap,
    generate_different_rate_lap,
    save_sample_data,
)


class TestCleanLapGeneration:
    """Tests for the clean lap generator."""

    def test_deterministic_output(self):
        """Same seed should produce identical data every time."""
        df1 = generate_clean_lap(seed=42)
        df2 = generate_clean_lap(seed=42)
        pd.testing.assert_frame_equal(df1, df2)

    def test_different_seeds_different_data(self):
        """Different seeds should produce different data."""
        df1 = generate_clean_lap(seed=42)
        df2 = generate_clean_lap(seed=99)
        assert not df1["speed_kmh"].equals(df2["speed_kmh"])

    def test_correct_row_count(self):
        """Should produce the requested number of samples."""
        df = generate_clean_lap(n_samples=200)
        assert len(df) == 200

    def test_correct_columns(self):
        """Should have all canonical columns."""
        df = generate_clean_lap()
        expected = {"time_s", "distance_m", "speed_kmh", "throttle_pct", "brake_pct"}
        assert set(df.columns) == expected

    def test_time_monotonic(self):
        """Time should be strictly increasing."""
        df = generate_clean_lap()
        diffs = df["time_s"].diff().iloc[1:]
        assert (diffs > 0).all(), "Time is not strictly monotonic"

    def test_distance_monotonic(self):
        """Distance should be monotonically increasing."""
        df = generate_clean_lap()
        diffs = df["distance_m"].diff().iloc[1:]
        assert (diffs >= 0).all(), "Distance is not monotonic"

    def test_speed_in_range(self):
        """Speed should be within plausible bounds."""
        df = generate_clean_lap()
        assert df["speed_kmh"].min() >= 0, "Negative speed found"
        assert df["speed_kmh"].max() <= 380, "Speed exceeds 380 km/h"

    def test_throttle_in_range(self):
        """Throttle should be 0-100%."""
        df = generate_clean_lap()
        assert df["throttle_pct"].min() >= 0
        assert df["throttle_pct"].max() <= 100

    def test_brake_in_range(self):
        """Brake should be 0-100%."""
        df = generate_clean_lap()
        assert df["brake_pct"].min() >= 0
        assert df["brake_pct"].max() <= 100

    def test_no_nan_values(self):
        """Clean data should have no NaN values."""
        df = generate_clean_lap()
        assert not df.isna().any().any()

    def test_no_infinite_values(self):
        """Clean data should have no infinite values."""
        df = generate_clean_lap()
        for col in df.columns:
            assert not np.isinf(df[col]).any()

    def test_distance_starts_at_zero(self):
        """Distance should start at 0."""
        df = generate_clean_lap()
        assert df["distance_m"].iloc[0] == 0.0

    def test_distance_reaches_target(self):
        """Distance should reach the target lap distance."""
        target = 5200.0
        df = generate_clean_lap(lap_distance_m=target)
        assert abs(df["distance_m"].iloc[-1] - target) < 1.0

    def test_custom_distance(self):
        """Custom lap distance should be respected."""
        df = generate_clean_lap(lap_distance_m=3000.0)
        assert abs(df["distance_m"].iloc[-1] - 3000.0) < 1.0


class TestCorruptedLapGeneration:
    """Tests for the corrupted lap generator."""

    def test_deterministic_output(self):
        """Same seed should produce identical corrupted data."""
        df1 = generate_corrupted_lap(seed=42)
        df2 = generate_corrupted_lap(seed=42)
        pd.testing.assert_frame_equal(df1, df2)

    def test_has_nan_values(self):
        """Should contain NaN values at expected locations."""
        df = generate_corrupted_lap()
        assert pd.isna(df.loc[10, "speed_kmh"])
        assert pd.isna(df.loc[11, "speed_kmh"])
        assert pd.isna(df.loc[50, "throttle_pct"])

    def test_has_duplicate_timestamp(self):
        """Should have duplicate timestamps at rows 100-101."""
        df = generate_corrupted_lap()
        assert df.loc[100, "time_s"] == df.loc[101, "time_s"]

    def test_has_time_reversal(self):
        """Should have a time reversal at row 200."""
        df = generate_corrupted_lap()
        assert df.loc[200, "time_s"] < df.loc[199, "time_s"]

    def test_has_distance_reversal(self):
        """Should have a distance reversal at row 300."""
        df = generate_corrupted_lap()
        assert df.loc[300, "distance_m"] < df.loc[299, "distance_m"]

    def test_has_negative_speed(self):
        """Should have a negative speed value."""
        df = generate_corrupted_lap()
        assert df.loc[150, "speed_kmh"] == -25.0

    def test_has_excessive_speed(self):
        """Should have a speed above 380 km/h."""
        df = generate_corrupted_lap()
        assert df.loc[350, "speed_kmh"] == 420.0

    def test_has_infinite_value(self):
        """Should have an infinite brake value."""
        df = generate_corrupted_lap()
        assert np.isinf(df.loc[250, "brake_pct"])


class TestMinimalLap:
    """Tests for the minimal (small) lap generator."""

    def test_correct_size(self):
        """Should produce the requested small number of samples."""
        df = generate_minimal_lap(n_samples=5)
        assert len(df) == 5

    def test_valid_data(self):
        """Even minimal data should be valid."""
        df = generate_minimal_lap()
        assert not df.isna().any().any()
        assert (df["time_s"].diff().iloc[1:] > 0).all()


class TestSecondLap:
    """Tests for the second-lap generator."""

    def test_different_from_first(self):
        """Second lap should be different from the first."""
        df1 = generate_clean_lap()
        df2 = generate_second_lap()
        assert not df1["speed_kmh"].equals(df2["speed_kmh"])

    def test_same_distance_range(self):
        """Both laps should cover the same distance for comparison."""
        df1 = generate_clean_lap()
        df2 = generate_second_lap()
        assert abs(df1["distance_m"].iloc[-1] - df2["distance_m"].iloc[-1]) < 1.0


class TestDifferentCoverage:
    """Tests for laps with different distance coverage."""

    def test_shorter_distance(self):
        """Different coverage lap should have a different max distance."""
        df = generate_different_coverage_lap()
        assert df["distance_m"].iloc[-1] < 5200.0


class TestDifferentRate:
    """Tests for laps with different sampling rates."""

    def test_fewer_samples(self):
        """Different rate lap should have fewer samples."""
        df = generate_different_rate_lap()
        clean = generate_clean_lap()
        assert len(df) < len(clean)


class TestSaveData:
    """Tests for saving sample data to disk."""

    def test_save_creates_files(self, tmp_path):
        """Should create CSV files in the specified directory."""
        files = save_sample_data(tmp_path)
        assert "clean_lap" in files
        assert "corrupted_lap" in files
        assert files["clean_lap"].exists()
        assert files["corrupted_lap"].exists()

    def test_saved_files_readable(self, tmp_path):
        """Saved files should be valid CSVs."""
        files = save_sample_data(tmp_path)
        for name, path in files.items():
            df = pd.read_csv(path)
            assert len(df) > 0
            assert "time_s" in df.columns
