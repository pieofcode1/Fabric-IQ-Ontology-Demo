# Build the Nimbus Semantic Model and Report

## Purpose

This is the detailed execution guide for step 7 of the [deployment runbook](12-deployment-runbook.md).
It starts with the 24 managed Gold tables created in step 6 and ends with a query-validated Direct Lake semantic model and a published report.
Use a development workspace: Direct Lake live editing changes the remote semantic model immediately.
No live Power BI deployment has been verified by this repository's local tests.

## 1. Confirm Prerequisites

1. Complete step 6 with `status: PASS` for both notebooks and confirm 24 Gold tables are present in `nimbus_iq_gold`.
2. Install a current Power BI Desktop release with TMDL view and Direct Lake live editing available, and sign in to the same tenant as Fabric.
3. Confirm the tenant permits XMLA endpoints and the capacity's XMLA endpoint is set to **Read Write**.
4. Confirm your account has a paid Power BI authoring license, permission to create items in the workspace, Write permission on the semantic model once created, and at least Viewer access to the Gold lakehouse.
5. Keep step 6's headline incident output available; use its counts and SLA amount as the validation baseline rather than hard-coded sample totals.

If Desktop's OneLake catalog or live-edit option is unavailable, resolve the version, license, tenant, and permission requirements before continuing.
The three repository TMDL scripts do not provide table partitions or credentials and cannot create a model from scratch through the Fabric REST API.

## 2. Create a Direct Lake Model and Rename Tables

1. In Power BI Desktop, open **OneLake catalog**, select the Gold **Lakehouse** item, and select **Connect**.
2. Name the new semantic model `nimbus_iq_semantic_model`, select the demo Fabric workspace, and select the 20 required Gold tables in the mapping below.
3. Select **OK**; Desktop creates the model in the workspace and opens it in live-edit mode using **Direct Lake on OneLake**.
4. In **Model view**, rename each semantic table using the exact display name below, including spaces.
5. Keep column names such as `incident_id` unchanged; rename semantic tables only, not lakehouse tables, `sourceColumn`, or partition `entityName` bindings.
6. Verify table storage mode is Direct Lake and monetary columns are numeric, keys are Text, and timestamp/date columns are Date/Time or Date as appropriate.

The Gold notebook writes physical `dim_`, `fact_`, `bridge_`, and `agg_` names.
The TMDL scripts use semantic display names, so applying them before these renames will fail with missing-table errors.
If a model already exists, connect to it through **OneLake catalog > semantic model > Connect dropdown > Edit**; do not create a duplicate or reuse an empty placeholder without adding the actual Gold tables.

| Gold table selected from the lakehouse | Exact semantic display name | Role |
|---|---|---|
| `dim_date` | Date | Calendar |
| `dim_account` | Account | Dimension |
| `dim_customer` | Customer | Dimension |
| `dim_product` | Product | Dimension |
| `bridge_subscription` | Subscription | Subscription dimension |
| `dim_device` | Device | Dimension |
| `dim_service_instance` | Service Instance | Service dimension |
| `dim_network_asset` | Network Asset | Dimension |
| `fact_incident` | Incident | Fact |
| `fact_network_telemetry` | Telemetry Event | Event-grain fact |
| `fact_alarm` | Alarm | Fact |
| `fact_support_case` | Support Case | Fact |
| `dim_technician` | Technician | Dimension |
| `fact_work_order` | Work Order | Fact |
| `fact_sla_exposure` | SLA Exposure | Fact |
| `fact_churn_risk` | Churn Risk | Fact |
| `bridge_incident_asset` | Bridge Incident Asset | Incident/asset pairs |
| `bridge_incident_service` | Bridge Incident Service | Incident/service pairs |
| `fact_investigation` | Investigation | Evidence fact |
| `agg_dispatch_priority` | Dispatch Priority | One row per work order |

The other four Gold tables are optional for this base model: `dim_region`, `fact_network_telemetry_hourly`, `agg_service_health_daily`, and `agg_customer_impact_by_incident`.
They are not missing or interchangeable with the base facts.
For example, selecting the hourly telemetry table instead of `fact_network_telemetry` will break event-grain measures expecting `metric_value` and `severity_band`.
Add these optional tables later only with appropriate relationships and aggregate-specific measures.

