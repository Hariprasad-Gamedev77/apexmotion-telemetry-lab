"""
Documentation page — Workflow, schema, rules, and methodology
"""
import streamlit as st
from pathlib import Path

from apexmotion.config import (
    APP_VERSION, DISCLAIMER, CANONICAL_COLUMNS, REQUIRED_COLUMNS,
    OPTIONAL_COLUMNS, DEFAULT_RANGES, COMMON_COLUMN_ALIASES,
)


def render_documentation():
    """Render the Documentation page."""

    st.markdown("""
        <h1 style="font-size: 1.6rem; font-weight: 700; margin-bottom: 0.2rem;">
            Documentation
        </h1>
        <p style="font-size: 0.92rem; color: var(--text-secondary); margin-bottom: 1.5rem;">
            Everything you need to understand the workflow, accepted data formats, validation rules,
            comparison methodology, and how to reproduce a report.
        </p>
    """, unsafe_allow_html=True)

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📋 Workflow",
        "📄 CSV Schema",
        "🔍 Validation Rules",
        "⇄ Alignment",
        "📐 Metrics & Limitations",
    ])

    with tab1:
        st.markdown("""
        ## How ApexMotion Works

        ApexMotion processes telemetry data through a **5-step pipeline**:

        ### 1. Import
        Upload a CSV file containing telemetry data from a single lap.
        The loader automatically recognizes common column names and maps them
        to the canonical format. You can also provide explicit column mappings.

        ### 2. Validate
        The quality engine inspects every row and column for data defects:
        - **Errors** (definite faults): missing values, infinities, duplicate timestamps,
          time reversals, distance reversals
        - **Warnings** (heuristic suspicions): out-of-range values, large gaps,
          suspicious jumps — these might be legitimate
        - **Info** (informational): irregular sampling, small sample counts

        The engine **never modifies your data**. It only reports findings.

        ### 3. Align
        To compare two laps, both are interpolated onto a common distance grid.
        This ensures the comparison is by **physical track position**, not by
        row index or timestamp.

        ### 4. Compare
        Side-by-side overlay plots show speed, throttle, and brake traces for both
        laps. A difference plot highlights where one lap gains or loses speed.

        ### 5. Report
        The Trust Passport captures everything about the analysis:
        input file hash, column mappings, validation thresholds, detected issues,
        per-channel status, and a complete methodology record.

        ---

        > **Reproducibility:** Anyone with the same CSV file, the same application
        > version, and the same threshold settings will get identical results.
        > The Trust Passport documents all of these so the analysis can be verified.
        """)

    with tab2:
        st.markdown("## Accepted CSV Schema")
        st.markdown("### Required Columns")

        req_data = []
        for col in REQUIRED_COLUMNS:
            desc = CANONICAL_COLUMNS.get(col, col)
            r = DEFAULT_RANGES.get(col)
            unit = r.unit if r else "—"
            range_str = f"{r.min_val} – {r.max_val}" if r else "—"
            req_data.append({"Column": f"`{col}`", "Description": desc, "Unit": unit, "Plausible Range": range_str})
        st.table(pd.DataFrame(req_data) if req_data else "No required columns defined")

        st.markdown("### Optional Columns")
        opt_data = []
        for col in OPTIONAL_COLUMNS:
            desc = CANONICAL_COLUMNS.get(col, col)
            r = DEFAULT_RANGES.get(col)
            unit = r.unit if r else "—"
            range_str = f"{r.min_val} – {r.max_val}" if r else "—"
            opt_data.append({"Column": f"`{col}`", "Description": desc, "Unit": unit, "Plausible Range": range_str})

        import pandas as pd
        st.table(pd.DataFrame(opt_data))

        st.markdown("### Auto-Recognized Column Names")
        st.markdown(
            "The loader recognizes these common names (case-insensitive) "
            "and maps them automatically:"
        )

        # Group aliases by canonical name
        alias_groups: dict[str, list[str]] = {}
        for alias, canonical in COMMON_COLUMN_ALIASES.items():
            alias_groups.setdefault(canonical, []).append(f"`{alias}`")

        for canonical, aliases in alias_groups.items():
            st.markdown(f"- **{canonical}**: {', '.join(aliases)}")

        st.markdown("""
        ### Unit Conversions

        | Channel | Supported Source Units | Canonical Unit |
        |---|---|---|
        | Speed | `m/s`, `mph`, `km/h` | km/h |
        | Distance | `km`, `ft`, `m` | metres |

        Specify source units via `unit_overrides` when loading programmatically,
        or use the column mapping UI.
        """)

    with tab3:
        st.markdown("## Validation Rules")
        st.markdown("""
        Each rule has an ID, a severity level, and a clear explanation.
        Thresholds are configurable on the Data Quality page.
        """)

        rules = [
            ("MISSING_VALUE", "ERROR", "Detects NaN / missing values in any channel. Each sample should have a recorded measurement."),
            ("NON_FINITE_VALUE", "ERROR", "Detects ±infinity in any channel. Infinity is not a valid telemetry measurement."),
            ("DUPLICATE_TIMESTAMP", "ERROR", "Detects rows with identical time values. Each sample should have a unique time."),
            ("NON_MONOTONIC_TIME", "ERROR", "Detects time values that decrease. Time should always increase within a lap."),
            ("DISTANCE_REVERSAL", "ERROR", "Detects distance values that decrease. Distance should always increase within a lap."),
            ("LARGE_TIME_GAP", "WARNING", "Detects time intervals exceeding the max gap threshold. Could indicate dropped samples or a legitimate pause. **Default threshold: 2.0 s.**"),
            ("IRREGULAR_SAMPLING", "INFO", "Detects sampling intervals that differ significantly from the median. Variable-rate logging is common in some systems. **Default factor: 3×.**"),
            ("OUT_OF_RANGE_LOW", "WARNING", "Detects values below the configured minimum. Unusual but might be legitimate (e.g., sensor calibration offset)."),
            ("OUT_OF_RANGE_HIGH", "WARNING", "Detects values above the configured maximum. Unusual but might be legitimate (e.g., very fast straight)."),
            ("SUSPICIOUS_JUMP", "WARNING", "Detects sudden large changes between consecutive samples. Could be real (hard braking, throttle cut) or a sensor glitch. **Default speed threshold: 80 km/h.**"),
            ("INSUFFICIENT_SAMPLES", "INFO", "Flags datasets with fewer samples than the minimum count. Small datasets can be valid but results may be unreliable. **Default minimum: 10 samples.**"),
        ]

        for rule_id, severity, desc in rules:
            sev_color = {"ERROR": "#DC2626", "WARNING": "#D97706", "INFO": "#0891B2"}[severity]
            st.markdown(f"""
            **`{rule_id}`** <span style="color:{sev_color}; font-weight:600; font-size:0.8rem;">{severity}</span>

            {desc}

            ---
            """, unsafe_allow_html=True)

    with tab4:
        st.markdown("""
        ## Distance Alignment Algorithm

        ### Why align by distance?
        Two laps may have different sampling rates, different timestamps, or
        different numbers of data points. Comparing them by row index or by
        timestamp would align unrelated track positions. Instead, we align
        by **physical distance** so that sample N from both laps represents
        the same point on the circuit.

        ### How it works

        1. **Shared coverage**: Find the distance range where both laps have
           data. Only this overlapping region is compared.

        2. **Common grid**: Create a regular distance grid (default 10m spacing)
           across the shared coverage.

        3. **Interpolation**: For each grid point, linearly interpolate each
           channel from the original samples. Only values between valid
           bracketing samples are interpolated.

        4. **Gap rule**: If the distance between the two nearest original
           samples exceeds the maximum gap threshold (default 100m), the
           interpolated value is marked as `NaN` (unavailable). This prevents
           interpolation across large missing regions.

        5. **No extrapolation**: Values outside the original data range are
           never estimated. They are marked as unavailable.

        ### Limitations

        - **Linear interpolation** assumes the signal changes linearly between
          samples. This is a reasonable approximation for densely sampled data
          but may miss peaks between widely spaced samples.
        - **The gap rule** is a conservative safeguard. If both laps have dense
          data, it has no effect. If one lap has sparse regions, those intervals
          are excluded from comparison.
        - **Sector timing** is not provided because it requires explicit sector
          boundary definitions and validated time reconstruction.
        """)

    with tab5:
        st.markdown("""
        ## Metrics & Limitations

        ### Computed Metrics

        | Metric | Definition | Unit | Limitations |
        |---|---|---|---|
        | **Max speed** | Highest valid speed value over shared distance | km/h | Depends on sampling rate; true peak may fall between samples |
        | **Mean speed** | Arithmetic mean of valid (non-NaN) speed samples | km/h | Affected by sampling density; denser regions contribute more |
        | **Distance coverage** | Total distance range of valid data | m | Shared coverage only; excludes non-overlapping regions |
        | **Lap duration** | Time at last sample minus time at first sample | s | Only meaningful if time data is reliable and continuous |
        | **Channel coverage** | Percentage of grid points with valid data | % | Depends on interpolation gap rule |

        ### What we do NOT claim

        - **Exact sector times** without explicit sector boundaries
        - **Tire degradation** or **fuel load** effects
        - **Absolute accuracy** — results depend on input data quality
        - **Real-time telemetry** — this is a post-session analysis tool

        ### Interpreting per-channel status

        | Status | Meaning |
        |---|---|
        | **Usable** | No errors or warnings. Data can be used with normal confidence. |
        | **Caution** | Warnings detected (out-of-range, suspicious jumps, gaps). Data can be used but review the flagged areas. |
        | **Insufficient data** | Errors detected (missing values, infinities, reversals). Data should not be relied upon without addressing the errors. |

        Each status is determined by the validation rules — not an opaque
        "confidence score". You can always inspect exactly which rules
        contributed to the status.
        """)

    # Footer
    st.markdown("---")
    st.markdown(f"""
    <div class="disclaimer">
        <strong>ApexMotion Telemetry Lab v{APP_VERSION}</strong><br>
        {DISCLAIMER}
    </div>
    """, unsafe_allow_html=True)
