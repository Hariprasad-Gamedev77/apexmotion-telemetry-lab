"""
test_loader.py — Tests for CSV loading and schema validation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Covers:
  - Clean CSV loading from bytes, file path, and file-like objects
  - Column auto-mapping from aliases
  - Explicit column mapping
  - Unit conversion (m/s → km/h)
  - Missing required columns
  - Empty files, header-only files, malformed CSVs
  - File hash computation
  - Non-existent file paths
"""

import io
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from apexmotion.loader import load_csv, compute_file_hash


class TestLoadCleanCSV:
    """Tests for loading valid, well-formed CSV data."""

    def test_load_from_bytes(self, clean_csv_bytes):
        """Loading from raw bytes should succeed."""
        result = load_csv(clean_csv_bytes)
        assert result.success is True
        assert result.data is not None
        assert len(result.errors) == 0
        assert result.row_count == 500

    def test_load_from_file_path(self, tmp_csv_file):
        """Loading from a file path should succeed."""
        result = load_csv(tmp_csv_file)
        assert result.success is True
        assert result.data is not None
        assert result.row_count == 500

    def test_load_from_string_path(self, tmp_csv_file):
        """Loading from a string path should succeed."""
        result = load_csv(str(tmp_csv_file))
        assert result.success is True

    def test_load_from_file_object(self, clean_csv_bytes):
        """Loading from a file-like object should succeed."""
        f = io.BytesIO(clean_csv_bytes)
        result = load_csv(f)
        assert result.success is True

    def test_canonical_columns_present(self, clean_csv_bytes):
        """Loaded data should have all canonical column names."""
        result = load_csv(clean_csv_bytes)
        assert "time_s" in result.data.columns
        assert "distance_m" in result.data.columns
        assert "speed_kmh" in result.data.columns
        assert "throttle_pct" in result.data.columns
        assert "brake_pct" in result.data.columns

    def test_columns_found_list(self, clean_csv_bytes):
        """columns_found should list all mapped canonical columns."""
        result = load_csv(clean_csv_bytes)
        assert "time_s" in result.columns_found
        assert "distance_m" in result.columns_found
        assert "speed_kmh" in result.columns_found

    def test_no_missing_columns(self, clean_csv_bytes):
        """No columns should be reported as missing for a complete CSV."""
        result = load_csv(clean_csv_bytes)
        assert len(result.columns_missing) == 0

    def test_file_hash_computed(self, clean_csv_bytes):
        """File hash should be a 64-character hex string (SHA-256)."""
        result = load_csv(clean_csv_bytes)
        assert result.file_hash is not None
        assert len(result.file_hash) == 64

    def test_file_hash_deterministic(self, clean_csv_bytes):
        """Same input should always produce the same hash."""
        r1 = load_csv(clean_csv_bytes)
        r2 = load_csv(clean_csv_bytes)
        assert r1.file_hash == r2.file_hash

    def test_data_types_numeric(self, clean_csv_bytes):
        """All columns should be numeric types."""
        result = load_csv(clean_csv_bytes)
        for col in result.data.columns:
            assert pd.api.types.is_numeric_dtype(result.data[col]), (
                f"Column {col} is not numeric"
            )


class TestColumnMapping:
    """Tests for automatic and explicit column mapping."""

    def test_auto_map_aliases(self, renamed_columns_csv_bytes):
        """Common column name aliases should be auto-mapped."""
        result = load_csv(renamed_columns_csv_bytes)
        assert result.success is True
        assert "time_s" in result.data.columns
        assert "distance_m" in result.data.columns
        assert "speed_kmh" in result.data.columns

    def test_explicit_mapping(self):
        """Explicit column mapping should override auto-mapping."""
        csv = b"a,b,c\n1.0,100.0,200.0\n2.0,200.0,250.0\n3.0,300.0,280.0\n"
        result = load_csv(csv, column_mapping={
            "a": "time_s",
            "b": "distance_m",
            "c": "speed_kmh",
        })
        assert result.success is True
        assert "time_s" in result.data.columns

    def test_mapping_records_original_columns(self, renamed_columns_csv_bytes):
        """original_columns should contain the CSV's actual column names."""
        result = load_csv(renamed_columns_csv_bytes)
        assert "elapsed" in result.original_columns
        assert "velocity" in result.original_columns

    def test_column_mapping_dict(self, renamed_columns_csv_bytes):
        """column_mapping should show original → canonical name mapping."""
        result = load_csv(renamed_columns_csv_bytes)
        assert result.column_mapping.get("elapsed") == "time_s"
        assert result.column_mapping.get("velocity") == "speed_kmh"


