# Báo cáo Day 13 Observability

## 1. Thông tin nhóm

- Tên nhóm: 5tuat
- Repository URL: https://github.com/phampau/K4-Day13-2A202601502
- Commit SHA cuối: cef636e09bc5b3676c3c1f5712e58f4b36dce87e
- Thành viên và vai trò:
  - Trần Hoàng Long (API & Middleware): CP1 Middleware, gán Correlation ID, và bổ sung exception handler (phần mở rộng).
  - Trần Đức Bảo (Security Engineer): CP1 PII Scrubbing, regex patterns và kiểm chứng log không lộ PII.
  - Phạm Quốc Bảo (Metrics & Dashboard): CP1/CP2 đo đếm error_rate_pct và thiết kế spec Dashboard 6 nhóm chỉ số.
  - Phạm Công Đạt (SRE & Alerts Engineer): CP2 Thiết lập SLO, viết Alerts rules và Alert Runbook xử lý sự cố.
  - Nguyễn Sỹ Mạnh Cường (QA & Chief Investigator): Chạy load test, bọc trace cho sub-component RAG/LLM (phần mở rộng), dẫn dắt điều tra Challenge (CP3) và hoàn thiện báo cáo nhóm.

## 2. Kết quả kỹ thuật

- Điểm `validate_logs.py`: 100/100 (PASSED — Total log records analyzed: 50; Records with missing required fields: 0; Records with missing enrichment (context): 0; Unique correlation IDs found: 16; Potential PII leaks detected: 0)
- Tổng số traces: 16+ traces (có đầy đủ `user_id_hash`, `session_id`, `feature`, `model`, `env` & metadata)
- Số PII leak còn lại: 0
- Link/đường dẫn dashboard: `submission/evidence/dashboard.png` (Validator `scripts/validate_dashboard.py` báo HỢP LỆ 6/6 panel)

## 3. Logging và tracing

- Evidence correlation ID:
  - Log `request_received`: `{"event": "request_received", "correlation_id": "req-ec6bb95f", "service": "api", "session_id": "s01", "user_id_hash": "2055254ee30a", "feature": "qa", "model": "claude-sonnet-4-5", "env": "dev"}`
  - Log `response_sent`: `{"event": "response_sent", "correlation_id": "req-ec6bb95f", "service": "api", "latency_ms": 1144, "cost_usd": 0.002253, "quality_score": 0.9}`
- Evidence PII redaction:
  - Email: `"What is your refund policy? My email is [REDACTED_EMAIL]"` (`req-ec6bb95f`)
  - Phone: `"Here is my phone [REDACTED_PHONE_VN], what should be logged?"` (`req-6863dac8`)
  - Credit Card: `"What is the policy for PII and credit card [REDACTED_CREDIT_CARD]?"` (`req-8b3f4a02`)
- Evidence trace waterfall:
  - Trace `chat-agent` (`as_type="agent"`) -> Retriever Observation `rag-retriever` (`as_type="retriever"`) -> Generation Observation `llm-generation` (`as_type="generation"`).
- Giải thích một span đáng chú ý:
  - Span `rag-retriever` trong `app/mock_rag.py`: Khi bị kích hoạt incident `rag_slow`, độ trễ của riêng span này tăng thêm +2500ms, khiến toàn bộ tổng latency của `chat-agent` bị đẩy từ 1100ms lên ~3600ms+.

## 4. Prompt versioning

- Prompt name: `day13-chat`
- Version/label baseline: `v1` (label: `baseline`, `production`)
- Version/label candidate: `v2` (label: `candidate`)
- Trace ID của mỗi version:
  - Trace version 1 (baseline): `req-ec6bb95f` (`prompt_version=1`, `prompt_label=production`, `prompt_source=langfuse`)
  - Trace version 2 (candidate): `req-4b30ac74` (`prompt_version=2`, `prompt_label=candidate`, `prompt_source=langfuse`)
- Bằng chứng đổi label hoặc rollback:
  - Chuyển label `production` từ v1 -> v2 và rollback từ v2 -> v1 thông qua Langfuse Prompt Management SDK. Trace metadata tự động phản ánh `prompt_version` và `prompt_label` chính xác theo từng request.

## 5. Dashboard, SLO và alerts

