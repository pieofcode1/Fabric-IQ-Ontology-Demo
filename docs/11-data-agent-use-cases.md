# Data Agent Use Cases for AI-Driven Decision Making

## Purpose

This project already builds the ingredients a Fabric **Data Agent** needs: a Gold Lakehouse/Warehouse
(SQL source), an Eventhouse fed by `stream_simulator.py` (KQL source), a Direct Lake semantic model,
and a Fabric IQ Ontology generated from that model (Ontology source). A Data Agent combines up to
five of these sources into one conversational surface. This doc is the methodology and catalog for
turning that surface into specific, testable **decisions** - not just answered questions.

A "use case" here means: a named business decision, the question that grounds it, which data
source(s) answer it, and what happens after the answer - because a Data Agent that only answers
questions is a chatbot; a Data Agent wired to `Investigation`, `Bridge Incident Asset/Service`, and
`Dispatch Priority Score` can drive an actual next action.

## How a Fabric Data Agent is actually configured (grounding)

Per current Fabric documentation, a Data Agent is configured with four levers, and support for each
varies by data source type:

| Data source | Agent Instructions | Data Source Instructions | Data Source Description | Example Queries |
|---|---|---|---|---|
| SQL (Lakehouse/Warehouse) | Yes | Yes (table/column context, joins, business terms) | Yes | Yes (NL/SQL pairs, top-k retrieved by similarity) |
| Eventhouse (KQL) | Yes | Yes (tables, functions, shortcuts) | Yes | Yes (NL/KQL pairs) |
| Semantic Model (Power BI) | Yes | No - configured via **Prep for AI** (AI Instructions, Verified Answers) on the model itself | No | No - use Verified Answers instead |
| Ontology (preview) | Yes | Yes (passed to the ontology-native query engine) | Yes | Not documented as supported today - rely on Agent/Data Source Instructions |
| Graph/GQL (preview) | Yes | Yes | Yes | Yes |

