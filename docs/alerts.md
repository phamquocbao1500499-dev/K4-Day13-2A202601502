# Alert Runbooks - Day 13 AI Observability

## Alert 1: High Latency

**Tên:** High Latency P95  
**Severity:** warning  
**SLI/SLO liên quan:** `latency_p95_ms` → objective 3000ms, target 99.5%  
**Điều kiện:** p95 latency > 3000ms trong 5 phút  
**Ảnh hưởng:** Users experience slow responses, degraded UX  
**Owner:** SRE  

### Ba bước kiểm tra đầu tiên

1. **Kiểm tra span traces trong Langfuse**
   ```bash
   # Truy cập Langfuse dashboard
   # Filter: operation_name CONTAINS "llm" OR "retrieval"
   # Sort by duration DESC
   # Identify: slow RAG retrieval hay slow LLM response
   ```

2. **Phân tích thành phần chậm**
   ```bash
   # Query logs.jsonl để xác định latency breakdown
   jq 'select(.event == "response_sent") | {latency_ms, rag_latency_ms, llm_latency_ms}' data/logs.jsonl | jq -s 'add | {avg_rag: (.[] | .rag_latency_ms) | add / length, avg_llm: (.[] | .llm_latency_ms) | add / length}'
   ```

3. **Check infrastructure metrics**
   - CPU/Memory của inference server
   - Vector DB query latency (Pinecone/Milvus metrics)
   - Network latency đến LLM provider

### Mitigation tạm thời

```bash
# Nếu RAG chậm: tăng vector DB connection pool
# Nếu LLM chậm: kiểm tra provider status, consider fallback model

# Enable caching nếu chưa có
export ENABLE_RESPONSE_CACHE=true
```

---

## Alert 2: High Error Rate

**Tên:** High Error Rate  
**Severity:** critical  
**SLI/SLO liên quan:** `error_rate_pct` → objective 2%, target 99.0%  
**Điều kiện:** error_rate_pct > 2% trong 3 phút  
**Ảnh hưởng:** Users nhận được error responses, possible data loss  
**Owner:** Backend  

### Ba bước kiểm tra đầu tiên

1. **Check error logs**
   ```bash
   # Xem chi tiết errors gần đây
   jq 'select(.event == "request_failed")' data/logs.jsonl | jq -s 'group_by(.error_type) | map({type: .[0].error_type, count: length})'

   # Error types phổ biến: "llm_timeout", "rag_empty_result", "validation_error", "auth_failed"
   ```

2. **Correlate với recent deployments**
   ```bash
   # Kiểm tra git log gần đây
   git log --oneline -10 --after="2 hours ago"

   # Rollback nếu cần
   git revert <commit_hash>
   ```

3. **Check error types breakdown**
   ```bash
   # Cụ thể hơn về từng loại error
   jq 'select(.event == "request_failed") | {error_type, error_message, timestamp}' data/logs.jsonl | tail -20
   ```

### Mitigation tạm thời

```bash
# Nếu LLM errors: restart service hoặc switch provider
# Nếu auth errors: kiểm tra API keys
# Nếu validation errors: check input format

# Temporary: enable error bypass mode
export ERROR_BYPASS_MODE=true
```

---

## Alert 3: Cost Spike

**Tên:** Cost Spike Alert  
**Severity:** warning  
**SLI/SLO liên quan:** `daily_cost_usd` → objective $2.5/day  
**Điều kiện:** cost_usd > 2.5 trong 1 giờ (tức ~$0.10/phút)  
**Ảnh hưởng:** Budget overrun, need to investigate expensive queries  
**Owner:** Product  

### Ba bước kiểm tra đầu tiên

1. **Identify high-cost queries**
   ```bash
   # Top 10 queries by cost
   jq 'select(.event == "response_sent") | {query_id, cost_usd, tokens_in, tokens_out, timestamp}' data/logs.jsonl | jq -s 'sort_by(.cost_usd) | reverse | .[:10]'
   ```

2. **Analyze token usage**
   ```bash
   # Total tokens trong 1 giờ
   jq 'select(.event == "response_sent") | {tokens_in, tokens_out}' data/logs.jsonl | jq -s '{(add | .tokens_in), (add | .tokens_out)}'

   # Identify high token queries (possible prompt injection hoặc loops)
   jq 'select(.event == "response_sent" and (.tokens_in > 5000 or .tokens_out > 2000))' data/logs.jsonl
   ```

3. **Check for anomalies**
   ```bash
   # Số lượng requests bất thường
   jq 'select(.event == "request_received")' data/logs.jsonl | jq -s 'length'

   # Nếu traffic spike: kiểm tra DoS hoặc abuse
   ```

### Mitigation tạm thời

```bash
# Enable rate limiting
export RATE_LIMIT_RPM=60

# Nếu specific query gây spike: block or throttle
# Consider using cheaper model cho simple queries
export LOW_COST_MODEL=gpt-3.5-turbo
```

---

## General Commands

```bash
# Real-time monitoring
tail -f data/logs.jsonl | jq 'select(.event | IN("response_sent", "request_failed"))'

# Calculate current SLO burn rate
python scripts/check_slo.py

# Export metrics for analysis
jq -r '@json' data/logs.jsonl > /tmp/metrics.json
```
