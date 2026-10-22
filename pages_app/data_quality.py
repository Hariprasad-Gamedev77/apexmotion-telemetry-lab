"""
Data Quality page — Upload, validate, and inspect telemetry data
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from apexmotion.loader import load_csv
from apexmotion.quality import run_quality_checks, QualityReport, Severity
from apexmotion.config import QualityThresholds, CANONICAL_COLUMNS, DEFAULT_RANGES


def _severity_badge(severity: Severity) -> str:
    """Return an HTML badge for a severity level."""
    config = {
        Severity.ERROR: ("badge-error", "ERROR", "✗"),
        Severity.WARNING: ("badge-warning", "WARN", "⚠"),
        Severity.INFO: ("badge-info", "INFO", "ℹ"),
    }
    cls, label, icon = config[severity]
    return f'<span class="badge {cls}">{icon} {label}</span>'


def _plot_signal_with_issues(df: pd.DataFrame, report: QualityReport, channel: str, x_col: str = "distance_m"):
    """Create a Plotly chart for a signal channel with issue regions highlighted."""
    if channel not in df.columns or x_col not in df.columns:
        return None

    fig = go.Figure()

    # Main signal trace
    fig.add_trace(go.Scatter(
        x=df[x_col],
        y=df[channel],
        mode="lines",
        name=channel,
        line=dict(color="#2563EB", width=1.5),
        hovertemplate=f"{channel}: %{{y:.1f}}<br>{x_col}: %{{x:.1f}}<extra></extra>",
    ))

    # Highlight error rows
    channel_issues = report.filter_by_channel(channel)
    error_rows = set()
    warning_rows = set()
    for issue in channel_issues:
        if issue.row is not None:
            rows = issue.row if isinstance(issue.row, list) else [issue.row]
            if issue.severity == Severity.ERROR:
                error_rows.update(rows)
            elif issue.severity == Severity.WARNING:
                warning_rows.update(rows)

    # Plot error points
    valid_error_rows = [r for r in error_rows if r < len(df)]
    if valid_error_rows:
        err_df = df.iloc[valid_error_rows]
        fig.add_trace(go.Scatter(
            x=err_df[x_col],
            y=err_df[channel],
            mode="markers",
            name="Error",
            marker=dict(color="#DC2626", size=7, symbol="x"),
            hovertemplate="ERROR at row %{text}<extra></extra>",
            text=[str(r) for r in valid_error_rows],
        ))

    # Plot warning points
    valid_warn_rows = [r for r in warning_rows if r < len(df)]
    if valid_warn_rows:
        warn_df = df.iloc[valid_warn_rows]
        fig.add_trace(go.Scatter(
            x=warn_df[x_col],
            y=warn_df[channel],
            mode="markers",
            name="Warning",
            marker=dict(color="#D97706", size=6, symbol="diamond"),
            hovertemplate="WARNING at row %{text}<extra></extra>",
            text=[str(r) for r in valid_warn_rows],
        ))

    # Layout
    unit = ""
    ch_range = DEFAULT_RANGES.get(channel)
    if ch_range:
        unit = f" ({ch_range.unit})"

    fig.update_layout(
        title=dict(text=f"{CANONICAL_COLUMNS.get(channel, channel)}", font=dict(size=14)),
        xaxis_title="Distance (m)" if x_col == "distance_m" else "Time (s)",
        yaxis_title=f"{channel}{unit}",
        template="plotly_white",
        height=300,
        margin=dict(l=50, r=20, t=40, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        plot_bgcolor="#FFFFFF",
        paper_bgcolor="#FAFBFC",
        font=dict(family="Inter, sans-serif", size=12, color="#1A1D23"),
    )

    fig.update_xaxes(gridcolor="#F0F2F5", zeroline=False)
    fig.update_yaxes(gridcolor="#F0F2F5", zeroline=False)

    return fig


def render_data_quality():
    """Render the Data Quality page."""

    st.markdown("""
        <h1 style="font-size: 1.6rem; font-weight: 700; margin-bottom: 0.2rem;">
            Data Quality
        </h1>
        <p style="font-size: 0.92rem; color: var(--text-secondary); margin-bottom: 1.5rem;">
            Inspect telemetry data for missing values, timing errors, range violations, and suspicious patterns.
        </p>
    """, unsafe_allow_html=True)

    # Upload or use loaded data
    tab_upload, tab_settings = st.tabs(["📂 Load Data", "⚙ Thresholds"])

    with tab_upload:
        col_up1, col_up2 = st.columns([2, 1])
        with col_up1:
            uploaded = st.file_uploader(
                "Upload a CSV file for quality analysis",
                type=["csv"],
                key="quality_upload",
            )
        with col_up2:
            use_demo = st.button("Use demo corrupted data", use_container_width=True)

        if uploaded is not None:
            raw = uploaded.read()
            result = load_csv(raw)
            if result.success:
                st.session_state["quality_data"] = result
                st.session_state["quality_name"] = uploaded.name
            else:
                for err in result.errors:
                    st.error(err)
                return

        if use_demo:
            from pathlib import Path
            sample_dir = Path(__file__).parent.parent / "sample_data"
            corrupted_path = sample_dir / "corrupted_lap.csv"
            if corrupted_path.exists():
                result = load_csv(str(corrupted_path))
                if result.success:
                    st.session_state["quality_data"] = result
                    st.session_state["quality_name"] = "corrupted_lap.csv (demo)"

    with tab_settings:
        st.markdown("**Quality thresholds** — adjust these to control sensitivity.")
        tc1, tc2, tc3 = st.columns(3)
        with tc1:
            max_gap = st.number_input("Max time gap (s)", value=2.0, min_value=0.1, step=0.5, key="th_gap")
            max_speed_jump = st.number_input("Max speed jump (km/h)", value=80.0, min_value=10.0, step=10.0, key="th_speed")
        with tc2:
            max_throttle_jump = st.number_input("Max throttle jump (%)", value=60.0, min_value=10.0, step=10.0, key="th_throttle")
            max_brake_jump = st.number_input("Max brake jump (%)", value=60.0, min_value=10.0, step=10.0, key="th_brake")
        with tc3:
            irregular_factor = st.number_input("Irregular sampling factor", value=3.0, min_value=1.5, step=0.5, key="th_irreg")
            min_samples = st.number_input("Min sample count", value=10, min_value=1, step=5, key="th_min")

    # Construct thresholds from user settings
    thresholds = QualityThresholds(
        max_time_gap_s=st.session_state.get("th_gap", 2.0),
        max_speed_jump_kmh=st.session_state.get("th_speed", 80.0),
        max_throttle_jump_pct=st.session_state.get("th_throttle", 60.0),
        max_brake_jump_pct=st.session_state.get("th_brake", 60.0),
        irregular_sampling_factor=st.session_state.get("th_irreg", 3.0),
        min_sample_count=int(st.session_state.get("th_min", 10)),
    )

    # Check if we have data
    if "quality_data" not in st.session_state:
        # Maybe use the overview loaded data
        if "loaded_data" in st.session_state:
            st.session_state["quality_data"] = st.session_state["loaded_data"]
            st.session_state["quality_name"] = st.session_state.get("loaded_name", "loaded data")

    if "quality_data" not in st.session_state:
        st.markdown("""
        <div class="panel" style="text-align: center; padding: 2.5rem;">
            <div style="font-size: 2rem; margin-bottom: 0.8rem; opacity: 0.3;">🔍</div>
            <div style="color: var(--text-secondary);">
                Upload a CSV file or load the demo corrupted dataset to begin quality analysis.
            </div>
        </div>
        """, unsafe_allow_html=True)
        return

    data_result = st.session_state["quality_data"]
    data_name = st.session_state.get("quality_name", "")
    df = data_result.data

    # Run quality checks
    report = run_quality_checks(df, thresholds)

    st.markdown("---")

    # Summary counts
    st.markdown(f"""
        <div style="font-size: 0.82rem; color: var(--text-secondary); margin-bottom: 1rem;">
            Analyzing <span class="mono" style="font-weight:500;">{data_name}</span>
            · <span class="mono">{report.sample_count:,}</span> samples
            · <span class="mono">{len(report.channels_inspected)}</span> channels
        </div>
    """, unsafe_allow_html=True)

    mc1, mc2, mc3, mc4 = st.columns(4)
    with mc1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Errors</div>
            <div class="metric-value" style="color: {'var(--critical)' if report.error_count > 0 else 'var(--positive)'};">
                {report.error_count}
            </div>
            <div class="metric-subtitle">Definite data faults</div>
        </div>
        """, unsafe_allow_html=True)
    with mc2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Warnings</div>
            <div class="metric-value" style="color: {'var(--warning)' if report.warning_count > 0 else 'var(--positive)'};">
                {report.warning_count}
            </div>
            <div class="metric-subtitle">Heuristic suspicions</div>
        </div>
        """, unsafe_allow_html=True)
    with mc3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Info</div>
            <div class="metric-value" style="color: var(--info-accent);">
                {report.info_count}
            </div>
            <div class="metric-subtitle">Informational findings</div>
        </div>
        """, unsafe_allow_html=True)
    with mc4:
        verdict = "Pass" if report.error_count == 0 else "Fail"
        v_color = "var(--positive)" if report.error_count == 0 else "var(--critical)"
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Verdict</div>
            <div class="metric-value" style="color: {v_color};">
                {verdict}
            </div>
            <div class="metric-subtitle">{'No definite faults' if verdict == 'Pass' else 'Errors must be resolved'}</div>
        </div>
        """, unsafe_allow_html=True)

    # Issue table
    st.markdown("""
    <div class="panel-header" style="margin-top: 1.5rem;">Issue Details</div>
    """, unsafe_allow_html=True)

    if report.total_issues == 0:
        st.success("✓ No issues detected. The data looks clean.")
    else:
        # Severity filter
        filter_options = ["All"]
        if report.error_count > 0:
            filter_options.append("Errors only")
        if report.warning_count > 0:
            filter_options.append("Warnings only")
        if report.info_count > 0:
            filter_options.append("Info only")

        selected_filter = st.segmented_control("Filter", filter_options, default="All", key="issue_filter")

        filtered = report.issues
        if selected_filter == "Errors only":
            filtered = report.filter_by_severity(Severity.ERROR)
        elif selected_filter == "Warnings only":
            filtered = report.filter_by_severity(Severity.WARNING)
        elif selected_filter == "Info only":
            filtered = report.filter_by_severity(Severity.INFO)

        # Build table
        table_data = []
        for issue in filtered:
            row_str = ""
            if issue.row is not None:
                if isinstance(issue.row, list):
                    if len(issue.row) <= 3:
                        row_str = ", ".join(str(r) for r in issue.row)
                    else:
                        row_str = f"{issue.row[0]}, {issue.row[1]}… +{len(issue.row)-2}"
                else:
                    row_str = str(issue.row)

            table_data.append({
                "Severity": issue.severity.value.upper(),
                "Rule": issue.rule_id,
                "Channel": issue.channel,
                "Rows": row_str,
                "Observed": issue.observed_value or "—",
                "Explanation": issue.explanation[:120] + ("…" if len(issue.explanation) > 120 else ""),
            })

        issue_df = pd.DataFrame(table_data)

        def color_severity(val):
            colors = {"ERROR": "#DC2626", "WARNING": "#D97706", "INFO": "#0891B2"}
            return f"color: {colors.get(val, '#1A1D23')}; font-weight: 600"

        styled = issue_df.style.map(color_severity, subset=["Severity"])
        st.dataframe(styled, use_container_width=True, hide_index=True, height=min(400, 40 + len(table_data) * 35))

        # Expandable details
        with st.expander("📝 Full issue explanations"):
            for i, issue in enumerate(filtered):
                sev_badge = _severity_badge(issue.severity)
                st.markdown(f"""
                {sev_badge} **{issue.rule_id}** — `{issue.channel}`

                {issue.explanation}

                ---
                """, unsafe_allow_html=True)

    # Signal plots with issues highlighted
    st.markdown("""
    <div class="panel-header" style="margin-top: 1.5rem;">Signal Plots</div>
    """, unsafe_allow_html=True)

    plot_channels = [c for c in ["speed_kmh", "throttle_pct", "brake_pct"] if c in df.columns]

    for channel in plot_channels:
        fig = _plot_signal_with_issues(df, report, channel)
        if fig:
            st.plotly_chart(fig, use_container_width=True, key=f"plot_{channel}")

    # Download quality report
    st.markdown("---")
    if report.total_issues > 0:
        csv_data = pd.DataFrame([{
            "severity": i.severity.value,
            "rule_id": i.rule_id,
            "channel": i.channel,
            "rows": str(i.row),
            "observed": i.observed_value or "",
            "explanation": i.explanation,
        } for i in report.issues])

        st.download_button(
            "⬇ Download issue report (CSV)",
            csv_data.to_csv(index=False),
            file_name="quality_report.csv",
            mime="text/csv",
        )
