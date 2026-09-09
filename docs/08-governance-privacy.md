# Governance and Privacy

## Data-use rule

This demo must use fabricated data only. Do not include real customer records, real network inventory, real support tickets, real incident data, real billing records, or real operational telemetry.

## Naming guidance

Use Nimbus Communications-inspired business context only where appropriate for the customer conversation. Keep synthetic entities clearly fictional:

- Invent customer names and account names.
- Invent network asset IDs.
- Use synthetic ticket IDs, incident IDs, and work order IDs.
- Avoid real cell-site identifiers or exact infrastructure topology.

## Recommended labels

For internal demo artifacts, use an appropriate sensitivity label before sharing externally. Synthetic data can still look realistic and should be handled with care to avoid confusion.

## Responsible AI considerations

- Clearly state that churn risk, sentiment, and recommendations are simulated.
- Avoid implying model accuracy or production readiness.
- Explain that real deployment would require privacy review, telecom data governance, lineage, access controls, and validation with domain experts.

## Access-control model

| Layer | Access pattern |
|---|---|
| Bronze | Engineering-only write access |
| Silver | Data engineering and data quality teams |
| Gold | BI developers, analysts, ontology builders |
| Semantic model | Business users and demo participants |
| Eventhouse | NOC and data engineering demo users |

