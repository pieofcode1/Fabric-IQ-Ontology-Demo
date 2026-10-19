# Nimbus Fabric IQ Semantic Model

This folder defines an IQ-friendly semantic model over the curated Gold tables derived from the fabricated telecom datasets.
[semantic_model.yml](semantic_model.yml) now points to the tables produced by [the Gold notebook](../notebooks/Transform_Nimbus_Silver_To_Gold.ipynb), including the physical calendar and both incident bridges.
Follow step 6 of the [deployment runbook](../docs/12-deployment-runbook.md) to materialize them before creating a Direct Lake model.
The mapping below lists deployed Gold sources, not raw CSV filenames.
For the complete model-and-report authoring sequence, use [the step 7 guide](../docs/09-semantic-model-for-iq.md).
It selects 20 of the 24 Gold tables and provides exact physical-to-semantic renames before applying the scripts.

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
| [tmdl/model.tmdl](tmdl/model.tmdl) | Merge-only model property fragment; insert into a fresh full-model script, never apply alone |
| [tmdl/relationships.tmdl](tmdl/relationships.tmdl) | TMDL view script for 31 explicit active/inactive relationships |
| [tmdl/measures.tmdl](tmdl/measures.tmdl) | TMDL view script for 27 scoped measures, including Gold dispatch scoring |
| [validate_model.dax](validate_model.dax) | Read-only post-apply checks for incident filtering, dispatch-score agreement, and relationships |

The relationship and measure files are scripts beginning with `createOrReplace`, not a complete semantic-model definition folder.
The model file is a property fragment, not an executable script: generate the complete current semantic model in TMDL view, merge its properties under the ordinary `model` declaration, preserve every descendant/source binding, and preview the full script before applying.
Do not put properties under `ref model`, and do not apply a tiny `createOrReplace model` script that omits the model's tables.
After that model-property update succeeds, apply the relationship and measure scripts in separate tabs using **Preview > Apply**.
Do not place the scripts in a PBIP `definition/` folder or use them alone as a Fabric API `-DefinitionDirectory`.
Keep the complete exported model definition separate from these scripts.

## Modeling approach

Rename only the semantic table to the business name; keep the physical Gold table and partition/source bindings unchanged:

| Gold table | Semantic table |
|---|---|
| `dim_date` | Date |
| `dim_account` | Account |
| `dim_customer` | Customer |
| `dim_product` | Product |
| `bridge_subscription` | Subscription |
| `dim_device` | Device |
| `dim_service_instance` | Service Instance |
| `dim_network_asset` | Network Asset |
| `fact_incident` | Incident |
| `fact_network_telemetry` | Telemetry Event |
| `fact_alarm` | Alarm |
| `dim_technician` | Technician |
| `fact_work_order` | Work Order |
| `fact_support_case` | Support Case |
| `fact_sla_exposure` | SLA Exposure |
| `fact_churn_risk` | Churn Risk |
| `bridge_incident_asset` | Bridge Incident Asset |
| `bridge_incident_service` | Bridge Incident Service |
| `fact_investigation` | Investigation |
| `agg_dispatch_priority` | Dispatch Priority |

The four additional Gold tables are optional: `dim_region`, `fact_network_telemetry_hourly`, `agg_service_health_daily`, and `agg_customer_impact_by_incident`.

## IQ design principles

- Use singular, business-friendly table names.
- Add descriptions for every major table and measure.
- Prefer explicit relationship names that match telecom language.
- Keep customer, service, network, support, and operations paths navigable.
- Add synonyms for domain terms such as tower, outage, ticket, dispatch, SLA credit, churn risk, and service degradation.
