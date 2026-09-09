"""Acceptance tests for the deterministic golden-scenario data.

These checks encode the six customer-facing questions in docs/06-demo-script.md as
executable assertions. Run after every `generate.py` invocation:

    uv run --no-sync python .\\src\\data_generator\\validate_scenario.py --data .\\sample_output

Exits non-zero if any invariant fails, so it can gate CI or a pre-demo smoke test.
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

PRIMARY_INCIDENT_ID = "INC-2026-ONT-001"
PRIMARY_REGION = "Toronto West"
PRIMARY_SERVICE_TYPE = "5G Home Internet"


def load(path: Path, name: str) -> list[dict[str, Any]]:
    with (path / name).open("r", encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value)


class Result:
    def __init__(self) -> None:
        self.failures: list[str] = []
        self.passes: list[str] = []

    def check(self, name: str, condition: bool, detail: str = "") -> None:
        if condition:
            self.passes.append(name)
        else:
            self.failures.append(f"{name}: {detail}")

    def report(self) -> int:
        print(f"PASS: {len(self.passes)}  FAIL: {len(self.failures)}")
        for name in self.passes:
            print(f"  [PASS] {name}")
        for failure in self.failures:
            print(f"  [FAIL] {failure}")
        return 1 if self.failures else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate causal integrity of generated scenario data.")
    parser.add_argument("--data", required=True, type=Path)
    args = parser.parse_args()
    data = args.data

    subscriptions = {row["subscription_id"]: row for row in load(data, "raw_subscriptions.csv")}
    service_instances = {row["service_instance_id"]: row for row in load(data, "raw_service_instances.csv")}
    incidents = {row["incident_id"]: row for row in load(data, "raw_incidents.csv")}
    support_cases = load(data, "raw_support_cases.csv")
    alarms = load(data, "raw_alarms.csv")
    work_orders = load(data, "raw_work_orders.csv")
    telemetry_events = load(data, "raw_telemetry_events.csv")
    technicians = {row["technician_id"]: row for row in load(data, "raw_technicians.csv")}
    bridge_asset = load(data, "raw_bridge_incident_asset.csv")
    bridge_service = load(data, "raw_bridge_incident_service.csv")
    investigations = load(data, "raw_investigations.csv")

    bridge_asset_ids = {row["network_asset_id"] for row in bridge_asset if row["incident_id"] == PRIMARY_INCIDENT_ID}
    bridge_service_ids = {
        row["service_instance_id"] for row in bridge_service if row["incident_id"] == PRIMARY_INCIDENT_ID
    }

    result = Result()

    primary_incident = incidents.get(PRIMARY_INCIDENT_ID)
    result.check("primary incident exists", primary_incident is not None, "INC-2026-ONT-001 missing")
    if primary_incident is None:
        return result.report()

    result.check(
        "primary incident is in Toronto West",
        primary_incident["region"] == PRIMARY_REGION,
        primary_incident["region"],
    )
    result.check(
        "primary incident affects 5G Home Internet",
        primary_incident["affected_service_type"] == PRIMARY_SERVICE_TYPE,
        primary_incident["affected_service_type"],
    )
    result.check("primary incident has a non-empty asset bridge", len(bridge_asset_ids) > 1, str(len(bridge_asset_ids)))
    result.check(
        "primary incident has a non-empty service bridge", len(bridge_service_ids) > 0, str(len(bridge_service_ids))
    )

    # Scene 1/2: every bridged service instance must be 5G Home Internet on a bridged asset.
    bad_bridge_services = [
        sid
        for sid in bridge_service_ids
        if service_instances[sid]["service_type"] != PRIMARY_SERVICE_TYPE
        or service_instances[sid]["network_asset_id"] not in bridge_asset_ids
    ]
    result.check(
        "every bridged service instance is 5G Home Internet on a bridged asset",
        not bad_bridge_services,
        f"{len(bad_bridge_services)} mismatched instances",
    )

    # Scene 3: every support case tied to the primary incident must resolve to a bridged
    # service instance whose owning account matches the case's account.
    primary_cases = [case for case in support_cases if case["incident_id"] == PRIMARY_INCIDENT_ID]
    result.check("primary incident has attached support cases", len(primary_cases) > 0, "0 cases")

    account_mismatch = 0
    asset_mismatch = 0
    service_type_mismatch = 0
    for case in primary_cases:
        instance = service_instances.get(case["service_instance_id"])
        if instance is None:
            asset_mismatch += 1
            continue
        subscription = subscriptions.get(instance["subscription_id"])
        if subscription is None or subscription["account_id"] != case["account_id"]:
            account_mismatch += 1
        if instance["network_asset_id"] not in bridge_asset_ids:
            asset_mismatch += 1
        if instance["service_type"] != PRIMARY_SERVICE_TYPE:
            service_type_mismatch += 1

    result.check("no case/account mismatches on primary incident", account_mismatch == 0, str(account_mismatch))
    result.check("no case/asset mismatches on primary incident", asset_mismatch == 0, str(asset_mismatch))
    result.check(
        "no case/service-type mismatches on primary incident", service_type_mismatch == 0, str(service_type_mismatch)
    )

    # Scene 2: every alarm tied to the primary incident must sit on a bridged asset.
    primary_alarms = [alarm for alarm in alarms if alarm["incident_id"] == PRIMARY_INCIDENT_ID]
    bad_alarms = [alarm for alarm in primary_alarms if alarm["network_asset_id"] not in bridge_asset_ids]
    result.check("primary incident has alarms", len(primary_alarms) > 0, "0 alarms")
    result.check("every primary incident alarm sits on a bridged asset", not bad_alarms, str(len(bad_alarms)))

    # Scene 5: the primary incident must have a saved investigation whose impact counts match
    # the bridge tables (OperationsIQ-inspired evidence trail).
    primary_investigations = [row for row in investigations if row["incident_id"] == PRIMARY_INCIDENT_ID]
    result.check("primary incident has an investigation", len(primary_investigations) == 1, str(len(primary_investigations)))
    if primary_investigations:
        investigation = primary_investigations[0]
        result.check(
            "investigation asset count matches the bridge",
            int(investigation["affected_asset_count"]) == len(bridge_asset_ids),
            f"investigation={investigation['affected_asset_count']} bridge={len(bridge_asset_ids)}",
        )
        result.check(
            "investigation service count matches the bridge",
            int(investigation["affected_service_count"]) == len(bridge_service_ids),
            f"investigation={investigation['affected_service_count']} bridge={len(bridge_service_ids)}",
        )
        result.check(
            "investigation related-case count matches primary cases",
            int(investigation["related_case_count"]) == len(primary_cases),
            f"investigation={investigation['related_case_count']} cases={len(primary_cases)}",
        )

    # Scene 4: work orders must not complete after their incident's resolution time, and the
    # assigned technician's home region should match the incident region.
    resolution_time = parse_time(primary_incident["resolution_time"])
    late_completions = 0
    region_mismatches = 0
    for order in work_orders:
        incident = incidents.get(order["incident_id"])
        if incident is None:
            continue
        if order["status"] == "Completed" and parse_time(order["completed_time"]) > parse_time(incident["resolution_time"]):
            late_completions += 1
        technician = technicians.get(order["technician_id"])
        if technician and technician["home_region"] != incident["region"]:
            region_mismatches += 1

    result.check("no work order completes after its incident resolves", late_completions == 0, str(late_completions))
    result.check("no cross-region technician assignments", region_mismatches == 0, str(region_mismatches))

    # Scene 1/5: telemetry on bridged assets must show degradation during the incident window
    # and recovery afterward.
    incident_start = parse_time(primary_incident["start_time"])
    incident_end = resolution_time
    during_packet_loss = [
        float(event["metric_value"])
        for event in telemetry_events
        if event["network_asset_id"] in bridge_asset_ids
        and event["metric_name"] == "packet_loss_pct"
        and incident_start <= parse_time(event["event_time"]) <= incident_end
    ]
    after_packet_loss = [
        float(event["metric_value"])
        for event in telemetry_events
        if event["network_asset_id"] in bridge_asset_ids
        and event["metric_name"] == "packet_loss_pct"
        and parse_time(event["event_time"]) > incident_end
    ]
    avg_during = sum(during_packet_loss) / len(during_packet_loss) if during_packet_loss else 0.0
    avg_after = sum(after_packet_loss) / len(after_packet_loss) if after_packet_loss else 0.0
    result.check("packet loss is elevated during the incident window", avg_during > 2.0, f"avg_during={avg_during:.3f}")
    result.check(
        "packet loss recovers after resolution",
        avg_after < avg_during,
        f"avg_during={avg_during:.3f} avg_after={avg_after:.3f}",
    )

    # Scene 3: ticket volume should rise during/after the incident vs. an equivalent pre-incident
    # window, then decline once past the immediate aftermath.
    case_day_counts: Counter[str] = Counter()
    for case in primary_cases:
        case_day_counts[parse_time(case["opened_time"]).date().isoformat()] += 1
    result.check(
        "primary incident cases concentrate in the first 3 days after the incident",
        sum(count for day, count in case_day_counts.items() if day <= "2026-06-19") >= len(primary_cases) * 0.8,
        str(dict(sorted(case_day_counts.items()))),
    )

    return result.report()


if __name__ == "__main__":
    sys.exit(main())
