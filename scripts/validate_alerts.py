from __future__ import annotations

from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
SLO_PATH = REPO_ROOT / "config" / "slo.yaml"
ALERT_PATH = REPO_ROOT / "config" / "alert_rules.yaml"
RUNBOOK_PATH = REPO_ROOT / "docs" / "alerts.md"
REQUIRED_ALERT_FIELDS = {
    "name",
    "summary",
    "severity",
    "condition",
    "type",
    "owner",
    "runbook",
    "sli",
    "objective",
}


class AlertConfigError(ValueError):
    pass


def load_and_validate(
    slo_path: Path = SLO_PATH,
    alert_path: Path = ALERT_PATH,
    runbook_path: Path = RUNBOOK_PATH,
) -> tuple[dict, dict]:
    slo_config = yaml.safe_load(slo_path.read_text(encoding="utf-8"))
    alert_config = yaml.safe_load(alert_path.read_text(encoding="utf-8"))
    runbook = runbook_path.read_text(encoding="utf-8")

    slis = slo_config.get("slis") if isinstance(slo_config, dict) else None
    if not isinstance(slis, dict) or not slis:
        raise AlertConfigError("config/slo.yaml must define non-empty 'slis'")

    alerts = alert_config.get("alerts") if isinstance(alert_config, dict) else None
    if not isinstance(alerts, list) or len(alerts) != 3:
        raise AlertConfigError("config/alert_rules.yaml must define exactly 3 alerts")

    for index, alert in enumerate(alerts, start=1):
        if not isinstance(alert, dict):
            raise AlertConfigError(f"alert {index} must be a YAML object")
        missing = REQUIRED_ALERT_FIELDS - alert.keys()
        if missing:
            raise AlertConfigError(f"alert {index} is missing: {', '.join(sorted(missing))}")
        if alert["type"] != "symptom-based":
            raise AlertConfigError(f"{alert['name']} must be symptom-based")
        if alert["severity"] not in {"warning", "critical"}:
            raise AlertConfigError(f"{alert['name']} has unsupported severity")
        sli = slis.get(alert["sli"])
        if not isinstance(sli, dict):
            raise AlertConfigError(f"{alert['name']} references unknown SLI")
        if alert["objective"] != sli.get("objective"):
            raise AlertConfigError(f"{alert['name']} objective does not match its SLO")
        if f"## Alert {index}" not in runbook:
            raise AlertConfigError(f"runbook is missing Alert {index}")

    return slo_config, alert_config


def main() -> int:
    try:
        slo_config, alert_config = load_and_validate()
    except (AlertConfigError, FileNotFoundError, yaml.YAMLError) as exc:
        print(f"INVALID: {exc}")
        return 1

    print(
        "VALID: "
        f"{len(slo_config['slis'])} SLOs, "
        f"{len(alert_config['alerts'])} symptom-based alerts, and 3 runbooks."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