## 3. Apply the TMDL Scripts

TMDL stands for **Tabular Model Definition Language**, not TDML.
The relationship and measure files are **TMDL view scripts**, not a complete PBIP semantic-model definition folder.
The [model.tmdl](../semantic_model/tmdl/model.tmdl) file is a **merge-only property fragment**, not an executable script; do not apply it in a blank TMDL view tab.
Use them only after the selected Gold tables have been created and renamed in the semantic model.

| File | Action in TMDL view |
|---|---|
| [model.tmdl](../semantic_model/tmdl/model.tmdl) | Merge these properties into a freshly scripted complete model; never apply this fragment alone. |
| [relationships.tmdl](../semantic_model/tmdl/relationships.tmdl) | Create the explicit active and inactive relationships after removing overlapping auto-detected relationships. |
| [measures.tmdl](../semantic_model/tmdl/measures.tmdl) | Create or replace the named measures inside existing tables through `ref table` declarations. |

1. Before applying changes, use **Version history** to retain a restorable model version, or export to **File > Export > Power BI Project (PBIP)** for a local metadata backup.
2. In **Model view > Manage relationships**, review auto-detected relationships and remove only those overlapping this demo's relationships, after approving that change; otherwise duplicates and ambiguous paths can remain.
3. Open **TMDL view** in the left navigation and create an empty script tab.
4. Drag the **Semantic model** node from the Data pane into the empty TMDL editor, or use its **Script TMDL** action, to generate the complete current model script, including all tables, columns, partitions, relationships, and source expressions.
5. Under that generated script's ordinary `model` declaration (not `ref model`), merge the two property lines from [model.tmdl](../semantic_model/tmdl/model.tmdl) at the same indentation as existing model properties; update an existing property/annotation rather than adding a duplicate.
6. Keep every other part of the generated full-model script intact, select **Preview**, and verify that only the intended model property/annotation changes appear, with no tables, columns, partitions, relationships, or source expressions removed; then select **Apply** and require a success notification.
7. In a new tab, paste the complete [relationships.tmdl](../semantic_model/tmdl/relationships.tmdl) script and use **Preview > Apply**.
8. In another new tab, repeat the same sequence for [measures.tmdl](../semantic_model/tmdl/measures.tmdl).
9. Check the **Problems** and **Output** panes after each application and stop on an error; do not continue to report authoring with a partially applied model.
10. Select **Refresh** to synchronize schema and reframe Direct Lake tables, then confirm the renamed tables still reference their original physical Gold tables.

The complete generated model script and the relationship/measure scripts begin with `createOrReplace`; the merge-only property fragment does not.
A `ref` object cannot have properties: `ref table` can scope child measure declarations, but `ref model` cannot contain `defaultPowerBIDataSourceVersion` or an annotation property.
Do not simply change `ref model` to `model` in a short script: `createOrReplace model` replaces the model and its descendants, so omitted tables or partitions can be removed.
Always start with a fresh full-model script generated from the actual live model and retain all its descendants and source bindings when editing model properties.
The measure script uses `ref table` parents and declares only child measures, without redefining table properties or partitions.
The scripts overwrite same-named demo measures and relationships; preview those replacements before applying them to an existing model.
Do not paste the relationship/measure script commands into a PBIP `definition/` file: executable scripts and serialized definition files are different formats.
Desktop live editing saves changes directly to Fabric; there is no separate semantic-model Publish action in this workflow.
Export to PBIP if you need to persist local TMDL script tabs and metadata, since bare live-edit sessions do not preserve local scripts.

If TMDL reports that a reference object cannot have properties, discard the invalid short `ref model` script and follow the full-model scripting procedure above.
If the service reports that `DefaultPowerBIDataSourceVersion` must be `PowerBI_V3`, confirm the full generated script contains `defaultPowerBIDataSourceVersion: powerBI_V3` under its ordinary `model` declaration, then use **Preview > Apply** while retaining all model contents.
If that full-model update still fails, stop before applying relationships or measures and have the model owner verify the current property, compatibility level, and XMLA write support; the service may require the property to be changed through authorized model-management tooling first.
This error alone is not a reason to recreate Gold tables or purchase a larger capacity SKU.

