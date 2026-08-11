# Challenge Investigation: rag_slow

## Incident Configuration
- **Challenge ID**: day13-k4-observability-v1
- **Incident**: rag_slow
- **Latency Threshold**: 2000ms
- **Affected Feature**: monitoring

## Symptom Identification (Metrics)

### Challenge Query Latencies
| Correlation ID | Latency (ms) | % of Threshold | Status |
|---------------|--------------|----------------|--------|
| req-34b4f1a7 | 3644 | 182.2% | EXCEEDS |
| req-f85346e6 | 3568 | 178.4% | EXCEEDS |
| req-fdcb9057 | 3559 | 178.0% | EXCEEDS |
| req-abe50d4a | 3578 | 178.9% | EXCEEDS |
| req-d43133da | 3610 | 180.5% | EXCEEDS |

**All 5 challenge queries exceeded 2000ms threshold by 78-82%.**

### Batch Analysis (P95 Comparison)
| Batch | Min | Max | P95 | Exceeds 2s |
|-------|-----|-----|-----|------------|
| Batch 2 (baseline) | 965ms | 1201ms | 1189ms | 0 |
| Batch 3 | 978ms | 1418ms | 1181ms | 0 |
| Batch 4 | 1035ms | 2781ms | 2537ms | 2 |
| Batch 5 (incident active) | 1162ms | 3664ms | 3644ms | 14 |
| Batch 6 | 3602ms | 3602ms | 3602ms | 1 |

**P95 jumped from ~1200ms (baseline) to ~3600ms (incident active).**

## Trace Evidence

### Correlation IDs (from logs.jsonl)
All challenge requests used feature="monitoring" with session_id starting "k4-challenge-s":

| Session ID | Correlation ID | Latency | Line in logs |
|------------|----------------|---------|--------------|
| k4-challenge-s03 | req-34b4f1a7 | 3644ms | 150-151 |
| k4-challenge-s02 | req-f85346e6 | 3568ms | 152-153 |
| k4-challenge-s05 | req-fdcb9057 | 3559ms | 154-155 |
| k4-challenge-s01 | req-abe50d4a | 3578ms | 156-157 |
| k4-challenge-s04 | req-d43133da | 3610ms | 158-159 |

### Incident Control Events
- **Line 149**: `incident_enabled` - rag_slow enabled at 2026-08-11T08:26:47.110871Z
- **Line 160**: `incident_enabled` - rag_slow re-enabled at 2026-08-11T08:27:45.273508Z
- **Line 181**: `incident_disabled` - rag_slow disabled at 2026-08-11T08:28:53.652471Z

## Log Evidence (Key Lines)

### Baseline (before incident)
```
Line 2-3: req-2bda1251 - latency_ms: 1143 (OK)
Line 4-5: req-ea457122 - latency_ms: 1053 (OK)
```

### Incident Active (after line 149)
```
Line 150-151: req-34b4f1a7 - latency_ms: 3644 (EXCEEDS by 1644ms)
Line 152-153: req-f85346e6 - latency_ms: 3568 (EXCEEDS by 1568ms)
Line 154-155: req-fdcb9057 - latency_ms: 3559 (EXCEEDS by 1559ms)
Line 156-157: req-abe50d4a - latency_ms: 3578 (EXCEEDS by 1578ms)
Line 158-159: req-d43133da - latency_ms: 3610 (EXCEEDS by 1610ms)
```

### Evidence of RAG Slowness Pattern
After incident enabled, ALL requests became slow (not just challenge queries):
```
Line 162: req-0cfd8152 - 3567ms (qa feature)
Line 164: req-bde2048c - 3477ms (summary feature)
Line 166: req-df3da646 - 3498ms (qa feature)
Line 168: req-ce33eece - 3498ms (qa feature)
```

**17 total requests exceeded 2500ms after incident enabled.**

## Root Cause

**RAG (Retrieval-Augmented Generation) retrieval slowness**

Evidence from `app/mock_rag.py`:
```python
def retrieve(message: str) -> list[str]:
    if STATE["rag_slow"]:
        time.sleep(2.5)  # Adds 2500ms delay
```

When `rag_slow` incident is enabled:
1. Every `retrieve()` call adds 2500ms delay
2. `LabAgent.run()` calls `retrieve()` before LLM generation (line 32 in agent.py)
3. This adds 2500ms to every request, pushing latencies from ~1000ms to ~3500ms

**Chain**: `rag_slow` enabled → `retrieve()` adds 2.5s → total latency exceeds 2s threshold

## Fix Action

1. **Immediate**: Disable `rag_slow` incident via control event
2. **Code Fix**: Add timeout to RAG retrieval or circuit breaker pattern:
   ```python
   def retrieve(message: str, timeout_ms: int = 1000) -> list[str]:
       import signal
       def timeout_handler(signum, frame):
           raise TimeoutError("RAG retrieval exceeded timeout")
       signal.signal(signal.SIGALRM, timeout_handler)
       signal.alarm(timeout_ms // 1000)
       try:
           # ... existing retrieval logic
       finally:
           signal.alarm(0)
   ```
3. **Alternative**: Async retrieval with fallback to cached results

## Preventive Measures

1. **SLO Alerting**: Set P95 latency alert at 1500ms (buffer before 2s threshold)
2. **RAG Health Check**: Add synthetic query to monitor retrieval latency
3. **Circuit Breaker**: Implement fallback when RAG exceeds threshold
4. **Trace Span Instrumentation**: Add spans around `retrieve()` to identify slowness in traces
5. **Load Testing**: Include RAG slowness scenario in chaos testing suite

## Evidence Files

- `correlation_ids.json` - List of all correlation IDs with latencies
- `incident_timeline.json` - Control events timeline
- This investigation document
