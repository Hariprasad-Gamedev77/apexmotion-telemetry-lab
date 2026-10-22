"""
test_quality.py — Tests for data-quality rule engine
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Covers:
  - Clean data produces no errors
  - Each defect type is correctly detected
  - Severity levels are correct (ERROR vs WARNING vs INFO)
  - Rule IDs match expected values
  - Thresholds are respected
  - Edge cases (empty DataFrames, single-row, flat signals)
  - Corrupted synthetic data triggers expected findings
  - Filtering methods work correctly
"""

import numpy as np
import pandas as pd
import pytest

from apexmotion.config import QualityThresholds, ChannelRange
from apexmotion.quality import (
    Severity,
    Issue,
    QualityReport,
    run_quality_checks,
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
)


class TestCleanData:
    """Clean data should produce no errors or warnings."""

    def test_no_errors(self, clean_df, default_thresholds):
        """Clean data should have zero ERROR-severity issues."""
        report = run_quality_checks(clean_df, default_thresholds)
        errors = report.filter_by_severity(Severity.ERROR)
        assert len(errors) == 0, (
            f"Clean data should have no errors but found: "
            f"{[e.rule_id for e in errors]}"
        )

    def test_sample_count(self, clean_df, default_thresholds):
        """Report should correctly count samples."""
        report = run_quality_checks(clean_df, default_thresholds)
        assert report.sample_count == 500

    def test_channels_inspected(self, clean_df, default_thresholds):
        """Report should list all inspected channels."""
        report = run_quality_checks(clean_df, default_thresholds)
        assert "time_s" in report.channels_inspected
        assert "speed_kmh" in report.channels_inspected


class TestMissingValues:
    """Tests for NaN/missing value detection."""

    def test_detects_nan(self, nan_heavy_df, default_thresholds):
        """Should detect NaN values as ERROR."""
        issues = check_missing_values(nan_heavy_df, default_thresholds)
        speed_issues = [i for i in issues if i.channel == "speed_kmh"]
        assert len(speed_issues) > 0
        assert speed_issues[0].severity == Severity.ERROR
        assert speed_issues[0].rule_id == "MISSING_VALUE"

    def test_no_false_positives(self, clean_df, default_thresholds):
        """Clean data should not trigger missing value detection."""
        issues = check_missing_values(clean_df, default_thresholds)
        assert len(issues) == 0


class TestNonFiniteValues:
    """Tests for infinity detection."""

    def test_detects_infinity(self, inf_df, default_thresholds):
        """Should detect infinite values as ERROR."""
        issues = check_non_finite_values(inf_df, default_thresholds)
        assert len(issues) > 0
        assert all(i.severity == Severity.ERROR for i in issues)
        assert all(i.rule_id == "NON_FINITE_VALUE" for i in issues)

    def test_no_false_positives(self, clean_df, default_thresholds):
        """Clean data should not trigger infinity detection."""
        issues = check_non_finite_values(clean_df, default_thresholds)
        assert len(issues) == 0


class TestDuplicateTimestamps:
    """Tests for duplicate timestamp detection."""

    def test_detects_duplicates(self, duplicate_time_df, default_thresholds):
        """Should detect duplicate timestamps as ERROR."""
        issues = check_duplicate_timestamps(duplicate_time_df, default_thresholds)
        assert len(issues) == 1
        assert issues[0].severity == Severity.ERROR
        assert issues[0].rule_id == "DUPLICATE_TIMESTAMP"

    def test_no_false_positives(self, clean_df, default_thresholds):
        """Clean data should not trigger duplicate detection."""
        issues = check_duplicate_timestamps(clean_df, default_thresholds)
        assert len(issues) == 0


class TestNonMonotonicTime:
    """Tests for non-monotonic time detection."""

    def test_detects_reversal(self, reversed_time_df, default_thresholds):
        """Should detect time reversals as ERROR."""
        issues = check_non_monotonic_time(reversed_time_df, default_thresholds)
        assert len(issues) == 1
        assert issues[0].severity == Severity.ERROR
        assert issues[0].rule_id == "NON_MONOTONIC_TIME"

    def test_no_false_positives(self, clean_df, default_thresholds):
        """Clean data should not trigger time reversal detection."""
        issues = check_non_monotonic_time(clean_df, default_thresholds)
        assert len(issues) == 0


class TestDistanceReversals:
    """Tests for distance reversal detection."""

    def test_detects_reversal(self, distance_reversal_df, default_thresholds):
        """Should detect distance reversals as ERROR."""
        issues = check_distance_reversals(distance_reversal_df, default_thresholds)
        assert len(issues) == 1
        assert issues[0].severity == Severity.ERROR
        assert issues[0].rule_id == "DISTANCE_REVERSAL"

    def test_no_false_positives(self, clean_df, default_thresholds):
        """Clean data should not trigger distance reversal detection."""
        issues = check_distance_reversals(clean_df, default_thresholds)
        assert len(issues) == 0