## 4. Check Relationships and Model Presentation

1. In **Manage relationships**, confirm many-to-one cardinality, single-direction filtering from the one side, and the active/inactive flags defined in the script.
2. Keep `Incident` to `Alarm`, `Support Case`, `Work Order`, `SLA Exposure`, both incident bridges, `Investigation`, and `Dispatch Priority` active.
3. Keep alternate paths such as Incident's root asset, service-to-device, service-to-case, account-to-case, telemetry-to-alarm, and asset-to-work-order inactive as specified; these paths remain documented but are not competing active routes.
4. Verify Date's active relationship targets `Incident[start_date]`; its relationships to `Support Case[opened_date]` and `Work Order[created_date]` are inactive role-playing alternatives, usable with `USERELATIONSHIP` in a purpose-built measure.
5. Set Date's `month_name` to sort by `month`, mark Date as the date table using its `date` column where available, and hide IDs and ingestion metadata from report authors while retaining them for relationships.
6. Set non-additive numeric columns such as coordinates, risk scores, and dispatch scores to **Don't summarize**; use explicit measures for report values.
7. In table/column properties, add the descriptions from [semantic_model.yml](../semantic_model/semantic_model.yml), and enter relevant business synonyms from [iq_synonyms.yml](../semantic_model/iq_synonyms.yml) in the tooling's supported Q&A/linguistic synonym settings; these design files are not auto-imported by the TMDL scripts.

Incident bridges filter their own measures, not upstream dimensions through bidirectional relationships.
The `Affected Customers` measure uses impacted account IDs inferred through Service Instance and Subscription with `TREATAS`; it does not invent a direct Customer-to-Subscription relationship.
Do not enable bidirectional filtering everywhere to make a slicer work.
For asset telemetry, use Network Asset filters; an Incident slicer alone does not automatically apply its asset bridge or incident time window to telemetry averages.
Likewise, `High Churn Risk Customers` describes the current customer context, not incident-attributed churn lift.
Dispatch Priority Score uses the score already computed in Gold and returns a value only for a single work-order context; it is not an additive score across all work orders.

## Business Traversal Paths

These paths describe the business graph for ontology/Q&A, not a promise that every arrow is an active Power BI filter direction.

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

## Measures Available After Applying the Script

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
| Affected Subscribers | Distinct bridged service instances in the incident context |
| Affected Network Assets | Distinct assets in the incident's asset bridge |
| Affected Customers | CRM customers on impacted accounts |
| Complaint Rate per 1000 Subscribers | Cases divided by the active subscription base, times 1,000 |
| Dispatch Priority Score | Gold score for a single work order |
| Investigations | Saved incident evidence artifacts |
| Confirmed Investigations | Evidence artifacts with Confirmed status |

## 5. Validate the Model with DAX

Open **DAX query view** in Desktop while live editing the semantic model and run [validate_model.dax](../semantic_model/validate_model.dax).
Execute its queries separately if your client runs only the selected statement.
The headline query filters `Incident[incident_id]` to `INC-2026-ONT-001` and checks the bridge counts, support cases, SLA amount, and investigation counts against raw Gold totals.
Require all comparison flags to return `TRUE`, then compare the displayed values with step 6's saved outputs.
The dispatch query checks every work-order score against the materialized Gold score; its mismatch count must be zero.
The metadata query lists relationships so you can verify that active and inactive paths match the script.
Successful TMDL parsing does not validate DAX semantics or permissions; do not skip these live queries.

The packet-loss source stores percentage points: `2.5` means `2.5%`.
The measure uses a literal percent sign rather than percentage scaling, and MTTR uses minute differences divided by 60 to retain fractional hours.

## 6. Create, Publish, and Check the Report

