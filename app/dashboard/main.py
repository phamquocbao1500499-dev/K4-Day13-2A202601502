"""
Day 13 AI Observability Dashboard — Demo Edition
================================================
Bố cục bám đúng "Kịch bản demo cuối giờ" (index.html), 5–7 phút / nhóm:

    GATE  — Điều kiện "demo đạt": validate_logs >= 80/100 · dashboard 6/6 panel · traces >= 10
    01    — API hoạt động         (health, correlation ID, latency/token/cost/quality)
    02    — Logging & bảo mật     (log JSON, correlation ID chung, PII redaction)
    03    — Dashboard             (6 panel theo contract + baseline + SLO threshold)
    04    — Langfuse              (traces, drill-down một trace, prompt v1/v2)
    05    — Demo một incident     (Metric -> Trace -> Log -> Root cause -> Fix -> Prevention)
    06    — Kết quả kiểm tra      (validators + pytest chạy thật)

Nguồn dữ liệu: data/logs.jsonl · Contract: config/dashboard.yaml · SLO: config/slo.yaml

Chạy:  streamlit run app/dashboard/main.py

Author: Metrics & Dashboard Engineer (Member C)
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yaml

# ═══════════════════════════════════════════════════════════════════════════════
# PATHS & CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

DATA_FILE = REPO_ROOT / "data" / "logs.jsonl"
DASHBOARD_CONTRACT = REPO_ROOT / "config" / "dashboard.yaml"
SLO_CONFIG = REPO_ROOT / "config" / "slo.yaml"
ALERT_CONFIG = REPO_ROOT / "config" / "alert_rules.yaml"

# Ngưỡng của mục "Điều kiện demo đạt" trong kịch bản demo.
PASS_LOG_SCORE = 80
PASS_PANEL_COUNT = 6
PASS_TRACE_COUNT = 10

# Palette đồng bộ với trang kịch bản demo (index.html).
C_CYAN, C_BLUE, C_VIOLET = "#5ce1e6", "#61a8ff", "#9b7bff"
C_GREEN, C_YELLOW, C_RED = "#56df9b", "#ffc95c", "#ff667a"
C_MUTED = "#9db0c7"

VIEWS = [
    "🏁 Toàn cảnh (evidence)",
    "01 · API hoạt động",
    "02 · Logging & bảo mật",
    "03 · Dashboard 6 panel",
    "04 · Langfuse & prompt",
    "05 · Demo một incident",
    "06 · Kết quả kiểm tra",
]

# ═══════════════════════════════════════════════════════════════════════════════
# PAGE CONFIG  (phải là lệnh Streamlit đầu tiên)
# ═══════════════════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="Day 13 Observability — Demo",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
<style>
    :root{
        --bg:#07111f; --card:#0f1c2e; --card-2:#13243a;
        --line:rgba(255,255,255,.10); --text:#f7f9fc; --muted:#9db0c7;
        --cyan:#5ce1e6; --blue:#61a8ff; --violet:#9b7bff;
        --green:#56df9b; --yellow:#ffc95c; --red:#ff667a;
    }
    .stApp{
        background:
            radial-gradient(circle at 8% 0%, rgba(92,225,230,.10), transparent 26%),
            radial-gradient(circle at 92% 6%, rgba(155,123,255,.11), transparent 30%),
            linear-gradient(180deg,#06101c 0%,#091625 45%,#07111f 100%);
        color:var(--text);
    }
    section[data-testid="stSidebar"]{ background:#08131f; border-right:1px solid var(--line); }

    .ctx-bar{
        display:flex; flex-wrap:wrap; gap:8px; align-items:center;
        padding:10px 14px; margin:2px 0 14px;
        border:1px solid var(--line); border-radius:14px;
        background:rgba(255,255,255,.035);
    }
    .ctx-bar .chip{
        padding:5px 10px; border-radius:9px; font-size:12.5px; font-weight:700;
        border:1px solid var(--line); background:rgba(255,255,255,.045); color:#dbe7f4;
    }
    .ctx-bar .chip b{ color:#fff; }

    .gate{
        padding:16px 18px; border-radius:18px; border:1px solid var(--line);
        background:linear-gradient(180deg, rgba(15,28,46,.92), rgba(11,24,40,.88));
        height:100%;
    }
    .gate .label{
        color:var(--muted); font-size:11.5px; font-weight:800;
        letter-spacing:.09em; text-transform:uppercase;
    }
    .gate .big{ margin:7px 0 2px; font-size:31px; font-weight:900; letter-spacing:-.03em; line-height:1; }
    .gate .desc{ color:#c9d6e3; font-size:12.5px; }
    .gate.pass{ border-color:rgba(86,223,155,.42); }
    .gate.fail{ border-color:rgba(255,102,122,.48); }

    .step{
        padding:15px 16px; border-radius:15px; border:1px solid var(--line);
        background:rgba(255,255,255,.035); height:100%;
    }
    .step small{
        color:#83a2bd; font-weight:800; font-size:10px;
        letter-spacing:.09em; text-transform:uppercase;
    }
    .step .title{ font-size:14.5px; font-weight:800; margin:5px 0 7px; }
    .step .body{ color:#cddaeb; font-size:12.5px; line-height:1.5; }
    .step .body code{ font-size:11.5px; }

    .panel-title{
        display:flex; align-items:baseline; gap:10px; flex-wrap:wrap;
        margin:0 0 2px;
    }
    .panel-title .pid{
        font:800 10.5px "SFMono-Regular",Consolas,monospace; letter-spacing:.1em;
        text-transform:uppercase; color:var(--cyan);
        border:1px solid rgba(92,225,230,.28); background:rgba(92,225,230,.08);
        padding:2px 7px; border-radius:6px;
    }
    .panel-title h4{ margin:0; font-size:16.5px; letter-spacing:-.01em; }
    .panel-meta{ color:var(--muted); font-size:11.5px; margin:0 0 10px; }
    .panel-meta b{ color:#dbe7f4; }

    .verdict-ok{ color:var(--green); font-weight:800; }
    .verdict-bad{ color:var(--red); font-weight:800; }
    .verdict-warn{ color:var(--yellow); font-weight:800; }

    .lede{ color:var(--muted); font-size:13.5px; margin:-6px 0 14px; }

    code{
        color:#b9f7f8; background:rgba(92,225,230,.08);
        border:1px solid rgba(255,255,255,.08); border-radius:6px; padding:1px 5px;
    }
    hr{ border-color:var(--line); }
</style>
""",
    unsafe_allow_html=True,
)


# ═══════════════════════════════════════════════════════════════════════════════
# CONFIG LOADERS — dashboard đọc thẳng từ contract để ảnh chụp luôn khớp validator
# ═══════════════════════════════════════════════════════════════════════════════


@st.cache_data(show_spinner=False)
def load_contract() -> dict:
    """Đọc config/dashboard.yaml: đây là contract chấm điểm 6 panel."""
    if not DASHBOARD_CONTRACT.exists():
        return {}
    payload = yaml.safe_load(DASHBOARD_CONTRACT.read_text(encoding="utf-8")) or {}
    dashboard = payload.get("dashboard", {})
    dashboard["panels_by_id"] = {p["id"]: p for p in dashboard.get("panels", []) if "id" in p}
    return dashboard


@st.cache_data(show_spinner=False)
def load_slo() -> dict:
    """Objective của từng SLI trong config/slo.yaml."""
    if not SLO_CONFIG.exists():
        return {"latency_p95_ms": 3000, "error_rate_pct": 2.0, "daily_cost_usd": 2.5, "quality_score_avg": 0.75}
    config = yaml.safe_load(SLO_CONFIG.read_text(encoding="utf-8")) or {}
    return {key: values["objective"] for key, values in config.get("slis", {}).items()}


@st.cache_data(show_spinner=False)
def load_alerts() -> list[dict]:
    if not ALERT_CONFIG.exists():
        return []
    config = yaml.safe_load(ALERT_CONFIG.read_text(encoding="utf-8")) or {}
    return config.get("alerts", [])


