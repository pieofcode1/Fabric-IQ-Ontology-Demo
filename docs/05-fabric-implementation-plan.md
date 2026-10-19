# Fabric Implementation Plan

For step-by-step execution, follow [Capacity to Deployment Runbook](12-deployment-runbook.md).
This document describes design phases rather than an executable deployment sequence.

## Build phases

### Phase 1: Local synthetic data and contracts

- Finalize entity and relationship definitions.
- Generate small scenario-driven CSV or Parquet files.
- Validate referential integrity across customer, service, network, support, and operations tables.
- Produce data dictionary and sample rows for review.

### Phase 2: Bronze Lakehouse

- Land raw files in the Bronze Lakehouse `Files\landing` area.
- Create Bronze Delta tables with ingestion metadata:
  - `ingestion_timestamp`
  - `ingestion_date`
  - `source_system`
  - `source_file`
  - `batch_id`
- Keep source-level structure for auditability.

### Phase 3: Silver Lakehouse

Use [the Bronze-to-Silver notebook](../notebooks/Transform_Nimbus_Bronze_To_Silver.ipynb) after Bronze generation passes validation.

- Conform all keys and data types.
- Standardize field names to snake_case.
- Deduplicate natural keys.
- Validate telemetry ranges and incident timestamps.
- Validate support-case links through the explicit incident-service and incident-asset bridges and the owning account, rather than inferring impact from region alone.

### Phase 4: Gold Lakehouse or Warehouse

Use [the Silver-to-Gold notebook](../notebooks/Transform_Nimbus_Silver_To_Gold.ipynb) to materialize all 24 contracted Gold tables.

Create curated tables for analytics and ontology grounding:

- `dim_customer`
- `dim_account`
- `dim_product`
- `dim_service_instance`
- `dim_network_asset`
- `dim_region`
- `fact_network_telemetry_hourly`
- `fact_support_case`
- `fact_incident`
- `fact_work_order`
- `fact_sla_exposure`
- `fact_churn_risk`
- `agg_service_health_daily`
- `agg_customer_impact_by_incident`
- `agg_dispatch_priority`

### Phase 5: Eventhouse and real-time simulation

- Stream telemetry and alarms into Eventhouse.
- Build KQL queries for high-latency, packet-loss, outage, and anomaly patterns.
- Join live alerts to incident and asset dimensions for demo investigation.

### Phase 6: Semantic model and Power BI

- Build Direct Lake semantic model over Gold tables.
- Measures:
  - affected subscribers
  - average latency
  - packet loss rate
  - complaint rate
  - open incidents
  - MTTR
  - SLA exposure
  - churn risk lift
  - dispatch priority score
- Create pages for executive, network operations, support, and field operations views.

### Phase 7: Fabric IQ ontology

- Define ontology entities from Gold dimensions and facts.
- Map relationships using stable IDs.
- Add business synonyms and example questions.
- Validate natural-language traversal across network, customer, support, and operations domains.

## Fabric design choices

| Decision | Recommendation |
|---|---|
| Medallion separation | Separate Bronze, Silver, and Gold lakehouses |
| Workspace model | Separate workspaces for enterprise demo; single workspace acceptable for POC |
| Semantic model | Direct Lake over Gold tables |
| Real-time telemetry | Eventhouse for network events and alarms |
| Data generation | Local Python first, then Fabric Spark scale-out |
| Ontology grounding | Gold tables plus carefully named relationships |

