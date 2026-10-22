"""
Validation Bench page — Test the engine against known synthetic examples
"""
import streamlit as st
import pandas as pd
import numpy as np

from apexmotion.synthetic import (
    generate_clean_lap,
    generate_corrupted_lap,
    generate_minimal_lap,
    generate_different_rate_lap,
    generate_different_coverage_lap,
)
from apexmotion.quality import run_quality_checks, Severity
from apexmotion.config import QualityThresholds


# Test scenario definitions
SCENARIOS = [
    {
        "name": "Clean dataset",
        "description": "A valid lap with no defects. Should produce zero errors.",
        "generator": lambda: generate_clean_lap(n_samples=100, seed=42),
        "expected": {"errors": 0, "key_rules_absent": ["MISSING_VALUE", "DUPLICATE_TIMESTAMP", "NON_MONOTONIC_TIME", "DISTANCE_REVERSAL"]},
    },
    {
        "name": "Missing samples (NaN)",
        "description": "Lap with NaN values injected into speed and throttle channels.",
        "generator": lambda: _inject_nan(),
        "expected": {"min_errors": 1, "key_rules_present": ["MISSING_VALUE"]},
    },
    {
        "name": "Duplicate timestamps",
        "description": "Lap where two consecutive rows share the same timestamp.",
        "generator": lambda: _inject_dup_time(),
        "expected": {"min_errors": 1, "key_rules_present": ["DUPLICATE_TIMESTAMP"]},
    },
    {
        "name": "Reversed timestamps",
        "description": "Lap where time decreases at one point (non-monotonic).",
        "generator": lambda: _inject_reversed_time(),
        "expected": {"min_errors": 1, "key_rules_present": ["NON_MONOTONIC_TIME"]},
    },
    {
        "name": "Distance reversals",
        "description": "Lap where distance goes backwards at one point.",
        "generator": lambda: _inject_dist_reversal(),
        "expected": {"min_errors": 1, "key_rules_present": ["DISTANCE_REVERSAL"]},
    },
    {
        "name": "Invalid / non-finite values",
        "description": "Lap with infinity injected into the brake channel.",
        "generator": lambda: _inject_inf(),
        "expected": {"min_errors": 1, "key_rules_present": ["NON_FINITE_VALUE"]},
    },
    {
        "name": "Large data gaps",
        "description": "Lap with a 10-second gap in the middle.",
        "generator": lambda: _inject_large_gap(),
        "expected": {"min_warnings": 1, "key_rules_present": ["LARGE_TIME_GAP"]},
    },
    {
        "name": "Sudden signal change",
        "description": "Lap with a sudden 200 km/h speed spike — potentially legitimate, flagged for review.",
        "generator": lambda: _inject_jump(),
        "expected": {"min_warnings": 1, "key_rules_present": ["SUSPICIOUS_JUMP"]},
    },
    {
        "name": "Different sampling rate",
        "description": "Lap with 250 samples instead of 500 over the same distance.",
        "generator": lambda: generate_different_rate_lap(),
        "expected": {"errors": 0},
    },
    {
        "name": "Unequal lap coverage",
        "description": "Lap covering 4800m instead of 5200m. Valid data, shorter circuit.",
        "generator": lambda: generate_different_coverage_lap(),
        "expected": {"errors": 0},
    },
]


def _inject_nan():
    df = generate_clean_lap(n_samples=100, seed=42)
    df.loc[10, "speed_kmh"] = np.nan
    df.loc[20, "throttle_pct"] = np.nan
    return df

def _inject_dup_time():
    df = generate_clean_lap(n_samples=100, seed=42)
    df.loc[50, "time_s"] = df.loc[49, "time_s"]
    return df

def _inject_reversed_time():
    df = generate_clean_lap(n_samples=100, seed=42)
    df.loc[60, "time_s"] = df.loc[55, "time_s"] - 1.0
    return df

def _inject_dist_reversal():
    df = generate_clean_lap(n_samples=100, seed=42)
    df.loc[70, "distance_m"] = df.loc[65, "distance_m"] - 20.0
    return df

def _inject_inf():
    df = generate_clean_lap(n_samples=100, seed=42)
    df.loc[30, "brake_pct"] = np.inf
    return df

def _inject_large_gap():
    df = generate_clean_lap(n_samples=100, seed=42)
    df.loc[50:, "time_s"] = df.loc[50:, "time_s"] + 10.0
    return df

def _inject_jump():
    df = generate_clean_lap(n_samples=100, seed=42)
    df.loc[45, "speed_kmh"] = df.loc[44, "speed_kmh"] + 200.0
    return df


