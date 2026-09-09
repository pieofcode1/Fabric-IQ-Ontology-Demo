# KPI Catalog

| KPI | Definition | Primary grain |
|---|---|---|
| Affected Subscribers | Count of active service instances mapped to degraded network assets or incidents | Incident, region, service type |
| Complaint Rate | Support cases per 1,000 active subscribers | Date, region, service type |
| Network Health Score | Composite score from availability, latency, packet loss, throughput, and signal quality | Network asset, hour |
| Average Latency | Mean latency in milliseconds across telemetry events | Network asset, hour |
| Packet Loss Rate | Mean packet loss percentage across telemetry events | Network asset, hour |
| Alarm Volume | Count of active or triggered alarms | Network asset, severity |
| Open Incidents | Count of incidents not resolved or closed | Region, severity |
| MTTR | Average time from incident start to resolution | Incident type, region |
| SLA Exposure | Estimated credits or penalties for impacted customers | Incident, account tier |
| Churn Risk Lift | Difference between baseline and current churn-risk score | Customer, segment |
| Repeat Issue Rate | Customers with more than one support case or incident impact in period | Customer, service type |
| Dispatch Priority Score | Weighted score from severity, affected subscribers, SLA exposure, and customer tier | Work order |
| First Contact Resolution | Support cases resolved without escalation | Support channel, issue reason |
| Sentiment Score | Normalized sentiment score from call or chat summaries | Case, customer |

## Suggested priority-score formula

```text
dispatch_priority_score =
  severity_weight
  + affected_subscriber_weight
  + sla_exposure_weight
  + premium_customer_weight
  + repeat_issue_weight
  - technician_distance_penalty
```

