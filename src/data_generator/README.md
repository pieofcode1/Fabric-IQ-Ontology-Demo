# Synthetic Data Generator

Generates scenario-driven, causally-consistent fabricated telecom data for the Fabric IQ ontology demo.

## Design goals

- Generate repeatable data using a seed.
- Keep customer, network, incident, support, and work-order data correlated through explicit
  incident-to-asset and incident-to-service-instance bridge tables (`raw_bridge_incident_asset`,
  `raw_bridge_incident_service`) rather than independent random selection.
- Output CSV files for local inspection and Fabric Lakehouse ingestion.
- Make the demo realistic without using real customer or network data.

## Commands

```powershell
uv run --no-sync python .\src\data_generator\generate.py --config .\src\data_generator\config\scenario_config.yaml --output .\sample_output
uv run --no-sync python .\src\data_generator\validate_scenario.py --data .\sample_output
```

`validate_scenario.py` runs 21 acceptance checks that mirror the six customer-facing questions in
`docs/06-demo-script.md` (e.g. "every support case tied to the headline incident traces to a
service instance the incident actually reaches"). Run it after any change to `generate.py` or
`config/scenario_config.yaml` - a change that breaks the causal chain should fail this script,
not surface as a wrong answer during a live demo.

## Run without a local Python setup (Fabric-native)

If your organization doesn't allow local package installs, run the generator entirely inside
Fabric instead of on your machine: `notebooks/Generate_Nimbus_Scenario_Data.ipynb` calls the
exact same `build_datasets()` and `run_validation()` functions that the local CLI calls, so the
output and the 21/21 acceptance checks are identical either way - no generation logic is
duplicated between the two paths.

1. Run `deployment/Create-FabricAssets.ps1` (default behavior uploads `generate.py`,
   `validate_scenario.py`, and `config/scenario_config.yaml` to
   `Files/src/data_generator/` in the Bronze lakehouse; pass `-SkipGeneratorSourceUpload` to
   opt out).
2. Import `notebooks/Generate_Nimbus_Scenario_Data.ipynb` into the
   `{prefix}_generate_scenario_data` notebook item the script creates, and attach it to the
   Bronze lakehouse as its default lakehouse.
3. Run it top to bottom. It `%pip install`s `faker`/`pyyaml` into the session only (not your
   machine), imports the two uploaded source files as modules, generates all 18 tables, writes
   them as Delta tables and/or CSVs under `Files/landing/raw/` depending on the `output_mode`
   parameter, and runs the same 21 acceptance checks against the CSV output.

Both code paths (local CLI and Fabric notebook) are validated against the same
`build_datasets()`/`run_validation()` functions in `generate.py`/`validate_scenario.py`, so a
regression in the causal-integrity logic fails identically in both places.

## Network topology

Each region has its own backhaul links, cell sites/sectors, fiber nodes, routers, and CMTS
devices. Cell sectors are parented (`parent_asset_id`) to a backhaul link in the same region,
so an incident on a backhaul link causally explains degradation on a known, traceable set of
dependent sectors - the "shared backhaul path" the demo script refers to.

## Live streaming replay

`stream_simulator.py` turns the static telemetry/alarm CSVs into a live, wall-clock-paced event
feed for a real-time demo:

```powershell
uv run --no-sync python .\src\data_generator\stream_simulator.py --data .\sample_output --incident INC-2026-ONT-001 --speed 60
```

By default it scopes to one incident's bridge (`raw_bridge_incident_asset.csv`) plus a time
window around it - about 5,750 events for the headline incident instead of the full 250k-row
telemetry table - and rebases every timestamp so the incident starts a couple of minutes after
you hit run, instead of showing the fixed 2026-06-16 scenario date. `--sink` supports `stdout`
(default), `file` (JSON lines), or `eventhub` (any Event Hub-compatible endpoint, including a
Fabric Eventstream "Custom App" source - see the script's module docstring for the exact
`uv add azure-eventhub` + connection-string wiring). `--speed` controls how many simulated
seconds elapse per real second; `--loop` restarts the replay indefinitely for a booth demo.