Four **intent layers** govern behavior, highest precedence first: **organizational** (tenant policy)
&gt; **role-based** (workspace/permission scope) &gt; **developer** (this doc's instructions/examples)
&gt; **user** (the question asked). Nothing configured below can override governance set above it -
see `docs/08-governance-privacy.md` for this project's access-control model.

## The carving-out method

Repeat this loop per candidate use case; don't skip step 5 - an answer nobody acts on isn't a decision.

1. **Pick the decision-maker and the decision.** Use the personas in `docs/01-demo-vision.md`. A use
   case exists to help one of them decide something specific, not to demo a query.
2. **Write the question(s) that ground the decision** in the user's own words, not schema names.
3. **Route to the right data source(s).** Use the traversal paths already documented in
   `docs/09-semantic-model-for-iq.md` to decide whether the question needs Ontology (relationship
   traversal), SQL/Lakehouse (aggregation over Gold facts/dimensions), or Eventhouse/KQL (live,
   high-volume telemetry from `stream_simulator.py`).
4. **Author instructions + examples for that source** - see the worked examples below. Keep
   instructions specific: name the exact tables/measures to prefer, and define any domain term the
   agent might otherwise mis-map (e.g., "tower" -&gt; `Network Asset`, per `iq_synonyms.yml`).
5. **Define the decision/action the answer unlocks.** Does it open an `Investigation`? Reprioritize a
   `Work Order` using `Dispatch Priority Score`? Trigger a churn save-offer? Write this down before
   building the agent, or the use case will silently regress to "just a chatbot."
6. **Give it a golden test.** Because this repo's scenario is deterministic and validated
   (`validate_scenario.py`, 21 checks), every use case gets a known-correct answer to regression-test
   against. See "Verification" below.

## Use case catalog

| # | Persona | Decision to make | Grounding question | Data source(s) | Grounding entities | Decision / action unlocked |
|---|---|---|---|---|---|---|
| 1 | Executive sponsor | Where to focus attention this week | "Why are complaints rising in Ontario?" | Ontology + SQL (Gold) | `Incident`, `Support Case`, `Region` | Escalate the region's incident to the leadership review list |
| 2 | Network operations leader | Which asset to remediate first | "Which network assets are causing the current degradation?" | Eventhouse (KQL, live) + Ontology | `Bridge Incident Asset`, `Telemetry Event`, `Alarm` | Open or update the `Investigation` for the incident |
| 3 | Field operations manager | Which work order to dispatch next | "Which work orders should be prioritized today?" | SQL (Gold) | `Work Order`, `Dispatch Priority Score`, `SLA Exposure` | Reorder the technician's queue by score |
| 4 | Service support leader | How to respond to affected customers | "Which customers are affected by this incident and what's their churn risk?" | Ontology + SQL (Gold) | `Bridge Incident Service`, `Customer`, `Churn Risk` | Trigger a proactive outreach or retention offer for High risk customers |
| 5 | Data and AI leader | Whether the finding is trustworthy enough to act on | "Show me the investigation and evidence for incident INC-2026-ONT-001" | Ontology + SQL (Gold) | `Investigation`, `Bridge Incident Asset/Service` | Approve the finding for promotion to an always-on Activator rule (see `docs/10-operationsiq-alignment.md`) |

## Worked configuration examples

### Use case 2 - Network operations leader (Eventhouse/KQL source)

**Data source instructions:**
> This Eventhouse contains live-replayed telemetry from `stream_simulator.py`, scoped to one
> incident's bridge (`raw_bridge_incident_asset`). `network_telemetry` has one row per metric
> reading (`metric_name` in `latency_ms`, `packet_loss_pct`, `throughput_mbps`,
> `backhaul_utilization_pct`, `rsrp_dbm`); `severity_band` is `Normal`/`Warning`/`Critical`. Always
> filter to the requested incident's asset IDs before aggregating, and prefer the most recent
> `event_time` window unless the user asks for history.

**Example query pair:**
> Q: "Which assets are showing critical packet loss right now?"
> KQL: `network_telemetry | where metric_name == "packet_loss_pct" and severity_band == "Critical" | summarize arg_max(event_time, *) by network_asset_id`

### Use case 3 - Field operations manager (SQL/Gold source)

**Data source instructions:**
> `Work Order` joins to `Incident` (severity), `SLA Exposure` (financial impact), and the incident's
> `Bridge Incident Service` count (affected subscribers). `Dispatch Priority Score` is precomputed
> per the formula in `docs/07-kpi-catalog.md` - prefer it over recomputing ranking logic ad hoc.

**Example query pair:**
> Q: "Which open work orders should I dispatch first today?"
> SQL: `SELECT work_order_id, incident_id, priority, dispatch_priority_score FROM work_order WHERE status <> 'Completed' ORDER BY dispatch_priority_score DESC`

### Use case 5 - Data and AI leader (Ontology + SQL source)

**Agent instructions:**
> When asked to "prove" or "show evidence for" a finding, prefer the `Investigation` entity over
> re-deriving the answer from raw facts - its `affected_asset_count`, `affected_service_count`, and
> `related_case_count` are pre-confirmed against the bridge tables (see
> `docs/10-operationsiq-alignment.md`). Only fall back to live traversal if no investigation exists
> for the incident.

## Verification: use the golden scenario as a test set

Because `INC-2026-ONT-001` has known, validated ground truth, every use case above has a
regression-testable expected answer today, without waiting for a live tenant:

| Question | Expected answer (from the current `sample_output`) |
|---|---|
| "How many network assets does the Toronto West incident affect?" | Matches `raw_bridge_incident_asset` row count for `INC-2026-ONT-001` |
| "How many support cases are tied to that incident?" | Matches `raw_support_cases` filtered to that `incident_id` |
| "What's the SLA exposure for that incident?" | Matches `sla_exposure_amount` on its `raw_investigations` row |

Re-run `validate_scenario.py` after any semantic model or instruction change - if the underlying
data no longer supports these answers, the Data Agent will confidently produce wrong ones, which is
worse than not answering.

## Non-goals

- No live Fabric Data Agent was created or deployed here - this repo has no live tenant/workspace
  (see `deployment/README.md`). This doc is the design so one can be configured quickly once a
  workspace exists.
- Power BI semantic model sources don't support Example Queries directly; if the agent's Semantic
  Model source underperforms, add Verified Answers via **Prep for AI** in Power BI instead of trying
  to configure examples on the Data Agent side.
