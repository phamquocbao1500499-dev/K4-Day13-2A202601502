# Day 13 Observability Dashboard Implementation

## Recommended Tool: Streamlit

**Justification:**
- Python-native, aligns with existing `app/metrics.py`
- Fast iteration for lab context
- Built-in caching, auto-refresh via `st.rerun()` or `st.empty()`
- Easier than Grafana (no Prometheus setup) for single-file JSONL source
- Langfuse dashboard is read-only; Streamlit allows custom calculations

**Alternatives:** Grafana + Loki (production scale), Langfuse dashboard (LLM-centric, limited panel customization)

---

## Setup Steps

```bash
pip install streamlit pandas plotly
mkdir -p app/dashboard
```

---

## Dashboard Implementation

**File:** `app/dashboard/main.py`

```python
import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path
from collections import Counter
from statistics import mean

# ─── Config ─────────────────────────────────────────────────────────────────
SLO = {
    "latency_p95_ms": 3000,
    "error_rate_pct": 2.0,
    "daily_cost_usd": 2.5,
    "quality_score_avg": 0.75,
}

DATA_FILE = Path(__file__).parent.parent.parent / "data" / "logs.jsonl"
TIME_RANGE_MINUTES = 60
REFRESH_SECONDS = 30

st.set_page_config(page_title="Day 13 Observability", layout="wide")
st.title("Day 13 AI Observability Dashboard")

# ─── Time Range Selector ────────────────────────────────────────────────────
time_options = {"30 min": 30, "60 min (default)": 60, "2 hours": 120}
selected_label = st.sidebar.selectbox("Time range", list(time_options.keys()), index=1)
time_range = time_options[selected_label]
st.sidebar.write(f"Auto-refresh: {REFRESH_SECONDS}s")

# ─── Data Loading with Cache ─────────────────────────────────────────────────
@st.cache_data(ttl=REFRESH_SECONDS)
def load_logs():
    if not DATA_FILE.exists():
        return pd.DataFrame()
    records = []
    with open(DATA_FILE) as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(eval(line))  # JSONL parse
    df = pd.DataFrame(records)
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        cutoff = pd.Timestamp.now() - pd.Timedelta(minutes=time_range)
        df = df[df["timestamp"] >= cutoff]
    return df

df = load_logs()

if df.empty:
    st.warning("No data in logs.jsonl")
    st.stop()

# ─── Helper: SLO threshold line ─────────────────────────────────────────────
def add_slo_line(fig, slo_key, orientation="v", color="red"):
    val = SLO.get(slo_key)
    if val is None:
        return
    if orientation == "h":
        fig.add_hline(y=val, line_dash="dash", line_color=color, annotation_text=f"SLO: {val}")
    else:
        fig.add_vline(x=val, line_dash="dash", line_color=color, annotation_text=f"SLO: {val}")

# ─── Panel 1: Latency Percentiles ───────────────────────────────────────────
st.header("1. Latency Percentiles (ms)")
if "latency_ms" in df.columns:
    p50 = df["latency_ms"].quantile(0.50)
    p95 = df["latency_ms"].quantile(0.95)
    p99 = df["latency_ms"].quantile(0.99)
    col1, col2, col3 = st.columns(3)
    col1.metric("P50", f"{p50:.0f} ms")
    col2.metric("P95", f"{p95:.0f} ms", delta="⚠️" if p95 > SLO["latency_p95_ms"] else None)
    col3.metric("P99", f"{p99:.0f} ms")
    
    fig = px.histogram(df, x="latency_ms", nbins=50, title="Latency Distribution")
    add_slo_line(fig, "latency_p95_ms")
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("latency_ms field not found")

# ─── Panel 2: Traffic (Request Count/Rate) ───────────────────────────────────
st.header("2. Request Traffic")
if "timestamp" in df.columns and "event" in df.columns:
    req_df = df[df["event"] == "request_received"].copy()
    total_requests = len(req_df)
    rate_per_min = total_requests / time_range if time_range > 0 else 0
    st.metric("Total Requests (window)", total_requests)
    st.metric("Rate", f"{rate_per_min:.1f} req/min")
    
    req_by_time = req_df.set_index("timestamp").resample("1min").size().reset_index(name="count")
    fig = px.line(req_by_time, x="timestamp", y="count", title="Requests per Minute")
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("timestamp or event field not found")

# ─── Panel 3: Error Rate ─────────────────────────────────────────────────────
st.header("3. Error Rate %")
if "event" in df.columns:
    total_received = len(df[df["event"] == "request_received"]) if "request_received" in df["event"].values else 0
    total_failed = len(df[df["event"] == "request_failed"]) if "request_failed" in df["event"].values else 0
    # NOTE: error_rate_pct = (count request_failed / count request_received) * 100
    error_rate_pct = (total_failed / total_received * 100) if total_received > 0 else 0
    
    st.metric("Error Rate", f"{error_rate_pct:.2f}%", delta="⚠️ BREACH" if error_rate_pct > SLO["error_rate_pct"] else None)
    
    # Error breakdown
    error_df = df[df["event"] == "request_failed"]
    if "error_type" in df.columns and not error_df.empty:
        error_counts = error_df["error_type"].value_counts().reset_index()
        error_counts.columns = ["error_type", "count"]
        fig = px.pie(error_counts, values="count", names="error_type", title="Error Breakdown")
        st.plotly_chart(fig, use_container_width=True)
else:
    st.info("event field not found")

# ─── Panel 4: Cost Over Time ────────────────────────────────────────────────
st.header("4. Cost Over Time (USD)")
if "cost_usd" in df.columns:
    if "timestamp" in df.columns:
        df_with_cost = df[df["event"] == "response_sent"].copy()
        cost_by_time = df_with_cost.set_index("timestamp").resample("1min")["cost_usd"].sum().reset_index()
        fig = px.area(cost_by_time, x="timestamp", y="cost_usd", title="Cost per Minute")
        add_slo_line(fig, "daily_cost_usd", orientation="h")
        st.plotly_chart(fig, use_container_width=True)
    
    total_cost = df["cost_usd"].sum()
    st.metric("Total Cost (window)", f"${total_cost:.4f}")
else:
    st.info("cost_usd field not found")

# ─── Panel 5: Token Totals ──────────────────────────────────────────────────
st.header("5. Token Totals")
if "tokens_in" in df.columns and "tokens_out" in df.columns:
    tokens_in_total = df["tokens_in"].sum()
    tokens_out_total = df["tokens_out"].sum()
    col1, col2 = st.columns(2)
    col1.metric("Tokens In", f"{tokens_in_total:,}")
    col2.metric("Tokens Out", f"{tokens_out_total:,}")
    
    # Time series
    if "timestamp" in df.columns:
        token_by_time = df.set_index("timestamp").resample("1min")[["tokens_in", "tokens_out"]].sum().reset_index()
        fig = px.line(token_by_time, x="timestamp", y=["tokens_in", "tokens_out"], title="Tokens Over Time")
        st.plotly_chart(fig, use_container_width=True)
else:
    st.info("tokens_in or tokens_out field not found")

# ─── Panel 6: Quality Score Mean ─────────────────────────────────────────────
st.header("6. Quality Score (mean)")
if "quality_score" in df.columns:
    quality_mean = df["quality_score"].mean()
    st.metric("Quality Score Avg", f"{quality_mean:.3f}", delta="⚠️ BELOW SLO" if quality_mean < SLO["quality_score_avg"] else None)
    
    if "timestamp" in df.columns:
        quality_by_time = df.set_index("timestamp").resample("1min")["quality_score"].mean().reset_index()
        fig = px.line(quality_by_time, x="timestamp", y="quality_score", title="Quality Score Over Time")
        fig.add_hline(y=SLO["quality_score_avg"], line_dash="dash", line_color="red", annotation_text=f"SLO: {SLO['quality_score_avg']}")
        st.plotly_chart(fig, use_container_width=True)
else:
    st.info("quality_score field not found")

# ─── SLO Summary Table ───────────────────────────────────────────────────────
st.sidebar.header("SLO Status")
current = {
    "latency_p95_ms": df["latency_ms"].quantile(0.95) if "latency_ms" in df.columns else 0,
    "error_rate_pct": error_rate_pct if "event" in df.columns else 0,
    "daily_cost_usd": total_cost if "cost_usd" in df.columns else 0,
    "quality_score_avg": quality_mean if "quality_score" in df.columns else 0,
}
for key, target in SLO.items():
    val = current.get(key, 0)
    status = "✅" if (
        (key in ["latency_p95_ms", "error_rate_pct", "daily_cost_usd"] and val <= target) or
        (key == "quality_score_avg" and val >= target)
    ) else "❌"
    st.sidebar.write(f"{status} {key}: {val:.2f} / {target}")
```