- Kết quả `validate_dashboard.py`: `HỢP LỆ: 6/6 panel có trong dashboard contract.`
- Evidence dashboard: `submission/evidence/dashboard.png` (Đã dựng đủ 6 panel theo `config/dashboard.yaml`: Latency P50/P95/P99, Request traffic, Error rate & breakdown, Cost over time, Input/Output tokens, Quality score).
- SLO đã chọn và lý do: P95 latency <= 3000 ms và error rate <= 2% phản ánh trực tiếp trải nghiệm/độ tin cậy; daily cost <= 2.5 USD kiểm soát ngân sách; quality average >= 0.75 là guardrail chất lượng. Cửa sổ SLO là 28 ngày.
- Alert rules và runbook: 3 alert symptom-based (`high_latency_p95`, `elevated_error_rate`, `cost_budget_exceeded`) đã đồng bộ objective với `config/slo.yaml`; mỗi alert có severity, duration, owner, ảnh hưởng, ba bước kiểm tra, mitigation và điều kiện đóng tại `docs/alerts.md`.
- Kết quả `python scripts/validate_alerts.py`: `VALID: 4 SLOs, 3 symptom-based alerts, and 3 runbooks.`
- Evidence cấu hình: `submission/evidence/cp2-alert-validation.txt`.

## 6. Điều tra challenge

- **Challenge ID**: day13-k4-observability-v1
- **Triệu chứng từ metrics**: 
  - P95 latency tăng từ ~1200ms (baseline) lên ~19,270ms / ~3600ms khi incident active.
  - 100% request trong đợt load test challenge chịu ảnh hưởng độ trễ tăng vọt.
- **Trace ID liên quan**: `req-006ac213`, `req-134c359f`, `req-b77dc92b`, `req-208da9fa`, `req-c659a9de` (tất cả feature=monitoring).
- **Log line/correlation ID liên quan**: 
  - Log event `incident_enabled` (scenario: `rag_slow`) tại timestamp `08:26:47Z`.
  - Log events `request_received` và `response_sent` với `correlation_id` `req-006ac213`, `req-134c359f`, `req-b77dc92b` hiển thị latency `19272ms`.
- **Root cause**: RAG retrieval slowness - trong `app/mock_rag.py`, cờ `STATE["rag_slow"]=True` tự động chèn thêm `time.sleep(2.5)` vào mỗi lần gọi `retrieve()`, làm chậm toàn bộ luồng xử lý agent.
- **Fix action**: 
  1. Tắt incident thông qua control endpoint `/incidents/rag_slow/disable`.
  2. Bổ sung timeout và circuit breaker cho hàm `retrieve()`.
  3. Áp dụng async retrieval với kết quả cached fallback.
- **Preventive measure**:
  1. Thiết lập Alert cảnh báo P95 Latency ở mức 1500ms.
  2. Triển khai RAG health check synthetic query định kỳ.
  3. Áp dụng Pattern Circuit Breaker cho các cuộc gọi dịch vụ bên ngoài.
  4. Gắn Trace Spans riêng cho `retrieve()` (`as_type="retriever"`) để nhanh chóng khoanh vùng nghẽn.
  5. Thực hiện Chaos testing định kỳ với các kịch bản RAG slowness.

## 7. Đóng góp cá nhân

Với mỗi thành viên, ghi rõ nhiệm vụ và link commit/PR tương ứng.

| Thành viên | Phần việc | Commit/PR | Điều đã học |
|---|---|---|---|
| Trần Hoàng Long | API & Middleware: CP1 Middleware, Correlation ID propagation, exception handler | `main` | Gắn correlation ID xuyên suốt request lifecycle trong FastAPI. |
| Trần Đức Bảo | Security Engineer: CP1 PII Scrubbing, regex patterns và redacted logs | `main` | Thiết lập regex pattern cho PII Việt Nam và thứ tự processor trong structlog. |
| Phạm Quốc Bảo | Metrics & Dashboard: CP1/CP2 error_rate_pct và thiết kế spec Dashboard 6 panel | `main` | Quy đổi log events thành 6 nhóm chỉ số dashboard theo contract. |
| Phạm Công Đạt | SRE & Alerts Engineer: CP2 Thiết lập SLO, Alerts rules và Alert Runbook | `main` | Thiết lập SLO/SLI và quy trình runbook xử lý sự cố. |
| Nguyễn Sỹ Mạnh Cường | QA & Chief Investigator (Role 5): Load test, bọc Langfuse trace sub-component RAG/LLM, điều tra CP3 Challenge | `main` | Bọc trace `@observe` đa tầng (retriever, generation, agent) và phương pháp điều tra Metrics → Traces → Logs. |
