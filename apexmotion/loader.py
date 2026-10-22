"""
loader.py — CSV loading and schema validation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Responsibilities:
  1. Read a CSV file (path or file-like object) into a pandas DataFrame.
  2. Map user column names to canonical names (time_s, distance_m, etc.).
  3. Convert units if the user specifies non-canonical units.
  4. Validate that required columns are present.
  5. Return a clean DataFrame with canonical column names, or a list of
     human-readable error messages explaining what went wrong.

This module NEVER modifies the source file. It NEVER silently drops
columns or rows. If something is wrong, it tells you.
"""

from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Union

import pandas as pd

from apexmotion.config import (
    CANONICAL_COLUMNS,
    COMMON_COLUMN_ALIASES,
    REQUIRED_COLUMNS,
    OPTIONAL_COLUMNS,
    UNIT_CONVERSIONS,
)


@dataclass
class LoadResult:
    """
    The result of loading and validating a CSV file.

    Attributes:
        success: True if loading produced a usable DataFrame.
        data: The loaded DataFrame with canonical column names, or None.
        errors: List of human-readable error messages.
        warnings: List of non-fatal warnings (e.g., missing optional columns).
        file_hash: SHA-256 hex digest of the raw file bytes.
        row_count: Number of rows in the loaded data.
        columns_found: List of canonical columns that were successfully mapped.
        columns_missing: List of canonical columns that could not be mapped.
        original_columns: List of column names as they appeared in the CSV.
        column_mapping: Dict mapping original → canonical column names.
    """
    success: bool = False
    data: Optional[pd.DataFrame] = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    file_hash: Optional[str] = None
    row_count: int = 0
    columns_found: list[str] = field(default_factory=list)
    columns_missing: list[str] = field(default_factory=list)
    original_columns: list[str] = field(default_factory=list)
    column_mapping: dict[str, str] = field(default_factory=dict)


def compute_file_hash(raw_bytes: bytes) -> str:
    """Compute SHA-256 hex digest of raw file bytes."""
    return hashlib.sha256(raw_bytes).hexdigest()


def _read_raw_bytes(source: Union[str, Path, io.IOBase, bytes]) -> bytes:
    """Read raw bytes from a file path, file-like object, or bytes."""
    if isinstance(source, bytes):
        return source
    if isinstance(source, (str, Path)):
        return Path(source).read_bytes()
    # File-like object
    pos = source.tell() if hasattr(source, "tell") else 0
    data = source.read()
    if hasattr(source, "seek"):
        source.seek(pos)
    if isinstance(data, str):
        return data.encode("utf-8")
    return data


def _parse_csv(raw_bytes: bytes) -> tuple[Optional[pd.DataFrame], list[str]]:
    """
    Parse CSV bytes into a DataFrame.

    Returns (DataFrame, errors). If errors is non-empty, DataFrame may be None.
    """
    errors = []
    if len(raw_bytes) == 0:
        errors.append("The file is empty (0 bytes).")
        return None, errors

    text = raw_bytes.decode("utf-8", errors="replace")
    # Check if there's any actual content
    stripped = text.strip()
    if not stripped:
        errors.append("The file contains only whitespace.")
        return None, errors

    try:
        df = pd.read_csv(io.StringIO(text))
    except pd.errors.EmptyDataError:
        errors.append("The CSV file has no parseable data rows.")
        return None, errors
    except pd.errors.ParserError as e:
        errors.append(f"CSV parsing failed: {e}")
        return None, errors
    except Exception as e:
        errors.append(f"Unexpected error reading CSV: {e}")
        return None, errors

    if df.empty or len(df) == 0:
        errors.append("The CSV file has headers but no data rows.")
        return None, errors

    return df, errors


def _build_column_mapping(
    csv_columns: list[str],
    user_mapping: Optional[dict[str, str]] = None,
) -> dict[str, str]:
    """
    Build a mapping from CSV column names → canonical names.

    Priority:
      1. Explicit user_mapping (user said "my_speed" → "speed_kmh")
      2. Automatic alias matching (case-insensitive)

    Returns dict where keys are original CSV column names and values
    are canonical column names.
    """
    mapping: dict[str, str] = {}

    # First, apply explicit user mapping
    if user_mapping:
        for csv_col, canonical_col in user_mapping.items():
            if csv_col in csv_columns:
                mapping[csv_col] = canonical_col

    # Then, try automatic alias matching for unmapped columns
    already_mapped_canonical = set(mapping.values())
    for csv_col in csv_columns:
        if csv_col in mapping:
            continue
        lower = csv_col.strip().lower()
        if lower in COMMON_COLUMN_ALIASES:
            canonical = COMMON_COLUMN_ALIASES[lower]
            if canonical not in already_mapped_canonical:
                mapping[csv_col] = canonical
                already_mapped_canonical.add(canonical)

    return mapping