@st.cache_data(show_spinner=False)
def load_pii_detectors() -> dict:
    """
    Nạp đúng bộ regex mà scripts/validate_logs.py dùng để chấm điểm.

    Dashboard soi PII bằng chính detector của grader, không dùng bản sao riêng,
    nên con số "PII leak" trên màn hình luôn khớp điểm validator.
    """
    spec = importlib.util.spec_from_file_location(
        "_grader_validate_logs", REPO_ROOT / "scripts" / "validate_logs.py"
    )
    if spec is None or spec.loader is None:
        return {}
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return dict(getattr(module, "PII_DETECTORS", {}))


CONTRACT = load_contract()
PANELS = CONTRACT.get("panels_by_id", {})
SLO = load_slo()
ALERTS = load_alerts()
CONTRACT_RANGE_MIN = int(CONTRACT.get("time_range_minutes", 60))
CONTRACT_REFRESH_S = int(CONTRACT.get("refresh_seconds", 30))


def panel_threshold(panel_id: str) -> tuple[str, str, float] | None:
    """(aggregation, operator, value) của threshold trong contract."""
    threshold = PANELS.get(panel_id, {}).get("threshold")
    if not isinstance(threshold, dict):
        return None
    return threshold.get("aggregation", ""), threshold.get("operator", ""), threshold.get("value", 0)


def panel_header(panel_id: str, fallback_title: str, extra: str = "") -> None:
    """Header hiển thị tên panel + đơn vị + threshold — bắt buộc có trong ảnh evidence."""
    panel = PANELS.get(panel_id, {})
    title = panel.get("title", fallback_title)
    unit = panel.get("unit", "—")
    threshold = panel_threshold(panel_id)
    op_text = {"lte": "≤", "gte": "≥"}
    if threshold:
        aggregation, operator, value = threshold
        threshold_text = f"threshold <b>{aggregation} {op_text.get(operator, operator)} {value}</b>"
    else:
        threshold_text = "threshold <b>—</b>"

    st.markdown(
        f"""
        <div class="panel-title">
            <span class="pid">{panel_id}</span><h4>{title}</h4>
        </div>
        <div class="panel-meta">unit <b>{unit}</b> · {threshold_text}{(" · " + extra) if extra else ""}</div>
        """,
        unsafe_allow_html=True,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# DATA LOADING
# ═══════════════════════════════════════════════════════════════════════════════


@st.cache_data(ttl=CONTRACT_REFRESH_S, show_spinner=False)
def load_logs() -> tuple[pd.DataFrame, list[str], int]:
    """
    Đọc toàn bộ data/logs.jsonl.

    Trả về (DataFrame, danh sách dòng JSON thô, số dòng hỏng) — dòng thô giữ lại
    để phần 02 show đúng log JSON gốc thay vì bản đã qua pandas.
    """
    if not DATA_FILE.exists():
        return pd.DataFrame(), [], 0

    records: list[dict] = []
    raw_lines: list[str] = []
    malformed = 0
    for line in DATA_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
            raw_lines.append(line)
        except json.JSONDecodeError:
            malformed += 1

    if not records:
        return pd.DataFrame(), raw_lines, malformed

    df = pd.DataFrame(records)
    if "ts" in df.columns:
        df["ts"] = pd.to_datetime(df["ts"], errors="coerce", utc=True)
        df = df.sort_values("ts").reset_index(drop=True)
    return df, raw_lines, malformed


def event_subset(df: pd.DataFrame, event: str) -> pd.DataFrame:
    if df.empty or "event" not in df.columns:
        return pd.DataFrame()
    return df[df["event"] == event]


def payload_field(df: pd.DataFrame, key: str) -> pd.Series:
    if df.empty or "payload" not in df.columns:
        return pd.Series(dtype="object")
    return df["payload"].apply(lambda p: p.get(key) if isinstance(p, dict) else None)


def numeric(df: pd.DataFrame, column: str) -> pd.Series:
    """Cột số an toàn: trả Series rỗng khi thiếu cột hoặc DataFrame rỗng."""
    if df.empty or column not in df.columns:
        return pd.Series(dtype="float64")
    return pd.to_numeric(df[column], errors="coerce").dropna()


def compute_metrics(df: pd.DataFrame) -> dict:
    """Tính đúng 6 nhóm chỉ số của contract từ một cửa sổ dữ liệu."""
    responses = event_subset(df, "response_sent")
    received = event_subset(df, "request_received")
    failed = event_subset(df, "request_failed")

    latency = numeric(responses, "latency_ms")
    cost = numeric(responses, "cost_usd")
    quality = numeric(responses, "quality_score")

    return {
        "responses": responses,
        "received": received,
        "failed": failed,
        "count_received": len(received),
        "count_responses": len(responses),
        "count_failed": len(failed),
        "latency_p50": float(latency.quantile(0.50)) if not latency.empty else 0.0,
        "latency_p95": float(latency.quantile(0.95)) if not latency.empty else 0.0,
        "latency_p99": float(latency.quantile(0.99)) if not latency.empty else 0.0,
        "latency_max": float(latency.max()) if not latency.empty else 0.0,
        "error_rate_pct": (len(failed) / len(received) * 100) if len(received) else 0.0,
        "total_cost_usd": float(cost.sum()) if not cost.empty else 0.0,
        "avg_cost_usd": float(cost.mean()) if not cost.empty else 0.0,
        "tokens_in": int(numeric(responses, "tokens_in").sum()),
        "tokens_out": int(numeric(responses, "tokens_out").sum()),
        "quality_avg": float(quality.mean()) if not quality.empty else 0.0,
        "quality_min": float(quality.min()) if not quality.empty else 0.0,
    }


def unique_correlation_ids(df: pd.DataFrame) -> list[str]:
    if df.empty or "correlation_id" not in df.columns:
        return []
    ids = df["correlation_id"].dropna()
    ids = ids[ids != "MISSING"]
    return sorted(ids.unique().tolist())


# ═══════════════════════════════════════════════════════════════════════════════
# VALIDATORS — chạy đúng script chấm điểm, không mô phỏng lại
# ═══════════════════════════════════════════════════════════════════════════════


@st.cache_data(ttl=CONTRACT_REFRESH_S, show_spinner=False)
def run_script(rel_path: str, args: tuple[str, ...] = ()) -> tuple[int, str]:
    """Chạy một script trong repo và trả (exit code, output hợp nhất stdout+stderr)."""
    try:
        proc = subprocess.run(
            [sys.executable, str(REPO_ROOT / rel_path), *args],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=180,
        )
    except Exception as exc:  # script lỗi không được làm sập dashboard giữa lúc demo
        return 1, f"Không chạy được {rel_path}: {type(exc).__name__}: {exc}"
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


@st.cache_data(ttl=CONTRACT_REFRESH_S, show_spinner=False)
def run_pytest() -> tuple[int, str]:
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "-q"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,
        )
    except Exception as exc:
        return 1, f"Không chạy được pytest: {type(exc).__name__}: {exc}"
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def parse_log_score(output: str) -> int | None:
    match = re.search(r"Estimated Score:\s*(\d+)\s*/\s*100", output)
    return int(match.group(1)) if match else None


def parse_panel_count(output: str) -> int | None:
    match = re.search(r"(\d+)\s*/\s*6\s*panel", output)
    return int(match.group(1)) if match else None


# ═══════════════════════════════════════════════════════════════════════════════
# INCIDENT DETECTION — dựng cửa sổ baseline vs incident từ chính log
# ═══════════════════════════════════════════════════════════════════════════════