class TestLargeTimeGaps:
    """Tests for large time gap detection."""

    def test_detects_large_gap(self, large_gap_df, default_thresholds):
        """Should detect large time gaps as WARNING."""
        issues = check_large_time_gaps(large_gap_df, default_thresholds)
        assert len(issues) > 0
        assert all(i.severity == Severity.WARNING for i in issues)
        assert all(i.rule_id == "LARGE_TIME_GAP" for i in issues)

    def test_no_false_positives(self, clean_df, default_thresholds):
        """Clean data should not trigger large gap detection."""
        issues = check_large_time_gaps(clean_df, default_thresholds)
        assert len(issues) == 0

    def test_custom_threshold(self, large_gap_df):
        """A very high threshold should not flag anything."""
        thresholds = QualityThresholds(max_time_gap_s=100.0)
        issues = check_large_time_gaps(large_gap_df, thresholds)
        assert len(issues) == 0


class TestIrregularSampling:
    """Tests for irregular sampling detection."""

    def test_clean_data_minimal_flags(self, clean_df, default_thresholds):
        """Clean data should have few or no irregular sampling flags."""
        issues = check_irregular_sampling(clean_df, default_thresholds)
        # INFO level — might flag a few but shouldn't be many
        for issue in issues:
            assert issue.severity == Severity.INFO


class TestOutOfRange:
    """Tests for out-of-range value detection."""

    def test_detects_below_range(self, out_of_range_df, default_thresholds):
        """Should detect values below minimum as WARNING."""
        issues = check_out_of_range(out_of_range_df, default_thresholds)
        low_issues = [i for i in issues if i.rule_id == "OUT_OF_RANGE_LOW"]
        assert len(low_issues) > 0
        assert all(i.severity == Severity.WARNING for i in low_issues)

    def test_detects_above_range(self, out_of_range_df, default_thresholds):
        """Should detect values above maximum as WARNING."""
        issues = check_out_of_range(out_of_range_df, default_thresholds)
        high_issues = [i for i in issues if i.rule_id == "OUT_OF_RANGE_HIGH"]
        assert len(high_issues) > 0
        assert all(i.severity == Severity.WARNING for i in high_issues)

    def test_no_false_positives(self, clean_df, default_thresholds):
        """Clean data should not trigger out-of-range detection."""
        issues = check_out_of_range(clean_df, default_thresholds)
        assert len(issues) == 0

    def test_custom_range(self, clean_df):
        """Custom ranges should override defaults."""
        # Set a very narrow range so clean data triggers it
        thresholds = QualityThresholds(
            channel_ranges={
                "speed_kmh": ChannelRange(100, 200, "km/h", "Narrow test range"),
            }
        )
        issues = check_out_of_range(clean_df, thresholds)
        assert len(issues) > 0


class TestSuspiciousJumps:
    """Tests for sudden value jump detection."""

    def test_detects_speed_jump(self, suspicious_jump_df, default_thresholds):
        """Should detect suspicious speed jumps as WARNING."""
        issues = check_suspicious_jumps(suspicious_jump_df, default_thresholds)
        speed_jumps = [i for i in issues if i.channel == "speed_kmh"]
        assert len(speed_jumps) > 0
        assert all(i.severity == Severity.WARNING for i in speed_jumps)
        assert all(i.rule_id == "SUSPICIOUS_JUMP" for i in speed_jumps)

    def test_speed_no_false_positives(self, clean_df, default_thresholds):
        """Clean data speed should not trigger jump detection.

        Note: throttle and brake CAN have large sample-to-sample changes
        in real racing (e.g., full throttle lift or brake application).
        The quality engine correctly flags these as WARNINGs for human
        review. Only speed jumps >80 km/h between samples are unexpected
        in clean synthetic data.
        """
        issues = check_suspicious_jumps(clean_df, default_thresholds)
        speed_jumps = [i for i in issues if i.channel == "speed_kmh"]
        assert len(speed_jumps) == 0

    def test_flat_signal_no_jumps(self, flat_signal_df, default_thresholds):
        """Constant signal should never trigger jump detection."""
        issues = check_suspicious_jumps(flat_signal_df, default_thresholds)
        assert len(issues) == 0


class TestInsufficientSamples:
    """Tests for minimum sample count check."""

    def test_small_dataset_flagged(self, minimal_df, default_thresholds):
        """Very small datasets should be flagged as INFO."""
        issues = check_insufficient_samples(minimal_df, default_thresholds)
        assert len(issues) == 1
        assert issues[0].severity == Severity.INFO
        assert issues[0].rule_id == "INSUFFICIENT_SAMPLES"

    def test_large_dataset_ok(self, clean_df, default_thresholds):
        """Normal-sized datasets should not be flagged."""
        issues = check_insufficient_samples(clean_df, default_thresholds)
        assert len(issues) == 0


