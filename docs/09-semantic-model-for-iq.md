# Semantic Model for Fabric IQ

## Purpose

The semantic model connects the fabricated telecom entities into a business-friendly model that Fabric IQ can reason over. It is intentionally named with business concepts rather than raw table names so users can ask natural questions about customers, towers, incidents, tickets, work orders, SLA exposure, and churn risk.

## Recommended semantic tables

| Semantic table | Role | Raw source |
|---|---|---|
| Account | Dimension | `raw_accounts.csv` |
| Customer | Dimension | `raw_customers.csv` |
| Product | Dimension | `raw_products.csv` |
| Subscription | Bridge / dimension | `raw_subscriptions.csv` |
| Device | Dimension | `raw_devices.csv` |
| Service Instance | Bridge | `raw_service_instances.csv` |
| Network Asset | Dimension | `raw_network_assets.csv` |
| Incident | Fact | `raw_incidents.csv` |
| Telemetry Event | Fact | `raw_telemetry_events.csv` |
| Alarm | Fact | `raw_alarms.csv` |
| Support Case | Fact | `raw_support_cases.csv` |
| Technician | Dimension | `raw_technicians.csv` |
| Work Order | Fact | `raw_work_orders.csv` |
| SLA Exposure | Fact | `raw_sla_exposure.csv` |
| Churn Risk | Fact | `raw_churn_risk.csv` |

## Most important IQ traversal paths

### Complaint root-cause path

```text
Support Case
  -> Incident
  -> Network Asset
  -> Telemetry Event
```

Use for questions like:

- Why are complaints rising in Toronto West?
- What network issue is driving support calls?
- Which metrics changed before complaints increased?

### Customer impact path

```text
Incident
  -> Support Case
  -> Customer
  -> Account
  -> SLA Exposure
  -> Churn Risk
```

Use for questions like:

- Which customers are affected by this incident?
- Which enterprise accounts have SLA exposure?
- Which customers have high churn risk after repeat issues?

### Service-to-network path

```text
Account
  -> Subscription
  -> Product
  -> Service Instance
  -> Network Asset
```

Use for questions like:

- Which services are served by a degraded tower?
- Which products are most affected?
- Which 5G Home Internet customers are connected to affected sectors?

### Operations remediation path

```text
Incident
  -> Work Order
  -> Technician
  -> Network Asset
  -> SLA Exposure
```

Use for questions like:

- Which work orders should be prioritized?
- Which technician is assigned to the highest-impact incident?
- What is the SLA exposure for open work orders?

## Measures to expose

Expose these measures with descriptions so Fabric IQ can select them reliably:

| Measure | Why it matters |
|---|---|
| Total Customers | Customer base size |
| Active Subscriptions | Active service footprint |
| Monthly Recurring Revenue | Revenue impact |
| Network Assets | Network footprint |
| Open Incidents | Current operational load |
| High Severity Incidents | Urgent service-impacting issues |
| Average Incident Resolution Hours | MTTR proxy |
| Critical Telemetry Events | Network degradation signal |
| Average Latency | Performance quality |
| Average Packet Loss | Service quality |
| Support Cases | Customer complaint volume |
| Escalated Cases | Support pressure |
| Average Sentiment | Customer experience |
| Work Orders | Field operations workload |
| P1 Work Orders | Urgent remediation work |
| SLA Exposure Amount | Financial exposure |
| High Churn Risk Customers | Retention risk |
| Average Churn Risk Score | Overall churn-risk trend |

## Files generated

The semantic model artifacts are in `semantic_model\`:

- `semantic_model.yml`
- `iq_synonyms.yml`
- `relationship_graph.mmd`
- `tmdl\model.tmdl`
- `tmdl\relationships.tmdl`
- `tmdl\measures.tmdl`

## Deployment note

The TMDL files are starter authoring assets. Before deploying to a Fabric Direct Lake semantic model, confirm the final Gold table names and column names. The cleanest production path is:

1. Land raw CSVs into Bronze.
2. Create conformed Silver tables.
3. Create Gold tables using the business names in `semantic_model.yml`.
4. Create a Direct Lake semantic model over Gold.
5. Add relationships, descriptions, measures, and synonyms.
6. Ground Fabric IQ on the semantic model and ontology terms.

