from __future__ import annotations

from scripts.validate_alerts import load_and_validate


def test_slo_alert_and_runbook_contract_is_valid() -> None:
    slo_config, alert_config = load_and_validate()

    assert set(slo_config["slis"]) == {
        "latency_p95_ms",
        "error_rate_pct",
        "daily_cost_usd",
        "quality_score_avg",
    }
    assert {alert["name"] for alert in alert_config["alerts"]} == {
        "high_latency_p95",
        "elevated_error_rate",
        "cost_budget_exceeded",
    }
