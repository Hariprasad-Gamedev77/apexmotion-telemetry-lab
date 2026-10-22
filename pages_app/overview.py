"""
Overview page — Dashboard landing page
"""
import streamlit as st
import pandas as pd
from pathlib import Path
from apexmotion.config import APP_NAME, DISCLAIMER
from apexmotion.loader import load_csv
from apexmotion.quality import run_quality_checks, Severity


def _load_demo_session():
    """Load demo data and store in session state."""
    sample_dir = Path(__file__).parent.parent / "sample_data"
    clean_path = sample_dir / "clean_lap.csv"
    corrupted_path = sample_dir / "corrupted_lap.csv"

    if clean_path.exists():
        result = load_csv(str(clean_path))
        if result.success:
            st.session_state["loaded_data"] = result
            st.session_state["loaded_name"] = "clean_lap.csv (demo)"
            report = run_quality_checks(result.data)
            st.session_state["quality_report"] = report
            st.session_state["demo_loaded"] = True

    if corrupted_path.exists():
        result2 = load_csv(str(corrupted_path))
        if result2.success:
            st.session_state["corrupted_data"] = result2
            report2 = run_quality_checks(result2.data)
            st.session_state["corrupted_report"] = report2


def render_overview():
    """Render the Overview dashboard page."""

    # Header
    st.markdown("""
        <h1 style="font-size: 2rem; font-weight: 700; margin-bottom: 0.2rem; color: var(--text-primary);">
            Telemetry, with evidence.
        </h1>
        <p style="font-size: 1.05rem; color: var(--text-secondary); margin-bottom: 2rem; max-width: 700px;">
            Quality assurance and distance-aligned comparison for motorsport telemetry data.
            Load your CSV data, inspect quality issues, compare laps, and generate transparent reports.
        </p>
    """, unsafe_allow_html=True)

    # Action row
    col_action1, col_action2, col_action3 = st.columns([1, 1, 2])
    with col_action1:
        if st.button("⬦ Load demo session", type="primary", use_container_width=True):
            _load_demo_session()
            st.rerun()
    with col_action2:
        uploaded = st.file_uploader("Upload CSV", type=["csv"], label_visibility="collapsed")
        if uploaded is not None:
            raw_bytes = uploaded.read()
            result = load_csv(raw_bytes)
            if result.success:
                st.session_state["loaded_data"] = result
                st.session_state["loaded_name"] = uploaded.name
                report = run_quality_checks(result.data)
                st.session_state["quality_report"] = report
                st.rerun()
            else:
                for err in result.errors:
                    st.error(err)

    # Show dashboard only if data is loaded
    has_data = "loaded_data" in st.session_state
    report = st.session_state.get("quality_report")

    if not has_data:
        # Empty state
        st.markdown("---")
        st.markdown("""
        <div class="panel" style="text-align: center; padding: 3rem;">
            <div style="font-size: 2.5rem; margin-bottom: 1rem; opacity: 0.3;">◈</div>
            <div style="font-size: 1.1rem; color: var(--text-secondary); margin-bottom: 0.5rem;">
                No data loaded yet
            </div>
            <div style="font-size: 0.85rem; color: var(--text-tertiary);">
                Click <strong>"Load demo session"</strong> to explore with synthetic data,
                or upload your own CSV file.
            </div>
        </div>
        """, unsafe_allow_html=True)
        return

    data_result = st.session_state["loaded_data"]
    data_name = st.session_state.get("loaded_name", "Unknown")

    # Summary metric cards
    st.markdown(f"""
        <div style="font-size: 0.82rem; color: var(--text-secondary); margin-bottom: 1rem;">
            📂 <span class="mono" style="font-weight:500;">{data_name}</span>
        </div>
    """, unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Samples Inspected</div>
            <div class="metric-value">{report.sample_count:,}<span class="metric-unit">rows</span></div>
            <div class="metric-subtitle">{len(data_result.columns_found)} channels mapped</div>
        </div>
        """, unsafe_allow_html=True)

    with c2:
        error_class = "badge-error" if report.error_count > 0 else "badge-success"
        error_icon = "✗" if report.error_count > 0 else "✓"
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Quality Issues</div>
            <div class="metric-value">{report.total_issues}</div>
            <div class="metric-subtitle">
                <span class="badge {error_class}">{error_icon} {report.error_count} errors</span>
                <span class="badge badge-warning">⚠ {report.warning_count}</span>
                <span class="badge badge-info">ℹ {report.info_count}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

    with c3:
        dist_data = data_result.data
        if "distance_m" in dist_data.columns:
            coverage = dist_data["distance_m"].max() - dist_data["distance_m"].min()
            coverage_str = f"{coverage:,.0f}"
        else:
            coverage_str = "—"
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Distance Coverage</div>
            <div class="metric-value">{coverage_str}<span class="metric-unit">m</span></div>
            <div class="metric-subtitle">Single lap loaded</div>
        </div>
        """, unsafe_allow_html=True)

    with c4:
        ready = report.error_count == 0
        ready_badge = "badge-success" if ready else "badge-error"
        ready_text = "Ready" if ready else "Issues found"
        ready_icon = "✓" if ready else "✗"
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Comparison Readiness</div>
            <div style="margin-top:0.5rem;">
                <span class="badge {ready_badge}" style="font-size:0.9rem; padding:0.35rem 1rem;">
                    {ready_icon} {ready_text}
                </span>
            </div>
            <div class="metric-subtitle">{'No errors — data can be used' if ready else 'Fix errors before comparing'}</div>
        </div>
        """, unsafe_allow_html=True)

    # Pipeline status
    st.markdown("<br>", unsafe_allow_html=True)

    import_done = has_data
    validate_done = report is not None
    align_step = "active" if validate_done and report.error_count == 0 else ""
    compare_step = ""
    report_step = ""

    st.markdown(f"""
    <div class="panel">
        <div class="panel-header">Analysis Pipeline</div>
        <div class="pipeline">
            <div class="pipeline-step done">✓ Import</div>
            <div class="pipeline-arrow">→</div>
            <div class="pipeline-step {'done' if validate_done else 'active'}">{'✓' if validate_done else '◉'} Validate</div>
            <div class="pipeline-arrow">→</div>
            <div class="pipeline-step {align_step}">{'◉' if align_step == 'active' else '○'} Align</div>
            <div class="pipeline-arrow">→</div>
            <div class="pipeline-step {compare_step}">○ Compare</div>
            <div class="pipeline-arrow">→</div>
            <div class="pipeline-step {report_step}">○ Report</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Quick data preview
    st.markdown("""
    <div class="panel-header" style="margin-top: 1.5rem;">Data Preview</div>
    """, unsafe_allow_html=True)
    st.dataframe(
        data_result.data.head(20),
        use_container_width=True,
        hide_index=False,
    )

    # File metadata
    with st.expander("📋 File metadata"):
        mc1, mc2 = st.columns(2)
        with mc1:
            st.markdown(f"**File:** `{data_name}`")
            st.markdown(f"**Rows:** `{data_result.row_count:,}`")
            st.markdown(f"**Columns mapped:** `{', '.join(data_result.columns_found)}`")
        with mc2:
            st.markdown(f"**SHA-256:** `{data_result.file_hash[:24]}…`")
            if data_result.columns_missing:
                st.markdown(f"**Missing columns:** `{', '.join(data_result.columns_missing)}`")
            if data_result.warnings:
                for w in data_result.warnings:
                    st.caption(f"⚠ {w}")

    # Disclaimer
    if st.session_state.get("demo_loaded"):
        st.markdown(f"""
        <div class="disclaimer" style="margin-top:1.5rem;">
            ℹ <strong>Demo mode:</strong> {DISCLAIMER}
        </div>
        """, unsafe_allow_html=True)
