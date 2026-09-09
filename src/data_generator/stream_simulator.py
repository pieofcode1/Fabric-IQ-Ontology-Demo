"""Replay generated telemetry/alarm rows as a live, "now"-anchored event stream.

This closes the gap between the architecture diagram's "Telemetry Stream Simulator" box
(architecture/medallion-architecture.mmd) and reality: until this script existed, nothing in
the repo actually produced a stream. `generate.py` only writes static, historically-dated CSVs.

What this does:
  1. Loads raw_telemetry_events.csv and raw_alarms.csv (generate.py output).
  2. Optionally narrows to one incident's blast radius via raw_bridge_incident_asset.csv, so a
     live demo replays a watchable few thousand rows instead of the full 250k-row dataset.
  3. Rebases every timestamp so the incident starts a few minutes after you hit run (--anchor
     now, the default) instead of showing the fixed 2026-06-16 scenario date.
  4. Paces emission in wall-clock time at --speed (simulated-seconds-per-real-second), so the
     pre-incident/during/post-incident telemetry story plays out live and on-screen.
  5. Sends each row to stdout (default), a JSON-lines file, or an Event Hub-compatible endpoint
     (what Fabric Eventstream's "Custom App" source gives you) via --sink.

Quick start (no Azure/Fabric setup required):

    uv run --no-sync python .\\src\\data_generator\\stream_simulator.py --data .\\sample_output --incident INC-2026-ONT-001 --speed 120

Wire it to a Fabric Eventstream Custom App source:

    uv add azure-eventhub
    $env:EVENTSTREAM_CONNECTION_STRING = "<connection string from the Eventstream Custom App source>"
    $env:EVENTSTREAM_EVENTHUB_NAME = "<event hub name from the same source>"
    uv run python .\\src\\data_generator\\stream_simulator.py --data .\\sample_output --incident INC-2026-ONT-001 --sink eventhub
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable


@dataclass
class Event:
    table: str
    time_field: str
    row: dict[str, Any]

    @property
    def event_time(self) -> datetime:
        return datetime.fromisoformat(self.row[self.time_field])


def load_csv(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def bridge_asset_ids(data_dir: Path, incident_id: str) -> set[str]:
    rows = load_csv(data_dir / "raw_bridge_incident_asset.csv")
    return {row["network_asset_id"] for row in rows if row["incident_id"] == incident_id}


def incident_window(data_dir: Path, incident_id: str, pad_hours: float) -> tuple[datetime, datetime] | None:
    for row in load_csv(data_dir / "raw_incidents.csv"):
        if row["incident_id"] == incident_id:
            start = datetime.fromisoformat(row["start_time"]) - timedelta(hours=pad_hours)
            end = datetime.fromisoformat(row["resolution_time"]) + timedelta(hours=pad_hours)
            return start, end
    return None


def load_events(
    data_dir: Path,
    incident_id: str | None,
    pad_hours: float,
) -> list[Event]:
    asset_filter: set[str] | None = None
    window: tuple[datetime, datetime] | None = None
    if incident_id:
        asset_filter = bridge_asset_ids(data_dir, incident_id)
        window = incident_window(data_dir, incident_id, pad_hours)

    events: list[Event] = []
    for row in load_csv(data_dir / "raw_telemetry_events.csv"):
        if asset_filter and row["network_asset_id"] not in asset_filter:
            continue
        event = Event(table="telemetry_events", time_field="event_time", row=row)
        if window and not (window[0] <= event.event_time <= window[1]):
            continue
        events.append(event)

    for row in load_csv(data_dir / "raw_alarms.csv"):
        if asset_filter and row["network_asset_id"] not in asset_filter:
            continue
        event = Event(table="alarms", time_field="raised_time", row=row)
        if window and not (window[0] <= event.event_time <= window[1]):
            continue
        events.append(event)

    events.sort(key=lambda event: event.event_time)
    return events


def rebase_row(event: Event, offset: timedelta) -> dict[str, Any]:
    """Shift every timestamp-looking field in the row by `offset` so it reads as "live"."""
    row = dict(event.row)
    for field in ("event_time", "raised_time", "cleared_time"):
        if row.get(field):
            row[field] = (datetime.fromisoformat(row[field]) + offset).isoformat()
    return row


def make_sink(args: argparse.Namespace) -> Callable[[str, dict[str, Any]], None]:
    if args.sink == "stdout":
        def sink(table: str, payload: dict[str, Any]) -> None:
            print(json.dumps({"table": table, **payload}))
        return sink

    if args.sink == "file":
        output_path = Path(args.output or "stream_output.jsonl")
        handle = output_path.open("a", encoding="utf-8")

        def sink(table: str, payload: dict[str, Any]) -> None:
            handle.write(json.dumps({"table": table, **payload}) + "\n")
            handle.flush()
        return sink

    if args.sink == "eventhub":
        try:
            from azure.eventhub import EventData, EventHubProducerClient
        except ImportError as exc:  # pragma: no cover - exercised only without the optional dep
            raise SystemExit(
                "azure-eventhub is not installed. Run `uv add azure-eventhub`, then set "
                "EVENTSTREAM_CONNECTION_STRING and EVENTSTREAM_EVENTHUB_NAME to the values from "
                "your Fabric Eventstream 'Custom App' source before using --sink eventhub."
            ) from exc

        import os

        connection_string = args.eventhub_connection_string or os.environ.get("EVENTSTREAM_CONNECTION_STRING")
        eventhub_name = args.eventhub_name or os.environ.get("EVENTSTREAM_EVENTHUB_NAME")
        if not connection_string or not eventhub_name:
            raise SystemExit(
                "Missing Event Hub connection details. Pass --eventhub-connection-string/--eventhub-name "
                "or set EVENTSTREAM_CONNECTION_STRING/EVENTSTREAM_EVENTHUB_NAME."
            )
        producer = EventHubProducerClient.from_connection_string(
            conn_str=connection_string, eventhub_name=eventhub_name
        )

        def sink(table: str, payload: dict[str, Any]) -> None:
            batch = producer.create_batch()
            batch.add(EventData(json.dumps({"table": table, **payload})))
            producer.send_batch(batch)
        return sink

    raise SystemExit(f"Unknown sink: {args.sink}")


def replay(events: list[Event], args: argparse.Namespace, sink: Callable[[str, dict[str, Any]], None]) -> None:
    if not events:
        print("No events matched the requested incident/window filters.", file=sys.stderr)
        return

    scenario_start = events[0].event_time
    now = datetime.now(timezone.utc).astimezone(scenario_start.tzinfo)
    offset = (now + timedelta(minutes=args.lead_minutes)) - scenario_start if args.anchor == "now" else timedelta(0)

    replay_started = time.monotonic()
    for event in events:
        elapsed_scenario_seconds = (event.event_time - scenario_start).total_seconds()
        target_wall_seconds = elapsed_scenario_seconds / args.speed
        remaining = target_wall_seconds - (time.monotonic() - replay_started)
        if remaining > 0:
            time.sleep(min(remaining, 5.0) if args.max_sleep is None else min(remaining, args.max_sleep))
            # Loop again in case a long remaining time was capped by max_sleep.
            while (time.monotonic() - replay_started) < target_wall_seconds:
                time.sleep(min(target_wall_seconds - (time.monotonic() - replay_started), 1.0))
        sink(event.table, rebase_row(event, offset))

    print(
        f"Replay complete: {len(events)} events over "
        f"{(events[-1].event_time - scenario_start).total_seconds() / 60:.1f} simulated minutes.",
        file=sys.stderr,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay generated telemetry/alarms as a live event stream.")
    parser.add_argument("--data", required=True, type=Path, help="Directory with generate.py output CSVs.")
    parser.add_argument("--incident", default="INC-2026-ONT-001", help="Incident ID to scope the replay to. Use '' for all data.")
    parser.add_argument("--window-pad-hours", type=float, default=2.0, help="Hours of pre/post buffer around the incident window.")
    parser.add_argument("--speed", type=float, default=60.0, help="Simulated seconds per real second (60 = 1 simulated hour per real minute).")
    parser.add_argument("--anchor", choices=["now", "original"], default="now", help="Rebase timestamps to start near now, or keep original scenario dates.")
    parser.add_argument("--lead-minutes", type=float, default=2.0, help="Minutes from start until the first event fires (anchor=now only).")
    parser.add_argument("--max-sleep", type=float, default=None, help="Cap each sleep interval in seconds (useful for responsive Ctrl+C).")
    parser.add_argument("--loop", action="store_true", help="Restart the replay (with a fresh 'now' anchor) after it completes.")
    parser.add_argument("--sink", choices=["stdout", "file", "eventhub"], default="stdout")
    parser.add_argument("--output", help="Output file path when --sink file.")
    parser.add_argument("--eventhub-connection-string")
    parser.add_argument("--eventhub-name")
    args = parser.parse_args()

    incident_id = args.incident or None
    events = load_events(args.data, incident_id, args.window_pad_hours)
    sink = make_sink(args)

    replay(events, args, sink)
    while args.loop:
        replay(events, args, sink)


if __name__ == "__main__":
    main()
