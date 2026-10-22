"""
Lap Comparison page — Compare two laps by distance alignment
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from pathlib import Path

from apexmotion.loader import load_csv
from apexmotion.quality import run_quality_checks, Severity
from apexmotion.config import CANONICAL_COLUMNS


def _interpolate_to_grid(df: pd.DataFrame, distance_grid: np.ndarray, max_gap_m: float = 100.0) -> pd.DataFrame:
    """
    Interpolate a lap's channels onto a common distance grid.

    Only interpolates between valid bracketing samples.
    Marks intervals with gaps > max_gap_m as NaN.
    """
    result = pd.DataFrame({"distance_m": distance_grid})

    src_dist = df["distance_m"].values
    channels = [c for c in ["speed_kmh", "throttle_pct", "brake_pct"] if c in df.columns]

    for ch in channels:
        src_vals = df[ch].values
        # Remove NaN pairs
        valid = ~(np.isnan(src_dist) | np.isnan(src_vals))
        sd = src_dist[valid]
        sv = src_vals[valid]

        if len(sd) < 2:
            result[ch] = np.nan
            continue

        interp_vals = np.interp(distance_grid, sd, sv, left=np.nan, right=np.nan)

        # Mask out points where source data has large gaps
        for i, d in enumerate(distance_grid):
            idx = np.searchsorted(sd, d)
            if idx == 0 or idx >= len(sd):
                interp_vals[i] = np.nan
            else:
                gap = sd[idx] - sd[idx - 1]
                if gap > max_gap_m:
                    interp_vals[i] = np.nan

        result[ch] = interp_vals

    if "time_s" in df.columns:
        src_time = df["time_s"].values
        valid_t = ~(np.isnan(src_dist) | np.isnan(src_time))
        if valid_t.sum() >= 2:
            result["time_s"] = np.interp(distance_grid, src_dist[valid_t], src_time[valid_t], left=np.nan, right=np.nan)

    return result


def render_lap_comparison():
    """Render the Lap Comparison page."""

    st.markdown("""
        <h1 style="font-size: 1.6rem; font-weight: 700; margin-bottom: 0.2rem;">
            Lap Comparison
        </h1>
        <p style="font-size: 0.92rem; color: var(--text-secondary); margin-bottom: 1.5rem;">
            Compare two laps aligned by physical distance. Upload or load demo data for both laps.
        </p>
    """, unsafe_allow_html=True)

    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown("##### Lap A")
        uploaded_a = st.file_uploader("Upload Lap A CSV", type=["csv"], key="lap_a_upload")
        load_demo_a = st.button("Load demo clean lap", key="demo_a", use_container_width=True)

    with col_b:
        st.markdown("##### Lap B")
        uploaded_b = st.file_uploader("Upload Lap B CSV", type=["csv"], key="lap_b_upload")
        load_demo_b = st.button("Load demo second lap", key="demo_b", use_container_width=True)

    # Process uploads / demo loads
    if uploaded_a is not None:
        result = load_csv(uploaded_a.read())
        if result.success:
            st.session_state["lap_a"] = result
            st.session_state["lap_a_name"] = uploaded_a.name
        else:
            for e in result.errors:
                st.error(f"Lap A: {e}")

    if load_demo_a:
        sample_dir = Path(__file__).parent.parent / "sample_data"
        result = load_csv(str(sample_dir / "clean_lap.csv"))
        if result.success:
            st.session_state["lap_a"] = result
            st.session_state["lap_a_name"] = "clean_lap.csv (demo)"

    if uploaded_b is not None:
        result = load_csv(uploaded_b.read())
        if result.success:
            st.session_state["lap_b"] = result
            st.session_state["lap_b_name"] = uploaded_b.name
        else:
            for e in result.errors:
                st.error(f"Lap B: {e}")

    if load_demo_b:
        # Generate second lap on the fly
        from apexmotion.synthetic import generate_second_lap
        df_b = generate_second_lap()
        from apexmotion.loader import LoadResult, compute_file_hash
        csv_bytes = df_b.to_csv(index=False).encode("utf-8")
        st.session_state["lap_b"] = LoadResult(
            success=True, data=df_b, row_count=len(df_b),
            columns_found=list(df_b.columns),
            file_hash=compute_file_hash(csv_bytes),
        )
        st.session_state["lap_b_name"] = "second_lap.csv (demo)"

    # Check if both laps loaded
    has_a = "lap_a" in st.session_state and st.session_state["lap_a"].success
    has_b = "lap_b" in st.session_state and st.session_state["lap_b"].success

    if not has_a or not has_b:
        missing = []
        if not has_a:
            missing.append("Lap A")
        if not has_b:
            missing.append("Lap B")
        st.markdown(f"""
        <div class="panel" style="text-align: center; padding: 2.5rem;">
            <div style="font-size: 2rem; margin-bottom: 0.8rem; opacity: 0.3;">⇄</div>
            <div style="color: var(--text-secondary);">
                Load {" and ".join(missing)} to begin comparison.
                Use the demo buttons or upload your own CSV files.
            </div>
        </div>
        """, unsafe_allow_html=True)
        return

    df_a = st.session_state["lap_a"].data
    df_b = st.session_state["lap_b"].data
    name_a = st.session_state.get("lap_a_name", "Lap A")
    name_b = st.session_state.get("lap_b_name", "Lap B")

    # Alignment settings
    st.markdown("---")
    with st.expander("⚙ Alignment settings", expanded=False):
        ac1, ac2 = st.columns(2)
        with ac1:
            grid_step = st.number_input("Distance grid step (m)", value=10.0, min_value=1.0, max_value=100.0, step=5.0)
        with ac2:
            max_gap = st.number_input("Max interpolation gap (m)", value=100.0, min_value=10.0, max_value=500.0, step=25.0)

    # Compute shared coverage
    min_dist = max(df_a["distance_m"].min(), df_b["distance_m"].min())
    max_dist = min(df_a["distance_m"].max(), df_b["distance_m"].max())

    if max_dist <= min_dist:
        st.error("The two laps have no overlapping distance range. Cannot align.")
        return

    shared_coverage = max_dist - min_dist
    grid = np.arange(min_dist, max_dist, grid_step)

    # Interpolate both laps to common grid
    aligned_a = _interpolate_to_grid(df_a, grid, max_gap)
    aligned_b = _interpolate_to_grid(df_b, grid, max_gap)

    # Summary cards
    sc1, sc2, sc3, sc4 = st.columns(4)
    with sc1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Shared Coverage</div>
            <div class="metric-value">{shared_coverage:,.0f}<span class="metric-unit">m</span></div>
        </div>
        """, unsafe_allow_html=True)
    with sc2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Grid Points</div>
            <div class="metric-value">{len(grid):,}</div>
            <div class="metric-subtitle">{grid_step}m spacing</div>
        </div>
        """, unsafe_allow_html=True)
    with sc3:
        # Max speed comparison
        max_a = aligned_a["speed_kmh"].max() if "speed_kmh" in aligned_a else float("nan")
        max_b = aligned_b["speed_kmh"].max() if "speed_kmh" in aligned_b else float("nan")
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Max Speed</div>
            <div class="metric-value" style="font-size:1.2rem;">
                A: <span class="mono">{max_a:.1f}</span> · B: <span class="mono">{max_b:.1f}</span>
            </div>
            <div class="metric-subtitle">km/h over shared distance</div>
        </div>
        """, unsafe_allow_html=True)
    with sc4:
        mean_a = aligned_a["speed_kmh"].mean() if "speed_kmh" in aligned_a else float("nan")
        mean_b = aligned_b["speed_kmh"].mean() if "speed_kmh" in aligned_b else float("nan")
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Mean Speed</div>
            <div class="metric-value" style="font-size:1.2rem;">
                A: <span class="mono">{mean_a:.1f}</span> · B: <span class="mono">{mean_b:.1f}</span>
            </div>
            <div class="metric-subtitle">km/h valid samples only</div>
        </div>
        """, unsafe_allow_html=True)

    # Overlay plots
    channels_to_plot = [
        ("speed_kmh", "Speed (km/h)"),
        ("throttle_pct", "Throttle (%)"),
        ("brake_pct", "Brake (%)"),
    ]

    for ch, label in channels_to_plot:
        if ch not in aligned_a.columns and ch not in aligned_b.columns:
            continue

        fig = go.Figure()

        if ch in aligned_a.columns:
            fig.add_trace(go.Scatter(
                x=grid, y=aligned_a[ch], mode="lines",
                name=f"A: {name_a}", line=dict(color="#2563EB", width=1.8),
                hovertemplate=f"A {label}: %{{y:.1f}}<br>Dist: %{{x:.0f}}m<extra></extra>",
            ))

        if ch in aligned_b.columns:
            fig.add_trace(go.Scatter(
                x=grid, y=aligned_b[ch], mode="lines",
                name=f"B: {name_b}", line=dict(color="#DC2626", width=1.5, dash="dot"),
                hovertemplate=f"B {label}: %{{y:.1f}}<br>Dist: %{{x:.0f}}m<extra></extra>",
            ))

        fig.update_layout(
            title=dict(text=label, font=dict(size=14)),
            xaxis_title="Distance (m)",
            yaxis_title=label,
            template="plotly_white",
            height=320,
            margin=dict(l=50, r=20, t=40, b=40),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            plot_bgcolor="#FFFFFF",
            paper_bgcolor="#FAFBFC",
            font=dict(family="Inter, sans-serif", size=12, color="#1A1D23"),
            hovermode="x unified",
        )
        fig.update_xaxes(gridcolor="#F0F2F5", zeroline=False)
        fig.update_yaxes(gridcolor="#F0F2F5", zeroline=False)

        st.plotly_chart(fig, use_container_width=True, key=f"cmp_{ch}")

    # Difference plot for speed
    if "speed_kmh" in aligned_a.columns and "speed_kmh" in aligned_b.columns:
        diff = aligned_a["speed_kmh"] - aligned_b["speed_kmh"]
        fig_diff = go.Figure()
        fig_diff.add_trace(go.Scatter(
            x=grid, y=diff, mode="lines", name="Speed Δ (A − B)",
            line=dict(color="#7C3AED", width=1.5),
            fill="tozeroy", fillcolor="rgba(124,58,237,0.08)",
        ))
        fig_diff.add_hline(y=0, line=dict(color="#CBD1D9", width=1, dash="dash"))
        fig_diff.update_layout(
            title=dict(text="Speed Difference (A − B)", font=dict(size=14)),
            xaxis_title="Distance (m)",
            yaxis_title="Δ Speed (km/h)",
            template="plotly_white",
            height=280,
            margin=dict(l=50, r=20, t=40, b=40),
            plot_bgcolor="#FFFFFF", paper_bgcolor="#FAFBFC",
            font=dict(family="Inter, sans-serif", size=12, color="#1A1D23"),
        )
        fig_diff.update_xaxes(gridcolor="#F0F2F5", zeroline=False)
        fig_diff.update_yaxes(gridcolor="#F0F2F5", zeroline=False)
        st.plotly_chart(fig_diff, use_container_width=True, key="speed_diff")

    # Comparison limitations
    st.markdown("---")
    with st.expander("⚠ Comparison limitations"):
        st.markdown("""
        - **Distance alignment** uses linear interpolation between the nearest valid samples.
          Intervals where source data has gaps exceeding the max gap threshold are marked as unavailable.
        - **Shared coverage only**: comparison is limited to the distance range where both laps have data.
          Areas outside this overlap are excluded.
        - **No sector timing**: this comparison does not claim sector-by-sector timing without
          explicit sector boundary definitions and validated time reconstruction.
        - **Mean/max metrics** are computed only over valid (non-NaN) interpolated samples.
        - **Different sampling rates** are handled by the common grid, but very sparse laps
          may lose detail between samples.
        """)