1. In Desktop choose **File > Blank report**, open **OneLake catalog**, select `nimbus_iq_semantic_model`, and choose **Connect**, not **Edit**.
2. Add an Incident ID slicer and select `INC-2026-ONT-001`.
3. Create the pages below manually or use the Copilot workflow in section 6.1; use explicit measures and do not sum incident-level SLA amounts repeated in dispatch rows.
4. Save the thin report as `nimbus_iq_service_assurance_report.pbix` and publish it to the same demo workspace.
5. Open the published report in Fabric and verify that its semantic-model binding points to `nimbus_iq_semantic_model`.
6. Test using the intended viewer's account and licensing, including source access or configured fixed identity as required by your Direct Lake security setup.
7. Require report values to match the DAX query results, and stop before step 8 if filters, credentials, or permissions produce different totals.

| Page | Minimum visuals and filters |
|---|---|
| NOC | Incident ID slicer; affected-service/asset cards; incident severity/status table; telemetry charts filtered explicitly by Network Asset and event time. |
| Customer Support | Incident ID slicer; Support Cases, Escalated Cases, and Average Sentiment cards; case reason/channel breakdown. |
| Field Operations | Incident ID slicer; Work Orders/P1 cards; table using `Dispatch Priority[work_order_id]`, its status/priority, and Dispatch Priority Score, sorted descending. |
| Business Impact | Incident ID slicer; Affected Customers and SLA Exposure Amount cards; investigation count/status; account tiers from supported dimension filtering. |

To show incident-specific telemetry, apply the impacted asset IDs and start/resolution times from step 6 as explicit visual/page filters; an automatic bridge-and-time-window telemetry measure is not shipped here.
An Incident filter limits affected-customer and bridge measures, but does not filter the global Customer dimension or global revenue/churn measures by itself.

### 6.1. Generate the Pages with Copilot in Power BI

Use **Copilot in the report authoring pane**, not GitHub Copilot, Fabric Data Agent, or standalone Copilot chat.
Copilot drafts report pages against the connected semantic model; it does not run the Gold notebook, apply the TMDL scripts, or repair relationships.
Complete sections 1-5 first and keep the successful DAX results and step 6 notebook evidence available.
The prompts below are authoring instructions, not a deterministic report definition; inspect every generated field binding and filter before presenting the demo.

#### Enable and Open Copilot

1. Confirm the workspace uses a paid Fabric capacity **F2 or higher**, or Power BI Premium **P1 or higher**, in a supported region. Trial capacities are not supported.
2. Ask the Fabric administrator to confirm **Users can use Copilot and other features powered by Azure OpenAI** is enabled for your account.
   Where required by the capacity/tenant location, cross-region processing also requires administrator approval and the applicable tenant setting; do not enable it without organizational approval.
3. Use an account with report editing and semantic-model Build permissions, in addition to the Direct Lake source access required earlier.
4. Confirm the model's **Q&A feature switch** is enabled and implicit measures are not disabled; these are current report-creation requirements.
   This feature requirement does not change the demo rule: bind visuals to the existing explicit measures instead of accepting automatically summed columns.
5. In the thin report connected to `nimbus_iq_semantic_model`, select **Copilot** on the Desktop ribbon.
   Alternatively, open the report in the Power BI service, select **Edit**, and open **Copilot** there.
6. If Copilot is missing or creation is unavailable, check capacity, region, tenant settings, model compatibility, and permissions using the [Copilot requirements][copilot-overview] and [report-creation limitations][copilot-create].
   Use the manual page specifications above if your environment does not support this experience.

This Direct Lake model is not a Power BI real-time streaming semantic model.
The separate Eventstream/Eventhouse replay does not automatically make these report pages live; do not promise streaming updates or automatic refresh from a generated visual.
Current Copilot report creation also excludes custom visuals and does not support styling/formatting changes.
Apply the theme, canvas layout, fonts, colors, currency formats, and accessibility settings manually after generation.

#### Generate One Page at a Time

Paste each complete prompt below separately into the report Copilot pane.
Review the result before requesting the next page; if a visual is omitted, add it manually with the specified fields rather than repeatedly generating duplicate pages.
After generation, rename the page if needed and set an **Incident page filter or slicer** to `INC-2026-ONT-001` on every page.
Verify the selection rather than assuming Copilot applied it.
Keep existing pages when adding the next one.

