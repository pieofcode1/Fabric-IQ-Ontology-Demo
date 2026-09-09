# Reference Architecture

## Logical architecture

The solution uses a medallion architecture in Microsoft Fabric with ontology and semantic consumption layers on top.

| Layer | Fabric capability | Demo responsibility |
|---|---|---|
| Source simulation | Python generator, Eventstream simulator | Create fabricated batch and real-time telecom data |
| Bronze | Fabric Lakehouse, Delta tables | Land raw data with ingestion metadata |
| Silver | Spark notebooks, Data Engineering | Clean, deduplicate, conform, correlate, enrich |
| Gold | Lakehouse or Warehouse | Curated facts, dimensions, and KPI aggregates |
| Real-time | Eventhouse, KQL database | Network telemetry, alarms, incident streams |
| Semantic | Power BI semantic model | Direct Lake metrics and reporting layer |
| Ontology | Fabric IQ | Business entities, relationships, synonyms, and natural-language grounding |
| Experience | Power BI, Fabric IQ Q&A, demo script | Executive and operational investigation |

## Recommended workspace strategy

For a customer-facing enterprise demo, use separate Fabric workspaces by layer:

| Workspace | Contents |
|---|---|
| `nimbus-iq-bronze-dev` | Raw landing lakehouse and ingestion pipeline |
| `nimbus-iq-silver-dev` | Cleaned and conformed lakehouse |
| `nimbus-iq-gold-dev` | Curated lakehouse, semantic model, reports |
| `nimbus-iq-realtime-dev` | Eventhouse and network telemetry streams |

For a lightweight local proof of concept, a single workspace with separate lakehouses is acceptable, but it weakens the governance story.

## Medallion design

Bronze principles:

- Preserve raw fabricated source shape.
- Add `ingestion_timestamp`, `source_system`, `source_file`, and `batch_id`.
- Partition large data by `ingestion_date`.

Silver principles:

- Standardize identifiers and naming.
- Deduplicate natural keys.
- Enforce valid ranges for telemetry, dates, and categorical values.
- Add derived fields such as region, customer tier, issue class, and service health band.

Gold principles:

- Build star-schema-friendly facts and dimensions.
- Pre-aggregate high-value KPIs for Direct Lake reporting.
- Optimize for Power BI filters by date, region, service type, product, customer segment, and incident.

## Architecture diagram

See `architecture\medallion-architecture.mmd`.