def _run_scenario(scenario: dict) -> dict:
    """Run a single validation scenario and check expectations."""
    df = scenario["generator"]()
    report = run_quality_checks(df, QualityThresholds())
    expected = scenario["expected"]

    results = {
        "name": scenario["name"],
        "description": scenario["description"],
        "errors": report.error_count,
        "warnings": report.warning_count,
        "info": report.info_count,
        "total": report.total_issues,
        "checks": [],
        "all_pass": True,
        "rules_found": [i.rule_id for i in report.issues],
    }

    # Check expectations
    if "errors" in expected:
        passed = report.error_count == expected["errors"]
        results["checks"].append({
            "check": f"Error count = {expected['errors']}",
            "expected": expected["errors"],
            "actual": report.error_count,
            "passed": passed,
        })
        if not passed:
            results["all_pass"] = False

    if "min_errors" in expected:
        passed = report.error_count >= expected["min_errors"]
        results["checks"].append({
            "check": f"Error count ≥ {expected['min_errors']}",
            "expected": f"≥ {expected['min_errors']}",
            "actual": report.error_count,
            "passed": passed,
        })
        if not passed:
            results["all_pass"] = False

    if "min_warnings" in expected:
        passed = report.warning_count >= expected["min_warnings"]
        results["checks"].append({
            "check": f"Warning count ≥ {expected['min_warnings']}",
            "expected": f"≥ {expected['min_warnings']}",
            "actual": report.warning_count,
            "passed": passed,
        })
        if not passed:
            results["all_pass"] = False

    if "key_rules_present" in expected:
        for rule in expected["key_rules_present"]:
            found = rule in results["rules_found"]
            results["checks"].append({
                "check": f"Rule {rule} detected",
                "expected": "Present",
                "actual": "Found" if found else "Not found",
                "passed": found,
            })
            if not found:
                results["all_pass"] = False

    if "key_rules_absent" in expected:
        for rule in expected["key_rules_absent"]:
            absent = rule not in results["rules_found"]
            results["checks"].append({
                "check": f"Rule {rule} absent",
                "expected": "Absent",
                "actual": "Absent" if absent else "Found",
                "passed": absent,
            })
            if not absent:
                results["all_pass"] = False

    return results


def render_validation_bench():
    """Render the Validation Bench page."""

    st.markdown("""
        <h1 style="font-size: 1.6rem; font-weight: 700; margin-bottom: 0.2rem;">
            Validation Bench
        </h1>
        <p style="font-size: 0.92rem; color: var(--text-secondary); margin-bottom: 0.5rem;">
            Test the quality engine against known synthetic examples with expected outcomes.
        </p>
        <p style="font-size: 0.82rem; color: var(--text-tertiary); margin-bottom: 1.5rem;">
            This page is a <strong>demonstration</strong> — it runs the validation checks live and
            compares results against expected findings. It is not a substitute for the automated
            test suite (<code>pytest tests/</code>).
        </p>
    """, unsafe_allow_html=True)

    if st.button("▶ Run all validation scenarios", type="primary", use_container_width=False):
        results = []
        progress = st.progress(0)

        for i, scenario in enumerate(SCENARIOS):
            result = _run_scenario(scenario)
            results.append(result)
            progress.progress((i + 1) / len(SCENARIOS))

        st.session_state["bench_results"] = results
        progress.empty()

    if "bench_results" not in st.session_state:
        st.markdown("""
        <div class="panel" style="text-align: center; padding: 2.5rem;">
            <div style="font-size: 2rem; margin-bottom: 0.8rem; opacity: 0.3;">🧪</div>
            <div style="color: var(--text-secondary);">
                Click <strong>"Run all validation scenarios"</strong> to test the engine
                against {count} known synthetic test cases.
            </div>
        </div>
        """.format(count=len(SCENARIOS)), unsafe_allow_html=True)
        return

    results = st.session_state["bench_results"]
    total = len(results)
    passed = sum(1 for r in results if r["all_pass"])
    failed = total - passed

    # Summary
    st.markdown("---")
    sc1, sc2, sc3 = st.columns(3)
    with sc1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Scenarios Run</div>
            <div class="metric-value">{total}</div>
        </div>
        """, unsafe_allow_html=True)
    with sc2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Passed</div>
            <div class="metric-value" style="color: var(--positive);">{passed}</div>
        </div>
        """, unsafe_allow_html=True)
    with sc3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Failed</div>
            <div class="metric-value" style="color: {'var(--critical)' if failed > 0 else 'var(--positive)'};">{failed}</div>
        </div>
        """, unsafe_allow_html=True)

    # Per-scenario results
    st.markdown('<div class="panel-header" style="margin-top:1.5rem;">Scenario Results</div>', unsafe_allow_html=True)

    for result in results:
        icon = "✅" if result["all_pass"] else "❌"
        with st.expander(f"{icon} {result['name']}", expanded=not result["all_pass"]):
            st.markdown(f"*{result['description']}*")
            st.markdown(f"**Findings:** {result['errors']} errors, {result['warnings']} warnings, {result['info']} info")

            if result["checks"]:
                check_df = pd.DataFrame(result["checks"])
                check_df["Result"] = check_df["passed"].map({True: "✓ Pass", False: "✗ Fail"})

                def color_result(val):
                    if "Pass" in str(val):
                        return "color: #16A34A; font-weight: 600"
                    elif "Fail" in str(val):
                        return "color: #DC2626; font-weight: 600"
                    return ""

                styled = check_df[["check", "expected", "actual", "Result"]].style.map(
                    color_result, subset=["Result"]
                )
                st.dataframe(styled, use_container_width=True, hide_index=True)

            if result["rules_found"]:
                st.markdown(f"**Rules triggered:** `{'`, `'.join(set(result['rules_found']))}`")

    # Link to automated tests
    st.markdown("---")
    st.markdown("""
    <div class="panel" style="background: var(--bg-elevated);">
        <div class="panel-header">Automated Test Suite</div>
        <p style="font-size: 0.88rem; color: var(--text-secondary);">
            The validation bench above is a live demonstration. For rigorous, repeatable testing,
            run the automated pytest suite:
        </p>
        <code style="display:block; padding: 0.75rem; background: var(--bg-card); border-radius: 6px; border: 1px solid var(--border); font-family: 'JetBrains Mono', monospace; font-size: 0.82rem;">
            pytest tests/ -v --tb=short
        </code>
        <p style="font-size: 0.82rem; color: var(--text-tertiary); margin-top: 0.5rem;">
            The test suite includes 99 tests covering loader, quality engine, and synthetic data generation.
        </p>
    </div>
    """, unsafe_allow_html=True)