INCIDENT_KB = {
    "rag_slow": {
        "panel": "latency",
        "signal": "P95 latency tăng vọt trong khi traffic và error rate gần như không đổi.",
        "root_cause": (
            "`app/mock_rag.py::retrieve()` chèn `time.sleep(2.5)` mỗi lần gọi khi "
            "`STATE['rag_slow'] = True` — toàn bộ luồng agent bị giữ lại ở bước retrieval."
        ),
        "fix": [
            "Tắt incident ngay: `POST /incidents/rag_slow/disable`.",
            "Đặt timeout cho `retrieve()` và trả fallback khi quá hạn.",
            "Bọc retrieval bằng circuit breaker để không kéo theo cả request.",
        ],
        "prevent": [
            "Alert `high_latency_p95` (P95 > 3000ms trong 5m) đã có trong `config/alert_rules.yaml`.",
            "Synthetic health check định kỳ riêng cho RAG retrieval.",
            "Giữ span riêng `as_type=\"retriever\"` để khoanh vùng nghẽn trong một lần mở trace.",
        ],
    },
    "tool_fail": {
        "panel": "errors",
        "signal": "Error rate vượt SLO, `error_type` dồn vào một loại lỗi duy nhất.",
        "root_cause": (
            "`app/mock_rag.py::retrieve()` raise `RuntimeError(\"Vector store timeout\")` khi "
            "`STATE['tool_fail'] = True` — request fail trước khi kịp gọi LLM."
        ),
        "fix": [
            "Tắt incident: `POST /incidents/tool_fail/disable`.",
            "Thêm retry có backoff cho tool call, giới hạn số lần thử.",
            "Trả degraded answer thay vì 500 khi vector store không phản hồi.",
        ],
        "prevent": [
            "Alert `elevated_error_rate` (error rate > 2% trong 3m).",
            "Dependency health check cho vector store trước khi nhận traffic.",
            "Gắn `error_type` vào log để breakdown chỉ ra ngay tool nào hỏng.",
        ],
    },
    "cost_spike": {
        "panel": "cost",
        "signal": "Cost và tokens_out tăng đột biến, latency gần như giữ nguyên.",
        "root_cause": (
            "`app/mock_llm.py::generate()` nhân `output_tokens *= 4` khi "
            "`STATE['cost_spike'] = True` — mỗi response tốn gấp bốn lần token đầu ra."
        ),
        "fix": [
            "Tắt incident: `POST /incidents/cost_spike/disable`.",
            "Áp `max_tokens` cho response và cắt ngữ cảnh thừa.",
            "Chặn theo budget khi cost tích luỹ chạm ngưỡng ngày.",
        ],
        "prevent": [
            "Alert `cost_budget_exceeded` (cost 24h > 2.5 USD trong 5m).",
            "Theo dõi cost/request thay vì chỉ tổng cost để bắt sớm bất thường.",
            "Cảnh báo khi tỉ lệ tokens_out/tokens_in lệch khỏi baseline.",
        ],
    },
}


def incident_windows(df: pd.DataFrame) -> list[dict]:
    """
    Ghép cặp incident_enabled -> incident_disabled thành các cửa sổ thời gian.

    Cửa sổ chưa đóng (chỉ có enable) kéo tới bản ghi cuối cùng — đúng với trạng
    thái "incident vẫn đang bật" khi nhóm demo trực tiếp.
    """
    if df.empty or "event" not in df.columns or "ts" not in df.columns:
        return []

    control = df[df["event"].isin(["incident_enabled", "incident_disabled"])].copy()
    if control.empty:
        return []
    control["name"] = payload_field(control, "name")
    last_ts = df["ts"].max()

    windows: list[dict] = []
    open_by_name: dict[str, pd.Timestamp] = {}
    for _, row in control.sort_values("ts").iterrows():
        name, ts = row["name"], row["ts"]
        if not name or pd.isna(ts):
            continue
        if row["event"] == "incident_enabled":
            open_by_name.setdefault(name, ts)
        else:
            start = open_by_name.pop(name, None)
            if start is not None:
                windows.append({"name": name, "start": start, "end": ts, "closed": True})
    for name, start in open_by_name.items():
        windows.append({"name": name, "start": start, "end": last_ts, "closed": False})

    return sorted(windows, key=lambda w: w["start"])


