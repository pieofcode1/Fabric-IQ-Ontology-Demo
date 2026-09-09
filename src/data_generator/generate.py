from __future__ import annotations

import argparse
import csv
import random
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import yaml
from faker import Faker


INGESTION_TIMESTAMP = "2026-06-16T12:00:00-04:00"
INGESTION_DATE = "2026-06-16"


def load_config(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as stream:
        return yaml.safe_load(stream)


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return

    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def source_metadata(source_system: str, source_file: str, batch_id: str) -> dict[str, str]:
    return {
        "source_system": source_system,
        "ingestion_timestamp": INGESTION_TIMESTAMP,
        "ingestion_date": INGESTION_DATE,
        "source_file": source_file,
        "batch_id": batch_id,
    }


def weighted_choice(values: list[str], weights: list[int]) -> str:
    return random.choices(values, weights=weights, k=1)[0]


def generate_accounts(
    fake: Faker, regions: list[str], count: int, batch_id: str
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    account_types = ["Consumer", "Small Business", "Enterprise", "Public Sector"]
    tiers_by_type = {
        "Consumer": ["Standard", "Premium"],
        "Small Business": ["Standard", "Premium"],
        "Enterprise": ["Premium", "Enterprise"],
        "Public Sector": ["Premium", "Enterprise"],
    }

    for index in range(1, count + 1):
        account_type = weighted_choice(account_types, [74, 16, 7, 3])
        account_tier = random.choice(tiers_by_type[account_type])
        rows.append(
            {
                "account_id": f"ACCT-{index:07d}",
                "account_name": fake.company() if account_type != "Consumer" else fake.name(),
                "account_type": account_type,
                "account_tier": account_tier,
                "industry": random.choice(
                    ["Residential", "Retail", "Healthcare", "Financial Services", "Government"]
                ),
                "city": random.choice(regions),
                "province": "ON",
                "created_date": fake.date_between(start_date="-7y", end_date="-60d").isoformat(),
                **source_metadata("crm", "raw_accounts.csv", batch_id),
            }
        )

    return rows


def generate_customers(
    fake: Faker, accounts: list[dict[str, Any]], count: int, batch_id: str
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    segments = ["Residential", "Small Business", "Enterprise", "Public Sector"]

    for index in range(1, count + 1):
        account = random.choice(accounts)
        if account["account_type"] == "Consumer":
            segment = "Residential"
            customer_name = fake.name()
            customer_type = "Consumer"
        else:
            segment = account["account_type"]
            customer_name = account["account_name"]
            customer_type = "Business"

        rows.append(
            {
                "customer_id": f"CUST-{index:07d}",
                "account_id": account["account_id"],
                "customer_name": customer_name,
                "customer_type": customer_type,
                "segment": segment if segment in segments else "Small Business",
                "city": account["city"],
                "province": account["province"],
                "postal_code_prefix": random.choice(["M5V", "M6K", "L5B", "L6Y", "K1P"]),
                "created_date": fake.date_between(start_date="-5y", end_date="-30d").isoformat(),
                **source_metadata("crm", "raw_customers.csv", batch_id),
            }
        )

    return rows


def generate_products(batch_id: str) -> list[dict[str, Any]]:
    product_specs = [
        ("PROD-5GHI-001", "5G Home Internet 100", "5G Home Internet", 65.00),
        ("PROD-5GHI-002", "5G Home Internet Unlimited", "5G Home Internet", 85.00),
        ("PROD-MOB-001", "Infinite Mobile 50GB", "Mobile Data", 75.00),
        ("PROD-MOB-002", "Infinite Mobile 150GB", "Mobile Data", 105.00),
        ("PROD-FIB-001", "Fiber Internet 500", "Fiber Internet", 90.00),
        ("PROD-FIB-002", "Fiber Internet Gigabit", "Fiber Internet", 120.00),
        ("PROD-TV-001", "Ignite TV Popular", "TV", 70.00),
    ]

    return [
        {
            "product_id": product_id,
            "product_name": product_name,
            "service_type": service_type,
            "monthly_price": monthly_price,
            "product_family": service_type,
            "status": "Active",
            **source_metadata("product_catalog", "raw_products.csv", batch_id),
        }
        for product_id, product_name, service_type, monthly_price in product_specs
    ]


def generate_network_assets(regions: list[str], count: int, batch_id: str) -> list[dict[str, Any]]:
    """Build a region-partitioned topology so cell sectors have a real parent backhaul link.

    Every region gets its own backhaul links, cell sites/sectors, fiber nodes, routers, and
    CMTS devices. Cell sectors are parented to a backhaul link in the *same* region, which is
    what lets an incident on one backhaul asset causally explain degradation across a known,
    traceable set of dependent sectors (and therefore services, customers, and cases).
    """
    rows: list[dict[str, Any]] = []
    index = 1
    per_region = max(6, count // len(regions))

    for region in regions:
        backhaul_count = max(1, per_region // 12)
        backhaul_ids: list[str] = []
        for _ in range(backhaul_count):
            asset_id = f"NET-{index:06d}"
            backhaul_ids.append(asset_id)
            rows.append(
                {
                    "network_asset_id": asset_id,
                    "parent_asset_id": "",
                    "asset_type": "Backhaul Link",
                    "asset_name": f"Backhaul-{region.replace(' ', '')}-{index:06d}",
                    "region": region,
                    "city": region,
                    "latitude": round(random.uniform(43.55, 45.45), 6),
                    "longitude": round(random.uniform(-79.85, -75.55), 6),
                    "vendor": random.choice(["Vendor A", "Vendor B", "Vendor C"]),
                    "technology": "IP/MPLS",
                    "operational_status": weighted_choice(["Active", "Maintenance", "Degraded"], [92, 5, 3]),
                    **source_metadata("network_inventory", "raw_network_assets.csv", batch_id),
                }
            )
            index += 1

        remaining = per_region - backhaul_count
        sector_count = max(3, int(remaining * 0.55))
        site_count = max(1, int(remaining * 0.15))
        fiber_count = max(1, int(remaining * 0.15))
        router_count = max(1, int(remaining * 0.10))
        cmts_count = max(1, remaining - sector_count - site_count - fiber_count - router_count)

        for _ in range(site_count):
            rows.append(
                {
                    "network_asset_id": f"NET-{index:06d}",
                    "parent_asset_id": "",
                    "asset_type": "Cell Site",
                    "asset_name": f"CellSite-{region.replace(' ', '')}-{index:06d}",
                    "region": region,
                    "city": region,
                    "latitude": round(random.uniform(43.55, 45.45), 6),
                    "longitude": round(random.uniform(-79.85, -75.55), 6),
                    "vendor": random.choice(["Vendor A", "Vendor B", "Vendor C"]),
                    "technology": "5G",
                    "operational_status": weighted_choice(["Active", "Maintenance", "Degraded"], [92, 5, 3]),
                    **source_metadata("network_inventory", "raw_network_assets.csv", batch_id),
                }
            )
            index += 1

        for _ in range(sector_count):
            rows.append(
                {
                    "network_asset_id": f"NET-{index:06d}",
                    "parent_asset_id": random.choice(backhaul_ids),
                    "asset_type": "Cell Sector",
                    "asset_name": f"CellSector-{region.replace(' ', '')}-{index:06d}",
                    "region": region,
                    "city": region,
                    "latitude": round(random.uniform(43.55, 45.45), 6),
                    "longitude": round(random.uniform(-79.85, -75.55), 6),
                    "vendor": random.choice(["Vendor A", "Vendor B", "Vendor C"]),
                    "technology": "5G",
                    "operational_status": weighted_choice(["Active", "Maintenance", "Degraded"], [92, 5, 3]),
                    **source_metadata("network_inventory", "raw_network_assets.csv", batch_id),
                }
            )
            index += 1

        for asset_type, type_count, technology in (
            ("Fiber Node", fiber_count, "Fiber"),
            ("Router", router_count, "IP/MPLS"),
            ("CMTS", cmts_count, "DOCSIS"),
        ):
            for _ in range(type_count):
                rows.append(
                    {
                        "network_asset_id": f"NET-{index:06d}",
                        "parent_asset_id": "",
                        "asset_type": asset_type,
                        "asset_name": f"{asset_type.replace(' ', '')}-{region.replace(' ', '')}-{index:06d}",
                        "region": region,
                        "city": region,
                        "latitude": round(random.uniform(43.55, 45.45), 6),
                        "longitude": round(random.uniform(-79.85, -75.55), 6),
                        "vendor": random.choice(["Vendor A", "Vendor B", "Vendor C"]),
                        "technology": technology,
                        "operational_status": weighted_choice(["Active", "Maintenance", "Degraded"], [92, 5, 3]),
                        **source_metadata("network_inventory", "raw_network_assets.csv", batch_id),
                    }
                )
                index += 1

    return rows


def generate_subscriptions(
    accounts: list[dict[str, Any]], products: list[dict[str, Any]], count: int, batch_id: str
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    for index in range(1, count + 1):
        account = random.choice(accounts)
        product = random.choice(products)
        rows.append(
            {
                "subscription_id": f"SUB-{index:08d}",
                "account_id": account["account_id"],
                "product_id": product["product_id"],
                "service_type": product["service_type"],
                "start_date": (
                    datetime(2026, 6, 16) - timedelta(days=random.randint(30, 1500))
                ).date().isoformat(),
                "status": weighted_choice(["Active", "Suspended", "Cancelled"], [94, 4, 2]),
                "monthly_recurring_revenue": product["monthly_price"],
                **source_metadata("billing", "raw_subscriptions.csv", batch_id),
            }
        )

    return rows


def generate_devices(
    subscriptions: list[dict[str, Any]], products: list[dict[str, Any]], batch_id: str
) -> list[dict[str, Any]]:
    product_lookup = {product["product_id"]: product for product in products}
    rows: list[dict[str, Any]] = []

    for index, subscription in enumerate(subscriptions, start=1):
        service_type = product_lookup[subscription["product_id"]]["service_type"]
        if service_type == "Mobile Data":
            device_type = "Handset"
            models = ["iPhone 15", "Galaxy S25", "Pixel 10", "Motorola Edge"]
        elif service_type == "5G Home Internet":
            device_type = "5G Gateway"
            models = ["Home Gateway X1", "Home Gateway X2", "Fixed Wireless Hub"]
        elif service_type == "Fiber Internet":
            device_type = "Fiber Gateway"
            models = ["Ignite Gateway Pro", "Fiber Gateway 2"]
        else:
            device_type = "Set Top Box"
            models = ["Ignite TV Box", "Streaming Box"]

        rows.append(
            {
                "device_id": f"DEV-{index:08d}",
                "subscription_id": subscription["subscription_id"],
                "device_type": device_type,
                "model": random.choice(models),
                "firmware_version": f"{random.randint(1, 5)}.{random.randint(0, 9)}.{random.randint(0, 9)}",
                "activation_date": subscription["start_date"],
                "device_status": weighted_choice(["Active", "Needs Update", "Retired"], [91, 7, 2]),
                **source_metadata("device_management", "raw_devices.csv", batch_id),
            }
        )

    return rows


SERVICE_ASSET_RULES: dict[str, tuple[set[str], str]] = {
    "5G Home Internet": ({"Cell Sector", "Cell Site"}, "5G Fixed Wireless"),
    "Mobile Data": ({"Cell Sector", "Cell Site"}, "Mobile RAN"),
    "Fiber Internet": ({"Fiber Node", "Router"}, "Fiber"),
    "TV": ({"CMTS", "Router"}, "Cable"),
}


def preferred_assets_for_service(
    assets_by_region: dict[str, list[dict[str, Any]]], region: str, service_type: str
) -> list[dict[str, Any]]:
    """Pick an asset that matches both the customer's region and the service's access technology.

    This is the fix for the story-breaking bug where a service instance could be bound to a
    network asset in a different region/technology than the account it serves.
    """
    allowed_types, _ = SERVICE_ASSET_RULES.get(service_type, ({"Router"}, "Fiber"))
    region_assets = assets_by_region.get(region, [])
    preferred = [asset for asset in region_assets if asset["asset_type"] in allowed_types]
    if preferred:
        return preferred
    # Fall back to the same asset type in any region rather than an unrelated technology.
    any_region_preferred = [
        asset for assets in assets_by_region.values() for asset in assets if asset["asset_type"] in allowed_types
    ]
    return any_region_preferred or region_assets or [asset for assets in assets_by_region.values() for asset in assets]


def generate_service_instances(
    subscriptions: list[dict[str, Any]],
    devices: list[dict[str, Any]],
    network_assets: list[dict[str, Any]],
    accounts: list[dict[str, Any]],
    batch_id: str,
) -> list[dict[str, Any]]:
    device_lookup = {device["subscription_id"]: device for device in devices}
    account_lookup = {account["account_id"]: account for account in accounts}
    assets_by_region: dict[str, list[dict[str, Any]]] = {}
    for asset in network_assets:
        assets_by_region.setdefault(asset["region"], []).append(asset)

    rows: list[dict[str, Any]] = []
    for index, subscription in enumerate(subscriptions, start=1):
        region = account_lookup[subscription["account_id"]]["city"]
        network_asset = random.choice(
            preferred_assets_for_service(assets_by_region, region, subscription["service_type"])
        )
        _, access_type = SERVICE_ASSET_RULES.get(subscription["service_type"], ({"Router"}, "Fiber"))
        rows.append(
            {
                "service_instance_id": f"SVC-{index:08d}",
                "subscription_id": subscription["subscription_id"],
                "device_id": device_lookup[subscription["subscription_id"]]["device_id"],
                "network_asset_id": network_asset["network_asset_id"],
                "service_type": subscription["service_type"],
                "access_type": access_type,
                "activation_date": subscription["start_date"],
                "status": subscription["status"],
                **source_metadata("service_inventory", "raw_service_instances.csv", batch_id),
            }
        )

    return rows


def generate_incidents(
    config: dict[str, Any], network_assets: list[dict[str, Any]], count: int, batch_id: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Generate incidents plus an explicit incident-to-asset impact bridge.

    The bridge is the causal backbone of the demo: an incident on a backhaul link or cell
    site also impacts every asset whose ``parent_asset_id`` points to it (its dependent cell
    sectors). Downstream generators (telemetry, alarms, support cases, work orders) must use
    this bridge instead of picking a random asset/incident pairing.
    """
    rows: list[dict[str, Any]] = []
    bridge_rows: list[dict[str, Any]] = []
    incident_config = config["incident"]
    start_time = datetime.fromisoformat(incident_config["start_time"])
    primary_region = incident_config["primary_region"]

    children_by_parent: dict[str, list[dict[str, Any]]] = {}
    for asset in network_assets:
        if asset["parent_asset_id"]:
            children_by_parent.setdefault(asset["parent_asset_id"], []).append(asset)

    def impacted_assets(root_asset: dict[str, Any]) -> list[dict[str, Any]]:
        return [root_asset] + children_by_parent.get(root_asset["network_asset_id"], [])

    def add_bridge(incident_id: str, assets: list[dict[str, Any]]) -> None:
        for position, asset in enumerate(assets):
            bridge_rows.append(
                {
                    "incident_id": incident_id,
                    "network_asset_id": asset["network_asset_id"],
                    "impact_role": "root_cause" if position == 0 else "downstream",
                    **source_metadata("incident_management", "raw_bridge_incident_asset.csv", batch_id),
                }
            )

    # Pick the backhaul link with the most dependent cell sectors in the primary region -
    # this is the "congested backhaul path" the demo script traces back to.
    primary_candidates = [
        asset
        for asset in network_assets
        if asset["region"] == primary_region and asset["asset_type"] == "Backhaul Link"
    ]
    primary_asset = max(
        primary_candidates,
        key=lambda asset: len(children_by_parent.get(asset["network_asset_id"], [])),
        default=network_assets[0],
    )
    primary_incident_id = "INC-2026-ONT-001"
    primary_impacted = impacted_assets(primary_asset)

    rows.append(
        {
            "incident_id": primary_incident_id,
            "network_asset_id": primary_asset["network_asset_id"],
            "scenario_id": config["scenario_id"],
            "incident_type": "Service Degradation",
            "root_cause": incident_config["root_cause"],
            "severity": "High",
            "status": "Resolved",
            "start_time": start_time.isoformat(),
            "detected_time": (start_time + timedelta(minutes=incident_config["detection_lag_minutes"])).isoformat(),
            "resolution_time": (start_time + timedelta(hours=5, minutes=20)).isoformat(),
            "region": primary_region,
            "affected_service_type": incident_config["affected_service_type"],
            **source_metadata("incident_management", "raw_incidents.csv", batch_id),
        }
    )
    add_bridge(primary_incident_id, primary_impacted)

    severities = ["Low", "Medium", "High"]
    for index in range(2, count + 1):
        asset = random.choice(network_assets)
        incident_id = f"INC-2026-ONT-{index:03d}"
        random_start = start_time - timedelta(days=random.randint(0, 14), hours=random.randint(0, 23))
        duration = timedelta(minutes=random.randint(30, 480))
        rows.append(
            {
                "incident_id": incident_id,
                "network_asset_id": asset["network_asset_id"],
                "scenario_id": config["scenario_id"],
                "incident_type": random.choice(["Outage", "Service Degradation", "Capacity Alert"]),
                "root_cause": random.choice(
                    ["Equipment fault", "Capacity threshold", "Maintenance delay", "Power event"]
                ),
                "severity": random.choice(severities),
                "status": weighted_choice(["Resolved", "Monitoring", "Open"], [75, 15, 10]),
                "start_time": random_start.isoformat(),
                "detected_time": (random_start + timedelta(minutes=random.randint(5, 45))).isoformat(),
                "resolution_time": (random_start + duration).isoformat(),
                "region": asset["region"],
                "affected_service_type": random.choice(config["service_types"]),
                **source_metadata("incident_management", "raw_incidents.csv", batch_id),
            }
        )
        add_bridge(incident_id, impacted_assets(asset))

    return rows, bridge_rows


def generate_telemetry_events(
    config: dict[str, Any],
    network_assets: list[dict[str, Any]],
    incidents: list[dict[str, Any]],
    bridge_asset_ids_by_incident: dict[str, set[str]],
    count: int,
    batch_id: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    primary_incident = incidents[0]
    incident_start = datetime.fromisoformat(primary_incident["start_time"])
    incident_end = datetime.fromisoformat(primary_incident["resolution_time"])
    affected_asset_ids = bridge_asset_ids_by_incident[primary_incident["incident_id"]]
    metrics = [
        ("latency_ms", "ms"),
        ("packet_loss_pct", "percent"),
        ("throughput_mbps", "Mbps"),
        ("backhaul_utilization_pct", "percent"),
        ("rsrp_dbm", "dBm"),
    ]

    for index in range(1, count + 1):
        asset = random.choice(network_assets)
        metric_name, metric_unit = random.choice(metrics)
        event_time = incident_start - timedelta(hours=6) + timedelta(
            seconds=random.randint(0, int((incident_end - incident_start + timedelta(hours=8)).total_seconds()))
        )
        degraded = asset["network_asset_id"] in affected_asset_ids and incident_start <= event_time <= incident_end

        if metric_name == "latency_ms":
            value = random.uniform(70, 180) if degraded else random.uniform(15, 55)
            severity = "Critical" if value > 120 else "Warning" if value > 70 else "Normal"
        elif metric_name == "packet_loss_pct":
            value = random.uniform(2.5, 9.0) if degraded else random.uniform(0.0, 1.2)
            severity = "Critical" if value > 5 else "Warning" if value > 2 else "Normal"
        elif metric_name == "throughput_mbps":
            value = random.uniform(5, 35) if degraded else random.uniform(80, 450)
            severity = "Critical" if value < 15 else "Warning" if value < 50 else "Normal"
        elif metric_name == "backhaul_utilization_pct":
            value = random.uniform(90, 99) if degraded else random.uniform(35, 82)
            severity = "Critical" if value > 95 else "Warning" if value > 85 else "Normal"
        else:
            value = random.uniform(-118, -105) if degraded else random.uniform(-95, -70)
            severity = "Warning" if value < -105 else "Normal"

        rows.append(
            {
                "telemetry_event_id": f"TEL-{index:010d}",
                "network_asset_id": asset["network_asset_id"],
                "event_time": event_time.isoformat(),
                "metric_name": metric_name,
                "metric_value": round(value, 3),
                "metric_unit": metric_unit,
                "severity_band": severity,
                "scenario_id": config["scenario_id"],
                **source_metadata("network_telemetry", "raw_telemetry_events.csv", batch_id),
            }
        )

    return rows


def generate_alarms(
    telemetry_events: list[dict[str, Any]],
    incidents: list[dict[str, Any]],
    bridge_asset_ids_by_incident: dict[str, set[str]],
    count: int,
    batch_id: str,
) -> list[dict[str, Any]]:
    """Attach each alarm to an incident whose bridge actually contains the alarm's asset."""
    abnormal_events = [
        event for event in telemetry_events if event["severity_band"] in {"Warning", "Critical"}
    ]
    if not abnormal_events:
        abnormal_events = telemetry_events
    events_by_asset: dict[str, list[dict[str, Any]]] = {}
    for event in abnormal_events:
        events_by_asset.setdefault(event["network_asset_id"], []).append(event)

    primary_incident = incidents[0]
    rows: list[dict[str, Any]] = []
    for index in range(1, count + 1):
        # Weight toward the headline incident so its alarm timeline is dense enough to demo.
        incident = primary_incident if random.random() < 0.55 else random.choice(incidents)
        candidate_events = [
            event
            for asset_id in bridge_asset_ids_by_incident.get(incident["incident_id"], set())
            for event in events_by_asset.get(asset_id, [])
        ]
        if not candidate_events:
            candidate_events = events_by_asset.get(incident["network_asset_id"], abnormal_events)
        event = random.choice(candidate_events)

        rows.append(
            {
                "alarm_id": f"ALM-{index:08d}",
                "telemetry_event_id": event["telemetry_event_id"],
                "network_asset_id": event["network_asset_id"],
                "incident_id": incident["incident_id"],
                "alarm_type": f"{event['metric_name']} threshold",
                "severity": event["severity_band"],
                "status": weighted_choice(["Cleared", "Active", "Acknowledged"], [70, 15, 15]),
                "raised_time": event["event_time"],
                "cleared_time": (
                    datetime.fromisoformat(event["event_time"]) + timedelta(minutes=random.randint(20, 240))
                ).isoformat(),
                **source_metadata("alarm_monitoring", "raw_alarms.csv", batch_id),
            }
        )

    return rows


def generate_technicians(regions: list[str], count: int, batch_id: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    skill_pool = ["RAN", "Fiber", "IP Network", "Cable", "Customer Premise"]

    for index in range(1, count + 1):
        skills = random.sample(skill_pool, k=random.randint(1, 3))
        rows.append(
            {
                "technician_id": f"TECH-{index:05d}",
                "technician_name": f"Technician {index:05d}",
                "home_region": random.choice(regions),
                "skill_set": "|".join(skills),
                "shift": random.choice(["Morning", "Afternoon", "Night", "On Call"]),
                "availability_status": weighted_choice(["Available", "Assigned", "Off Shift"], [55, 35, 10]),
                **source_metadata("field_ops", "raw_technicians.csv", batch_id),
            }
        )

    return rows


def generate_work_orders(
    incidents: list[dict[str, Any]], technicians: list[dict[str, Any]], count: int, batch_id: str
) -> list[dict[str, Any]]:
    technicians_by_region: dict[str, list[dict[str, Any]]] = {}
    for technician in technicians:
        technicians_by_region.setdefault(technician["home_region"], []).append(technician)

    rows: list[dict[str, Any]] = []
    for index in range(1, count + 1):
        incident = incidents[(index - 1) % len(incidents)]
        technician_pool = technicians_by_region.get(incident["region"]) or technicians
        technician = random.choice(technician_pool)
        created_time = datetime.fromisoformat(incident["detected_time"]) + timedelta(
            minutes=random.randint(5, 90)
        )
        scheduled_time = created_time + timedelta(minutes=random.randint(30, 240))
        completed_time = scheduled_time + timedelta(minutes=random.randint(45, 360))
        status = weighted_choice(["Completed", "In Progress", "Scheduled"], [70, 15, 15])
        resolution_time = datetime.fromisoformat(incident["resolution_time"])
        if status == "Completed" and completed_time > resolution_time:
            # A closed work order cannot finish after its own incident was marked resolved.
            completed_time = resolution_time - timedelta(minutes=random.randint(5, 30))
            scheduled_time = min(scheduled_time, completed_time - timedelta(minutes=15))
        priority = "P1" if incident["severity"] == "High" else "P2" if incident["severity"] == "Medium" else "P3"

        rows.append(
            {
                "work_order_id": f"WO-{index:08d}",
                "incident_id": incident["incident_id"],
                "network_asset_id": incident["network_asset_id"],
                "technician_id": technician["technician_id"],
                "priority": priority,
                "status": status,
                "created_time": created_time.isoformat(),
                "scheduled_time": scheduled_time.isoformat(),
                "completed_time": completed_time.isoformat(),
                **source_metadata("field_ops", "raw_work_orders.csv", batch_id),
            }
        )

    return rows


def generate_support_cases(
    config: dict[str, Any],
    customers: list[dict[str, Any]],
    accounts: list[dict[str, Any]],
    service_instances: list[dict[str, Any]],
    subscriptions: list[dict[str, Any]],
    incidents: list[dict[str, Any]],
    bridge_asset_ids_by_incident: dict[str, set[str]],
    count: int,
    batch_id: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Generate support cases plus an explicit incident-to-service-instance impact bridge.

    A case is only ever opened against a service instance that the incident's asset bridge
    actually reaches, and the case's account/customer are derived *from that instance* rather
    than picked independently - this is what fixes the account/asset mismatch bugs.
    """
    account_lookup = {account["account_id"]: account for account in accounts}
    subscription_lookup = {
        subscription["subscription_id"]: subscription for subscription in subscriptions
    }
    customers_by_account: dict[str, list[str]] = {}
    for customer in customers:
        customers_by_account.setdefault(customer["account_id"], []).append(customer["customer_id"])

    instances_by_asset: dict[str, list[dict[str, Any]]] = {}
    for service_instance in service_instances:
        instances_by_asset.setdefault(service_instance["network_asset_id"], []).append(service_instance)

    def affected_instances(incident: dict[str, Any]) -> list[dict[str, Any]]:
        asset_ids = bridge_asset_ids_by_incident.get(incident["incident_id"], set())
        matches = [
            instance
            for asset_id in asset_ids
            for instance in instances_by_asset.get(asset_id, [])
            if instance["service_type"] == incident["affected_service_type"]
        ]
        if matches:
            return matches
        matches = [instance for asset_id in asset_ids for instance in instances_by_asset.get(asset_id, [])]
        return matches or instances_by_asset.get(incident["network_asset_id"], service_instances)

    affected_instances_by_incident = {incident["incident_id"]: affected_instances(incident) for incident in incidents}
    bridge_rows: list[dict[str, Any]] = []
    for incident in incidents:
        for instance in affected_instances_by_incident[incident["incident_id"]]:
            bridge_rows.append(
                {
                    "incident_id": incident["incident_id"],
                    "service_instance_id": instance["service_instance_id"],
                    **source_metadata("incident_management", "raw_bridge_incident_service.csv", batch_id),
                }
            )

    primary_incident = incidents[0]
    start_time = datetime.fromisoformat(primary_incident["start_time"])
    min_lag = config["incident"]["ticket_lag_min_minutes"]
    max_lag = config["incident"]["ticket_lag_max_minutes"]
    rows: list[dict[str, Any]] = []

    for index in range(1, count + 1):
        if random.random() < 0.65:
            incident = primary_incident
            opened_time = start_time + timedelta(minutes=random.randint(min_lag, max_lag + 240))
        else:
            incident = random.choice(incidents)
            opened_time = datetime.fromisoformat(incident["start_time"]) + timedelta(
                minutes=random.randint(10, 360)
            )

        service_instance = random.choice(affected_instances_by_incident[incident["incident_id"]])
        subscription = subscription_lookup[service_instance["subscription_id"]]
        account = account_lookup[subscription["account_id"]]
        customer_ids = customers_by_account.get(account["account_id"]) or [
            customer["customer_id"] for customer in customers
        ]
        customer_id = random.choice(customer_ids)
        sentiment = random.uniform(-0.95, -0.15) if incident["severity"] == "High" else random.uniform(-0.4, 0.6)

        rows.append(
            {
                "case_id": f"CASE-{index:09d}",
                "customer_id": customer_id,
                "account_id": account["account_id"],
                "service_instance_id": service_instance["service_instance_id"],
                "incident_id": incident["incident_id"],
                "opened_time": opened_time.isoformat(),
                "closed_time": (opened_time + timedelta(minutes=random.randint(20, 1440))).isoformat(),
                "channel": random.choice(["Phone", "Chat", "Retail", "Social", "Email"]),
                "case_reason": random.choice(
                    ["Slow speed", "Intermittent service", "No service", "Dropped connection"]
                ),
                "sentiment_score": round(sentiment, 3),
                "case_status": weighted_choice(["Closed", "Open", "Escalated"], [72, 18, 10]),
                "customer_tier": account["account_tier"],
                "scenario_id": config["scenario_id"],
                **source_metadata("service_support", "raw_support_cases.csv", batch_id),
            }
        )

    return rows, bridge_rows


def generate_sla_exposure(
    accounts: list[dict[str, Any]],
    incidents: list[dict[str, Any]],
    support_cases: list[dict[str, Any]],
    count: int,
    batch_id: str,
) -> list[dict[str, Any]]:
    premium_cases = [
        case for case in support_cases if case["customer_tier"] in {"Premium", "Enterprise"}
    ] or support_cases
    rows: list[dict[str, Any]] = []

    for index in range(1, count + 1):
        case = random.choice(premium_cases)
        incident = next(
            (candidate for candidate in incidents if candidate["incident_id"] == case["incident_id"]),
            random.choice(incidents),
        )
        account = next(
            (candidate for candidate in accounts if candidate["account_id"] == case["account_id"]),
            random.choice(accounts),
        )
        base_amount = 25 if account["account_tier"] == "Premium" else 100
        rows.append(
            {
                "exposure_id": f"SLA-{index:08d}",
                "incident_id": incident["incident_id"],
                "account_id": account["account_id"],
                "customer_tier": account["account_tier"],
                "breach_type": random.choice(["Availability", "Latency", "Resolution Time"]),
                "exposure_amount": round(base_amount * random.uniform(1.0, 8.0), 2),
                "currency": "CAD",
                "exposure_status": weighted_choice(["Estimated", "Approved", "Waived"], [70, 20, 10]),
                **source_metadata("billing", "raw_sla_exposure.csv", batch_id),
            }
        )

    return rows


def generate_churn_risk(
    customers: list[dict[str, Any]],
    support_cases: list[dict[str, Any]],
    primary_incident_id: str,
    batch_id: str,
) -> list[dict[str, Any]]:
    case_counts: dict[str, int] = {}
    primary_incident_customers: set[str] = set()
    for case in support_cases:
        case_counts[case["customer_id"]] = case_counts.get(case["customer_id"], 0) + 1
        if case["incident_id"] == primary_incident_id:
            primary_incident_customers.add(case["customer_id"])

    rows: list[dict[str, Any]] = []
    for index, customer in enumerate(customers, start=1):
        repeat_cases = case_counts.get(customer["customer_id"], 0)
        baseline = random.uniform(0.05, 0.25)
        incident_lift = random.uniform(0.10, 0.22) if customer["customer_id"] in primary_incident_customers else 0.0
        score = min(0.98, baseline + repeat_cases * random.uniform(0.04, 0.12) + incident_lift)
        if incident_lift > 0 and repeat_cases >= 2:
            driver = "Repeat impact from Ontario 5G Home Internet incident"
        elif incident_lift > 0:
            driver = "Ontario 5G Home Internet incident impact"
        elif repeat_cases >= 2:
            driver = "Repeat service issues"
        else:
            driver = "Baseline propensity"
        if score > 0.65:
            risk_band = "High"
        elif score > 0.35:
            risk_band = "Medium"
        else:
            risk_band = "Low"

        rows.append(
            {
                "risk_id": f"RISK-{index:08d}",
                "customer_id": customer["customer_id"],
                "risk_score": round(score, 4),
                "risk_band": risk_band,
                "primary_driver": driver,
                "repeat_case_count": repeat_cases,
                "model_version": "synthetic-v1",
                "scored_time": INGESTION_TIMESTAMP,
                **source_metadata("cx_analytics", "raw_churn_risk.csv", batch_id),
            }
        )

    return rows


def generate_investigations(
    incidents: list[dict[str, Any]],
    bridge_incident_asset: list[dict[str, Any]],
    bridge_incident_service: list[dict[str, Any]],
    support_cases: list[dict[str, Any]],
    sla_exposure: list[dict[str, Any]],
    batch_id: str,
) -> list[dict[str, Any]]:
    """Saved-evidence artifacts, one per High severity incident (OperationsIQ-inspired).

    Mirrors OperationsIQ's "investigation" concept: a durable record of what was found and
    how it was confirmed, linking back to the bridge tables and impact counts instead of
    just a free-text summary. Only High severity incidents get an investigation, since low/
    medium incidents in this scenario are baseline noise, not root-cause narratives worth
    preserving.
    """
    asset_counts: dict[str, int] = {}
    for row in bridge_incident_asset:
        asset_counts[row["incident_id"]] = asset_counts.get(row["incident_id"], 0) + 1

    service_counts: dict[str, int] = {}
    for row in bridge_incident_service:
        service_counts[row["incident_id"]] = service_counts.get(row["incident_id"], 0) + 1

    case_counts: dict[str, int] = {}
    for case in support_cases:
        case_counts[case["incident_id"]] = case_counts.get(case["incident_id"], 0) + 1

    exposure_totals: dict[str, float] = {}
    for exposure in sla_exposure:
        exposure_totals[exposure["incident_id"]] = exposure_totals.get(exposure["incident_id"], 0.0) + float(
            exposure["exposure_amount"]
        )

    rows: list[dict[str, Any]] = []
    index = 1
    for incident in incidents:
        if incident["severity"] != "High":
            continue
        affected_assets = asset_counts.get(incident["incident_id"], 0)
        affected_services = service_counts.get(incident["incident_id"], 0)
        related_cases = case_counts.get(incident["incident_id"], 0)
        exposure_amount = round(exposure_totals.get(incident["incident_id"], 0.0), 2)
        summary = (
            f"{incident['incident_type']} on {incident['region']} traced to {affected_assets} bridged "
            f"network asset(s), impacting {affected_services} service instance(s) and {related_cases} "
            f"support case(s). Estimated SLA exposure: ${exposure_amount:,.2f} CAD. Root cause: "
            f"{incident['root_cause']}."
        )
        rows.append(
            {
                "investigation_id": f"INV-{index:05d}",
                "incident_id": incident["incident_id"],
                "title": f"{incident['affected_service_type']} degradation - {incident['region']}",
                "summary": summary,
                "affected_asset_count": affected_assets,
                "affected_service_count": affected_services,
                "related_case_count": related_cases,
                "sla_exposure_amount": exposure_amount,
                "status": "Confirmed" if incident["status"] == "Resolved" else "In Progress",
                "created_time": incident["resolution_time"],
                "created_by": "fabric-iq-demo-generator",
                **source_metadata("investigations", "raw_investigations.csv", batch_id),
            }
        )
        index += 1

    return rows


def entity_scale(config: dict[str, Any], key: str, default: int) -> int:
    return int(config.get("scale", {}).get(key, default))


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate fabricated telecom ontology demo data.")
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    config = load_config(args.config)
    random.seed(config["seed"])
    fake = Faker("en_CA")
    Faker.seed(config["seed"])
    batch_id = str(uuid.uuid4())

    regions = config["regions"]
    accounts = generate_accounts(fake, regions, entity_scale(config, "accounts", 7500), batch_id)
    customers = generate_customers(fake, accounts, entity_scale(config, "customers", 10000), batch_id)
    products = generate_products(batch_id)
    network_assets = generate_network_assets(regions, entity_scale(config, "network_assets", 300), batch_id)
    subscriptions = generate_subscriptions(
        accounts, products, entity_scale(config, "subscriptions", 15000), batch_id
    )
    devices = generate_devices(subscriptions, products, batch_id)
    service_instances = generate_service_instances(subscriptions, devices, network_assets, accounts, batch_id)
    incidents, bridge_incident_asset = generate_incidents(
        config, network_assets, entity_scale(config, "incidents", 25), batch_id
    )
    bridge_asset_ids_by_incident: dict[str, set[str]] = {}
    for row in bridge_incident_asset:
        bridge_asset_ids_by_incident.setdefault(row["incident_id"], set()).add(row["network_asset_id"])

    telemetry_events = generate_telemetry_events(
        config,
        network_assets,
        incidents,
        bridge_asset_ids_by_incident,
        entity_scale(config, "telemetry_events", 250000),
        batch_id,
    )
    alarms = generate_alarms(
        telemetry_events,
        incidents,
        bridge_asset_ids_by_incident,
        entity_scale(config, "alarms", 500),
        batch_id,
    )
    technicians = generate_technicians(regions, entity_scale(config, "technicians", 120), batch_id)
    work_orders = generate_work_orders(
        incidents, technicians, entity_scale(config, "work_orders", 500), batch_id
    )
    support_cases, bridge_incident_service = generate_support_cases(
        config,
        customers,
        accounts,
        service_instances,
        subscriptions,
        incidents,
        bridge_asset_ids_by_incident,
        entity_scale(config, "support_cases", 2000),
        batch_id,
    )
    sla_exposure = generate_sla_exposure(
        accounts, incidents, support_cases, entity_scale(config, "sla_exposure", 300), batch_id
    )
    churn_risk = generate_churn_risk(customers, support_cases, incidents[0]["incident_id"], batch_id)
    investigations = generate_investigations(
        incidents, bridge_incident_asset, bridge_incident_service, support_cases, sla_exposure, batch_id
    )

    datasets = {
        "raw_accounts.csv": accounts,
        "raw_customers.csv": customers,
        "raw_products.csv": products,
        "raw_subscriptions.csv": subscriptions,
        "raw_devices.csv": devices,
        "raw_service_instances.csv": service_instances,
        "raw_network_assets.csv": network_assets,
        "raw_incidents.csv": incidents,
        "raw_bridge_incident_asset.csv": bridge_incident_asset,
        "raw_bridge_incident_service.csv": bridge_incident_service,
        "raw_telemetry_events.csv": telemetry_events,
        "raw_alarms.csv": alarms,
        "raw_technicians.csv": technicians,
        "raw_work_orders.csv": work_orders,
        "raw_support_cases.csv": support_cases,
        "raw_sla_exposure.csv": sla_exposure,
        "raw_churn_risk.csv": churn_risk,
        "raw_investigations.csv": investigations,
    }

    for file_name, rows in datasets.items():
        write_csv(args.output / file_name, rows)

    for file_name, rows in datasets.items():
        print(f"{file_name}: {len(rows)} rows")


if __name__ == "__main__":
    main()