**Prompt 1 - NOC**

```text
Create a new page named "NOC" in this report using the connected
nimbus_iq_semantic_model. This is a synthetic Nimbus Communications
telecom service-assurance demo, not real customer or network data.
Use existing explicit measures only. Do not invent measures or data.

Add a single-select slicer using Incident[incident_id] and select
INC-2026-ONT-001. Add cards for [Affected Subscribers] and
[Affected Network Assets]. Label the first card "Affected service instances":
this measure counts distinct impacted services, not unique people.
Add an incident details table with Incident[incident_id], [region],
[severity], [status], [root_cause], [start_time], and [resolution_time].

Add two line charts with Telemetry Event[event_time] on the X axis:
one using [Average Latency], the other using [Average Packet Loss].
Use Network Asset[network_asset_id] as the series where practical.
Do not combine different metric units in one average.
Incident selection alone does not scope telemetry to impacted assets
and incident time. Do not describe these charts as incident-specific
until the author applies explicit impacted-asset and time-window filters.
Do not claim this page is real-time or that root cause was inferred by AI.
Preserve other report pages.
```

**Required manual NOC step:** set visual-level asset filters on both telemetry charts to the exact impacted asset IDs from step 6.
Set `Telemetry Event[event_time]` to a window including pre-incident baseline, degradation, and recovery using the actual source times.
Check Desktop's timestamp representation/time zone against the notebook evidence rather than entering local times blindly.
Use the raw timestamp axis rather than an automatic date hierarchy if you need intraday detail.
Do not infer the impacted set from `Incident[network_asset_id]` alone; it excludes downstream bridged assets.
Keep these fixed filters aligned with the selected headline incident; hide the incident selector or restrict it to the headline incident for a fixed demo, or reset both filters manually when changing incidents.

**Prompt 2 - Customer Support**

```text
Create a new page named "Customer Support" for the synthetic Nimbus
Communications service-assurance demo using this report's connected model.
Use existing explicit measures only; do not create calculations.
Add a single-select Incident[incident_id] slicer set to INC-2026-ONT-001.
Add cards for [Support Cases], [Escalated Cases], and [Average Sentiment].
Add a bar chart of [Support Cases] by Support Case[case_reason],
and another by Support Case[channel].
Add a case table containing Support Case[case_id], [opened_time],
[channel], [case_reason], [case_status], and [sentiment_score].
These facts have an active incident relationship.
Do not add a global customer count, churn chart, or revenue metric and
label it as incident impact. Do not imply synthetic sentiment is a
production sentiment model. Preserve other pages.
```

**Prompt 3 - Field Operations**

```text
Create a new page named "Field Operations" for the synthetic Nimbus
Communications service-assurance demo using this report's connected model.
Use existing explicit measures only; do not create calculations.
Add a single-select Incident[incident_id] slicer set to INC-2026-ONT-001.
Add cards for [Work Orders] and [P1 Work Orders].
Add a dispatch table using Dispatch Priority[work_order_id],
Dispatch Priority[priority], Dispatch Priority[status],
Dispatch Priority[network_asset_id], Dispatch Priority[technician_id],
and the existing measure [Dispatch Priority Score].
Sort the table descending by [Dispatch Priority Score].
The score is defined per work order and intentionally blank at totals:
do not sum scores or replace a blank total with a new calculation.
Do not sum Dispatch Priority[sla_exposure_amount] or
Dispatch Priority[affected_service_count]; these repeat incident totals
for each order. This is decision support, not an automatic dispatch action.
Preserve other pages.
```

**Prompt 4 - Business Impact**

