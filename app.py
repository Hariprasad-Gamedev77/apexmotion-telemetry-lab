"""
ApexMotion Telemetry Lab — Streamlit Application
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A motorsport telemetry quality and lap-comparison platform.
All demo data is synthetic.
"""

import streamlit as st
import sys
import os

# Ensure the project root is in the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from apexmotion.config import APP_NAME, APP_VERSION, DISCLAIMER
from pages_app.overview import render_overview
from pages_app.data_quality import render_data_quality
from pages_app.lap_comparison import render_lap_comparison
from pages_app.trust_passport import render_trust_passport
from pages_app.validation_bench import render_validation_bench
from pages_app.documentation import render_documentation

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title=APP_NAME,
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Global CSS — Light motorsport engineering theme
# ---------------------------------------------------------------------------
st.markdown("""
<style>
    /* Import fonts */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

    /* Root variables */
    :root {
        --bg-primary: #FAFBFC;
        --bg-sidebar: #F0F2F5;
        --bg-card: #FFFFFF;
        --bg-elevated: #F7F8FA;
        --border: #E2E6EB;
        --border-strong: #CBD1D9;
        --text-primary: #1A1D23;
        --text-secondary: #6B7280;
        --text-tertiary: #9CA3AF;
        --accent: #2563EB;
        --accent-light: #EFF6FF;
        --positive: #16A34A;
        --positive-bg: #F0FDF4;
        --warning: #D97706;
        --warning-bg: #FFFBEB;
        --critical: #DC2626;
        --critical-bg: #FEF2F2;
        --info-accent: #0891B2;
        --info-bg: #ECFEFF;
    }

    /* Global font */
    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }

    /* Hide default Streamlit branding */
    #MainMenu {visibility: hidden;}
    header {visibility: hidden;}
    footer {visibility: hidden;}

    /* Sidebar styling */
    section[data-testid="stSidebar"] {
        background-color: var(--bg-sidebar);
        border-right: 1px solid var(--border);
    }

    section[data-testid="stSidebar"] .stRadio > label {
        font-weight: 500;
    }

    /* Main content area */
    .main .block-container {
        padding-top: 2rem;
        max-width: 1200px;
    }

    /* Metric cards */
    .metric-card {
        background: var(--bg-card);
        border: 1px solid var(--border);
        border-radius: 10px;
        padding: 1.25rem;
        margin-bottom: 0.75rem;
        transition: box-shadow 0.15s ease;
    }
    .metric-card:hover {
        box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    }
    .metric-label {
        font-size: 0.78rem;
        font-weight: 500;
        color: var(--text-secondary);
        text-transform: uppercase;
        letter-spacing: 0.04em;
        margin-bottom: 0.35rem;
    }
    .metric-value {
        font-family: 'JetBrains Mono', monospace;
        font-size: 1.7rem;
        font-weight: 600;
        color: var(--text-primary);
        line-height: 1.2;
    }
    .metric-unit {
        font-size: 0.82rem;
        color: var(--text-secondary);
        font-family: 'JetBrains Mono', monospace;
        margin-left: 0.2rem;
    }
    .metric-subtitle {
        font-size: 0.75rem;
        color: var(--text-tertiary);
        margin-top: 0.25rem;
    }

    /* Status badges */
    .badge {
        display: inline-flex;
        align-items: center;
        gap: 0.3rem;
        padding: 0.2rem 0.65rem;
        border-radius: 999px;
        font-size: 0.75rem;
        font-weight: 600;
        letter-spacing: 0.02em;
    }
    .badge-error {
        background: var(--critical-bg);
        color: var(--critical);
        border: 1px solid #FECACA;
    }
    .badge-warning {
        background: var(--warning-bg);
        color: var(--warning);
        border: 1px solid #FDE68A;
    }
    .badge-info {
        background: var(--info-bg);
        color: var(--info-accent);
        border: 1px solid #A5F3FC;
    }
    .badge-success {
        background: var(--positive-bg);
        color: var(--positive);
        border: 1px solid #BBF7D0;
    }

    /* Panel / section card */
    .panel {
        background: var(--bg-card);
        border: 1px solid var(--border);
        border-radius: 10px;
        padding: 1.5rem;
        margin-bottom: 1rem;
    }
    .panel-header {
        font-size: 0.85rem;
        font-weight: 600;
        color: var(--text-primary);
        margin-bottom: 1rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }

    /* Pipeline status */
    .pipeline {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        flex-wrap: wrap;
    }
    .pipeline-step {
        display: flex;
        align-items: center;
        gap: 0.4rem;
        padding: 0.4rem 0.85rem;
        border-radius: 8px;
        font-size: 0.78rem;
        font-weight: 500;
        background: var(--bg-elevated);
        color: var(--text-secondary);
        border: 1px solid var(--border);
    }
    .pipeline-step.active {
        background: var(--accent-light);
        color: var(--accent);
        border-color: #BFDBFE;
    }
    .pipeline-step.done {
        background: var(--positive-bg);
        color: var(--positive);
        border-color: #BBF7D0;
    }
    .pipeline-arrow {
        color: var(--text-tertiary);
        font-size: 0.9rem;
    }

    /* Data table styling */
    .dataframe {
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 0.82rem !important;
    }

    /* Wordmark */
    .wordmark {
        font-weight: 700;
        font-size: 1.2rem;
        color: var(--text-primary);
        letter-spacing: -0.02em;
        margin-bottom: 0.2rem;
    }
    .wordmark-icon {
        color: var(--accent);
        margin-right: 0.35rem;
    }
    .wordmark-sub {
        font-size: 0.72rem;
        color: var(--text-tertiary);
        font-weight: 400;
        letter-spacing: 0.04em;
    }

    /* Plotly charts background */
    .stPlotlyChart {
        border: 1px solid var(--border);
        border-radius: 10px;
        overflow: hidden;
    }

    /* Severity table row colors */
    .severity-error { color: var(--critical); font-weight: 600; }
    .severity-warning { color: var(--warning); font-weight: 600; }
    .severity-info { color: var(--info-accent); font-weight: 500; }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0.5rem;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px;
        font-weight: 500;
    }

    /* Disclaimer */
    .disclaimer {
        font-size: 0.72rem;
        color: var(--text-tertiary);
        padding: 0.6rem 0.85rem;
        background: var(--bg-elevated);
        border-radius: 6px;
        border: 1px solid var(--border);
        margin-top: 1rem;
    }

    /* Hide the streamlit header anchor links */
    .stMarkdown h1 a, .stMarkdown h2 a, .stMarkdown h3 a {
        display: none !important;
    }

    /* Monospace for telemetry values */
    .mono {
        font-family: 'JetBrains Mono', monospace;
    }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Sidebar navigation
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("""
        <div style="padding: 0.5rem 0 1.5rem 0;">
            <div class="wordmark">
                <span class="wordmark-icon">◈</span>ApexMotion
            </div>
            <div class="wordmark-sub">TELEMETRY LAB</div>
        </div>
    """, unsafe_allow_html=True)

    page = st.radio(
        "Navigation",
        [
            "Overview",
            "Data Quality",
            "Lap Comparison",
            "Trust Passport",
            "Validation Bench",
            "Documentation",
        ],
        label_visibility="collapsed",
    )

    st.markdown("---")
    st.markdown(f"""
        <div class="disclaimer">
            <strong>v{APP_VERSION}</strong><br>
            {DISCLAIMER}
        </div>
    """, unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Page routing
# ---------------------------------------------------------------------------
if page == "Overview":
    render_overview()
elif page == "Data Quality":
    render_data_quality()
elif page == "Lap Comparison":
    render_lap_comparison()
elif page == "Trust Passport":
    render_trust_passport()
elif page == "Validation Bench":
    render_validation_bench()
elif page == "Documentation":
    render_documentation()