def split_by_incident(df: pd.DataFrame, windows: list[dict]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Tách dữ liệu thành (baseline, trong incident) để so sánh trực tiếp."""
    if df.empty or "ts" not in df.columns or not windows:
        return df, pd.DataFrame()
    inside = pd.Series(False, index=df.index)
    for window in windows:
        inside |= (df["ts"] >= window["start"]) & (df["ts"] <= window["end"])
    return df[~inside], df[inside]


# ═══════════════════════════════════════════════════════════════════════════════
# CHART HELPERS
# ═══════════════════════════════════════════════════════════════════════════════


def style_figure(fig: go.Figure, height: int = 270, ytitle: str = "") -> go.Figure:
    fig.update_layout(
        template="plotly_dark",
        height=height,
        margin=dict(l=10, r=10, t=30, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="right", x=1),
        hovermode="x unified",
        yaxis_title=ytitle,
        font=dict(size=12),
    )
    return fig


def threshold_line(fig: go.Figure, value: float, text: str, color: str = C_RED) -> None:
    fig.add_hline(y=value, line_dash="dash", line_color=color, annotation_text=text,
                  annotation_position="top left", annotation_font_color=color)


def mark_incidents(fig: go.Figure, windows: list[dict]) -> None:
    """Tô vùng thời gian có incident lên mọi biểu đồ theo thời gian."""
    for window in windows:
        fig.add_vrect(
            x0=window["start"], x1=window["end"],
            fillcolor=C_RED, opacity=0.13, line_width=0,
            annotation_text=window["name"], annotation_position="top left",
            annotation_font_color=C_RED, annotation_font_size=10,
        )


def verdict_html(ok: bool, ok_text: str, bad_text: str) -> str:
    css = "verdict-ok" if ok else "verdict-bad"
    return f'<span class="{css}">{ok_text if ok else bad_text}</span>'


def gate_card(label: str, value: str, desc: str, passed: bool) -> str:
    color = C_GREEN if passed else C_RED
    icon = "✅ ĐẠT" if passed else "❌ CHƯA ĐẠT"
    return f"""
    <div class="gate {'pass' if passed else 'fail'}">
        <div class="label">{label}</div>
        <div class="big" style="color:{color};">{value}</div>
        <div class="desc">{desc}</div>
        <div style="margin-top:9px;font-size:12.5px;font-weight:800;color:{color};">{icon}</div>
    </div>
    """


def step_card(step_no: str, title: str, body: str) -> str:
    return f"""
    <div class="step">
        <small>Bước {step_no}</small>
        <div class="title">{title}</div>
        <div class="body">{body}</div>
    </div>
    """


# ═══════════════════════════════════════════════════════════════════════════════
# LOAD DATA
# ═══════════════════════════════════════════════════════════════════════════════

df_all, raw_lines, malformed_lines = load_logs()

# ═══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ═══════════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown("## 🎬 Kịch bản demo")
    view = st.radio("Phần đang trình bày", VIEWS, index=0, label_visibility="collapsed")

    st.divider()
    st.markdown("### 🕒 Cửa sổ dữ liệu")

    range_options = {
        f"{CONTRACT_RANGE_MIN} phút (contract)": CONTRACT_RANGE_MIN,
        "30 phút": 30,
        "2 giờ": 120,
        "24 giờ": 1440,
        "Toàn bộ dữ liệu": None,
    }
    range_label = st.selectbox("Khoảng thời gian", list(range_options), index=0)
    range_minutes = range_options[range_label]

    anchor_to_data = st.toggle(
        "Neo theo log mới nhất",
        value=True,
        help=(
            "Bật: cửa sổ tính lùi từ bản ghi log mới nhất — demo không bị trống khi log "
            "được sinh từ trước. Tắt: tính lùi từ đồng hồ thực."
        ),
    )

    st.divider()
    st.markdown("### 🔄 Làm mới")
    st.caption(f"Cache dữ liệu {CONTRACT_REFRESH_S}s theo contract.")
    if st.button("Làm mới ngay", width="stretch"):
        st.cache_data.clear()
        st.rerun()

    st.divider()
    st.markdown("### 📌 Contract")
    st.caption(
        f"Nguồn: `data/logs.jsonl`\n\n"
        f"Panels: {len(PANELS)}/6 · Range: {CONTRACT_RANGE_MIN}m · Refresh: {CONTRACT_REFRESH_S}s"
    )
    langfuse_host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
    st.caption(f"Langfuse: {langfuse_host}")

# ─── Áp cửa sổ thời gian ──────────────────────────────────────────────────────

if df_all.empty or "ts" not in df_all.columns:
    df_window = df_all
    anchor_ts = None
    cutoff_ts = None
else:
    anchor_ts = df_all["ts"].max() if anchor_to_data else pd.Timestamp.now(tz="UTC")
    if range_minutes is None:
        df_window = df_all
        cutoff_ts = df_all["ts"].min()
    else:
        cutoff_ts = anchor_ts - pd.Timedelta(minutes=range_minutes)
        df_window = df_all[df_all["ts"] >= cutoff_ts].copy()

metrics = compute_metrics(df_window)
windows_all = incident_windows(df_all)
windows_view = [w for w in windows_all if cutoff_ts is None or w["end"] >= cutoff_ts]
trace_ids_all = unique_correlation_ids(df_all)

# ─── Kết quả validator (chạy thật) ────────────────────────────────────────────

log_rc, log_out = run_script("scripts/validate_logs.py")
dash_rc, dash_out = run_script("scripts/validate_dashboard.py")
log_score = parse_log_score(log_out)
panel_count = parse_panel_count(dash_out)

pass_logs = log_score is not None and log_score >= PASS_LOG_SCORE
pass_panels = panel_count == PASS_PANEL_COUNT and dash_rc == 0
pass_traces = len(trace_ids_all) >= PASS_TRACE_COUNT
demo_ready = pass_logs and pass_panels and pass_traces

# ═══════════════════════════════════════════════════════════════════════════════
# HEADER + CONTEXT BAR (luôn hiển thị — ảnh evidence phải đọc được các thông số này)
# ═══════════════════════════════════════════════════════════════════════════════

head_left, head_right = st.columns([3, 1])
with head_left:
    st.markdown(
        f"# 📊 {CONTRACT.get('title', 'Day 13 AI Observability')}"
        f"\n<div class='lede'>Observe → Explain → Fix → Prevent · service "
        f"<code>{os.getenv('APP_NAME', 'day13-observability-lab')}</code></div>",
        unsafe_allow_html=True,
    )
with head_right:
    color = C_GREEN if demo_ready else C_YELLOW
    text = "DEMO SẴN SÀNG" if demo_ready else "CHƯA ĐỦ ĐIỀU KIỆN"
    st.markdown(
        f"<div style='text-align:right;padding-top:18px;'>"
        f"<span style='color:{color};font-weight:900;font-size:15px;'>{text}</span><br>"
        f"<span style='color:{C_MUTED};font-size:12px;'>Cập nhật {datetime.now().strftime('%H:%M:%S')}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )

anchor_text = (
    f"{anchor_ts.strftime('%Y-%m-%d %H:%M:%SZ')}" if anchor_ts is not None else "—"
)
st.markdown(
    f"""
    <div class="ctx-bar">
        <span class="chip">Nguồn <b>data/logs.jsonl</b></span>
        <span class="chip">Time range <b>{range_label}</b></span>
        <span class="chip">Neo <b>{'log mới nhất' if anchor_to_data else 'đồng hồ thực'}</b> · {anchor_text}</span>
        <span class="chip">Refresh <b>{CONTRACT_REFRESH_S}s</b></span>
        <span class="chip">Bản ghi <b>{len(df_window)}</b>/{len(df_all)}</span>
        <span class="chip">Traces <b>{len(trace_ids_all)}</b></span>
        <span class="chip">SLO P95 <b>≤ {SLO.get('latency_p95_ms', 3000):.0f}ms</b></span>
        <span class="chip">SLO error <b>≤ {SLO.get('error_rate_pct', 2):.0f}%</b></span>
    </div>
    """,
    unsafe_allow_html=True,
)

if df_all.empty:
    st.error(
        "Chưa có dữ liệu trong `data/logs.jsonl`. Chạy API rồi sinh log:\n\n"
        "```\nuvicorn app.main:app --reload\npython scripts/load_test.py --concurrency 5\n```"
    )
    st.stop()

if df_window.empty:
    st.warning(
        "Cửa sổ thời gian đang chọn không có bản ghi nào. Bật **Neo theo log mới nhất** "
        "hoặc chọn **Toàn bộ dữ liệu** trong sidebar."
    )

# ═══════════════════════════════════════════════════════════════════════════════
# GATE — ĐIỀU KIỆN "DEMO ĐẠT" (3 checkpoint cuối của kịch bản)
# ═══════════════════════════════════════════════════════════════════════════════


def render_gate() -> None:
    st.markdown("### 🎯 Điều kiện “demo đạt”")
    st.markdown(
        "<div class='lede'>Ba checkpoint tự xác nhận trước khi lên trình bày — "
        "số liệu lấy trực tiếp từ validator, không nhập tay.</div>",
        unsafe_allow_html=True,
    )
    gate_cols = st.columns(3)
    with gate_cols[0]:
        st.markdown(
            gate_card(
                "Logging validation",
                f"{log_score if log_score is not None else '—'}/100",
                f"<code>validate_logs.py</code> · yêu cầu ≥ {PASS_LOG_SCORE}/100",
                pass_logs,
            ),
            unsafe_allow_html=True,
        )
    with gate_cols[1]:
        st.markdown(
            gate_card(
                "Dashboard validation",
                f"{panel_count if panel_count is not None else '—'} / 6",
                "Đủ latency · traffic · error · cost · token · quality",
                pass_panels,
            ),
            unsafe_allow_html=True,
        )
    with gate_cols[2]:
        st.markdown(
            gate_card(
                "Tracing evidence",
                f"{len(trace_ids_all)}",
                f"Correlation ID duy nhất trong log · yêu cầu ≥ {PASS_TRACE_COUNT}",
                pass_traces,
            ),
            unsafe_allow_html=True,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 6 PANEL THEO CONTRACT
# ═══════════════════════════════════════════════════════════════════════════════


def panel_latency(container, data: dict, windows: list[dict]) -> None:
    with container:
        p95 = data["latency_p95"]
        target = SLO.get("latency_p95_ms", 3000)
        breach = p95 > target
        panel_header("latency", "Latency percentiles",
                     verdict_html(not breach, "P95 trong ngưỡng", "P95 vượt SLO"))

        cols = st.columns(3)
        cols[0].metric("P50", f"{data['latency_p50']:.0f} ms")
        cols[1].metric("P95", f"{p95:.0f} ms", f"{p95 - target:+.0f} ms so với SLO",
                       delta_color="inverse")
        cols[2].metric("P99", f"{data['latency_p99']:.0f} ms")

        responses = data["responses"]
        if responses.empty or "ts" not in responses.columns:
            st.caption("Chưa có `response_sent` để vẽ latency.")
            return

        series = responses.set_index("ts")["latency_ms"].astype(float)
        by_min = series.resample("1min")
        frame = pd.DataFrame(
            {
                "p50": by_min.quantile(0.50),
                "p95": by_min.quantile(0.95),
                "p99": by_min.quantile(0.99),
            }
        ).dropna(how="all").reset_index()

        fig = go.Figure()
        for name, color in (("p50", C_BLUE), ("p95", C_VIOLET), ("p99", C_YELLOW)):
            fig.add_trace(go.Scatter(x=frame["ts"], y=frame[name], name=name.upper(),
                                     mode="lines+markers", line=dict(color=color, width=2)))
        threshold_line(fig, target, f"SLO P95 ≤ {target:.0f}ms")
        mark_incidents(fig, windows)
        st.plotly_chart(style_figure(fig, ytitle="ms"), width="stretch")


def panel_traffic(container, data: dict, windows: list[dict]) -> None:
    with container:
        received = data["received"]
        span_min = max(range_minutes or CONTRACT_RANGE_MIN, 1)
        rate = data["count_received"] / span_min
        panel_header("traffic", "Request traffic")

        cols = st.columns(3)
        cols[0].metric("Requests", f"{data['count_received']:,}")
        cols[1].metric("Rate", f"{rate:.2f} req/min")
        success = (data["count_responses"] / data["count_received"] * 100) if data["count_received"] else 0.0
        cols[2].metric("Success rate", f"{success:.1f} %")

        if received.empty or "ts" not in received.columns:
            st.caption("Chưa có `request_received` để vẽ traffic.")
            return

        by_min = received.set_index("ts").resample("1min").size().reset_index(name="requests")
        fig = go.Figure()
        fig.add_trace(go.Bar(x=by_min["ts"], y=by_min["requests"], name="Requests",
                             marker_color=C_BLUE, opacity=0.75))
        mark_incidents(fig, windows)
        st.plotly_chart(style_figure(fig, ytitle="req / phút"), width="stretch")


def panel_errors(container, data: dict, windows: list[dict]) -> None:
    with container:
        error_rate = data["error_rate_pct"]
        target = SLO.get("error_rate_pct", 2)
        breach = error_rate > target
        panel_header("errors", "Error rate and breakdown",
                     verdict_html(not breach, "Trong ngưỡng", "Vượt SLO"))

        cols = st.columns(3)
        cols[0].metric("Error rate", f"{error_rate:.2f} %", f"SLO ≤ {target}%")
        cols[1].metric("Failed", f"{data['count_failed']:,}")
        cols[2].metric("Received", f"{data['count_received']:,}")

        failed = data["failed"]
        if failed.empty:
            st.success(f"0 request lỗi trong cửa sổ — error_rate_pct = {error_rate:.2f}%.")
            st.caption("Công thức: `count(request_failed) / count(request_received) * 100`")
            return

        if "error_type" in failed.columns:
            breakdown = failed["error_type"].value_counts()
            fig = go.Figure(
                go.Bar(x=breakdown.values, y=breakdown.index, orientation="h",
                       marker_color=C_RED)
            )
            st.plotly_chart(style_figure(fig, height=220, ytitle=""), width="stretch")
        else:
            st.caption("Log lỗi chưa có trường `error_type` để breakdown.")


def panel_cost(container, data: dict, windows: list[dict]) -> None:
    with container:
        total = data["total_cost_usd"]
        budget = SLO.get("daily_cost_usd", 2.5)
        breach = total > budget
        panel_header("cost", "Cost over time",
                     verdict_html(not breach, "Trong budget", "Vượt budget"))

        cols = st.columns(3)
        cols[0].metric("Tổng cost", f"${total:.4f}", f"Budget ${budget:.2f}")
        cols[1].metric("Cost / request", f"${data['avg_cost_usd']:.5f}")
        cols[2].metric("Budget đã dùng", f"{(total / budget * 100) if budget else 0:.1f} %")

        responses = data["responses"]
        if responses.empty or "ts" not in responses.columns or "cost_usd" not in responses.columns:
            st.caption("Chưa có `cost_usd` để vẽ cost.")
            return

        by_min = responses.set_index("ts")["cost_usd"].astype(float).resample("1min").sum()
        frame = by_min.cumsum().reset_index(name="cumulative")
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=frame["ts"], y=frame["cumulative"], name="Cost tích luỹ",
                                 fill="tozeroy", line=dict(color=C_YELLOW, width=2),
                                 fillcolor="rgba(255,201,92,.22)"))
        threshold_line(fig, budget, f"Budget ${budget}")
        mark_incidents(fig, windows)
        st.plotly_chart(style_figure(fig, ytitle="USD"), width="stretch")


def panel_tokens(container, data: dict, windows: list[dict]) -> None:
    with container:
        tokens_in, tokens_out = data["tokens_in"], data["tokens_out"]
        panel_header("tokens", "Input and output tokens")

        cols = st.columns(3)
        cols[0].metric("Tokens in", f"{tokens_in:,}")
        cols[1].metric("Tokens out", f"{tokens_out:,}")
        cols[2].metric("Tỉ lệ out/in", f"{(tokens_out / tokens_in) if tokens_in else 0:.2f}")

        responses = data["responses"]
        if responses.empty or "ts" not in responses.columns or "tokens_in" not in responses.columns:
            st.caption("Chưa có dữ liệu token.")
            return

        by_min = (
            responses.set_index("ts")[["tokens_in", "tokens_out"]]
            .astype(float).resample("1min").sum().reset_index()
        )
        fig = go.Figure()
        fig.add_trace(go.Bar(x=by_min["ts"], y=by_min["tokens_in"], name="Tokens in",
                             marker_color=C_BLUE))
        fig.add_trace(go.Bar(x=by_min["ts"], y=by_min["tokens_out"], name="Tokens out",
                             marker_color=C_VIOLET))
        fig.update_layout(barmode="stack")
        mark_incidents(fig, windows)
        st.plotly_chart(style_figure(fig, ytitle="tokens / phút"), width="stretch")


def panel_quality(container, data: dict, windows: list[dict]) -> None:
    with container:
        quality = data["quality_avg"]
        target = SLO.get("quality_score_avg", 0.75)
        breach = quality < target
        panel_header("quality", "Quality proxy",
                     verdict_html(not breach, "Đạt guardrail", "Dưới guardrail"))

        cols = st.columns(3)
        cols[0].metric("Mean quality", f"{quality:.3f}", f"SLO ≥ {target}")
        cols[1].metric("Min", f"{data['quality_min']:.3f}")
        cols[2].metric("Số response", f"{data['count_responses']:,}")

        responses = data["responses"]
        if responses.empty or "ts" not in responses.columns or "quality_score" not in responses.columns:
            st.caption("Chưa có `quality_score` để vẽ.")
            return

        by_min = (
            responses.set_index("ts")["quality_score"].astype(float)
            .resample("1min").mean().dropna().reset_index()
        )
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=by_min["ts"], y=by_min["quality_score"], name="Quality",
                                 mode="lines+markers", line=dict(color=C_GREEN, width=2),
                                 fill="tozeroy", fillcolor="rgba(86,223,155,.18)"))
        threshold_line(fig, target, f"SLO ≥ {target}", color=C_GREEN)
        mark_incidents(fig, windows)
        fig.update_yaxes(range=[0, 1.05])
        st.plotly_chart(style_figure(fig, ytitle="score 0–1"), width="stretch")


def render_six_panels(data: dict, windows: list[dict]) -> None:
    """6 panel đúng thứ tự contract: latency · traffic · errors · cost · tokens · quality."""
    row1 = st.columns(2)
    panel_latency(row1[0].container(border=True), data, windows)
    panel_traffic(row1[1].container(border=True), data, windows)

    row2 = st.columns(2)
    panel_errors(row2[0].container(border=True), data, windows)
    panel_cost(row2[1].container(border=True), data, windows)

    row3 = st.columns(2)
    panel_tokens(row3[0].container(border=True), data, windows)
    panel_quality(row3[1].container(border=True), data, windows)


# ═══════════════════════════════════════════════════════════════════════════════
# 01 — API HOẠT ĐỘNG
# ═══════════════════════════════════════════════════════════════════════════════


def check_health(base_url: str) -> tuple[bool, dict | str]:
    try:
        import httpx

        response = httpx.get(f"{base_url}/health", timeout=2.0)
        return response.status_code == 200, response.json()
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def view_api() -> None:
    st.markdown("## 01 · API hoạt động")
    st.markdown(
        "<div class='lede'>Show <code>/health</code> → gửi một request <code>/chat</code> → "
        "response phải có correlation ID, latency, token, cost và quality.</div>",
        unsafe_allow_html=True,
    )

    left, right = st.columns([1, 2])

    with left.container(border=True):
        st.markdown("#### `GET /health`")
        base_url = st.text_input("Base URL", value="http://127.0.0.1:8000", label_visibility="collapsed")
        if st.button("Gọi /health", width="stretch"):
            st.session_state["health"] = check_health(base_url)
        ok, payload = st.session_state.get("health", (None, None))
        if ok is None:
            st.caption("Bấm nút để kiểm tra service đang chạy.")
        elif ok:
            st.success("Service UP")
            st.json(payload)
        else:
            st.error("Không gọi được /health — API chưa chạy?")
            st.code(str(payload))
            st.caption("Khởi động: `uvicorn app.main:app --reload`")

    with right.container(border=True):
        st.markdown("#### Request gần nhất trong log")
        responses = metrics["responses"]
        if responses.empty:
            st.info("Chưa có `response_sent` trong cửa sổ đang chọn.")
        else:
            latest = responses.sort_values("ts").iloc[-1]
            st.markdown(
                f"Correlation ID: **`{latest.get('correlation_id', '—')}`** · "
                f"feature `{latest.get('feature', '—')}` · model `{latest.get('model', '—')}`"
            )
            cols = st.columns(4)
            cols[0].metric("Latency", f"{float(latest.get('latency_ms', 0)):.0f} ms")
            cols[1].metric("Tokens in/out",
                           f"{int(latest.get('tokens_in', 0))}/{int(latest.get('tokens_out', 0))}")
            cols[2].metric("Cost", f"${float(latest.get('cost_usd', 0)):.5f}")
            cols[3].metric("Quality", f"{float(latest.get('quality_score', 0)):.2f}")
            st.caption(
                "Bốn chỉ số này chính là nguồn của panel latency · token · cost · quality."
            )

    with st.container(border=True):
        st.markdown("#### Trạng thái incident (từ log điều khiển)")
        active = {w["name"] for w in windows_all if not w["closed"]}
        cols = st.columns(3)
        for i, name in enumerate(["rag_slow", "tool_fail", "cost_spike"]):
            is_on = name in active
            cols[i].markdown(
                f"<div class='step'><small>scenario</small>"
                f"<div class='title'><code>{name}</code></div>"
                f"<div class='body' style='color:{C_RED if is_on else C_GREEN};font-weight:800;'>"
                f"{'ĐANG BẬT' if is_on else 'tắt'}</div></div>",
                unsafe_allow_html=True,
            )
        st.caption(
            "Bật/tắt bằng `python scripts/inject_incident.py --scenario rag_slow` "
            "(thêm `--disable` để tắt)."
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 02 — LOGGING & BẢO MẬT
# ═══════════════════════════════════════════════════════════════════════════════


def view_logging() -> None:
    st.markdown("## 02 · Logging & bảo mật")
    st.markdown(
        "<div class='lede'>Log JSON có cấu trúc → các event cùng một correlation ID → "
        "email, số điện thoại và thẻ đã bị redact.</div>",
        unsafe_allow_html=True,
    )

    ids_in_window = unique_correlation_ids(df_window)

    with st.container(border=True):
        st.markdown("#### Correlation ID xuyên suốt một request")
        if not ids_in_window:
            st.info("Không có correlation ID trong cửa sổ đang chọn.")
        else:
            selected = st.selectbox(
                "Chọn correlation ID để xem toàn bộ event của request đó",
                ids_in_window,
                index=len(ids_in_window) - 1,
                key="corr_pick",
            )
            related = df_window[df_window["correlation_id"] == selected].sort_values("ts")
            st.caption(
                f"**{len(related)} event** dùng chung `{selected}` — "
                f"{' → '.join(related['event'].tolist())}"
            )
            for _, row in related.iterrows():
                record = {k: v for k, v in row.to_dict().items() if pd.notna(v)}
                if isinstance(record.get("ts"), pd.Timestamp):
                    record["ts"] = record["ts"].isoformat()
                st.code(json.dumps(record, ensure_ascii=False, indent=2), language="json")

    scan_left, scan_right = st.columns(2)

    with scan_left.container(border=True):
        st.markdown("#### Quét PII bằng detector của grader")
        detectors = load_pii_detectors()
        haystack = "\n".join(raw_lines)
        leaks = {name: len(pattern.findall(haystack)) for name, pattern in detectors.items()}
        total_leaks = sum(leaks.values())

        if total_leaks == 0:
            st.markdown(
                f"<div class='big' style='color:{C_GREEN};font-size:30px;font-weight:900;'>"
                f"0 PII leak</div>",
                unsafe_allow_html=True,
            )
            st.caption(
                f"Quét {len(raw_lines)} dòng log bằng {len(detectors)} detector "
                f"({', '.join(detectors)}) — không còn dữ liệu thô."
            )
        else:
            st.error(f"Phát hiện {total_leaks} PII leak")
            st.json(leaks)

    with scan_right.container(border=True):
        st.markdown("#### Bằng chứng đã redact")
        redactions = re.findall(r"\[REDACTED_([A-Z_]+)\]", haystack)
        if not redactions:
            st.info("Chưa có log nào chứa PII để redact — thử gửi query có email/SĐT/thẻ.")
        else:
            counts = pd.Series(redactions).value_counts()
            st.dataframe(
                counts.rename_axis("Loại PII").reset_index(name="Số lần redact"),
                width="stretch", hide_index=True,
            )
            samples = [line for line in raw_lines if "[REDACTED_" in line][:3]
            st.caption("Ví dụ payload đã che:")
            for line in samples:
                record = json.loads(line)
                preview = (record.get("payload") or {}).get("message_preview") or json.dumps(
                    record.get("payload"), ensure_ascii=False
                )
                st.code(f"{record.get('correlation_id', '—')}  →  {preview}", language="text")

    with st.container(border=True):
        st.markdown("#### Chất lượng schema log")
        cols = st.columns(4)
        cols[0].metric("Bản ghi hợp lệ", f"{len(raw_lines):,}")
        cols[1].metric("Dòng hỏng", f"{malformed_lines:,}")
        cols[2].metric("Correlation ID duy nhất", f"{len(trace_ids_all):,}")
        enrich_fields = ["user_id_hash", "session_id", "feature", "model"]
        api_rows = df_all[df_all.get("service") == "api"] if "service" in df_all.columns else pd.DataFrame()
        missing = 0
        if not api_rows.empty:
            missing = int(sum(1 for _, r in api_rows.iterrows() if any(pd.isna(r.get(f)) for f in enrich_fields)))
        cols[3].metric("API log thiếu enrichment", f"{missing:,}")
        st.caption(
            "Enrichment bắt buộc: `user_id_hash`, `session_id`, `feature`, `model` — "
            "đây là phần validate_logs.py chấm 20 điểm."
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 03 — DASHBOARD (6 panel + baseline + SLO)
# ═══════════════════════════════════════════════════════════════════════════════


def view_dashboard() -> None:
    st.markdown("## 03 · Dashboard")
    st.markdown(
        "<div class='lede'>Đủ 6 nhóm chỉ số → nêu số liệu baseline → nêu SLO/threshold "
        "và cách nhận biết bất thường.</div>",
        unsafe_allow_html=True,
    )

    baseline_df, incident_df = split_by_incident(df_all, windows_all)
    baseline = compute_metrics(baseline_df)

    with st.container(border=True):
        st.markdown("#### Baseline vs cửa sổ đang xem")
        st.caption(
            "Baseline = toàn bộ dữ liệu **ngoài** mọi cửa sổ incident. Đây là số liệu để "
            "so sánh khi có bất thường."
        )
        rows = [
            ("Latency P95 (ms)", baseline["latency_p95"], metrics["latency_p95"],
             SLO.get("latency_p95_ms", 3000), "lte"),
            ("Error rate (%)", baseline["error_rate_pct"], metrics["error_rate_pct"],
             SLO.get("error_rate_pct", 2), "lte"),
            ("Cost (USD)", baseline["total_cost_usd"], metrics["total_cost_usd"],
             SLO.get("daily_cost_usd", 2.5), "lte"),
            ("Quality (avg)", baseline["quality_avg"], metrics["quality_avg"],
             SLO.get("quality_score_avg", 0.75), "gte"),
        ]
        table = []
        for label, base_value, current, target, operator in rows:
            healthy = current <= target if operator == "lte" else current >= target
            table.append(
                {
                    "Chỉ số": label,
                    "Baseline": f"{base_value:,.4f}".rstrip("0").rstrip(".") if base_value else "0",
                    "Hiện tại": f"{current:,.4f}".rstrip("0").rstrip(".") if current else "0",
                    "SLO": f"{'≤' if operator == 'lte' else '≥'} {target}",
                    "Trạng thái": "✅ OK" if healthy else "🚨 BREACH",
                }
            )
        st.dataframe(pd.DataFrame(table), width="stretch", hide_index=True)

    st.markdown("#### 6 panel theo `config/dashboard.yaml`")
    render_six_panels(metrics, windows_view)

    with st.container(border=True):
        st.markdown("#### Cách nhận biết bất thường")
        for alert in ALERTS:
            st.markdown(
                f"- **`{alert['name']}`** ({alert['severity']}) — {alert['summary']}  \n"
                f"  điều kiện `{alert['condition']}` · owner `{alert['owner']}` · runbook `{alert['runbook']}`"
            )
        if not ALERTS:
            st.caption("Chưa đọc được `config/alert_rules.yaml`.")


# ═══════════════════════════════════════════════════════════════════════════════
# 04 — LANGFUSE & PROMPT VERSIONING
# ═══════════════════════════════════════════════════════════════════════════════


def view_langfuse() -> None:
    st.markdown("## 04 · Langfuse — tracing & prompt versioning")
    st.markdown(
        "<div class='lede'>Tối thiểu 10 traces → mở một trace để drill-down → "
        "prompt v1/v2 kèm bằng chứng đổi label hoặc rollback.</div>",
        unsafe_allow_html=True,
    )

    host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")

    top = st.columns(3)
    top[0].metric("Traces (correlation ID)", f"{len(trace_ids_all)}",
                  f"yêu cầu ≥ {PASS_TRACE_COUNT}")
    top[1].metric("Prompt name", os.getenv("LANGFUSE_PROMPT_NAME", "day13-chat"))
    top[2].metric("Prompt label đang chạy", os.getenv("LANGFUSE_PROMPT_LABEL", "production"))
    st.caption(
        f"Mỗi correlation ID tương ứng một trace `chat-agent` trong Langfuse. "
        f"Mở drill-down tại {host} → Traces, lọc theo session hoặc user hash."
    )

    with st.container(border=True):
        st.markdown("#### Danh sách trace để chọn drill-down")
        responses = event_subset(df_window, "response_sent")
        if responses.empty:
            st.info("Chưa có trace nào trong cửa sổ đang chọn.")
            return

        columns = [c for c in
                   ["ts", "correlation_id", "feature", "model", "session_id", "user_id_hash",
                    "latency_ms", "tokens_in", "tokens_out", "cost_usd", "quality_score"]
                   if c in responses.columns]
        table = responses[columns].sort_values("ts", ascending=False).copy()
        if "ts" in table.columns:
            table["ts"] = table["ts"].dt.strftime("%H:%M:%S")
        st.dataframe(table, width="stretch", hide_index=True, height=280)

    with st.container(border=True):
        st.markdown("#### Drill-down một trace")
        ids = unique_correlation_ids(df_window)
        if not ids:
            st.info("Không có correlation ID để drill-down.")
            return
        picked = st.selectbox("Correlation ID", ids, index=len(ids) - 1, key="lf_pick")
        related = df_window[df_window["correlation_id"] == picked].sort_values("ts")

        spans = []
        for _, row in related.iterrows():
            spans.append(
                {
                    "Thời điểm": row["ts"].strftime("%H:%M:%S.%f")[:-3] if pd.notna(row.get("ts")) else "—",
                    "Event": row.get("event", "—"),
                    "Latency (ms)": row.get("latency_ms", "—"),
                    "Cost (USD)": row.get("cost_usd", "—"),
                    "Quality": row.get("quality_score", "—"),
                }
            )
        st.dataframe(pd.DataFrame(spans), width="stretch", hide_index=True)
        st.caption(
            "Trong Langfuse, trace này có cấu trúc `chat-agent` (agent) → `rag-retriever` "
            "(retriever) → `llm-generation` (generation); metadata mang `prompt_name`, "
            "`prompt_version`, `prompt_label`, `prompt_source`."
        )

    with st.container(border=True):
        st.markdown("#### Prompt versioning")
        st.markdown(
            "- Prompt `day13-chat` được lấy qua Langfuse Prompt Management "
            "(`app/prompt_management.py::resolve_prompt`), có fallback local khi Langfuse lỗi.\n"
            "- Label đang áp dụng đọc từ biến môi trường `LANGFUSE_PROMPT_LABEL`; đổi label "
            "hoặc rollback chỉ cần trỏ label `production` sang version khác — không phải deploy lại.\n"
            "- Mỗi trace ghi kèm `prompt_version` và `prompt_label`, nên so sánh v1 vs v2 là so "
            "hai tập trace cùng metadata."
        )
        st.caption("Chi tiết quy trình: `docs/PROMPT_VERSIONING.md`")


# ═══════════════════════════════════════════════════════════════════════════════
# 05 — DEMO MỘT INCIDENT (Metric → Trace → Log → Root cause → Fix → Prevention)
# ═══════════════════════════════════════════════════════════════════════════════


def view_incident() -> None:
    st.markdown("## 05 · Demo một incident")
    st.markdown(
        "<div class='lede'>Metric bất thường → Trace liên quan → Log chứng minh → "
        "Root cause → Cách xử lý → Cách phòng ngừa.</div>",
        unsafe_allow_html=True,
    )

    if not windows_all:
        st.info(
            "Chưa phát hiện incident nào trong log. Tạo một incident để demo:\n\n"
            "```\npython scripts/inject_incident.py --scenario rag_slow\n"
            "python scripts/load_test.py --concurrency 5\n"
            "python scripts/inject_incident.py --scenario rag_slow --disable\n```"
        )
        return

    labels = {
        f"{i + 1}. {w['name']} — {w['start'].strftime('%H:%M:%S')} → "
        f"{w['end'].strftime('%H:%M:%S')}{'' if w['closed'] else ' (đang bật)'}": w
        for i, w in enumerate(windows_all)
    }
    picked_label = st.selectbox("Chọn cửa sổ incident", list(labels), index=len(labels) - 1)
    window = labels[picked_label]
    scenario = window["name"]
    kb = INCIDENT_KB.get(scenario, {})

    baseline_df, _ = split_by_incident(df_all, windows_all)
    inside_df = df_all[(df_all["ts"] >= window["start"]) & (df_all["ts"] <= window["end"])]
    baseline = compute_metrics(baseline_df)
    during = compute_metrics(inside_df)

    # ─── Bước 1: Metric bất thường ────────────────────────────────────────────
    with st.container(border=True):
        st.markdown("#### Bước 1 — Metric bất thường")
        cols = st.columns(4)
        cols[0].metric("P95 latency", f"{during['latency_p95']:.0f} ms",
                       f"{during['latency_p95'] - baseline['latency_p95']:+.0f} ms so baseline",
                       delta_color="inverse")
        cols[1].metric("Error rate", f"{during['error_rate_pct']:.2f} %",
                       f"{during['error_rate_pct'] - baseline['error_rate_pct']:+.2f} pp",
                       delta_color="inverse")
        cols[2].metric("Cost / request", f"${during['avg_cost_usd']:.5f}",
                       f"{during['avg_cost_usd'] - baseline['avg_cost_usd']:+.5f}",
                       delta_color="inverse")
        cols[3].metric("Tokens out", f"{during['tokens_out']:,}")
        st.caption(f"Dấu hiệu đặc trưng của `{scenario}`: {kb.get('signal', '—')}")

        responses_all = event_subset(df_all, "response_sent")
        if not responses_all.empty and "ts" in responses_all.columns:
            series = responses_all.set_index("ts")["latency_ms"].astype(float)
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=series.index, y=series.values, name="latency mỗi request",
                                     mode="lines+markers", line=dict(color=C_BLUE, width=1.6)))
            threshold_line(fig, SLO.get("latency_p95_ms", 3000),
                           f"SLO P95 ≤ {SLO.get('latency_p95_ms', 3000):.0f}ms")
            mark_incidents(fig, windows_all)
            st.plotly_chart(style_figure(fig, height=260, ytitle="ms"), width="stretch")

    # ─── Bước 2 & 3: Trace và Log ─────────────────────────────────────────────
    trace_col, log_col = st.columns(2)

    slow_requests = event_subset(inside_df, "response_sent")
    if not slow_requests.empty and "latency_ms" in slow_requests.columns:
        slow_requests = slow_requests.sort_values("latency_ms", ascending=False)

    with trace_col.container(border=True):
        st.markdown("#### Bước 2 — Trace liên quan")
        if slow_requests.empty:
            st.caption("Không có response nào trong cửa sổ incident.")
            picked_trace = None
        else:
            columns = [c for c in ["correlation_id", "latency_ms", "feature", "cost_usd"]
                       if c in slow_requests.columns]
            st.dataframe(slow_requests[columns].head(5), width="stretch", hide_index=True)
            picked_trace = slow_requests.iloc[0].get("correlation_id")
            st.caption(f"Trace chậm nhất: **`{picked_trace}`** — mở trace này trong Langfuse để xem span nào ăn thời gian.")

    with log_col.container(border=True):
        st.markdown("#### Bước 3 — Log chứng minh")
        control = inside_df[inside_df["event"].isin(["incident_enabled", "incident_disabled"])]
        if not control.empty:
            row = control.iloc[0].to_dict()
            if isinstance(row.get("ts"), pd.Timestamp):
                row["ts"] = row["ts"].isoformat()
            st.code(json.dumps({k: v for k, v in row.items() if pd.notna(v)},
                               ensure_ascii=False, indent=2), language="json")
        if slow_requests is not None and not slow_requests.empty:
            row = slow_requests.iloc[0].to_dict()
            if isinstance(row.get("ts"), pd.Timestamp):
                row["ts"] = row["ts"].isoformat()
            st.code(json.dumps({k: v for k, v in row.items() if pd.notna(v)},
                               ensure_ascii=False, indent=2), language="json")
            st.caption("Cùng `correlation_id` với trace ở bước 2 — metric, trace và log khớp nhau.")

    # ─── Bước 4, 5, 6 ─────────────────────────────────────────────────────────
    steps = st.columns(3)
    with steps[0]:
        st.markdown(step_card("4", "Root cause", kb.get("root_cause", "—")), unsafe_allow_html=True)
    with steps[1]:
        fixes = "".join(f"• {item}<br>" for item in kb.get("fix", []))
        st.markdown(step_card("5", "Cách xử lý", fixes or "—"), unsafe_allow_html=True)
    with steps[2]:
        prevents = "".join(f"• {item}<br>" for item in kb.get("prevent", []))
        st.markdown(step_card("6", "Cách phòng ngừa", prevents or "—"), unsafe_allow_html=True)

    st.caption(
        f"Panel bị ảnh hưởng rõ nhất: **{kb.get('panel', '—')}** — đây cũng là panel nên mở "
        "đầu tiên khi alert bắn."
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 06 — KẾT QUẢ KIỂM TRA
# ═══════════════════════════════════════════════════════════════════════════════


def view_validation() -> None:
    st.markdown("## 06 · Kết quả kiểm tra")
    st.markdown(
        "<div class='lede'>Tests quan trọng pass → <code>validate_logs.py</code> ≥ 80/100 → "
        "<code>validate_dashboard.py</code> báo 6/6 panel.</div>",
        unsafe_allow_html=True,
    )

    render_gate()
    st.divider()

    with st.container(border=True):
        st.markdown(f"#### `python scripts/validate_logs.py` — yêu cầu ≥ {PASS_LOG_SCORE}/100")
        st.code(log_out.strip() or "(không có output)", language="text")

    with st.container(border=True):
        st.markdown("#### `python scripts/validate_dashboard.py` — yêu cầu 6/6 panel")
        st.code(dash_out.strip() or "(không có output)", language="text")

    with st.container(border=True):
        st.markdown("#### `python scripts/validate_alerts.py` — SLO & alert rules")
        alerts_rc, alerts_out = run_script("scripts/validate_alerts.py")
        st.code(alerts_out.strip() or "(không có output)", language="text")

    with st.container(border=True):
        st.markdown("#### `python -m pytest -q`")
        if st.button("Chạy pytest", width="stretch"):
            with st.spinner("Đang chạy test suite..."):
                st.session_state["pytest"] = run_pytest()
        result = st.session_state.get("pytest")
        if result is None:
            st.caption("Bấm nút để chạy toàn bộ test suite (mất vài giây).")
        else:
            rc, output = result
            (st.success if rc == 0 else st.error)(
                "Tất cả test pass" if rc == 0 else f"Test suite fail (exit code {rc})"
            )
            st.code(output.strip()[-4000:] or "(không có output)", language="text")


# ═══════════════════════════════════════════════════════════════════════════════
# TOÀN CẢNH — màn hình dùng để chụp ảnh evidence
# ═══════════════════════════════════════════════════════════════════════════════


def view_overview() -> None:
    render_gate()
    st.divider()

    st.markdown("### 📈 6 panel bắt buộc")
    st.markdown(
        "<div class='lede'>latency · traffic · error · cost · token · quality — "
        "đúng contract <code>config/dashboard.yaml</code>, có threshold và vùng incident.</div>",
        unsafe_allow_html=True,
    )
    render_six_panels(metrics, windows_view)

    st.divider()
    st.markdown("### 🔁 Incident flow bắt buộc")
    flow = st.columns(6)
    flow_steps = [
        ("1", "Metric bất thường", "P95 / error / cost lệch khỏi baseline"),
        ("2", "Trace liên quan", "Correlation ID của request chậm nhất"),
        ("3", "Log chứng minh", "Log JSON cùng correlation ID"),
        ("4", "Root cause", "Hàm và cờ gây lỗi trong code"),
        ("5", "Cách xử lý", "Tắt incident + guardrail"),
        ("6", "Cách phòng ngừa", "Alert + health check + chaos test"),
    ]
    for column, (number, title, body) in zip(flow, flow_steps):
        with column:
            st.markdown(step_card(number, title, body), unsafe_allow_html=True)

    st.caption("Chi tiết từng bước với dữ liệu thật: chọn **05 · Demo một incident** ở sidebar.")


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTER
# ═══════════════════════════════════════════════════════════════════════════════

if view.startswith("🏁"):
    view_overview()
elif view.startswith("01"):
    view_api()
elif view.startswith("02"):
    view_logging()
elif view.startswith("03"):
    view_dashboard()
elif view.startswith("04"):
    view_langfuse()
elif view.startswith("05"):
    view_incident()
else:
    view_validation()

# ═══════════════════════════════════════════════════════════════════════════════
# FOOTER
# ═══════════════════════════════════════════════════════════════════════════════

st.divider()
st.markdown(
    f"<div style='color:{C_MUTED};font-size:12.5px;'>"
    f"<b>Observe → Explain → Fix → Prevent</b> · Day 13 · Monitoring · Logging · Observability "
    f"&nbsp;|&nbsp; nguồn <code>data/logs.jsonl</code> · contract <code>config/dashboard.yaml</code> "
    f"· cập nhật {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    f"</div>",
    unsafe_allow_html=True,
)
