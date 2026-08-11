"""
Day 13 AI Observability Dashboard
==================================
Production-grade Streamlit dashboard for monitoring AI service metrics.
Monitors 6 required panels: latency, traffic, errors, cost, tokens, quality.
Supports SLO thresholds, real-time updates, incident injection for demos.

Author: Metrics & Dashboard Engineer (Member C)
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import yaml
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
from collections import Counter
import io
import json

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

DATA_FILE = Path(__file__).parent.parent.parent / "data" / "logs.jsonl"
SLO_CONFIG = Path(__file__).parent.parent.parent / "config" / "slo.yaml"
ALERT_CONFIG = Path(__file__).parent.parent.parent / "config" / "alert_rules.yaml"

REFRESH_SECONDS = 30
DEFAULT_TIME_RANGE = 60

# ─── Load SLO thresholds from config ─────────────────────────────────────────
def load_slo_config() -> dict:
    """Load SLO objectives from config/slo.yaml."""
    if SLO_CONFIG.exists():
        with open(SLO_CONFIG) as f:
            config = yaml.safe_load(f)
            slis = config.get("slis", {})
            return {key: values["objective"] for key, values in slis.items()}
    # Fallback defaults matching config/slo.yaml
    return {
        "latency_p95_ms": 3000,
        "error_rate_pct": 2.0,
        "daily_cost_usd": 2.5,
        "quality_score_avg": 0.75,
    }

# ─── Load alert rules ────────────────────────────────────────────────────────
def load_alert_rules() -> list:
    """Load alert rules from config/alert_rules.yaml."""
    if ALERT_CONFIG.exists():
        with open(ALERT_CONFIG) as f:
            config = yaml.safe_load(f)
            return config.get("alerts", [])
    return []

SLO = load_slo_config()
ALERT_RULES = load_alert_rules()

# ═══════════════════════════════════════════════════════════════════════════════
# PAGE CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="Day 13 Observability",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ═══════════════════════════════════════════════════════════════════════════════
# CUSTOM CSS - Dark Theme Observability Style
# ═══════════════════════════════════════════════════════════════════════════════

st.markdown("""
<style>
    /* ─── Root Variables ─────────────────────────────────────────────────── */
    :root {
        --bg-primary: #0e1117;
        --bg-secondary: #161b22;
        --bg-card: #1c2128;
        --border-color: #30363d;
        --text-primary: #e6edf3;
        --text-secondary: #8b949e;
        --accent-green: #3fb950;
        --accent-red: #f85149;
        --accent-yellow: #d29922;
        --accent-blue: #58a6ff;
        --accent-purple: #a371f7;
    }

    /* ─── Global Styles ──────────────────────────────────────────────────── */
    .stApp {
        background: linear-gradient(135deg, var(--bg-primary) 0%, #0d1117 100%);
        color: var(--text-primary);
    }
    
    /* ─── Cards & Containers ─────────────────────────────────────────────── */
    .metric-card {
        background: var(--bg-card);
        border: 1px solid var(--border-color);
        border-radius: 12px;
        padding: 1.25rem;
        margin: 0.5rem 0;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
        transition: all 0.3s ease;
    }
    
    .metric-card:hover {
        border-color: var(--accent-blue);
        box-shadow: 0 6px 12px rgba(88, 166, 255, 0.15);
    }
    
    .panel-card {
        background: var(--bg-card);
        border: 1px solid var(--border-color);
        border-radius: 16px;
        padding: 1.5rem;
        margin: 0.75rem 0;
        box-shadow: 0 4px 8px rgba(0, 0, 0, 0.25);
    }
    
    .panel-header {
        font-size: 1.1rem;
        font-weight: 600;
        color: var(--text-primary);
        margin-bottom: 1rem;
        padding-bottom: 0.75rem;
        border-bottom: 2px solid var(--border-color);
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }
    
    /* ─── Status Indicators ──────────────────────────────────────────────── */
    .status-ok {
        color: var(--accent-green);
        font-weight: 700;
    }
    
    .status-breach {
        color: var(--accent-red);
        font-weight: 700;
        animation: pulse 2s infinite;
    }
    
    .status-warning {
        color: var(--accent-yellow);
        font-weight: 700;
    }
    
    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.6; }
    }
    
    /* ─── SLO Header Bar ─────────────────────────────────────────────────── */
    .slo-header {
        background: linear-gradient(90deg, var(--bg-secondary) 0%, var(--bg-card) 100%);
        border: 1px solid var(--border-color);
        border-radius: 12px;
        padding: 1rem 1.5rem;
        margin-bottom: 1rem;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    
    /* ─── Alert Banner ───────────────────────────────────────────────────── */
    .alert-banner {
        background: linear-gradient(90deg, rgba(248, 81, 73, 0.15) 0%, rgba(248, 81, 73, 0.05) 100%);
        border: 1px solid var(--accent-red);
        border-radius: 8px;
        padding: 0.75rem 1rem;
        margin: 0.5rem 0;
        display: flex;
        align-items: center;
        gap: 0.75rem;
    }
    
    .alert-banner.warning {
        background: linear-gradient(90deg, rgba(210, 153, 34, 0.15) 0%, rgba(210, 153, 34, 0.05) 100%);
        border-color: var(--accent-yellow);
    }
    
    /* ─── Sparkline Container ────────────────────────────────────────────── */
    .sparkline-container {
        display: flex;
        align-items: flex-end;
        gap: 2px;
        height: 30px;
        margin-top: 0.5rem;
    }
    
    /* ─── Sidebar Styling ────────────────────────────────────────────────── */
    .css-1d391kg {
        background-color: var(--bg-secondary);
    }
    
    /* ─── Metrics Styling ────────────────────────────────────────────────── */
    div[data-testid="stMetricValue"] {
        font-size: 1.75rem !important;
        font-weight: 700 !important;
    }
    
    div[data-testid="stMetricLabel"] {
        font-size: 0.85rem !important;
        color: var(--text-secondary) !important;
    }
    
    /* ─── Charts ─────────────────────────────────────────────────────────── */
    .js-plotly-plot .plotly .modebar {
        background: transparent !important;
    }
    
    /* ─── Timestamp ─────────────────────────────────────────────────────── */
    .last-updated {
        color: var(--text-secondary);
        font-size: 0.8rem;
        text-align: right;
        padding: 0.5rem;
    }
    
    /* ─── Incident Indicator ─────────────────────────────────────────────── */
    .incident-active {
        background: linear-gradient(90deg, rgba(248, 81, 73, 0.2) 0%, transparent 100%);
        border-left: 4px solid var(--accent-red);
        padding: 0.5rem 1rem;
        margin: 0.25rem 0;
    }
    
    /* ─── Custom Scrollbar ───────────────────────────────────────────────── */
    ::-webkit-scrollbar {
        width: 8px;
        height: 8px;
    }
    
    ::-webkit-scrollbar-track {
        background: var(--bg-secondary);
    }
    
    ::-webkit-scrollbar-thumb {
        background: var(--border-color);
        border-radius: 4px;
    }
    
    ::-webkit-scrollbar-thumb:hover {
        background: var(--text-secondary);
    }
    
    /* ─── Button Styling ──────────────────────────────────────────────────── */
    .stButton > button {
        background: linear-gradient(135deg, var(--accent-blue) 0%, #1f6feb 100%);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 0.5rem 1rem;
        font-weight: 600;
        transition: all 0.2s ease;
    }
    
    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(88, 166, 255, 0.3);
    }
    
    /* ─── Export Button ──────────────────────────────────────────────────── */
    .export-btn {
        background: linear-gradient(135deg, var(--accent-purple) 0%, #8957e5 100%);
    }
</style>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
# SESSION STATE
# ═══════════════════════════════════════════════════════════════════════════════

if "incident_mode" not in st.session_state:
    st.session_state.incident_mode = False
if "last_incident_time" not in st.session_state:
    st.session_state.last_incident_time = None
if "refresh_count" not in st.session_state:
    st.session_state.refresh_count = 0

# ═══════════════════════════════════════════════════════════════════════════════
# SIDEBAR - Settings & Controls
# ═══════════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown("## ⚙️ Dashboard Controls")
    st.divider()
    
    # ─── Time Range Selector ───────────────────────────────────────────────
    st.markdown("### 📅 Time Range")
    time_options = {
        "30 minutes": 30,
        "60 minutes (default)": 60,
        "2 hours": 120,
        "24 hours": 1440,
    }
    selected_label = st.selectbox(
        "Select window",
        list(time_options.keys()),
        index=1,
        label_visibility="collapsed"
    )
    time_range_min = time_options[selected_label]
    
    st.divider()
    
    # ─── Auto-Refresh Toggle ───────────────────────────────────────────────
    st.markdown("### 🔄 Auto-Refresh")
    auto_refresh = st.checkbox(f"Enable ({REFRESH_SECONDS}s interval)", value=True)
    
    # Refresh indicator
    if auto_refresh:
        st.session_state.refresh_count += 1
        st.markdown(f"""
        <div style="display: flex; align-items: center; gap: 8px; padding: 8px;">
            <span style="width: 10px; height: 10px; background: var(--accent-green); 
                  border-radius: 50%; animation: pulse 1.5s infinite;"></span>
            <span style="color: var(--text-secondary); font-size: 0.85rem;">
                Live • Refresh #{st.session_state.refresh_count}
            </span>
        </div>
        """, unsafe_allow_html=True)
    
    st.divider()
    
    # ─── Incident Injection Controls ──────────────────────────────────────
    st.markdown("### 🔧 Demo Controls")
    st.caption("For testing alert behavior")
    
    if st.button("🚨 Inject Test Incident", use_container_width=True):
        st.session_state.incident_mode = True
        st.session_state.last_incident_time = datetime.now()
        st.rerun()
    
    if st.button("✓ Clear Incident", use_container_width=True):
        st.session_state.incident_mode = False
        st.rerun()
    
    if st.session_state.incident_mode:
        st.markdown(f"""
        <div class="incident-active">
            <strong>⚠️ INCIDENT ACTIVE</strong><br>
            <small>Injected: {st.session_state.last_incident_time.strftime('%H:%M:%S')}</small>
        </div>
        """, unsafe_allow_html=True)
    
    st.divider()
    
    # ─── Correlation ID Lookup ────────────────────────────────────────────
    st.markdown("### 🔍 Trace Lookup")
    correlation_id = st.text_input(
        "Correlation ID",
        placeholder="e.g., req-abc123",
        label_visibility="collapsed"
    )
    
    if st.button("Search Trace", use_container_width=True) and correlation_id:
        # Enhancement: implement trace lookup
        st.info(f"Looking up trace: {correlation_id}")
    
    st.divider()
    
    # ─── Export Metrics ────────────────────────────────────────────────────
    st.markdown("### 📥 Export")
    
    def get_metrics_csv(df: pd.DataFrame) -> bytes:
        """Generate CSV of current metrics snapshot."""
        metrics = snapshot_metrics(df)
        df_export = pd.DataFrame([metrics])
        return df_export.to_csv(index=False).encode()
    
    csv_data = None
    if "df" in locals():
        csv_data = get_metrics_csv(df)
    
    st.download_button(
        "📊 Export Metrics CSV",
        data=csv_data or b"",
        file_name=f"metrics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv",
        use_container_width=True,
        disabled=csv_data is None,
    )
    
    st.divider()
    
    # ─── About ────────────────────────────────────────────────────────────
    st.markdown("""
    <div style="color: var(--text-secondary); font-size: 0.75rem; text-align: center;">
        Day 13 Observability Lab<br>
        Streamlit Dashboard v1.0<br>
        <br>
        <strong>Panels:</strong><br>
        • Latency (P50/P95/P99)<br>
        • Traffic (req/min)<br>
        • Error Rate (%)<br>
        • Cost (USD)<br>
        • Tokens (in/out)<br>
        • Quality Score
    </div>
    """, unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
# DATA LOADING
# ═══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=REFRESH_SECONDS if auto_refresh else None, show_spinner=False)
def load_logs() -> pd.DataFrame:
    """
    Load and filter logs from data/logs.jsonl.
    
    Filters by time range selected in sidebar.
    Parses JSONL format with error handling for malformed entries.
    
    Returns:
        pd.DataFrame: Filtered log data
    """
    if not DATA_FILE.exists():
        return pd.DataFrame()
    
    records = []
    with open(DATA_FILE) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue  # Skip malformed lines
    
    df = pd.DataFrame(records)
    
    if "ts" in df.columns or "timestamp" in df.columns:
        ts_col = "ts" if "ts" in df.columns else "timestamp"
        df[ts_col] = pd.to_datetime(df[ts_col], errors="coerce", utc=True)
        cutoff = pd.Timestamp.now(tz="UTC") - pd.Timedelta(minutes=time_range_min)
        df = df[df[ts_col] >= cutoff].copy()
    
    return df

# ─── Load data ────────────────────────────────────────────────────────────────
df = load_logs()

# ═══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def get_slo_status(value: float, target: float, lower_is_better: bool = True) -> tuple:
    """
    Determine SLO status based on value vs target.
    
    Args:
        value: Current metric value
        target: SLO target threshold
        lower_is_better: If True, breach when value > target
        
    Returns:
        tuple: (status_text, css_class, is_breach)
    """
    if lower_is_better:
        is_breach = value > target
    else:
        is_breach = value < target
    
    if is_breach:
        return "BREACH", "status-breach", True
    return "OK", "status-ok", False


def snapshot_metrics(data: pd.DataFrame) -> dict:
    """
    Generate metrics snapshot for export.
    
    Args:
        data: Full DataFrame
        
    Returns:
        dict: Current values for all SLO metrics
    """
    response_df = data[data["event"] == "response_sent"] if "event" in data.columns else pd.DataFrame()
    failed_df = data[data["event"] == "request_failed"] if "event" in data.columns else pd.DataFrame()
    received_df = data[data["event"] == "request_received"] if "event" in data.columns else pd.DataFrame()
    
    return {
        "timestamp": datetime.now().isoformat(),
        "time_range_min": time_range_min,
        "latency_p50": response_df["latency_ms"].quantile(0.50) if "latency_ms" in response_df else 0,
        "latency_p95": response_df["latency_ms"].quantile(0.95) if "latency_ms" in response_df else 0,
        "latency_p99": response_df["latency_ms"].quantile(0.99) if "latency_ms" in response_df else 0,
        "error_rate_pct": len(failed_df) / len(received_df) * 100 if len(received_df) > 0 else 0,
        "total_cost_usd": response_df["cost_usd"].sum() if "cost_usd" in response_df else 0,
        "tokens_in_total": response_df["tokens_in"].sum() if "tokens_in" in response_df else 0,
        "tokens_out_total": response_df["tokens_out"].sum() if "tokens_out" in response_df else 0,
        "quality_score_avg": response_df["quality_score"].mean() if "quality_score" in response_df else 0,
        "total_requests": len(received_df),
        "total_failures": len(failed_df),
    }


def add_threshold_lines(fig: go.Figure, threshold: float, orientation: str = "v", 
                        name: str = "SLO Threshold", color: str = "#f85149") -> go.Figure:
    """
    Add dashed threshold line to Plotly figure.
    
    Args:
        fig: Plotly figure object
        threshold: Threshold value to mark
        orientation: 'v' for vertical, 'h' for horizontal
        name: Label for the line
        color: Line color
    """
    if orientation == "h":
        fig.add_hline(
            y=threshold,
            line_dash="dash",
            line_color=color,
            annotation_text=name,
            annotation_position="top"
        )
    else:
        fig.add_vline(
            x=threshold,
            line_dash="dash",
            line_color=color,
            annotation_text=name,
            annotation_position="top"
        )
    return fig


def get_sparkline_data(series: pd.Series, bins: int = 20) -> list:
    """
    Generate sparkline data from time series.
    
    Args:
        series: Time series data
        bins: Number of buckets to aggregate
        
    Returns:
        list: Normalized values for sparkline rendering
    """
    if series.empty:
        return [0] * bins
    
    # Downsample to bins
    if len(series) > bins:
        indices = np.linspace(0, len(series) - 1, bins).astype(int)
        return series.iloc[indices].tolist()
    return series.tolist() + [0] * (bins - len(series))


# ═══════════════════════════════════════════════════════════════════════════════
# HEADER - Title & Alert Banner
# ═══════════════════════════════════════════════════════════════════════════════

col_title, col_status = st.columns([3, 1])

with col_title:
    st.markdown("""
    <div style="padding: 1rem 0;">
        <h1 style="margin: 0; color: var(--text-primary);">
            📊 Day 13 AI Observability
        </h1>
        <p style="margin: 0.5rem 0 0 0; color: var(--text-secondary);">
            Real-time monitoring dashboard • Service: day13-observability-lab
        </p>
    </div>
    """, unsafe_allow_html=True)

with col_status:
    # Live indicator
    if auto_refresh:
        st.markdown(f"""
        <div style="text-align: right; padding: 1rem;">
            <span style="display: inline-flex; align-items: center; gap: 8px;">
                <span style="width: 12px; height: 12px; background: var(--accent-green); 
                      border-radius: 50%; animation: pulse 1.5s infinite;"></span>
                <span style="color: var(--accent-green); font-weight: 600;">LIVE</span>
            </span>
            <br>
            <span style="color: var(--text-secondary); font-size: 0.8rem;">
                Updated: {datetime.now().strftime('%H:%M:%S')}
            </span>
        </div>
        """, unsafe_allow_html=True)

st.divider()

# ═══════════════════════════════════════════════════════════════════════════════
# ALERT BANNER - Active Breaches
# ═══════════════════════════════════════════════════════════════════════════════

# Calculate current metrics
response_df = df[df["event"] == "response_sent"] if "event" in df.columns and not df.empty else pd.DataFrame()
failed_df = df[df["event"] == "request_failed"] if "event" in df.columns and not df.empty else pd.DataFrame()
received_df = df[df["event"] == "request_received"] if "event" in df.columns and not df.empty else pd.DataFrame()

current_metrics = {
    "latency_p95_ms": response_df["latency_ms"].quantile(0.95) if "latency_ms" in response_df else 0,
    "error_rate_pct": len(failed_df) / len(received_df) * 100 if len(received_df) > 0 else 0,
    "daily_cost_usd": response_df["cost_usd"].sum() if "cost_usd" in response_df else 0,
    "quality_score_avg": response_df["quality_score"].mean() if "quality_score" in response_df else 0,
}

# Check for breaches (include incident mode simulation)
active_alerts = []
for metric, value in current_metrics.items():
    target = SLO.get(metric, 0)
    if metric in ["latency_p95_ms", "error_rate_pct", "daily_cost_usd"]:
        if value > target or st.session_state.incident_mode:
            active_alerts.append(metric)
    elif metric == "quality_score_avg":
        if value < target:
            active_alerts.append(metric)

# Simulate incident alert
if st.session_state.incident_mode and "error_rate_pct" not in active_alerts:
    active_alerts.append("error_rate_pct")

if active_alerts:
    alert_colors = {"error_rate_pct": "#f85149", "latency_p95_ms": "#d29922", "daily_cost_usd": "#d29922"}
    alert_msgs = {
        "error_rate_pct": "Error rate above SLO threshold",
        "latency_p95_ms": "P95 latency exceeds 3000ms",
        "daily_cost_usd": "Daily cost budget exceeded",
    }
    
    for alert in active_alerts[:3]:  # Show max 3 alerts
        color = alert_colors.get(alert, "#f85149")
        st.markdown(f"""
        <div class="alert-banner" style="border-color: {color}; background: linear-gradient(90deg, {color}22 0%, transparent 100%);">
            <span style="font-size: 1.5rem;">🚨</span>
            <div>
                <strong style="color: {color};">{alert_msgs.get(alert, alert)}</strong><br>
                <span style="color: var(--text-secondary); font-size: 0.85rem;">
                    {ALERT_RULES[0]['summary'] if ALERT_RULES else 'Check metrics immediately'}
                </span>
            </div>
        </div>
        """, unsafe_allow_html=True)
else:
    st.markdown("""
    <div class="alert-banner" style="border-color: var(--accent-green); background: linear-gradient(90deg, rgba(63, 185, 80, 0.1) 0%, transparent 100%);">
        <span style="font-size: 1.5rem;">✅</span>
        <div>
            <strong style="color: var(--accent-green);">All SLOs Healthy</strong><br>
            <span style="color: var(--text-secondary); font-size: 0.85rem;">
                No active alerts • Service operating within targets
            </span>
        </div>
    </div>
    """, unsafe_allow_html=True)

st.divider()

# ═══════════════════════════════════════════════════════════════════════════════
# SLO STATUS ROW - 4 Cards
# ═══════════════════════════════════════════════════════════════════════════════

st.markdown("### 📈 Service Level Objectives")
slo_cols = st.columns(4)

slo_data = [
    {
        "id": "latency",
        "title": "Latency P95",
        "value": current_metrics.get("latency_p95_ms", 0),
        "unit": "ms",
        "target": SLO.get("latency_p95_ms", 3000),
        "format": lambda v: f"{v:.0f}",
        "lower_is_better": True,
        "icon": "⏱️",
    },
    {
        "id": "errors",
        "title": "Error Rate",
        "value": current_metrics.get("error_rate_pct", 0),
        "unit": "%",
        "target": SLO.get("error_rate_pct", 2),
        "format": lambda v: f"{v:.2f}",
        "lower_is_better": True,
        "icon": "❌",
    },
    {
        "id": "cost",
        "title": "Daily Cost",
        "value": current_metrics.get("daily_cost_usd", 0),
        "unit": "USD",
        "target": SLO.get("daily_cost_usd", 2.5),
        "format": lambda v: f"${v:.4f}",
        "lower_is_better": True,
        "icon": "💰",
    },
    {
        "id": "quality",
        "title": "Quality Score",
        "value": current_metrics.get("quality_score_avg", 0),
        "unit": "",
        "target": SLO.get("quality_score_avg", 0.75),
        "format": lambda v: f"{v:.3f}",
        "lower_is_better": False,
        "icon": "⭐",
    },
]

for i, slo in enumerate(slo_data):
    with slo_cols[i]:
        status, css_class, is_breach = get_slo_status(
            slo["value"], slo["target"], slo["lower_is_better"]
        )
        
        # Inject incident simulation for error rate
        display_value = slo["value"]
        if st.session_state.incident_mode and slo["id"] == "errors":
            display_value = 5.2  # Simulated breach
        
        st.markdown(f"""
        <div class="panel-card">
            <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                <div>
                    <span style="font-size: 1.2rem;">{slo['icon']}</span>
                    <span style="color: var(--text-secondary); font-size: 0.85rem;">{slo['title']}</span>
                </div>
                <span class="{css_class}" style="font-size: 0.75rem; padding: 2px 8px; 
                      background: {'rgba(248,81,73,0.2)' if is_breach else 'rgba(63,185,80,0.2)'}; 
                      border-radius: 4px;">
                    {status}
                </span>
            </div>
            <div style="font-size: 2rem; font-weight: 700; margin: 0.5rem 0; color: var(--text-primary);">
                {slo['format'](display_value)}<span style="font-size: 0.9rem; color: var(--text-secondary);">{slo['unit']}</span>
            </div>
            <div style="color: var(--text-secondary); font-size: 0.8rem;">
                Target: {slo['format'](slo['target'])}{slo['unit']}
            </div>
        </div>
        """, unsafe_allow_html=True)

st.divider()

# ═══════════════════════════════════════════════════════════════════════════════
# PANEL 1: LATENCY PERCENTILES
# ═══════════════════════════════════════════════════════════════════════════════

st.markdown("""
<div class="panel-header">
    <span>⏱️</span> 1. Latency Percentiles
    <span style="margin-left: auto; font-size: 0.8rem; color: var(--text-secondary);">
        P50 / P95 / P99 distribution
    </span>
</div>
""", unsafe_allow_html=True)

lat_col1, lat_col2 = st.columns([1, 2])

with lat_col1:
    if not response_df.empty and "latency_ms" in response_df.columns:
        p50 = response_df["latency_ms"].quantile(0.50)
        p95 = response_df["latency_ms"].quantile(0.95)
        p99 = response_df["latency_ms"].quantile(0.99)
        
        st.markdown(f"""
        <div class="metric-card">
            <div style="color: var(--accent-blue); font-weight: 600;">P50</div>
            <div style="font-size: 1.8rem; font-weight: 700;">{p50:.0f} <span style="font-size: 0.9rem; color: var(--text-secondary);">ms</span></div>
        </div>
        """, unsafe_allow_html=True)
        
        p95_status = "status-breach" if p95 > SLO["latency_p95_ms"] else "status-ok"
        st.markdown(f"""
        <div class="metric-card">
            <div style="color: var(--accent-purple); font-weight: 600;">P95 <span class="{p95_status}">{'⚠️' if p95 > SLO["latency_p95_ms"] else '✓'}</span></div>
            <div style="font-size: 1.8rem; font-weight: 700;">{p95:.0f} <span style="font-size: 0.9rem; color: var(--text-secondary);">ms</span></div>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown(f"""
        <div class="metric-card">
            <div style="color: var(--accent-yellow); font-weight: 600;">P99</div>
            <div style="font-size: 1.8rem; font-weight: 700;">{p99:.0f} <span style="font-size: 0.9rem; color: var(--text-secondary);">ms</span></div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.info("No latency data available")

with lat_col2:
    if not response_df.empty and "latency_ms" in response_df.columns:
        # Multi-line chart: latency over time with percentiles
        response_with_ts = response_df.copy()
        if "ts" in response_with_ts.columns:
            response_with_ts = response_with_ts.set_index("ts")
            latency_by_time = response_with_ts["latency_ms"].resample("1min").agg(
                ["min", lambda x: x.quantile(0.50), lambda x: x.quantile(0.95), lambda x: x.quantile(0.99), "max"]
            ).reset_index()
            latency_by_time.columns = ["time", "min", "p50", "p95", "p99", "max"]
            
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=latency_by_time["time"], y=latency_by_time["p50"],
                name="P50", line=dict(color="#58a6ff", width=2), mode="lines"
            ))
            fig.add_trace(go.Scatter(
                x=latency_by_time["time"], y=latency_by_time["p95"],
                name="P95", line=dict(color="#a371f7", width=2), mode="lines"
            ))
            fig.add_trace(go.Scatter(
                x=latency_by_time["time"], y=latency_by_time["p99"],
                name="P99", line=dict(color="#d29922", width=2), mode="lines"
            ))
            
            # Add threshold line
            fig.add_hline(
                y=SLO["latency_p95_ms"],
                line_dash="dash",
                line_color="#f85149",
                annotation_text=f"SLO: {SLO['latency_p95_ms']}ms"
            )
            
            fig.update_layout(
                template="plotly_dark",
                height=300,
                margin=dict(l=20, r=20, t=40, b=20),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                hovermode="x unified",
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            # Histogram fallback
            fig = px.histogram(
                response_df, x="latency_ms", nbins=30,
                title="Latency Distribution",
                color_discrete_sequence=["#58a6ff"]
            )
            fig.add_vline(x=SLO["latency_p95_ms"], line_dash="dash", line_color="#f85149")
            fig.update_layout(template="plotly_dark", height=300)
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No latency data for chart")

st.divider()

# ═══════════════════════════════════════════════════════════════════════════════
# PANEL 2: REQUEST TRAFFIC
# ═══════════════════════════════════════════════════════════════════════════════

st.markdown("""
<div class="panel-header">
    <span>📨</span> 2. Request Traffic
    <span style="margin-left: auto; font-size: 0.8rem; color: var(--text-secondary);">
        Request count and rate analysis
    </span>
</div>
""", unsafe_allow_html=True)

traffic_col1, traffic_col2 = st.columns([1, 2])

with traffic_col1:
    total_requests = len(received_df)
    rate_per_min = total_requests / time_range_min if time_range_min > 0 else 0
    success_count = len(response_df)
    success_rate = (success_count / total_requests * 100) if total_requests > 0 else 0
    
    st.markdown(f"""
    <div class="metric-card">
        <div style="color: var(--accent-blue); font-weight: 600;">Total Requests</div>
        <div style="font-size: 1.8rem; font-weight: 700;">{total_requests:,}</div>
        <div style="color: var(--text-secondary); font-size: 0.85rem; margin-top: 0.25rem;">
            in {time_range_min} min window
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown(f"""
    <div class="metric-card">
        <div style="color: var(--accent-green); font-weight: 600;">Rate</div>
        <div style="font-size: 1.8rem; font-weight: 700;">{rate_per_min:.1f} <span style="font-size: 0.9rem; color: var(--text-secondary);">req/min</span></div>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown(f"""
    <div class="metric-card">
        <div style="color: var(--accent-purple); font-weight: 600;">Success Rate</div>
        <div style="font-size: 1.8rem; font-weight: 700;">{success_rate:.1f}<span style="font-size: 0.9rem; color: var(--text-secondary);">%</span></div>
        <div style="color: var(--text-secondary); font-size: 0.85rem; margin-top: 0.25rem;">
            {success_count} successful
        </div>
    </div>
    """, unsafe_allow_html=True)

with traffic_col2:
    if not received_df.empty and "ts" in received_df.columns:
        # Multi-series traffic chart
        received_ts = received_df.set_index("ts")
        traffic_by_time = received_ts.resample("1min").size().reset_index(name="requests")
        
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=traffic_by_time["ts"], y=traffic_by_time["requests"],
            name="Requests", marker_color="#58a6ff", opacity=0.7
        ))
        fig.add_trace(go.Scatter(
            x=traffic_by_time["ts"], y=traffic_by_time["requests"].rolling(5, min_periods=1).mean(),
            name="5-min Avg", line=dict(color="#f85149", width=2)
        ))
        
        fig.update_layout(
            template="plotly_dark",
            height=300,
            margin=dict(l=20, r=20, t=40, b=20),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            hovermode="x unified",
            yaxis_title="Requests / min"
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No traffic data available")

st.divider()

# ═══════════════════════════════════════════════════════════════════════════════
# PANEL 3: ERROR RATE & BREAKDOWN
# ═══════════════════════════════════════════════════════════════════════════════

st.markdown("""
<div class="panel-header">
    <span>❌</span> 3. Error Rate
    <span style="margin-left: auto; font-size: 0.8rem; color: var(--text-secondary);">
        error_rate_pct = (count request_failed / count request_received) * 100
    </span>
</div>
""", unsafe_allow_html=True)

error_col1, error_col2 = st.columns([1, 2])

with error_col1:
    total_failed = len(failed_df)
    total_received = len(received_df)
    error_rate = total_failed / total_received * 100 if total_received > 0 else 0
    
    # Simulate incident mode
    if st.session_state.incident_mode:
        error_rate = 5.2
        total_failed = 26
    
    error_status, _, is_breach = get_slo_status(error_rate, SLO["error_rate_pct"], True)
    
    st.markdown(f"""
    <div class="metric-card" style="{'border-color: var(--accent-red);' if is_breach else ''}">
        <div style="color: var(--accent-red); font-weight: 600;">Error Rate</div>
        <div style="font-size: 2rem; font-weight: 700; color: {'var(--accent-red)' if is_breach else 'var(--text-primary)'};">
            {error_rate:.2f}<span style="font-size: 0.9rem; color: var(--text-secondary);">%</span>
        </div>
        <div style="color: {('var(--accent-red)' if is_breach else 'var(--accent-green)')}; font-size: 0.85rem; margin-top: 0.25rem;">
            {error_status} • SLO: {SLO["error_rate_pct"]}%
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown(f"""
    <div class="metric-card">
        <div style="color: var(--text-secondary); font-weight: 600;">Failed Requests</div>
        <div style="font-size: 1.5rem; font-weight: 700;">{total_failed:,}</div>
        <div style="color: var(--text-secondary); font-size: 0.85rem; margin-top: 0.25rem;">
            of {total_received:,} total
        </div>
    </div>
    """, unsafe_allow_html=True)

with error_col2:
    if not failed_df.empty and "error_type" in failed_df.columns:
        # Error breakdown pie chart
        error_counts = failed_df["error_type"].value_counts().reset_index()
        error_counts.columns = ["error_type", "count"]
        
        fig = go.Figure(data=[go.Pie(
            labels=error_counts["error_type"],
            values=error_counts["count"],
            hole=0.4,
            marker=dict(colors=["#f85149", "#d29922", "#58a6ff"])
        )])
        fig.update_layout(
            template="plotly_dark",
            height=280,
            margin=dict(l=20, r=20, t=20, b=20),
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=-0.2),
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        if st.session_state.incident_mode:
            # Show simulated error breakdown
            st.markdown(f"""
            <div class="metric-card" style="border-color: var(--accent-red);">
                <div style="color: var(--accent-red); font-weight: 600;">⚠️ Incident Mode Active</div>
                <div style="color: var(--text-secondary); margin-top: 0.5rem;">
                    Simulated errors: timeout (15), validation (7), auth (4)
                </div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.info("No error breakdown available (no failed requests)")

st.divider()

# ═══════════════════════════════════════════════════════════════════════════════
# PANEL 4: COST OVER TIME
# ═══════════════════════════════════════════════════════════════════════════════

st.markdown("""
<div class="panel-header">
    <span>💰</span> 4. Cost Over Time
    <span style="margin-left: auto; font-size: 0.8rem; color: var(--text-secondary);">
        Rolling cost analysis with SLO budget
    </span>
</div>
""", unsafe_allow_html=True)

cost_col1, cost_col2 = st.columns([1, 2])

with cost_col1:
    total_cost = response_df["cost_usd"].sum() if "cost_usd" in response_df else 0
    avg_cost_per_req = total_cost / len(response_df) if len(response_df) > 0 else 0
    budget_used_pct = (total_cost / SLO["daily_cost_usd"] * 100) if SLO["daily_cost_usd"] > 0 else 0
    
    cost_status, _, is_breach = get_slo_status(total_cost, SLO["daily_cost_usd"], True)
    
    st.markdown(f"""
    <div class="metric-card" style="{'border-color: var(--accent-yellow);' if budget_used_pct > 80 else ''}">
        <div style="color: var(--accent-yellow); font-weight: 600;">Total Cost</div>
        <div style="font-size: 2rem; font-weight: 700;">${total_cost:.4f}</div>
        <div style="color: {('var(--accent-yellow)' if is_breach else 'var(--accent-green)')}; font-size: 0.85rem; margin-top: 0.25rem;">
            {cost_status} • Budget: ${SLO["daily_cost_usd"]:.2f}
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Budget progress bar
    progress_color = "#f85149" if budget_used_pct > 100 else "#d29922" if budget_used_pct > 80 else "#3fb950"
    st.markdown(f"""
    <div class="metric-card">
        <div style="color: var(--text-secondary); font-size: 0.85rem; margin-bottom: 0.5rem;">Budget Used</div>
        <div style="background: var(--bg-secondary); border-radius: 4px; height: 8px; overflow: hidden;">
            <div style="width: {min(budget_used_pct, 100):.1f}%; background: {progress_color}; height: 100%;"></div>
        </div>
        <div style="color: var(--text-secondary); font-size: 0.8rem; margin-top: 0.25rem; text-align: right;">
            {budget_used_pct:.1f}%
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown(f"""
    <div class="metric-card">
        <div style="color: var(--text-secondary); font-weight: 600;">Avg per Request</div>
        <div style="font-size: 1.3rem; font-weight: 700;">${avg_cost_per_req:.4f}</div>
    </div>
    """, unsafe_allow_html=True)

with cost_col2:
    if not response_df.empty and "cost_usd" in response_df.columns and "ts" in response_df.columns:
        # Cost over time area chart
        cost_ts = response_df.set_index("ts")
        cost_by_time = cost_ts["cost_usd"].resample("1min").sum().cumsum().reset_index()
        cost_by_time.columns = ["time", "cumulative_cost"]
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=cost_by_time["time"], y=cost_by_time["cumulative_cost"],
            fill="tozeroy", name="Cumulative Cost",
            line=dict(color="#d29922"), fillcolor="rgba(210, 153, 34, 0.3)"
        ))
        
        # Add SLO threshold
        fig.add_hline(
            y=SLO["daily_cost_usd"],
            line_dash="dash",
            line_color="#f85149",
            annotation_text=f"Budget: ${SLO['daily_cost_usd']}"
        )
        
        fig.update_layout(
            template="plotly_dark",
            height=280,
            margin=dict(l=20, r=20, t=20, b=20),
            yaxis_title="Cumulative Cost (USD)",
            hovermode="x unified"
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No cost data available")

st.divider()

# ═══════════════════════════════════════════════════════════════════════════════
# PANEL 5: TOKEN TOTALS
# ═══════════════════════════════════════════════════════════════════════════════

st.markdown("""
<div class="panel-header">
    <span>🔤</span> 5. Token Usage
    <span style="margin-left: auto; font-size: 0.8rem; color: var(--text-secondary);">
        Input and output token breakdown
    </span>
</div>
""", unsafe_allow_html=True)

token_col1, token_col2 = st.columns([1, 2])

with token_col1:
    tokens_in = response_df["tokens_in"].sum() if "tokens_in" in response_df else 0
    tokens_out = response_df["tokens_out"].sum() if "tokens_out" in response_df else 0
    total_tokens = tokens_in + tokens_out
    in_out_ratio = tokens_out / tokens_in if tokens_in > 0 else 0
    
    st.markdown(f"""
    <div class="metric-card">
        <div style="color: var(--accent-blue); font-weight: 600;">Tokens In</div>
        <div style="font-size: 1.5rem; font-weight: 700;">{tokens_in:,}</div>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown(f"""
    <div class="metric-card">
        <div style="color: var(--accent-purple); font-weight: 600;">Tokens Out</div>
        <div style="font-size: 1.5rem; font-weight: 700;">{tokens_out:,}</div>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown(f"""
    <div class="metric-card">
        <div style="color: var(--accent-green); font-weight: 600;">Total</div>
        <div style="font-size: 1.5rem; font-weight: 700;">{total_tokens:,}</div>
        <div style="color: var(--text-secondary); font-size: 0.85rem; margin-top: 0.25rem;">
            In/Out ratio: {in_out_ratio:.2f}
        </div>
    </div>
    """, unsafe_allow_html=True)

with token_col2:
    if not response_df.empty and "tokens_in" in response_df.columns and "tokens_out" in response_df.columns:
        if "ts" in response_df.columns:
            # Multi-line token chart
            token_ts = response_df.set_index("ts")
            token_by_time = token_ts[["tokens_in", "tokens_out"]].resample("1min").sum().reset_index()
            
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=token_by_time["ts"], y=token_by_time["tokens_in"],
                name="Tokens In", line=dict(color="#58a6ff"), stackgroup="one", fillcolor="rgba(88, 166, 255, 0.3)"
            ))
            fig.add_trace(go.Scatter(
                x=token_by_time["ts"], y=token_by_time["tokens_out"],
                name="Tokens Out", line=dict(color="#a371f7"), stackgroup="one", fillcolor="rgba(163, 113, 247, 0.3)"
            ))
            
            fig.update_layout(
                template="plotly_dark",
                height=280,
                margin=dict(l=20, r=20, t=20, b=20),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                hovermode="x unified",
                yaxis_title="Tokens / min"
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            # Bar chart fallback
            fig = go.Figure(data=[
                go.Bar(name="Tokens In", x=["Total"], y=[tokens_in], marker_color="#58a6ff"),
                go.Bar(name="Tokens Out", x=["Total"], y=[tokens_out], marker_color="#a371f7")
            ])
            fig.update_layout(template="plotly_dark", height=280, barmode="stack")
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No token data available")

st.divider()

# ═══════════════════════════════════════════════════════════════════════════════
# PANEL 6: QUALITY SCORE
# ═══════════════════════════════════════════════════════════════════════════════

st.markdown("""
<div class="panel-header">
    <span>⭐</span> 6. Quality Score
    <span style="margin-left: auto; font-size: 0.8rem; color: var(--text-secondary);">
        Mean quality proxy (0-1 scale)
    </span>
</div>
""", unsafe_allow_html=True)

quality_col1, quality_col2 = st.columns([1, 2])

with quality_col1:
    quality_mean = response_df["quality_score"].mean() if "quality_score" in response_df else 0
    quality_median = response_df["quality_score"].median() if "quality_score" in response_df else 0
    quality_min = response_df["quality_score"].min() if "quality_score" in response_df else 0
    quality_max = response_df["quality_score"].max() if "quality_score" in response_df else 0
    
    quality_status, css_class, is_breach = get_slo_status(quality_mean, SLO["quality_score_avg"], False)
    
    st.markdown(f"""
    <div class="metric-card" style="{'border-color: var(--accent-yellow);' if is_breach else ''}">
        <div style="color: var(--accent-yellow); font-weight: 600;">Mean Quality</div>
        <div style="font-size: 2rem; font-weight: 700; color: {'var(--accent-yellow)' if is_breach else 'var(--text-primary)'};">
            {quality_mean:.3f}
        </div>
        <div style="color: {('var(--accent-yellow)' if is_breach else 'var(--accent-green)')}; font-size: 0.85rem; margin-top: 0.25rem;">
            {quality_status} • SLO: {SLO["quality_score_avg"]:.2f}
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown(f"""
    <div class="metric-card">
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.5rem;">
            <div>
                <div style="color: var(--text-secondary); font-size: 0.75rem;">Median</div>
                <div style="font-weight: 600;">{quality_median:.3f}</div>
            </div>
            <div>
                <div style="color: var(--text-secondary); font-size: 0.75rem;">Min</div>
                <div style="font-weight: 600;">{quality_min:.3f}</div>
            </div>
            <div>
                <div style="color: var(--text-secondary); font-size: 0.75rem;">Max</div>
                <div style="font-weight: 600;">{quality_max:.3f}</div>
            </div>
            <div>
                <div style="color: var(--text-secondary); font-size: 0.75rem;">Count</div>
                <div style="font-weight: 600;">{len(response_df)}</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

with quality_col2:
    if not response_df.empty and "quality_score" in response_df.columns:
        if "ts" in response_df.columns:
            # Quality over time with threshold
            quality_ts = response_df.set_index("ts")
            quality_by_time = quality_ts["quality_score"].resample("1min").mean().reset_index()
            
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=quality_by_time["ts"], y=quality_by_time["quality_score"],
                name="Quality", line=dict(color="#d29922", width=2), fill="tozeroy", fillcolor="rgba(210, 153, 34, 0.2)"
            ))
            
            # SLO threshold line
            fig.add_hline(
                y=SLO["quality_score_avg"],
                line_dash="dash",
                line_color="#3fb950",
                annotation_text=f"SLO: {SLO['quality_score_avg']}"
            )
            
            fig.update_layout(
                template="plotly_dark",
                height=280,
                margin=dict(l=20, r=20, t=20, b=20),
                yaxis=dict(range=[0, 1.05]),
                hovermode="x unified"
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            # Distribution histogram
            fig = px.histogram(
                response_df, x="quality_score", nbins=20,
                title="Quality Score Distribution",
                color_discrete_sequence=["#d29922"]
            )
            fig.add_vline(x=SLO["quality_score_avg"], line_dash="dash", line_color="#3fb950")
            fig.update_layout(template="plotly_dark", height=280)
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No quality score data available")

st.divider()

# ═══════════════════════════════════════════════════════════════════════════════
# FOOTER
# ═══════════════════════════════════════════════════════════════════════════════

# Last incident summary
if st.session_state.last_incident_time:
    st.markdown(f"""
    <div style="background: var(--bg-secondary); border: 1px solid var(--border-color); 
                border-radius: 8px; padding: 1rem; margin: 1rem 0;">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <div>
                <strong style="color: var(--accent-red);">🔴 Last Incident</strong>
                <div style="color: var(--text-secondary); font-size: 0.85rem;">
                    Injected at {st.session_state.last_incident_time.strftime('%Y-%m-%d %H:%M:%S')}
                </div>
            </div>
            <div style="color: var(--text-secondary); font-size: 0.8rem;">
                {int((datetime.now() - st.session_state.last_incident_time).total_seconds())}s ago
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

# Footer
st.markdown(f"""
<div class="last-updated">
    <strong>Day 13 AI Observability Dashboard</strong> • 
    Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} • 
    Source: {DATA_FILE.name} • 
    Time range: {time_range_min} min
</div>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
# AUTO-REFRESH (JavaScript)
# ═══════════════════════════════════════════════════════════════════════════════

if auto_refresh:
    st.markdown(f"""
    <meta http-equiv="refresh" content="{REFRESH_SECONDS}">
    <script>
        setTimeout(function() {{
            window.location.reload(1);
        }}, {REFRESH_SECONDS * 1000});
    </script>
    """, unsafe_allow_html=True)
