# Activator Rule: 5G Home Internet Degradation Alert

Ready-to-import artifacts for the Activator closed-loop design described in
`docs/10-operationsiq-alignment.md`. These were never deployed live (this repo has no Fabric
tenant credentials); they exist so a real deployment can import a working starting point instead
of authoring a rule from scratch.

## What's here

| File | Purpose |
|---|---|
| `network_degradation_query.kql` | KQL query for the Activator's `kqlSource-v1` data source. Reads `network_telemetry`, scopes to `packet_loss_pct` readings on assets bridged to a High severity incident. |
| `ReflexEntities.template.json` | A Fabric Activator (`reflexes`) item definition: Container -> KQL Source -> SourceEvent -> EventTrigger Rule -> Teams action. Fires when `metric_value` (packet loss %) becomes greater than 5 on a bridged asset, and posts a Teams message with the asset, incident, and region. |

## Prerequisites before importing

1. A live Fabric workspace with an Eventhouse/KQL database populated by `stream_simulator.py`
   (or a scheduled pipeline) writing to a `network_telemetry` table with the columns
   `event_time`, `network_asset_id`, `metric_name`, `metric_value`, `severity_band`.
2. A `network_incident_bridge` lookup table in the same KQL database, mirroring
   `raw_bridge_incident_asset` joined to `raw_incidents` (columns: `network_asset_id`,
   `incident_id`, `severity`, `region`). This isn't produced by the generator/pipeline yet -
   it needs to be added as a Silver/Gold-to-Eventhouse export step.

## How to import

`ReflexEntities.template.json` is a **template**, not something to paste in as-is:

1. Regenerate every `uniqueIdentifier` GUID (the placeholders all start with
   `11111111-1111-4111-8111-...`) with a fresh `uuid4()` - duplicate GUIDs corrupt the
   definition.
2. Replace `<workspace-id>` and `<kql-database-item-id>` with the real Fabric workspace ID and
   KQL Database item ID.
3. Update `recipients` in the Teams action (currently `noc-team@nimbuscomms.example`) to a real
   distribution list or channel-connected email.
4. Create (or reuse) an Activator item, then call `updateDefinition` with this file
   Base64-encoded as the `ReflexEntities.json` part - see the `activator-authoring-cli` skill for
   the exact `az rest` / Python workflow (GUID handling, LRO polling, Base64 encoding).

## Design notes

- Uses `NumberBecomes`/`BecomesGreaterThan` (transition-based) rather than a steady-state
  `IsGreaterThan` condition, so the alert fires once per crossing instead of on every polling
  interval while packet loss remains elevated.
- The KQL query only *scopes* the data (bridged assets of a High severity incident); the actual
  `> 5` threshold lives in the rule's `EventDetectStep`, not the query, per Activator authoring
  guidance (detection logic belongs in the rule, not the data source).
