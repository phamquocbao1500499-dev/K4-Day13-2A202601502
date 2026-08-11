# Alert runbook — Day 13 AI Observability

Runbook này dùng cùng SLI và ngưỡng trong `config/slo.yaml`. Người trực xử lý theo luồng **Metrics → Traces → Logs**, ghi lại thời điểm, correlation ID/trace ID, hành động giảm thiểu và kết quả. Không đưa API key hoặc PII vào evidence.

## Alert 1

### High latency P95

- **Tên:** `high_latency_p95`
- **Severity:** `warning`
- **Owner:** `on-call-engineer`
- **SLI/SLO:** `latency_p95_ms <= 3000 ms`; đạt cho ít nhất 99,5% cửa sổ trong 28 ngày.
- **Điều kiện kích hoạt:** `latency_p95_ms > 3000` liên tục 5 phút.
- **Ảnh hưởng người dùng:** phản hồi chat chậm, tăng tỷ lệ bỏ phiên hoặc gửi lại yêu cầu.

Ba bước kiểm tra đầu tiên:

1. Mở panel **Latency**, xác nhận P95 vượt 3000 ms trong đúng cửa sổ cảnh báo; so sánh P50/P99 để phân biệt chậm diện rộng với outlier.
2. Trong Langfuse, lọc trace cùng khoảng thời gian, sắp xếp theo duration giảm dần và mở một trace chậm. So sánh thời lượng span `retrieve`, `generate` và span cha `run` nếu sub-span đã được bật.
3. Lấy correlation ID của trace/request và tìm `request_received` cùng `response_sent` trong `data/logs.jsonl`. Kiểm tra `latency_ms`, `feature`, `model` và trạng thái incident; không suy luận từ tên hàm đơn lẻ.

Mitigation tạm thời:

- Nếu `retrieve` chậm: giảm tải truy vấn, dùng cache hoặc tạm giảm số tài liệu trả về.
- Nếu `generate` chậm: chuyển sang model fallback đã được phê duyệt hoặc giảm giới hạn output.
- Nếu toàn hệ thống chậm: giới hạn concurrency/rate và báo trạng thái dịch vụ cho nhóm.
- Tắt incident practice sau khi kiểm chứng: `python scripts/inject_incident.py --scenario rag_slow --disable`.

Điều kiện đóng alert: P95 dưới hoặc bằng 3000 ms ít nhất 10 phút, request mới hoạt động bình thường và evidence đã được lưu.

## Alert 2

### Elevated error rate

- **Tên:** `elevated_error_rate`
- **Severity:** `critical`
- **Owner:** `on-call-engineer`
- **SLI/SLO:** `error_rate_pct <= 2%`; đạt cho ít nhất 99% cửa sổ trong 28 ngày.
- **Điều kiện kích hoạt:** `error_rate_pct > 2` liên tục 3 phút.
- **Ảnh hưởng người dùng:** request chat thất bại hoặc nhận HTTP 5xx, không có câu trả lời hữu ích.

Ba bước kiểm tra đầu tiên:

1. Mở panel **Error**, xác nhận mẫu số traffic không bằng 0 và xem breakdown theo `error_type` để tìm nhóm lỗi chiếm ưu thế.
2. Trong Langfuse, lọc trace lỗi theo cùng thời gian, feature và model; kiểm tra span cuối thành công và span đầu tiên lỗi.
3. Dùng correlation ID để tìm event `request_failed`/`unhandled_exception` trong log; đối chiếu `error_type`, `feature`, `model` và thay đổi triển khai gần nhất.

Mitigation tạm thời:

- Cô lập feature lỗi hoặc giảm traffic tới dependency lỗi.
- Dùng fallback/retry có giới hạn khi dependency tạm thời không ổn định; không retry lỗi validation.
- Nếu lỗi xuất hiện ngay sau deployment, rollback theo quy trình của nhóm và giữ nguyên evidence trước rollback.
- Với incident practice `tool_fail`, tắt bằng `python scripts/inject_incident.py --scenario tool_fail --disable`.

Điều kiện đóng alert: error rate không quá 2% ít nhất 10 phút, request kiểm thử thành công và không còn nhóm lỗi tăng bất thường.

## Alert 3

### Cost budget exceeded

- **Tên:** `cost_budget_exceeded`
- **Severity:** `warning`
- **Owner:** `team-lead`
- **SLI/SLO:** `daily_cost_usd <= 2.5 USD` trên cửa sổ trượt 24 giờ.
- **Điều kiện kích hoạt:** `daily_cost_usd > 2.5` liên tục 5 phút.
- **Ảnh hưởng người dùng/kinh doanh:** vượt ngân sách có thể buộc giảm hạn mức, gián đoạn dịch vụ hoặc dùng model kém phù hợp.

Ba bước kiểm tra đầu tiên:

1. Mở panel **Cost** và **Traffic**; xác định chi phí tăng do traffic tăng hay chi phí trung bình mỗi request tăng.
2. Trong Langfuse, lọc trace cùng cửa sổ và sắp xếp theo cost/tokens; đối chiếu model, feature, `tokens_in` và `tokens_out` của các trace đắt nhất.
3. Dùng correlation ID của trace đắt để tìm `response_sent` trong log; kiểm tra `cost_usd`, token, model và trạng thái incident `cost_spike`.

Mitigation tạm thời:

- Áp dụng rate limit theo user/session và giới hạn input/output token.
- Chuyển workload phù hợp sang model rẻ hơn đã được phê duyệt; giữ model chất lượng cao cho yêu cầu cần thiết.
- Giảm context dư thừa, cache kết quả an toàn và chặn vòng lặp retry không giới hạn.
- Tắt incident practice: `python scripts/inject_incident.py --scenario cost_spike --disable`.

Điều kiện đóng alert: tốc độ tăng chi phí trở lại bình thường, nguyên nhân đã được xác nhận và có kế hoạch đưa tổng chi phí cửa sổ 24 giờ về ngân sách.

## Checklist evidence

- Ảnh panel có time range và đường SLO/threshold.
- Trace ID và correlation ID đại diện; không chứa PII.
- Dòng log chứng minh triệu chứng/root cause.
- Thời điểm bắt đầu/kết thúc, owner, mitigation và kết quả xác minh.

## Câu hỏi phản biện

Alert nên dựa trên triệu chứng người dùng thấy vì nó phản ánh trực tiếp độ tin cậy của dịch vụ, không phụ thuộc cấu trúc triển khai và vẫn đúng khi code được refactor. Tên hàm hoặc lỗi nội bộ phù hợp cho chẩn đoán sau khi alert đã kích hoạt, nhưng nếu dùng làm điều kiện cảnh báo chính sẽ dễ gây nhiễu và có thể bỏ sót lỗi có cùng tác động từ component khác.
