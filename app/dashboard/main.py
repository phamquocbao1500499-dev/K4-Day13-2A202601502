import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path
from datetime import datetime, timedelta

st.set_page_config(page_title="Day 13 AI Observability", layout="wide")
st.title("Day 13 AI Observability Dashboard")

DATA_FILE = Path(__file__).parent.parent.parent / "data" / "logs.jsonl"

SLO = {
    "latency_p95_ms": 3000,
    "error_rate_pct": 2.0,
    "daily_cost_usd": 2.5,
    "quality_score_avg": 0.75,
}

REFRESH_SECONDS = 30

st.sidebar.header("Settings")
time_range_min = st.sidebar.selectbox("Time range (minutes)", [30, 60, 120], index=1)
st.sidebar.caption(f"Auto-refresh: {REFRESH_SECONDS}s")


def load_logs():
    if not DATA_FILE.exists():
        return pd.DataFrame()
    records = []
    with open(DATA_FILE) as f:
        for line in f:
            line = line.strip()
            if line:
                import json as _json
                records.append(_json.loads(line))
    df = pd.DataFrame(records)
    if "ts" in df.columns:
        df["ts"] = pd.to_datetime(df["ts"], errors="coerce")
        cutoff = pd.Timestamp.now() - pd.Timedelta(minutes=time_range_min)
        df = df[df["ts"] >= cutoff]
    return df


df = load_logs()

if df.empty:
    st.warning("No data in logs.jsonl - run load test first")
    st.stop()

response_df = df[df["event"] == "response_sent"]
failed_df = df[df["event"] == "request_failed"]
received_df = df[df["event"] == "request_received"]

st.divider()
st.header("SLO Status")
cols = st.columns(4)
slo_checks = [
    ("Latency P95", response_df["latency_ms"].quantile(0.95) if "latency_ms" in response_df else 0, 3000, "ms", True),
    ("Error Rate", len(failed_df) / len(received_df) * 100 if len(received_df) > 0 else 0, 2, "%", True),
    ("Cost Total", response_df["cost_usd"].sum() if "cost_usd" in response_df else 0, 2.5, "USD", True),
    ("Quality Avg", response_df["quality_score"].mean() if "quality_score" in response_df else 0, 0.75, "", False),
]
for col, (name, val, target, unit, lower_is_better) in zip(cols, slo_checks):
    if unit:
        status = "✅" if (val <= target if lower_is_better else val >= target) else "❌"
        col.metric(f"{status} {name}", f"{val:.2f} {unit}", f"Target: {target}")
    else:
        status = "✅" if val >= target else "❌"
        col.metric(f"{status} {name}", f"{val:.3f}", f"Target: {target}")

st.divider()

c1, c2, c3 = st.columns(3)
with c1:
    st.header("1. Latency (ms)")
    if "latency_ms" in response_df:
        p50 = response_df["latency_ms"].quantile(0.50)
        p95 = response_df["latency_ms"].quantile(0.95)
        p99 = response_df["latency_ms"].quantile(0.99)
        st.metric("P50", f"{p50:.0f} ms")
        st.metric("P95", f"{p95:.0f} ms")
        st.metric("P99", f"{p99:.0f} ms")
        fig = px.histogram(response_df, x="latency_ms", nbins=30, title="Latency Distribution")
        fig.add_vline(x=SLO["latency_p95_ms"], line_dash="dash", line_color="red", annotation_text=f"SLO: {SLO['latency_p95_ms']}ms")
        st.plotly_chart(fig, use_container_width=True)

with c2:
    st.header("2. Traffic")
    total_req = len(received_df)
    rate = total_req / time_range_min if time_range_min > 0 else 0
    st.metric("Total Requests", total_req)
    st.metric("Rate", f"{rate:.1f} req/min")
    if "ts" in received_df and not received_df.empty:
        by_time = received_df.set_index("ts").resample("1min").size().reset_index(name="count")
        fig = px.line(by_time, x="ts", y="count", title="Requests per Minute")
        st.plotly_chart(fig, use_container_width=True)

with c3:
    st.header("3. Error Rate")
    total_failed = len(failed_df)
    total_received = len(received_df)
    error_rate = total_failed / total_received * 100 if total_received > 0 else 0
    st.metric("Error Rate", f"{error_rate:.2f}%", delta="⚠️ BREACH" if error_rate > SLO["error_rate_pct"] else None)
    if "error_type" in failed_df and not failed_df.empty:
        counts = failed_df["error_type"].value_counts().reset_index()
        counts.columns = ["error_type", "count"]
        fig = px.pie(counts, values="count", names="error_type", title="Error Breakdown")
        st.plotly_chart(fig, use_container_width=True)

c4, c5, c6 = st.columns(3)
with c4:
    st.header("4. Cost (USD)")
    if "cost_usd" in response_df:
        total_cost = response_df["cost_usd"].sum()
        st.metric("Total Cost", f"${total_cost:.4f}")
        if "ts" in response_df and not response_df.empty:
            by_time = response_df.set_index("ts").resample("1min")["cost_usd"].sum().reset_index()
            fig = px.area(by_time, x="ts", y="cost_usd", title="Cost per Minute")
            fig.add_hline(y=SLO["daily_cost_usd"], line_dash="dash", line_color="red")
            st.plotly_chart(fig, use_container_width=True)

with c5:
    st.header("5. Tokens")
    if "tokens_in" in response_df and "tokens_out" in response_df:
        st.metric("Tokens In", f"{response_df['tokens_in'].sum():,}")
        st.metric("Tokens Out", f"{response_df['tokens_out'].sum():,}")
        if "ts" in response_df and not response_df.empty:
            by_time = response_df.set_index("ts").resample("1min")[["tokens_in", "tokens_out"]].sum().reset_index()
            fig = px.line(by_time, x="ts", y=["tokens_in", "tokens_out"], title="Tokens Over Time")
            st.plotly_chart(fig, use_container_width=True)

with c6:
    st.header("6. Quality Score")
    if "quality_score" in response_df:
        quality_mean = response_df["quality_score"].mean()
        st.metric("Avg Quality", f"{quality_mean:.3f}", delta="⚠️ BELOW SLO" if quality_mean < SLO["quality_score_avg"] else None)
        if "ts" in response_df and not response_df.empty:
            by_time = response_df.set_index("ts").resample("1min")["quality_score"].mean().reset_index()
            fig = px.line(by_time, x="ts", y="quality_score", title="Quality Over Time")
            fig.add_hline(y=SLO["quality_score_avg"], line_dash="dash", line_color="red", annotation_text=f"SLO: {SLO['quality_score_avg']}")
            st.plotly_chart(fig, use_container_width=True)

st.caption(f"Last updated: {datetime.now().strftime('%H:%M:%S')} | Source: {DATA_FILE}")
