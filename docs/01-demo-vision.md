# Demo Vision

## Objective

Build a Fabric IQ Ontology demo for a fictional Canadian telecom services provider, Nimbus Communications. The demo should show how Fabric can unify network, operations, service support, and customer-impact data into a governed business ontology that supports executive dashboards and natural-language investigation.

## Core storyline

Customers in selected Ontario markets experience degraded 5G Home Internet and mobile service. Support ticket volumes rise, network telemetry shows worsening latency and packet loss, and field operations has multiple open work orders. Fabric IQ connects these signals to explain root cause, quantify impact, and recommend next operational actions.

## Primary demo question

Why are complaints rising in a specific region, which network assets are causing the issue, which customers are affected, and what should operations prioritize?

## Personas

| Persona | What they care about | Demo value |
|---|---|---|
| Executive sponsor | Revenue, churn, SLA exposure, customer experience | Unified impact view across network and customer operations |
| Network operations leader | Network health, alarms, affected assets, MTTR | Faster root-cause investigation |
| Field operations manager | Work order priority, dispatch efficiency, technician utilization | Better prioritization based on customer and SLA impact |
| Service support leader | Ticket spikes, sentiment, repeat callers, escalations | Explain complaint drivers and improve agent response |
| Data and AI leader | Governed semantic layer, reusable data products, Copilot-ready ontology | Demonstrate Fabric as the enterprise data and AI foundation |

## Scope

In scope:

- Synthetic telecom customer and subscription data.
- Fabricated network assets, telemetry, incidents, alarms, and work orders.
- Fabricated support tickets, call/chat summaries, sentiment, and SLA exposure.
- Ontology design across customer, service, network, operations, and business domains.
- Medallion lakehouse pattern and Direct Lake semantic model design.

Out of scope for the first version:

- Real telecom operator data ingestion.
- Real network inventory integration.
- Production-grade MDM, privacy engineering, and telecom OSS/BSS integration.
- Actual Fabric workspace deployment automation.

## Guiding principle

The demo should feel realistic because the data is correlated by scenario, not because it is real. Every spike, outage, ticket, dispatch, SLA credit, and churn-risk change should be explainable through the ontology.