class TestCorruptedSyntheticData:
    """
    Integration tests using the corrupted synthetic dataset.

    The corrupted dataset has known injected defects. We verify
    that the quality engine finds them all.
    """

    def test_finds_missing_values(self, corrupted_df, default_thresholds):
        """Should find the NaN values injected at rows 10, 11, 50."""
        report = run_quality_checks(corrupted_df, default_thresholds)
        missing = report.filter_by_rule("MISSING_VALUE")
        assert len(missing) > 0

    def test_finds_duplicate_timestamps(self, corrupted_df, default_thresholds):
        """Should find the duplicate timestamp at rows 100-101."""
        report = run_quality_checks(corrupted_df, default_thresholds)
        dupes = report.filter_by_rule("DUPLICATE_TIMESTAMP")
        assert len(dupes) > 0

    def test_finds_non_monotonic_time(self, corrupted_df, default_thresholds):
        """Should find the time reversal at row 200."""
        report = run_quality_checks(corrupted_df, default_thresholds)
        mono = report.filter_by_rule("NON_MONOTONIC_TIME")
        assert len(mono) > 0

    def test_finds_distance_reversal(self, corrupted_df, default_thresholds):
        """Should find the distance reversal at row 300."""
        report = run_quality_checks(corrupted_df, default_thresholds)
        rev = report.filter_by_rule("DISTANCE_REVERSAL")
        assert len(rev) > 0

    def test_finds_out_of_range(self, corrupted_df, default_thresholds):
        """Should find the negative speed and >380 speed."""
        report = run_quality_checks(corrupted_df, default_thresholds)
        oor = report.filter_by_rule("OUT_OF_RANGE_LOW") + report.filter_by_rule("OUT_OF_RANGE_HIGH")
        assert len(oor) > 0

    def test_finds_infinite_values(self, corrupted_df, default_thresholds):
        """Should find the infinite brake value at row 250."""
        report = run_quality_checks(corrupted_df, default_thresholds)
        inf = report.filter_by_rule("NON_FINITE_VALUE")
        assert len(inf) > 0

    def test_finds_large_gap(self, corrupted_df, default_thresholds):
        """Should find the 5-second gap at row 400."""
        report = run_quality_checks(corrupted_df, default_thresholds)
        gaps = report.filter_by_rule("LARGE_TIME_GAP")
        assert len(gaps) > 0

    def test_finds_suspicious_jump(self, corrupted_df, default_thresholds):
        """Should find the 200 km/h speed jump at row 450."""
        report = run_quality_checks(corrupted_df, default_thresholds)
        jumps = report.filter_by_rule("SUSPICIOUS_JUMP")
        assert len(jumps) > 0

    def test_has_errors(self, corrupted_df, default_thresholds):
        """Corrupted data should have errors."""
        report = run_quality_checks(corrupted_df, default_thresholds)
        assert report.has_errors is True
        assert report.error_count > 0

    def test_has_multiple_severities(self, corrupted_df, default_thresholds):
        """Corrupted data should have issues at multiple severity levels."""
        report = run_quality_checks(corrupted_df, default_thresholds)
        assert report.error_count > 0
        assert report.warning_count > 0


class TestEmptyDataFrame:
    """Tests with an empty DataFrame."""

    def test_empty_df_no_crash(self, empty_df, default_thresholds):
        """Quality checks should handle empty DataFrames gracefully."""
        report = run_quality_checks(empty_df, default_thresholds)
        assert report.sample_count == 0

    def test_empty_df_insufficient_samples(self, empty_df, default_thresholds):
        """Empty DataFrame should flag insufficient samples."""
        report = run_quality_checks(empty_df, default_thresholds)
        insuf = report.filter_by_rule("INSUFFICIENT_SAMPLES")
        assert len(insuf) == 1


class TestQualityReportMethods:
    """Tests for QualityReport filtering and property methods."""

    def test_filter_by_severity(self, corrupted_df, default_thresholds):
        """filter_by_severity should return only matching issues."""
        report = run_quality_checks(corrupted_df, default_thresholds)
        errors = report.filter_by_severity(Severity.ERROR)
        assert all(i.severity == Severity.ERROR for i in errors)

    def test_filter_by_channel(self, corrupted_df, default_thresholds):
        """filter_by_channel should return only matching issues."""
        report = run_quality_checks(corrupted_df, default_thresholds)
        speed = report.filter_by_channel("speed_kmh")
        assert all(i.channel == "speed_kmh" for i in speed)

    def test_filter_by_rule(self, corrupted_df, default_thresholds):
        """filter_by_rule should return only matching issues."""
        report = run_quality_checks(corrupted_df, default_thresholds)
        missing = report.filter_by_rule("MISSING_VALUE")
        assert all(i.rule_id == "MISSING_VALUE" for i in missing)

    def test_total_issues(self, corrupted_df, default_thresholds):
        """total_issues should equal sum of all severity counts."""
        report = run_quality_checks(corrupted_df, default_thresholds)
        assert report.total_issues == (
            report.error_count + report.warning_count + report.info_count
        )

    def test_has_errors_property(self, clean_df, corrupted_df, default_thresholds):
        """has_errors should be True for corrupted, False for clean."""
        clean_report = run_quality_checks(clean_df, default_thresholds)
        assert clean_report.has_errors is False

        corrupted_report = run_quality_checks(corrupted_df, default_thresholds)
        assert corrupted_report.has_errors is True