**Run:**
```bash
streamlit run app/dashboard/main.py
```

---

## Metrics Addition Required

**File:** `app/metrics.py`

Add `error_rate_pct` to `snapshot()`:

```python
def snapshot() -> dict:
    total_failed = sum(ERRORS.values())
    # error_rate_pct = (count request_failed / count request_received) * 100
    error_rate_pct = round(total_failed / TRAFFIC * 100, 4) if TRAFFIC > 0 else 0.0
    return {
        # ... existing fields ...
        "error_rate_pct": error_rate_pct,
    }
```

Also track `request_received` count:

```python
TRAFFIC: int = 0  # counts request_received

def record_request(...) -> None:
    global TRAFFIC
    TRAFFIC += 1
    # ...

def record_error(error_type: str) -> None:
    ERRORS[error_type] += 1
```

---

## Auto-Refresh Option

Add to `app/dashboard/main.py` after imports:

```python
if "run_interval" not in st.session_state:
    import threading
    import time
    
    def auto_refresh():
        while True:
            time.sleep(REFRESH_SECONDS)
            st.rerun()
    
    t = threading.Thread(target=auto_refresh, daemon=True)
    t.start()
```

---

## Expected logs.jsonl Fields

| Field | Type | Events |
|-------|------|--------|
| timestamp | datetime | all |
| event | str | request_received, request_sent, request_failed |
| latency_ms | int | response_sent |
| cost_usd | float | response_sent |
| tokens_in | int | response_sent |
| tokens_out | int | response_sent |
| quality_score | float (0-1) | response_sent |
| error_type | str | request_failed |
