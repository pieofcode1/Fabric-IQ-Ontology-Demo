# Nimbus Fabric IQ Semantic Model

This folder defines an IQ-friendly semantic model over the fabricated telecom datasets in `sample_output\`.

The model is designed around business entities, not raw file names. It can be used as the blueprint for:

- Fabric Direct Lake semantic model authoring.
- Fabric IQ ontology grounding.
- Power BI executive and operational reports.
- Natural-language Q&A over network, support, operations, and customer impact.

## Files

| File | Purpose |
|---|---|
| `semantic_model.yml` | Canonical semantic model definition: tables, columns, measures, relationships |
| `iq_synonyms.yml` | Business terms and synonyms to improve Fabric IQ interpretation |
| `relationship_graph.mmd` | Mermaid graph of semantic-model relationships |
| `tmdl\model.tmdl` | Starter TMDL-style model metadata |
| `tmdl\relationships.tmdl` | Starter TMDL-style relationship definitions |
| `tmdl\measures.tmdl` | Starter TMDL-style measure definitions |

## Modeling approach

The semantic model uses conformed business names and hides raw dataset prefixes:

| Raw generated file | Semantic table |
|---|---|
| `raw_accounts.csv` | Account |
| `raw_customers.csv` | Customer |
| `raw_products.csv` | Product |
| `raw_subscriptions.csv` | Subscription |
| `raw_devices.csv` | Device |
| `raw_service_instances.csv` | Service Instance |
| `raw_network_assets.csv` | Network Asset |
| `raw_incidents.csv` | Incident |
| `raw_telemetry_events.csv` | Telemetry Event |
| `raw_alarms.csv` | Alarm |
| `raw_technicians.csv` | Technician |
| `raw_work_orders.csv` | Work Order |
| `raw_support_cases.csv` | Support Case |
| `raw_sla_exposure.csv` | SLA Exposure |
| `raw_churn_risk.csv` | Churn Risk |

## IQ design principles

- Use singular, business-friendly table names.
- Add descriptions for every major table and measure.
- Prefer explicit relationship names that match telecom language.
- Keep customer, service, network, support, and operations paths navigable.
- Add synonyms for domain terms such as tower, outage, ticket, dispatch, SLA credit, churn risk, and service degradation.

