# Báo cáo Day 13 Observability

## 1. Thông tin nhóm

- Tên nhóm:
- Repository URL:
- Commit SHA cuối:
- Thành viên và vai trò:

## 2. Kết quả kỹ thuật

- Điểm `validate_logs.py`: 30/100 (baseline — Total log records analyzed: 24; Records with missing required fields: 20; Records with missing enrichment (context): 20; Unique correlation IDs found: 0; Potential PII leaks detected: 0)
- Tổng số traces: 0 (chưa có correlation ID nào được propagate)
- Số PII leak còn lại: 0
- Link/đường dẫn dashboard:

## 3. Logging và tracing

- Evidence correlation ID:
- Evidence PII redaction:
- Evidence trace waterfall:
- Giải thích một span đáng chú ý:

## 4. Prompt versioning

- Prompt name:
- Version/label baseline:
- Version/label candidate:
- Trace ID của mỗi version:
- Bằng chứng đổi label hoặc rollback:

## 5. Dashboard, SLO và alerts

- Kết quả `validate_dashboard.py`:
- Evidence dashboard:
- SLO đã chọn và lý do: P95 latency <= 3000 ms và error rate <= 2% phản ánh trực tiếp trải nghiệm/độ tin cậy; daily cost <= 2.5 USD kiểm soát ngân sách; quality average >= 0.75 là guardrail chất lượng. Cửa sổ SLO là 28 ngày.
- Alert rules và runbook: 3 alert symptom-based (`high_latency_p95`, `elevated_error_rate`, `cost_budget_exceeded`) đã đồng bộ objective với `config/slo.yaml`; mỗi alert có severity, duration, owner, ảnh hưởng, ba bước kiểm tra, mitigation và điều kiện đóng tại `docs/alerts.md`.
- Kết quả `python scripts/validate_alerts.py`: `VALID: 4 SLOs, 3 symptom-based alerts, and 3 runbooks.`
- Evidence cấu hình: `submission/evidence/cp2-alert-validation.txt`.

## 6. Điều tra challenge

- **Challenge ID**: day13-k4-observability-v1
- **Triệu chứng từ metrics**: 
  - P95 latency tăng từ ~1200ms (baseline) lên ~3600ms (incident active)
  - Tất cả 5 challenge queries đều vượt ngưỡng 2000ms (3559-3644ms)
  - 17 requests vượt 2500ms sau khi incident enabled
- **Trace ID liên quan**: req-34b4f1a7, req-f85346e6, req-fdcb9057, req-abe50d4a, req-d43133da (tất cả feature=monitoring)
- **Log line/correlation ID liên quan**: 
  - Line 149: incident_enabled (rag_slow) tại ts 08:26:47
  - Lines 150-159: 5 challenge requests với latency 3559-3644ms
  - Line 181: incident_disabled tại ts 08:28:53
- **Root cause**: RAG retrieval slowness - `app/mock_rag.py` thêm 2500ms delay khi `STATE["rag_slow"]=True`
- **Fix action**: 
  1. Disable incident qua control event
  2. Thêm timeout/circuit breaker cho RAG retrieval
  3. Implement async retrieval với fallback cached results
- **Preventive measure**:
  1. SLO alert P95 latency tại 1500ms
  2. RAG health check synthetic query
  3. Circuit breaker pattern cho external calls
  4. Trace spans cho `retrieve()` để identify slowness
  5. Chaos testing với RAG slowness scenario

## 7. Đóng góp cá nhân

Với mỗi thành viên, ghi rõ nhiệm vụ và link commit/PR tương ứng.

| Thành viên | Phần việc | Commit/PR | Điều đã học |
|---|---|---|---|
| | | | |