def load_csv(
    source: Union[str, Path, io.IOBase, bytes],
    column_mapping: Optional[dict[str, str]] = None,
    unit_overrides: Optional[dict[str, str]] = None,
) -> LoadResult:
    """
    Load a CSV file and validate its schema.

    Args:
        source: File path, file-like object, or raw bytes.
        column_mapping: Optional explicit mapping of CSV column names
                        to canonical names (e.g., {"my_speed": "speed_kmh"}).
        unit_overrides: Optional dict specifying source units for conversion.
                        Keys are channel categories ("speed", "distance"),
                        values are unit labels ("m/s", "km").

    Returns:
        LoadResult with success status, data, errors, warnings, and metadata.

    Example:
        >>> result = load_csv("lap_data.csv", unit_overrides={"speed": "m/s"})
        >>> if result.success:
        ...     print(result.data.head())
    """
    result = LoadResult()

    # Step 1: Read raw bytes and compute hash
    try:
        raw_bytes = _read_raw_bytes(source)
    except FileNotFoundError:
        result.errors.append(f"File not found: {source}")
        return result
    except PermissionError:
        result.errors.append(f"Permission denied reading: {source}")
        return result
    except Exception as e:
        result.errors.append(f"Could not read file: {e}")
        return result

    result.file_hash = compute_file_hash(raw_bytes)

    # Step 2: Parse CSV
    df, parse_errors = _parse_csv(raw_bytes)
    if parse_errors:
        result.errors.extend(parse_errors)
        return result

    assert df is not None  # guaranteed by no errors
    result.original_columns = list(df.columns)

    # Step 3: Map columns
    col_map = _build_column_mapping(list(df.columns), column_mapping)
    result.column_mapping = col_map

    # Rename columns
    df = df.rename(columns=col_map)
    mapped_canonical = set(col_map.values())

    # Step 4: Check required columns
    for req in REQUIRED_COLUMNS:
        if req in mapped_canonical:
            result.columns_found.append(req)
        else:
            result.columns_missing.append(req)
            result.errors.append(
                f"Required column '{req}' ({CANONICAL_COLUMNS[req]}) "
                f"is missing. Available columns: {result.original_columns}"
            )

    # Check optional columns
    for opt in OPTIONAL_COLUMNS:
        if opt in mapped_canonical:
            result.columns_found.append(opt)
        else:
            result.warnings.append(
                f"Optional column '{opt}' ({CANONICAL_COLUMNS[opt]}) "
                f"not found. Some analyses will be limited."
            )

    if result.errors:
        return result

    # Step 5: Convert units if needed
    if unit_overrides:
        for channel_category, source_unit in unit_overrides.items():
            if channel_category in UNIT_CONVERSIONS:
                converters = UNIT_CONVERSIONS[channel_category]
                if source_unit in converters:
                    convert_fn = converters[source_unit]
                    # Find the canonical column for this category
                    cat_to_col = {"speed": "speed_kmh", "distance": "distance_m"}
                    col = cat_to_col.get(channel_category)
                    if col and col in df.columns:
                        df[col] = df[col].apply(convert_fn)
                        result.warnings.append(
                            f"Converted {channel_category} from {source_unit} "
                            f"to canonical units."
                        )
                else:
                    result.warnings.append(
                        f"Unknown unit '{source_unit}' for {channel_category}. "
                        f"Supported: {list(converters.keys())}"
                    )

    # Step 6: Keep only canonical columns (plus any extras the user might want)
    canonical_cols = [c for c in REQUIRED_COLUMNS + OPTIONAL_COLUMNS if c in df.columns]
    df = df[canonical_cols]

    # Step 7: Convert to numeric (coerce non-numeric to NaN — will be caught by quality checks)
    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    result.data = df
    result.row_count = len(df)
    result.success = True

    return result
