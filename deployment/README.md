# Fabric Deployment Guide

This guide explains how to create a specific Microsoft Fabric workspace and create the demo assets for the Nimbus Fabric IQ Ontology Demo.

The included script creates a **single workspace** with separate assets for Bronze, Silver, Gold, real-time, semantic, and reporting layers. This is the simplest structure for a demo. For production or enterprise governance, use separate workspaces for Bronze, Silver, Gold, and real-time.

## Assets created

| Asset | Fabric item type | Purpose |
|---|---|---|
| `{prefix}_bronze` | Lakehouse | Raw generated CSV landing and Bronze Delta tables |
| `{prefix}_silver` | Lakehouse | Cleaned and conformed telecom entities |
| `{prefix}_gold` | Lakehouse | Curated IQ and Power BI tables |
| `{prefix}_eventhouse` | Eventhouse | Real-time network telemetry and alarm scenario |
| `{prefix}_kql` | KQLDatabase | KQL database for telemetry and alarm analytics |
| `{prefix}_degradation_alert` | Reflex (Activator) | Placeholder alert item - import `deployment/activator/ReflexEntities.template.json` (see `deployment/activator/README.md`) for a working starting rule |
| `{prefix}_bronze_ingestion` | Notebook | Starter ingestion notebook placeholder |
| `{prefix}_silver_transform` | Notebook | Starter Silver transformation notebook placeholder |
| `{prefix}_gold_curate` | Notebook | Starter Gold curation notebook placeholder |
| `{prefix}_generate_scenario_data` | Notebook | Placeholder for `notebooks/Generate_Nimbus_Scenario_Data.ipynb` - runs the scenario generator natively in Fabric, no local Python setup required |
| `{prefix}_orchestration` | DataPipeline | Placeholder pipeline for Bronze to Silver to Gold orchestration |
| `{prefix}_semantic_model` | SemanticModel | Placeholder Direct Lake semantic model target |
| `{prefix}_service_assurance_report` | Report | Placeholder Power BI report target |

The script also uploads the generated CSV files from `sample_output\` to:

```text
Files/landing/raw/<file>.csv
```

inside the Bronze lakehouse.

By default it also uploads the generator source (`generate.py`, `validate_scenario.py`,
`config/scenario_config.yaml`) to:

```text
Files/src/data_generator/generate.py
Files/src/data_generator/validate_scenario.py
Files/src/data_generator/config/scenario_config.yaml
```

so that `notebooks/Generate_Nimbus_Scenario_Data.ipynb` can import them and generate the scenario
data directly inside Fabric, without any local Python setup. Pass `-SkipGeneratorSourceUpload` to
the script to skip this step.

## Prerequisites

1. Azure CLI installed.
2. Access to Microsoft Fabric REST APIs.
3. Permission to create Fabric workspaces and items.
4. Optional but recommended: a Fabric capacity ID if your tenant requires assigning workspaces to capacity.

Sign in:

```powershell
az login --tenant 0fd4406a-d774-4531-b099-d19828f5a597
az account set --subscription 569c92fe-efb6-440d-9274-73860e3f69aa
az account get-access-token --resource https://api.fabric.microsoft.com --query accessToken --output tsv
```

If you have Fabric access but no Azure subscription context, use:

```powershell
az login --allow-no-subscriptions --tenant 0fd4406a-d774-4531-b099-d19828f5a597
```

## Run the deployment script

From the project root:

```powershell
.\deployment\Create-FabricAssets.ps1 `
  -WorkspaceName "nimbus-fabric-iq-demo-dev" `
  -AssetPrefix "nimbus_iq" `
  -TenantId "0fd4406a-d774-4531-b099-d19828f5a597" `
  -SubscriptionId "569c92fe-efb6-440d-9274-73860e3f69aa"
```

If you know the Fabric capacity ID:

```powershell
.\deployment\Create-FabricAssets.ps1 `
  -WorkspaceName "nimbus-fabric-iq-demo-dev" `
  -AssetPrefix "nimbus_iq" `
  -CapacityId "<fabric-capacity-guid>" `
  -TenantId "0fd4406a-d774-4531-b099-d19828f5a597" `
  -SubscriptionId "569c92fe-efb6-440d-9274-73860e3f69aa"
```

## After the script runs

1. Open the Fabric workspace.
2. Confirm the three lakehouses exist.
3. Open the Bronze lakehouse and confirm the generated CSVs are in `Files/landing/raw` and the
   generator source is in `Files/src/data_generator`.
4. **Optional, no-local-setup path:** import `notebooks/Generate_Nimbus_Scenario_Data.ipynb`
   into the `{prefix}_generate_scenario_data` notebook item, attach it to the Bronze lakehouse,
   and run it top to bottom to (re)generate and validate the scenario data entirely inside
   Fabric - see `src/data_generator/README.md` for details.
5. **Optional, closing the loop:** import `deployment/activator/ReflexEntities.template.json`
   into the `{prefix}_degradation_alert` Activator item to get a working packet-loss alert rule
   instead of starting from a blank Activator - see `deployment/activator/README.md` for the
   prerequisites (a `network_incident_bridge` lookup table in the KQL database) and import steps.
6. Implement Bronze ingestion notebook:
   - Read CSVs from `Files/landing/raw`.
   - Add ingestion metadata.
   - Write Bronze Delta tables.
5. Implement Silver transformation notebook:
   - Clean and conform IDs, dates, and business names.
   - Write conformed Silver tables.
6. Implement Gold curation notebook:
   - Create business-friendly Gold tables using names from `semantic_model\semantic_model.yml`.
7. Build the Direct Lake semantic model over Gold.
8. Add relationships and measures from `semantic_model\tmdl`.
9. Ground Fabric IQ using `semantic_model\iq_synonyms.yml` and the relationship design.

## Important implementation note

The script creates Fabric item containers and uploads source files. It does **not** fully deploy working notebook code, Power BI report visuals, or a production TMDL semantic model because those must match the final Gold lakehouse schema after you materialize the tables.

