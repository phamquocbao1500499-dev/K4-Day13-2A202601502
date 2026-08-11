# Runbook demo cuối giờ — 5–7 phút / nhóm

Bám đúng kịch bản trong `index.html`. Mỗi phần ghi rõ: mở view nào trên dashboard, chạy lệnh gì, và bằng chứng cần chỉ ra.

Mở dashboard trước khi bắt đầu:

```bash
uvicorn app.main:app --reload          # terminal 1
streamlit run app/dashboard/main.py    # terminal 2
```

Sidebar dashboard có đúng 7 view: `🏁 Toàn cảnh` + `01`…`06` khớp 6 phần của kịch bản.

---

## Trước khi lên: 3 điều kiện "demo đạt"

Mở view **🏁 Toàn cảnh** — ba thẻ trên cùng phải xanh hết. Dashboard chạy thẳng validator nên số này không nhập tay.

| Điều kiện | Ngưỡng | Nguồn |
|---|---|---|
| Logging validation | ≥ 80/100 | `scripts/validate_logs.py` |
| Dashboard validation | 6/6 panel | `scripts/validate_dashboard.py` |
| Tracing evidence | ≥ 10 traces | correlation ID duy nhất trong `data/logs.jsonl` |

Nếu thẻ nào đỏ, chưa lên trình bày. Cách chữa nhanh nhất: chạy lại load test để sinh đủ log.

```bash
python scripts/load_test.py --concurrency 5
```

---

## 01 · API hoạt động (~45s)

View **01 · API hoạt động**.

1. Bấm **Gọi /health** → chỉ vào `tracing_enabled` và trạng thái incident.
2. Gửi một request thật:
   ```bash
   curl -X POST http://127.0.0.1:8000/chat -H "Content-Type: application/json" \
     -d "{\"user_id\":\"demo\",\"session_id\":\"s-demo\",\"feature\":\"qa\",\"message\":\"What is your refund policy?\"}"
   ```
3. Card **Request gần nhất trong log** hiện đúng request đó: correlation ID, latency, token, cost, quality.

**Câu chốt:** bốn con số này chính là nguồn của bốn panel trên dashboard.

## 02 · Logging & bảo mật (~60s)

View **02 · Logging & bảo mật**.

1. Chọn correlation ID vừa tạo → dashboard in ra toàn bộ event JSON dùng chung ID đó (`request_received` → `response_sent`).
2. Chỉ vào thẻ **Quét PII**: 0 leak, quét bằng chính detector của grader.
3. Chỉ vào bảng **Bằng chứng đã redact**: email / phone / credit card đã thành `[REDACTED_*]`.

**Câu chốt:** một request = một correlation ID xuyên suốt, và không có PII thô nào lọt xuống file log.

## 03 · Dashboard (~75s)

View **03 · Dashboard 6 panel**.

1. Bảng **Baseline vs cửa sổ đang xem** — nêu số baseline (P95, error rate, cost, quality).
2. Cuộn xuống 6 panel: mỗi panel hiện tên, `unit` và `threshold` đọc thẳng từ `config/dashboard.yaml`.
3. Chỉ vào đường đứt SLO trên biểu đồ latency và cost.
4. Cuối trang: 3 alert rule và điều kiện bắn.

**Câu chốt:** bất thường = số hiện tại lệch khỏi baseline và cắt qua đường SLO.

## 04 · Langfuse (~60s)

View **04 · Langfuse & prompt**.

1. Chỉ số **Traces** ≥ 10.
2. Bảng trace → chọn một correlation ID → phần **Drill-down** liệt kê các event của trace.
3. Mở Langfuse thật, vào trace tương ứng: `chat-agent` → `rag-retriever` → `llm-generation`.
4. Chỉ `prompt_version` / `prompt_label` trong metadata, và nói cách đổi label `production` từ v1 sang v2 (rollback là trỏ ngược lại, không deploy lại).

## 05 · Demo một incident (~90s)

Chuẩn bị trước buổi demo:

```bash
python scripts/inject_incident.py --scenario rag_slow
python scripts/load_test.py --concurrency 5
python scripts/inject_incident.py --scenario rag_slow --disable
```

View **05 · Demo một incident** → chọn cửa sổ incident. Trình bày đúng 6 bước dashboard đã dựng sẵn:

| Bước | Nội dung | Bằng chứng trên màn hình |
|---|---|---|
| 1 | Metric bất thường | P95 trong incident so với baseline, biểu đồ có vùng đỏ |
| 2 | Trace liên quan | Bảng 5 request chậm nhất + correlation ID chậm nhất |
| 3 | Log chứng minh | Log `incident_enabled` và log request chậm, cùng correlation ID |
| 4 | Root cause | Hàm và cờ gây lỗi trong code |
| 5 | Cách xử lý | Tắt incident + timeout/circuit breaker |
| 6 | Cách phòng ngừa | Alert + health check + chaos test |

Với `rag_slow`, root cause là `app/mock_rag.py::retrieve()` chèn `time.sleep(2.5)` khi `STATE['rag_slow'] = True`.

## 06 · Kết quả kiểm tra (~40s)

View **06 · Kết quả kiểm tra**.

1. Ba khối output validator hiển thị nguyên văn (logs, dashboard, alerts).
2. Bấm **Chạy pytest** → toàn bộ test pass.
3. Quay lại ba thẻ gate ở đầu view.

**Câu chốt:** "Observe → Explain → Fix → Prevent" — hệ thống tốt phải giải thích được chuyện gì đang xảy ra.

---

## Lưu ý khi demo

- Nếu dashboard trống: bật **Neo theo log mới nhất** trong sidebar (cửa sổ 60 phút tính lùi từ log mới nhất thay vì đồng hồ thực), hoặc chọn **Toàn bộ dữ liệu**.
- Sau khi sinh log mới, bấm **Làm mới ngay** để xoá cache.
- Ảnh evidence chụp ở view **🏁 Toàn cảnh**: có sẵn context bar (nguồn, time range, refresh, SLO) và cả 6 panel trong một khung hình.
