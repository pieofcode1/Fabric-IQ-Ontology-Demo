# Synthetic Data Design

## Objective

Generate fabricated but realistic telecom data that creates explainable correlations across network, service, support, operations, and business impact.

## Data generation principle

Do not generate independent random tables. Generate scenario-driven data where root causes produce downstream signals.

Example causal chain:

```text
Backhaul congestion
  -> packet loss and latency increase
  -> service quality drops for affected sectors
  -> speed tests worsen
  -> customer support tickets rise
  -> SLA exposure increases for enterprise accounts
  -> work orders are prioritized
  -> telemetry improves after resolution
```

## Starter scenario

Name: `ontario_5g_home_internet_degradation`

Summary:

- Region: Toronto West and nearby GTA neighborhoods.
- Services: 5G Home Internet and mobile data.
- Root cause: backhaul congestion after delayed capacity upgrade.
- Impact window: multi-hour degradation with ticket spike.
- Operational response: NOC incident, field work order, technician dispatch, post-resolution monitoring.

## Suggested first data scale

| Dataset | Initial size |
|---|---:|
| Customers | 10,000 |
| Accounts | 7,500 |
| Subscriptions | 15,000 |
| Network assets | 300 |
| Cell sites | 40 |
| Cell sectors | 120 |
| Telemetry events | 250,000 |
| Alarms | 500 |
| Incidents | 25 |
| Support cases | 2,000 |
| Work orders | 500 |
| SLA exposure rows | 300 |
| Churn risk rows | 10,000 |

## Correlation rules

| Rule | Description |
|---|---|
| Geographic density | Urban markets have more subscribers and more congestion events |
| Service sensitivity | 5G Home Internet is more sensitive to signal quality and backhaul utilization |
| Ticket lag | Support cases appear 15 to 90 minutes after service degradation starts |
| Enterprise priority | Enterprise and premium accounts have higher SLA exposure and dispatch priority |
| Repeat impact | Customers with multiple recent incidents receive higher churn-risk scores |
| Resolution effect | Telemetry and complaint volume improve after work order completion |

## Privacy and realism

- Use fake names, addresses, emails, and phone numbers.
- Use realistic Canadian cities and provinces, but not real customer records.
- Use invented network asset IDs and coordinates that approximate public regions only.
- Do not model any real telecom provider's network topology, site identifiers, customer segments, subscriber records, or operational data.