```text
Create a new page named "Business Impact" for the synthetic Nimbus
Communications service-assurance demo using this report's connected model.
Use existing explicit measures only; do not create calculations.
Add a single-select Incident[incident_id] slicer set to INC-2026-ONT-001.
Add cards for [Affected Customers], [SLA Exposure Amount],
[Investigations], and [Confirmed Investigations].
Label Affected Customers "Customers on impacted accounts"; it is
account-level attribution, not a direct customer-to-service count.
Add a bar chart of [SLA Exposure Amount] by Account[account_tier].
Add an investigation table with Investigation[investigation_id],
Investigation[title], Investigation[status], and Investigation[summary].
Use the SLA Exposure fact measure for financial totals, never the
repeated exposure values in Dispatch Priority or Investigation.
Exposure is estimated credit/penalty exposure in CAD, not lost revenue.
Do not claim incident-attributed churn, revenue loss, causal predictions,
or real customer impact. Preserve other pages.
```

#### Refine and Validate the Draft

For an incorrect aggregation, select the affected visual and use this follow-up prompt, replacing both placeholders:

```text
Update only the selected visual. Replace <incorrect field or aggregation>
with the existing explicit measure <exact measure name>.
Keep its incident filter and other report pages unchanged.
Do not create a new measure. If this edit is unsupported, leave it for
manual correction rather than substituting another metric.
```

1. Inspect each visual's field wells: cards must use the named measures, not `Sum of` a raw numeric column.
   Verify the dispatch table includes `Dispatch Priority[work_order_id]`, which supplies the score's required single-order context.
2. Check **Filters** and **Edit interactions**: each incident selector must filter its page's incident facts and bridge measures.
   For the fixed NOC demo, verify telemetry has both explicit asset and time filters; changing Incident alone is not sufficient.
3. Reconcile cards with section 5's DAX results for the same incident.
   Compare support totals, affected-service/asset/customer counts, SLA amount, investigations, and individual dispatch scores; do not hard-code the sample results in a visual.
4. Verify the Business Impact tier chart totals reconcile to the SLA card.
   Do not use the global Customer dimension, revenue, or churn measures as an incident-specific cohort without separately implementing and validating that attribution.
5. Apply formatting manually: readable titles, consistent layout, accessible contrast, CAD currency, milliseconds, and packet-loss percentage points (`2.5` displays as `2.5%`, not `250%`).
   Add a visible **Synthetic demonstration data** label.
6. Inspect any generated narrative against the visible evidence. Remove unsupported root-cause claims, invented figures, automated-action claims, or suggestions that the historical Gold data is a live feed.
7. Continue section 6 steps 4-7 to save/publish, verify the semantic-model binding, and test with the intended viewer.
   A generated page is not accepted until these checks pass.

See Microsoft's [Copilot report creation guide][copilot-create] and [prompt-writing examples][copilot-prompts] for the current supported authoring experience.

## Assets and API Boundaries

The semantic model artifacts are in `semantic_model/`:

- `semantic_model.yml`
- `iq_synonyms.yml`
- `relationship_graph.mmd`
- `tmdl\model.tmdl`
- `tmdl\relationships.tmdl`
- `tmdl\measures.tmdl`

The Desktop path above is the complete first-run authoring workflow; the repository still does not ship a fully bound semantic-model definition or report-visual definition for unattended creation.
For later CLI redeployment, export the complete authored PBIP metadata and use Fabric Git integration or supported item-definition APIs with the deployed Gold bindings and report model ID.
Do not point `-DefinitionDirectory` at `semantic_model/tmdl`: these scripts alone lack the database, table columns, Direct Lake partitions, connection expressions, and report definition.
Consult [Direct Lake Desktop authoring][direct-lake], [TMDL view][tmdl-view], and [TMDL script semantics][tmdl-scripts] for prerequisites and supported behavior.

[direct-lake]: https://learn.microsoft.com/en-us/fabric/fundamentals/direct-lake-power-bi-desktop
[tmdl-view]: https://learn.microsoft.com/en-us/power-bi/transform-model/desktop-tmdl-view
[tmdl-scripts]: https://learn.microsoft.com/en-us/analysis-services/tmdl/tmdl-scripts
[copilot-overview]: https://learn.microsoft.com/en-us/power-bi/create-reports/copilot-introduction
[copilot-create]: https://learn.microsoft.com/en-us/power-bi/create-reports/copilot-create-reports
[copilot-prompts]: https://learn.microsoft.com/en-us/power-bi/create-reports/copilot-prompts-report-pages
