"""
quality.py — Data-quality rule engine
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This module inspects a loaded DataFrame and produces a list of Issue
objects describing every data-quality problem or heuristic suspicion.

Design principles:
  - READ ONLY: this module never modifies the DataFrame.
  - Each check is a separate function returning a list of Issues.
  - Issues have a severity: ERROR (definite data fault), WARNING
    (heuristic suspicion — might be legitimate), or INFO (informational).
  - Every Issue includes a plain-language explanation.
  - All thresholds come from QualityThresholds so they are visible and tunable.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

import numpy as np
import pandas as pd

from apexmotion.config import QualityThresholds


# ---------------------------------------------------------------------------
# Issue data model
# ---------------------------------------------------------------------------

class Severity(Enum):
    """Issue severity levels."""
    ERROR = "error"       # Definite data fault (schema violation, NaN, etc.)
    WARNING = "warning"   # Heuristic suspicion (might be legitimate)
    INFO = "info"         # Informational finding


@dataclass
class Issue:
    """
    A single data-quality finding.

    Attributes:
        severity: ERROR, WARNING, or INFO.
        rule_id: Short identifier for the check that produced this issue
                 (e.g., "MISSING_VALUE", "NON_MONOTONIC_TIME").
        channel: Which column is affected (e.g., "speed_kmh").
        row: Row index or indices where the issue occurs.
        distance_interval: (start_m, end_m) distance range, if applicable.
        observed_value: The problematic value(s).
        explanation: Human-readable explanation.
    """
    severity: Severity
    rule_id: str
    channel: str
    row: Optional[int | list[int]] = None
    distance_interval: Optional[tuple[float, float]] = None
    observed_value: Optional[str] = None
    explanation: str = ""


# ---------------------------------------------------------------------------
# Individual quality checks
# ---------------------------------------------------------------------------

def check_missing_values(df: pd.DataFrame, thresholds: QualityThresholds) -> list[Issue]:
    """
    Detect missing (NaN) values in each column.

    This is an ERROR because NaN means the measurement is absent.
    """
    issues = []
    for col in df.columns:
        nan_mask = df[col].isna()
        nan_count = nan_mask.sum()
        if nan_count > 0:
            nan_rows = df.index[nan_mask].tolist()
            # Report first 10 rows to keep the message readable
            shown = nan_rows[:10]
            suffix = f" (and {nan_count - 10} more)" if nan_count > 10 else ""
            issues.append(Issue(
                severity=Severity.ERROR,
                rule_id="MISSING_VALUE",
                channel=col,
                row=nan_rows,
                observed_value=f"{nan_count} NaN values",
                explanation=(
                    f"Column '{col}' has {nan_count} missing (NaN) value(s) "
                    f"at rows {shown}{suffix}. These samples have no "
                    f"recorded measurement."
                ),
            ))
    return issues


def check_non_finite_values(df: pd.DataFrame, thresholds: QualityThresholds) -> list[Issue]:
    """
    Detect infinity values in numeric columns.

    This is an ERROR because ±inf is not a valid measurement.
    """
    issues = []
    for col in df.columns:
        series = df[col].dropna()
        if len(series) == 0:
            continue
        try:
            inf_mask = np.isinf(series.to_numpy(dtype=float, na_value=np.nan))
        except (TypeError, ValueError):
            continue
        inf_count = inf_mask.sum()
        if inf_count > 0:
            inf_rows = series.index[inf_mask].tolist()
            shown = inf_rows[:10]
            suffix = f" (and {inf_count - 10} more)" if inf_count > 10 else ""
            issues.append(Issue(
                severity=Severity.ERROR,
                rule_id="NON_FINITE_VALUE",
                channel=col,
                row=inf_rows,
                observed_value=f"{inf_count} infinite values",
                explanation=(
                    f"Column '{col}' has {inf_count} infinite value(s) "
                    f"at rows {shown}{suffix}. Infinity is not a valid "
                    f"telemetry measurement."
                ),
            ))
    return issues


def check_duplicate_timestamps(df: pd.DataFrame, thresholds: QualityThresholds) -> list[Issue]:
    """
    Detect duplicate values in the time column.

    This is an ERROR because two samples at the same time instant
    means one of them is incorrect or redundant.
    """
    issues = []
    if "time_s" not in df.columns:
        return issues

    time = df["time_s"].dropna()
    dup_mask = time.duplicated(keep=False)
    dup_count = dup_mask.sum()
    if dup_count > 0:
        dup_rows = time.index[dup_mask].tolist()
        shown = dup_rows[:10]
        suffix = f" (and {dup_count - 10} more)" if dup_count > 10 else ""
        issues.append(Issue(
            severity=Severity.ERROR,
            rule_id="DUPLICATE_TIMESTAMP",
            channel="time_s",
            row=dup_rows,
            observed_value=f"{dup_count} duplicated rows",
            explanation=(
                f"The time column has {dup_count} rows with duplicate "
                f"timestamps at rows {shown}{suffix}. Each sample should "
                f"have a unique time value."
            ),
        ))
    return issues


def check_non_monotonic_time(df: pd.DataFrame, thresholds: QualityThresholds) -> list[Issue]:
    """
    Detect non-monotonically increasing time values.

    If time goes backwards, that's an ERROR — the recording is
    out of order or corrupted.
    """
    issues = []
    if "time_s" not in df.columns:
        return issues

    time = df["time_s"].dropna()
    if len(time) < 2:
        return issues

    diffs = time.diff().iloc[1:]
    backwards = diffs[diffs < 0]
    if len(backwards) > 0:
        bad_rows = backwards.index.tolist()
        shown = bad_rows[:10]
        suffix = f" (and {len(backwards) - 10} more)" if len(backwards) > 10 else ""
        issues.append(Issue(
            severity=Severity.ERROR,
            rule_id="NON_MONOTONIC_TIME",
            channel="time_s",
            row=bad_rows,
            observed_value=f"{len(backwards)} reversals",
            explanation=(
                f"Time decreases at {len(backwards)} location(s): rows "
                f"{shown}{suffix}. Time should always increase — this "
                f"suggests recording errors or data corruption."
            ),
        ))
    return issues


def check_distance_reversals(df: pd.DataFrame, thresholds: QualityThresholds) -> list[Issue]:
    """
    Detect non-monotonically increasing distance values.

    If distance goes backwards during a single lap, that's an ERROR.
    """
    issues = []
    if "distance_m" not in df.columns:
        return issues

    dist = df["distance_m"].dropna()
    if len(dist) < 2:
        return issues

    diffs = dist.diff().iloc[1:]
    backwards = diffs[diffs < 0]
    if len(backwards) > 0:
        bad_rows = backwards.index.tolist()
        shown = bad_rows[:10]
        suffix = f" (and {len(backwards) - 10} more)" if len(backwards) > 10 else ""
        issues.append(Issue(
            severity=Severity.ERROR,
            rule_id="DISTANCE_REVERSAL",
            channel="distance_m",
            row=bad_rows,
            observed_value=f"{len(backwards)} reversals",
            explanation=(
                f"Distance decreases at {len(backwards)} location(s): rows "
                f"{shown}{suffix}. Within a single lap, distance should "
                f"always increase."
            ),
        ))
    return issues


def check_large_time_gaps(df: pd.DataFrame, thresholds: QualityThresholds) -> list[Issue]:
    """
    Detect gaps in time larger than the configured threshold.

    This is a WARNING because gaps might represent legitimate pauses
    (e.g., red flag, pit lane) or might indicate dropped data.
    """
    issues = []
    if "time_s" not in df.columns:
        return issues

    time = df["time_s"].dropna()
    if len(time) < 2:
        return issues

    diffs = time.diff().iloc[1:]
    large = diffs[diffs > thresholds.max_time_gap_s]
    for idx, gap in large.items():
        issues.append(Issue(
            severity=Severity.WARNING,
            rule_id="LARGE_TIME_GAP",
            channel="time_s",
            row=int(idx),
            observed_value=f"{gap:.4f} s gap",
            explanation=(
                f"A {gap:.4f} s gap between rows {idx-1} and {idx} "
                f"exceeds the threshold of {thresholds.max_time_gap_s} s. "
                f"This could indicate dropped samples or a legitimate "
                f"pause in recording."
            ),
        ))
    return issues


def check_irregular_sampling(df: pd.DataFrame, thresholds: QualityThresholds) -> list[Issue]:
    """
    Detect irregular sampling intervals in the time column.

    Compares each interval to the median. If an interval is much larger
    or smaller than the median, it's flagged as INFO because irregular
    sampling is common and might be intentional.
    """
    issues = []
    if "time_s" not in df.columns:
        return issues

    time = df["time_s"].dropna()
    if len(time) < 3:
        return issues

    diffs = time.diff().iloc[1:]
    positive_diffs = diffs[diffs > 0]
    if len(positive_diffs) == 0:
        return issues

    median_dt = positive_diffs.median()
    if median_dt <= 0:
        return issues

    factor = thresholds.irregular_sampling_factor
    irregular = diffs[
        (diffs > median_dt * factor) | (diffs < median_dt / factor)
    ]
    # Exclude entries already caught by other rules (large gaps, etc.)
    irregular = irregular[irregular > 0]  # exclude non-monotonic (negative)

    if len(irregular) > 0:
        shown_rows = irregular.index.tolist()[:10]
        suffix = f" (and {len(irregular) - 10} more)" if len(irregular) > 10 else ""
        issues.append(Issue(
            severity=Severity.INFO,
            rule_id="IRREGULAR_SAMPLING",
            channel="time_s",
            row=irregular.index.tolist(),
            observed_value=(
                f"{len(irregular)} irregular intervals "
                f"(median dt={median_dt:.4f} s)"
            ),
            explanation=(
                f"Found {len(irregular)} sampling interval(s) that differ "
                f"from the median ({median_dt:.4f} s) by more than "
                f"{factor}×: rows {shown_rows}{suffix}. This may indicate "
                f"variable-rate logging, which is normal for some systems."
            ),
        ))
    return issues


def check_out_of_range(df: pd.DataFrame, thresholds: QualityThresholds) -> list[Issue]:
    """
    Detect values outside the configured plausible range.

    This is a WARNING (heuristic) because unusual values might be
    legitimate. We don't want to label every high speed as "wrong".
    """
    issues = []
    for col in df.columns:
        ch_range = thresholds.get_range(col)
        if ch_range is None:
            continue

        series = df[col].dropna()
        below = series[series < ch_range.min_val]
        above = series[series > ch_range.max_val]

        if len(below) > 0:
            shown = below.index.tolist()[:10]
            suffix = f" (and {len(below) - 10} more)" if len(below) > 10 else ""
            issues.append(Issue(
                severity=Severity.WARNING,
                rule_id="OUT_OF_RANGE_LOW",
                channel=col,
                row=below.index.tolist(),
                observed_value=f"min={below.min():.2f} {ch_range.unit}",
                explanation=(
                    f"Column '{col}' has {len(below)} value(s) below the "
                    f"minimum plausible value of {ch_range.min_val} "
                    f"{ch_range.unit} at rows {shown}{suffix}. "
                    f"Lowest observed: {below.min():.2f} {ch_range.unit}."
                ),
            ))

        if len(above) > 0:
            shown = above.index.tolist()[:10]
            suffix = f" (and {len(above) - 10} more)" if len(above) > 10 else ""
            issues.append(Issue(
                severity=Severity.WARNING,
                rule_id="OUT_OF_RANGE_HIGH",
                channel=col,
                row=above.index.tolist(),
                observed_value=f"max={above.max():.2f} {ch_range.unit}",
                explanation=(
                    f"Column '{col}' has {len(above)} value(s) above the "
                    f"maximum plausible value of {ch_range.max_val} "
                    f"{ch_range.unit} at rows {shown}{suffix}. "
                    f"Highest observed: {above.max():.2f} {ch_range.unit}."
                ),
            ))

    return issues


def check_suspicious_jumps(df: pd.DataFrame, thresholds: QualityThresholds) -> list[Issue]:
    """
    Detect sudden large changes in signal values between consecutive samples.

    This is a WARNING because sudden changes CAN be legitimate
    (e.g., hard braking, throttle lift). We flag them for human review.
    """
    issues = []

    jump_thresholds = {
        "speed_kmh": thresholds.max_speed_jump_kmh,
        "throttle_pct": thresholds.max_throttle_jump_pct,
        "brake_pct": thresholds.max_brake_jump_pct,
    }

    for col, max_jump in jump_thresholds.items():
        if col not in df.columns:
            continue

        series = df[col].dropna()
        if len(series) < 2:
            continue

        diffs = series.diff().iloc[1:].abs()
        jumps = diffs[diffs > max_jump]

        if len(jumps) > 0:
            shown = jumps.index.tolist()[:10]
            suffix = f" (and {len(jumps) - 10} more)" if len(jumps) > 10 else ""
            issues.append(Issue(
                severity=Severity.WARNING,
                rule_id="SUSPICIOUS_JUMP",
                channel=col,
                row=jumps.index.tolist(),
                observed_value=f"max Δ={jumps.max():.2f}",
                explanation=(
                    f"Column '{col}' has {len(jumps)} sudden change(s) "
                    f"exceeding {max_jump} per sample at rows "
                    f"{shown}{suffix}. Largest jump: {jumps.max():.2f}. "
                    f"These could be real (hard braking, throttle cut) "
                    f"or sensor glitches — review manually."
                ),
            ))

    return issues


def check_insufficient_samples(df: pd.DataFrame, thresholds: QualityThresholds) -> list[Issue]:
    """
    Check if the dataset has enough samples for meaningful analysis.

    This is an INFO finding because small datasets can still be valid,
    but results may be unreliable.
    """
    issues = []
    if len(df) < thresholds.min_sample_count:
        issues.append(Issue(
            severity=Severity.INFO,
            rule_id="INSUFFICIENT_SAMPLES",
            channel="all",
            observed_value=f"{len(df)} rows",
            explanation=(
                f"The dataset has only {len(df)} sample(s), which is below "
                f"the recommended minimum of {thresholds.min_sample_count}. "
                f"Analysis results may be unreliable with very small datasets."
            ),
        ))
    return issues


# ---------------------------------------------------------------------------
# Main quality-check runner
# ---------------------------------------------------------------------------

# All checks in execution order
ALL_CHECKS = [
    check_missing_values,
    check_non_finite_values,
    check_duplicate_timestamps,
    check_non_monotonic_time,
    check_distance_reversals,
    check_large_time_gaps,
    check_irregular_sampling,
    check_out_of_range,
    check_suspicious_jumps,
    check_insufficient_samples,
]


@dataclass
class QualityReport:
    """
    Complete quality assessment of a telemetry dataset.

    Attributes:
        issues: All detected issues.
        error_count: Number of ERROR-severity issues.
        warning_count: Number of WARNING-severity issues.
        info_count: Number of INFO-severity issues.
        sample_count: Number of rows inspected.
        channels_inspected: List of columns that were checked.
    """
    issues: list[Issue]
    error_count: int
    warning_count: int
    info_count: int
    sample_count: int
    channels_inspected: list[str]

    @property
    def has_errors(self) -> bool:
        """True if there are any ERROR-severity issues."""
        return self.error_count > 0

    @property
    def total_issues(self) -> int:
        """Total number of issues across all severities."""
        return len(self.issues)

    def filter_by_severity(self, severity: Severity) -> list[Issue]:
        """Return only issues with the given severity."""
        return [i for i in self.issues if i.severity == severity]

    def filter_by_channel(self, channel: str) -> list[Issue]:
        """Return only issues affecting the given channel."""
        return [i for i in self.issues if i.channel == channel]

    def filter_by_rule(self, rule_id: str) -> list[Issue]:
        """Return only issues from the given rule."""
        return [i for i in self.issues if i.rule_id == rule_id]


def run_quality_checks(
    df: pd.DataFrame,
    thresholds: Optional[QualityThresholds] = None,
) -> QualityReport:
    """
    Run all data-quality checks on a DataFrame.

    Args:
        df: DataFrame with canonical column names (time_s, distance_m, etc.).
        thresholds: Optional custom thresholds. Uses defaults if not provided.

    Returns:
        QualityReport with all detected issues and summary counts.

    Example:
        >>> report = run_quality_checks(df)
        >>> print(f"Found {report.error_count} errors, {report.warning_count} warnings")
        >>> for issue in report.issues:
        ...     print(f"[{issue.severity.value}] {issue.rule_id}: {issue.explanation}")
    """
    if thresholds is None:
        thresholds = QualityThresholds()

    all_issues: list[Issue] = []
    for check_fn in ALL_CHECKS:
        all_issues.extend(check_fn(df, thresholds))

    error_count = sum(1 for i in all_issues if i.severity == Severity.ERROR)
    warning_count = sum(1 for i in all_issues if i.severity == Severity.WARNING)
    info_count = sum(1 for i in all_issues if i.severity == Severity.INFO)

    return QualityReport(
        issues=all_issues,
        error_count=error_count,
        warning_count=warning_count,
        info_count=info_count,
        sample_count=len(df),
        channels_inspected=list(df.columns),
    )