class TestUnitConversion:
    """Tests for unit conversion during loading."""

    def test_speed_ms_to_kmh(self, speed_in_ms_csv_bytes):
        """Speed in m/s should be converted to km/h."""
        result = load_csv(
            speed_in_ms_csv_bytes,
            unit_overrides={"speed": "m/s"},
        )
        assert result.success is True
        # The original clean data has speeds around 80-340 km/h
        # After converting back from m/s, we should get similar values
        max_speed = result.data["speed_kmh"].max()
        assert max_speed > 50, f"Max speed {max_speed} seems too low after conversion"

    def test_unknown_unit_warns(self, clean_csv_bytes):
        """Unknown unit should produce a warning, not crash."""
        result = load_csv(
            clean_csv_bytes,
            unit_overrides={"speed": "furlongs_per_fortnight"},
        )
        assert result.success is True
        assert any("Unknown unit" in w for w in result.warnings)


class TestErrorHandling:
    """Tests for various error conditions."""

    def test_empty_file(self, empty_csv_bytes):
        """Empty file should fail with a clear error."""
        result = load_csv(empty_csv_bytes)
        assert result.success is False
        assert len(result.errors) > 0
        assert any("empty" in e.lower() for e in result.errors)

    def test_header_only(self, header_only_csv_bytes):
        """Header-only CSV should fail with a clear error."""
        result = load_csv(header_only_csv_bytes)
        assert result.success is False
        assert len(result.errors) > 0

    def test_missing_required_columns(self, missing_columns_csv_bytes):
        """Missing required columns should produce specific errors."""
        result = load_csv(missing_columns_csv_bytes)
        assert result.success is False
        assert len(result.columns_missing) > 0
        assert "time_s" in result.columns_missing

    def test_nonexistent_file(self):
        """Non-existent file path should fail gracefully."""
        result = load_csv("/nonexistent/path/to/file.csv")
        assert result.success is False
        assert any("not found" in e.lower() or "could not read" in e.lower()
                    for e in result.errors)

    def test_whitespace_only_file(self):
        """File with only whitespace should fail."""
        result = load_csv(b"   \n  \n  ")
        assert result.success is False

    def test_malformed_csv(self, malformed_csv_bytes):
        """Malformed CSV should either fail or handle gracefully."""
        result = load_csv(malformed_csv_bytes)
        # It might parse with NaN fill or might fail — either is acceptable
        # as long as it doesn't crash
        if result.success:
            assert result.data is not None
        else:
            assert len(result.errors) > 0

    def test_non_numeric_values(self):
        """Non-numeric values should be coerced to NaN, not crash."""
        csv = b"time_s,distance_m,speed_kmh\n1.0,100,abc\n2.0,200,def\n3.0,300,ghi\n"
        result = load_csv(csv)
        assert result.success is True
        # Non-numeric should become NaN
        assert result.data["speed_kmh"].isna().all()


class TestOptionalColumns:
    """Tests for handling optional columns."""

    def test_missing_optional_warns(self):
        """Missing optional columns should produce warnings, not errors."""
        csv = b"time_s,distance_m,speed_kmh\n1.0,100,200\n2.0,200,250\n"
        result = load_csv(csv)
        assert result.success is True
        assert any("throttle_pct" in w for w in result.warnings)
        assert any("brake_pct" in w for w in result.warnings)


class TestFileHash:
    """Tests for SHA-256 hash computation."""

    def test_hash_is_sha256(self):
        """Hash should be a valid SHA-256 hex digest."""
        h = compute_file_hash(b"hello world")
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_different_content_different_hash(self):
        """Different content should produce different hashes."""
        h1 = compute_file_hash(b"data1")
        h2 = compute_file_hash(b"data2")
        assert h1 != h2
