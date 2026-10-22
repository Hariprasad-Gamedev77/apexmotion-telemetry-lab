"""
Trust Passport page — Generate transparent, downloadable analysis reports
"""
import streamlit as st
import pandas as pd
import json
import hashlib
from datetime import datetime, timezone

from apexmotion.config import APP_VERSION, DISCLAIMER, DEFAULT_RANGES
from apexmotion.quality import Severity


def _determine_metric_status(report, channel: str) -> tuple[str, str]:
    """
    Determine the status of a metric based on quality findings.

    Returns (status, reason) where status is one of:
    "Usable", "Caution", "Insufficient data"
    """
    ch_issues = report.filter_by_channel(channel)
    errors = [i for i in ch_issues if i.severity == Severity.ERROR]
    warnings = [i for i in ch_issues if i.severity == Severity.WARNING]

    if len(errors) > 0:
        rules = ", ".join(set(i.rule_id for i in errors))
        return "Insufficient data", f"Channel has {len(errors)} error(s): {rules}"
    elif len(warnings) > 0:
        rules = ", ".join(set(i.rule_id for i in warnings))
        return "Caution", f"Channel has {len(warnings)} warning(s): {rules}"
    else:
        return "Usable", "No errors or warnings detected for this channel"


def render_trust_passport():
    """Render the Trust Passport page."""

    st.markdown("""
        <h1 style="font-size: 1.6rem; font-weight: 700; margin-bottom: 0.2rem;">
            Telemetry Trust Passport
        </h1>
        <p style="font-size: 0.92rem; color: var(--text-secondary); margin-bottom: 1.5rem;">
            A transparent, downloadable report documenting every aspect of the analysis —
            input hashes, validation rules, detected issues, and per-metric status verdicts.
        </p>
    """, unsafe_allow_html=True)

    # Check for loaded data
    has_data = "loaded_data" in st.session_state or "quality_data" in st.session_state
    if not has_data:
        st.markdown("""
        <div class="panel" style="text-align: center; padding: 2.5rem;">
            <div style="font-size: 2rem; margin-bottom: 0.8rem; opacity: 0.3;">📋</div>
            <div style="color: var(--text-secondary);">
                Load data from the <strong>Overview</strong> or <strong>Data Quality</strong> page first
                to generate a Trust Passport.
            </div>
        </div>
        """, unsafe_allow_html=True)
        return

    # Gather data
    data_result = st.session_state.get("quality_data", st.session_state.get("loaded_data"))
    data_name = st.session_state.get("quality_name", st.session_state.get("loaded_name", "unknown"))

    from apexmotion.quality import run_quality_checks
    from apexmotion.config import QualityThresholds

    thresholds = QualityThresholds()
    report = run_quality_checks(data_result.data, thresholds)

    now = datetime.now(timezone.utc)

    # Build passport document
    passport = {
        "passport_version": "1.0",
        "generated_at": now.isoformat(),
        "application": {
            "name": "ApexMotion Telemetry Lab",
            "version": APP_VERSION,
        },
        "input_file": {
            "name": data_name,
            "sha256": data_result.file_hash,
            "rows": data_result.row_count,
            "original_columns": data_result.original_columns,
            "column_mapping": data_result.column_mapping,
        },
        "validation": {
            "thresholds": {
                "max_time_gap_s": thresholds.max_time_gap_s,
                "max_speed_jump_kmh": thresholds.max_speed_jump_kmh,
                "max_throttle_jump_pct": thresholds.max_throttle_jump_pct,
                "max_brake_jump_pct": thresholds.max_brake_jump_pct,
                "irregular_sampling_factor": thresholds.irregular_sampling_factor,
                "min_sample_count": thresholds.min_sample_count,
            },
            "channel_ranges": {
                ch: {"min": r.min_val, "max": r.max_val, "unit": r.unit}
                for ch, r in DEFAULT_RANGES.items()
            },
            "total_issues": report.total_issues,
            "error_count": report.error_count,
            "warning_count": report.warning_count,
            "info_count": report.info_count,
        },
        "issues": [
            {
                "severity": i.severity.value,
                "rule_id": i.rule_id,
                "channel": i.channel,
                "row_count": len(i.row) if isinstance(i.row, list) else (1 if i.row is not None else 0),
                "observed": i.observed_value,
                "explanation": i.explanation,
            }
            for i in report.issues
        ],
        "sample_counts": {
            "original": data_result.row_count,
            "retained": data_result.row_count,  # No cleaning performed
            "cleaning_operations": [],
        },
        "channel_status": {},
        "disclaimer": DISCLAIMER,
    }

    # Per-channel status
    channels = data_result.columns_found
    for ch in channels:
        status, reason = _determine_metric_status(report, ch)
        passport["channel_status"][ch] = {
            "status": status,
            "reason": reason,
        }

    # Display
    st.markdown("---")

    # Status overview cards
    st.markdown('<div class="panel-header">Per-Channel Status</div>', unsafe_allow_html=True)

    cols = st.columns(min(len(channels), 5))
    status_styles = {
        "Usable": ("badge-success", "✓"),
        "Caution": ("badge-warning", "⚠"),
        "Insufficient data": ("badge-error", "✗"),
    }

    for i, ch in enumerate(channels):
        status, reason = passport["channel_status"][ch]["status"], passport["channel_status"][ch]["reason"]
        badge_cls, icon = status_styles.get(status, ("badge-info", "?"))
        with cols[i % len(cols)]:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">{ch}</div>
                <div style="margin: 0.5rem 0;">
                    <span class="badge {badge_cls}" style="font-size: 0.82rem;">{icon} {status}</span>
                </div>
                <div class="metric-subtitle">{reason}</div>
            </div>
            """, unsafe_allow_html=True)

    # Passport details
    st.markdown('<div class="panel-header" style="margin-top:1.5rem;">Passport Contents</div>', unsafe_allow_html=True)

    tab1, tab2, tab3 = st.tabs(["📋 Summary", "🔍 Issues", "📄 Raw JSON"])

    with tab1:
        st.markdown(f"""
        | Field | Value |
        |---|---|
        | **File** | `{data_name}` |
        | **SHA-256** | `{data_result.file_hash}` |
        | **Rows** | {data_result.row_count:,} |
        | **Columns mapped** | {', '.join(f'`{c}`' for c in channels)} |
        | **Generated** | {now.strftime('%Y-%m-%d %H:%M:%S UTC')} |
        | **App version** | {APP_VERSION} |
        | **Errors / Warnings / Info** | {report.error_count} / {report.warning_count} / {report.info_count} |
        | **Cleaning operations** | None (original data preserved) |
        """)

    with tab2:
        if report.total_issues == 0:
            st.success("✓ No issues found.")
        else:
            for issue in report.issues:
                sev_map = {
                    Severity.ERROR: "🔴",
                    Severity.WARNING: "🟡",
                    Severity.INFO: "🔵",
                }
                st.markdown(f"""
                {sev_map.get(issue.severity, '⚪')} **{issue.rule_id}** `{issue.channel}` — {issue.explanation[:150]}
                """)

    with tab3:
        st.code(json.dumps(passport, indent=2, default=str), language="json")

    # Download buttons
    st.markdown("---")
    dc1, dc2 = st.columns(2)
    with dc1:
        st.download_button(
            "⬇ Download Trust Passport (JSON)",
            json.dumps(passport, indent=2, default=str),
            file_name=f"trust_passport_{now.strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json",
            use_container_width=True,
        )
    with dc2:
        # CSV version
        flat = []
        for ch in channels:
            cs = passport["channel_status"][ch]
            flat.append({
                "channel": ch,
                "status": cs["status"],
                "reason": cs["reason"],
                "errors": len([i for i in report.issues if i.channel == ch and i.severity == Severity.ERROR]),
                "warnings": len([i for i in report.issues if i.channel == ch and i.severity == Severity.WARNING]),
            })
        st.download_button(
            "⬇ Download Channel Status (CSV)",
            pd.DataFrame(flat).to_csv(index=False),
            file_name=f"channel_status_{now.strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            use_container_width=True,
        )
