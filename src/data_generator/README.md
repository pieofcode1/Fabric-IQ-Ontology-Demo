# Synthetic Data Generator

Generates scenario-driven, causally-consistent fabricated telecom data for the Fabric IQ ontology demo.

## Design goals

- Generate repeatable data using a seed.
- Keep customer, network, incident, support, and work-order data correlated through explicit
  incident-to-asset and incident-to-service-instance bridge tables (`raw_bridge_incident_asset`,
  `raw_bridge_incident_service`) rather than independent random selection.
- Output CSV files for local inspection and Fabric Lakehouse ingestion.
- Make the demo realistic without using real customer or network data.

## First-version scope and boundaries

The generator is a reusable **Industry (Telco) Synthetic Data** asset for the
`ontario_5g_home_internet_degradation` use case, not a general-purpose telecom simulator.
The golden scenario is `INC-2026-ONT-001`: Toronto West backhaul congestion after a delayed
capacity upgrade, with downstream service degradation, support cases, work orders, simulated
SLA exposure, and churn risk. Other incidents and products supply background context rather
than a promise of complete scenario coverage.

The current output is 18 CSV datasets, including explicit incident-asset and incident-service
bridges plus saved investigations. The Fabric generation notebook calls the same code;
Silver/Gold transformations are a separate step. The replay script emits telemetry and alarms
for the RTI/Eventhouse demonstration, not changes to every business table.
See the root [scope and asset-readiness guide](../../README.md#first-version-scope-and-boundaries)
and the [deployment runbook](../../docs/12-deployment-runbook.md) for the surrounding solution.

## Limitations

- All identities, topology, events, sentiment, risk scores, and financial exposure are
  fabricated. The data demonstrates a designed causal story, not a trained predictive model,
  production SLA calculation, or validated representation of a real operator.
- The configuration controls a bounded scenario, seed, regions, scale, and incident settings;
  it is not a scenario plug-in engine. Changing the label or root-cause text does not implement
  a new failure mechanism.
- Generation creates an in-memory, fixed-date snapshot. Source metadata includes fixed June
  2026 values; it is not a production ingestion clock. Replay rebases telemetry/alarm dates,
  but does not synchronize cases, work orders, investigations, or risk/exposure snapshots to
  that new clock.
- The 21 acceptance checks cover the configured golden story and selected integrity rules,
  not every possible background incident or arbitrary scale/configuration combination.
  Rerun validation after changes; do not assume new scenarios inherit the same guarantees.
- There is no autonomous remediation, real-network connector, real customer ingestion, or
  Foundry integration. A replay script is available, but live RTI ingestion and downstream
  Fabric experiences still need tenant setup and verification.

## Future Releases

Candidate extensions, not current features or committed release dates:

- Add independently validated failure scenarios with configurable onset, impact, recovery,
  and expected-answer fixtures.
- Make scenario dates and ingestion metadata configurable and align replay-time business
  snapshots with telemetry where the demonstration requires it.
- Add broader configuration/scale coverage and resource-efficient generation for larger demos.
- Add a managed/Fabric-native replay runner and verified Eventstream/Eventhouse mappings.

Prioritize end-to-end verification of the current scenario before expanding the generator.
Any extension must preserve synthetic-only data use and add scenario-specific acceptance checks.

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
