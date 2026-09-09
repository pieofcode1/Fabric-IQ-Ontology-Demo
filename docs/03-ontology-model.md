# Fabric IQ Ontology Model

## Design intent

The ontology should hide table complexity and expose telecom business concepts. Users should ask business questions using terms like customer, service, tower, outage, ticket, technician, churn risk, and SLA exposure.

## Entity catalog

| Entity | Description | Example fields |
|---|---|---|
| Customer | Residential or business customer | customer_id, customer_name, segment, province, city |
| Account | Billing or enterprise account | account_id, account_type, account_tier, industry |
| Subscription | Product subscription | subscription_id, product_id, start_date, status |
| Product | Telecom product or plan | product_id, product_name, service_type, monthly_price |
| Service Instance | Active delivered service | service_instance_id, access_type, status, activation_date |
| Device | Handset, modem, router, gateway | device_id, device_type, model, firmware_version |
| Network Asset | Cell site, sector, fiber node, CMTS, router, backhaul link | network_asset_id, asset_type, region, latitude, longitude |
| Telemetry Event | Network or device metric event | event_id, event_time, metric_name, metric_value |
| Alarm | Threshold or anomaly alert | alarm_id, severity, alarm_type, status |
| Incident | Operational incident | incident_id, severity, start_time, resolution_time |
| Support Case | Customer support interaction | case_id, channel, reason, sentiment, status |
| Work Order | Field or NOC remediation task | work_order_id, priority, status, scheduled_time |
| Technician | Field resource | technician_id, region, skill_set, shift |
| SLA Exposure | Potential credit or penalty | exposure_id, amount, breach_type, customer_tier |
| Churn Risk | Customer churn prediction snapshot | risk_id, score, driver, model_version |

## Relationships

| From | Relationship | To |
|---|---|---|
| Customer | owns | Account |
| Account | has | Subscription |
| Subscription | includes | Product |
| Subscription | delivered_as | Service Instance |
| Service Instance | uses | Device |
| Service Instance | served_by | Network Asset |
| Network Asset | emits | Telemetry Event |
| Network Asset | triggers | Alarm |
| Alarm | contributes_to | Incident |
| Incident | affects | Network Asset |
| Incident | impacts | Service Instance |
| Customer | opens | Support Case |
| Support Case | linked_to | Incident |
| Incident | remediated_by | Work Order |
| Work Order | assigned_to | Technician |
| Incident | creates | SLA Exposure |
| Customer | has | Churn Risk |

## Business synonyms

| Business term | Ontology entity |
|---|---|
| tower | Network Asset where asset_type = Cell Site |
| sector | Network Asset where asset_type = Cell Sector |
| outage | Incident |
| trouble ticket | Support Case |
| field dispatch | Work Order |
| premium customer | Account where account_tier is Premium or Enterprise |
| service degradation | Incident or telemetry anomaly with non-zero customer impact |
| customer impact | affected service instances, tickets, SLA exposure, churn risk |

## Sample questions

- Why are complaints rising in Toronto West?
- Which network assets are most likely causing 5G Home Internet degradation?
- Which enterprise customers are affected by incident INC-2026-ONT-001?
- What is the SLA exposure for unresolved incidents today?
- Which work orders should be prioritized based on customer impact?
- Which customers had repeat service issues in the last 30 days?
- What changed after the incident was resolved?

