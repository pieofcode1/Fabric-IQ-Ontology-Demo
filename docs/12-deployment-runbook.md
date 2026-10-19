# Nimbus Demo: Capacity to Deployment Runbook

Use this document as the single execution guide.
Follow the steps in order and pass each checkpoint before continuing.
The linked design documents provide schemas and context; they are not alternative deployment sequences.

**Status:** every numbered step includes a CLI/script option alongside the portal instructions.
Use PowerShell 7, Azure CLI, and Bicep for the CLI path, running commands from the repository root in the same terminal.
The [Fabric REST helper](../deployment/Invoke-FabricStep.ps1) supports `-WhatIf`, checks tenant/subscription context, and returns HTTP status and asynchronous operation/job receipts.
The [source uploader](../deployment/Upload-FabricGenerator.ps1) uses a OneLake storage token without printing it.
Silver/Gold transformations have local Spark regression coverage, but their Fabric execution and the report, ontology, Data Agent, and Activator stages still require live verification.
For those stages the CLI commands import authored definitions or execute implemented notebooks; they do not manufacture missing application logic.
No live deployment was performed while writing this guide.

## 1. Confirm Access and Record Deployment Values

1. Confirm your Azure subscription belongs to the same Microsoft Entra tenant as your Fabric account.
2. Obtain permission to create Microsoft Fabric capacities in the intended resource group.
3. Ask the Fabric administrator to enable Fabric for your account and confirm the required IQ, ontology, Data Agent, and Copilot features are available in the tenant and region.
4. Confirm workspace creation permission and Power BI licensing for everyone who will view the report.
5. Record the following values without copying tokens or secrets into this repository.

| Value | Suggested demo value or source |
|---|---|
| Tenant ID | Your approved tenant, not the existing script's defaults |
| Subscription ID | Your approved Azure subscription |
| Resource group | `rg-nimbus-fabric-demo` |
| Capacity name | `nimbusfabricdemo` (subject to portal validation) |
| Region | Supported region approved for your data and intended workloads |
| SKU | Budget-approved F SKU; verify feature-specific minimums before purchase |
| Capacity administrator | An internal user in the same tenant, not a B2B guest |
| Workspace name | `nimbus-fabric-iq-demo-dev` |
| Asset prefix | `nimbus_iq` |
| Fabric capacity ID | Fabric capacity GUID, not the Azure ARM resource path |

Do not assume the smallest SKU supports every IQ/Copilot capability or the intended concurrent Spark workload.
Review current [capacity purchase prerequisites][capacity] and [regional availability][regions].

### CLI Option

Initialize config files once, fill their placeholders, and dot-source the environment script in this PowerShell terminal.
Dot-sourcing is intentional: it makes the isolated Azure config paths, verified context, and helper functions available to later CLI steps in this same session.
The tenant, subscription, resource group, workspace name, and asset prefix come from `fabric-capacity.param.txt`; capacity resource properties come from `fabric-capacity.bicepparam`.
Fabric REST commands read tenant and subscription IDs directly from the config file, so they do not depend on `$FabricContext`.
Initialization is still required for isolated authentication and the request-writing helpers; `$FabricContext` is retained for the source uploader.

```powershell
./deployment/Deploy-FabricCapacity.ps1 -ConfigFile ./deployment/fabric-capacity.param.txt -Action InitializeConfig
code ./deployment/fabric-capacity.param.txt
code ./infra/fabric-capacity.bicepparam
$DemoContext = . ./deployment/Initialize-env.ps1 -ConfigFile ./deployment/fabric-capacity.param.txt
$FabricContext = $DemoContext.FabricContext
./deployment/Invoke-FabricStep.ps1 -ConfigFile ./deployment/fabric-capacity.param.txt -Method GET -Path capacities
$capacities = ./deployment/Invoke-FabricStep.ps1 -ConfigFile ./deployment/fabric-capacity.param.txt -Method GET -Path capacities
$capacities.body.value | Format-Table id, displayName, sku, state
```

The list API shows capacities you can access, not every capacity in the tenant.
If a list response has `continuationUri`, fetch that URI with the same helper before concluding an item is absent.
Tenant feature enablement, licensing, regional availability, and CU quota still require administrator confirmation.

**Checkpoint:** subscription, tenant, administrator, region, SKU, licensing, and spending approval are confirmed.

## 2. Create the Paid Fabric Capacity in Azure

1. Open [Azure portal][azure] and select the approved directory and subscription.
2. Open the subscription's **Resource providers** and register `Microsoft.Fabric` if it is not registered.
3. Confirm regional Fabric CU quota is sufficient for the selected SKU; request an increase if needed.
4. Search for **Microsoft Fabric**, then select **Create Fabric Capacity**.
5. Select the subscription, resource group, capacity name, region, size, and Fabric capacity administrator from step 1.
6. Add owner, environment, and cost-center tags appropriate to your organization.
7. Review the price and select **Review + create**, then **Create** only after approving the cost.
8. Wait for deployment completion and confirm the capacity is active.
9. Configure a budget and cost alert at the resource-group or subscription scope.

Capacity compute is billable while active, even when you are not using the demo.
Azure resource permissions and Fabric capacity/workspace permissions are separate.

### CLI Option

The [capacity template](../infra/fabric-capacity.bicep) requires explicit sizing and uses the documented `2026-08-01-preview` resource API with overage disabled.
If your organization disallows preview resource APIs, use the portal path or an approved stable template instead.
Check quota and obtain spending approval before the create command.
Run [Deploy-FabricCapacity.ps1](../deployment/Deploy-FabricCapacity.ps1) for the CLI path.
It accepts a deployment-context file plus the [Bicep parameter-file example](../infra/fabric-capacity.bicepparam.example); both populated local files are Git-ignored.

Open the context and Bicep parameter files created in step 1 and replace every remaining placeholder before continuing.
The Bicep example sets no SKU default; enter the SKU approved in step 1.
Use Azure region names such as `canadacentral` for the resource-group location.
Since the populated files are Git-ignored, keep protected backups if your organization requires them.
The capacity name must match `^[a-z][a-z0-9]*$` (letters and digits only, starting with a letter); for example, use `nimbusiqf16`, not `nimbus-iq-f16`.

```powershell
./deployment/Deploy-FabricCapacity.ps1 -ConfigFile ./deployment/fabric-capacity.param.txt -Action RegisterProvider
./deployment/Deploy-FabricCapacity.ps1 -ConfigFile ./deployment/fabric-capacity.param.txt -Action CreateResourceGroup
./deployment/Deploy-FabricCapacity.ps1 -ConfigFile ./deployment/fabric-capacity.param.txt -Action Validate
./deployment/Deploy-FabricCapacity.ps1 -ConfigFile ./deployment/fabric-capacity.param.txt -Action Preview
```

Review the what-if and estimated cost before executing this separate purchase operation.

```powershell
./deployment/Deploy-FabricCapacity.ps1 -ConfigFile ./deployment/fabric-capacity.param.txt -Action Deploy
./deployment/Deploy-FabricCapacity.ps1 -ConfigFile ./deployment/fabric-capacity.param.txt -Action Verify
```

`RegisterProvider` and `CreateResourceGroup` prepare Azure prerequisites; `Validate` checks the template, `Preview` shows proposed changes, `Deploy` creates the billable capacity and prompts for confirmation, and `Verify` reads the deployment output and capacity state.
The script takes the deployment-context file as one input instead of repeating tenant, subscription, resource group, and file paths on every command.
Capacity resource values (name, capacity region, SKU, administrator, and owner) live in the `.bicepparam` file; tenant, subscription, resource group, and resource-group region live in `fabric-capacity.param.txt` because they select the authenticated deployment context.
`-Action` remains explicit so each command states whether it registers, prepares, validates, previews, deploys, or verifies; reading a config file cannot accidentally trigger a deployment.

Budget creation is separate from capacity provisioning; the template does not create a budget or grant Azure/Fabric roles.
Do not proceed until your organization's cost-alert configuration is in place.

**Checkpoint:** the Azure capacity exists and your capacity administrator can see it in Fabric.

## 3. Create and Assign the Fabric Workspace

1. Open [Microsoft Fabric][fabric] using the same tenant account.
2. Select **Workspaces > New workspace** and create the configured workspace name shown by `$DemoContext.WorkspaceName`.
3. In workspace settings, find the license/capacity assignment and select the new Fabric capacity.
4. Grant only the required workspace roles to the demo builders and viewers.
5. Confirm the workspace is not still assigned to shared/Pro or an unintended trial capacity.
6. Record the workspace ID and Fabric capacity GUID from Fabric settings or the Fabric capacities API if automation will be used later.

The existing script only uses `-CapacityId` when creating a new workspace.
It does not reassign an already-existing workspace; perform that assignment here.

### CLI Option

Discover the Fabric capacity GUID, create the workspace only if absent, and explicitly assign its capacity even when it already exists.
Avoid automatic selection when multiple names match.

```powershell
$capacities = ./deployment/Invoke-FabricStep.ps1 -ConfigFile ./deployment/fabric-capacity.param.txt -Method GET -Path capacities
$capacities.body.value | Format-Table id, displayName, sku, state
$CapacityId = '<Fabric-capacity-guid-from-list>'
$workspaces = ./deployment/Invoke-FabricStep.ps1 -ConfigFile ./deployment/fabric-capacity.param.txt -Method GET -Path workspaces
$workspaces.body.value | Format-Table id, displayName, capacityId
```

For a new workspace only:

```powershell
$request = Write-DemoRequest 'workspace.json' @{ displayName = $DemoContext.WorkspaceName; capacityId = $CapacityId }
$createdWorkspace = ./deployment/Invoke-FabricStep.ps1 -ConfigFile ./deployment/fabric-capacity.param.txt -Method POST -Path workspaces -BodyPath $request
```

Use the returned workspace ID or rediscover it after creation has completed.

```powershell
$WorkspaceId = '<created-or-existing-workspace-guid>'
$request = Write-DemoRequest 'assign-capacity.json' @{ capacityId = $CapacityId }
$assignment = ./deployment/Invoke-FabricStep.ps1 -ConfigFile ./deployment/fabric-capacity.param.txt -Method POST -Path "workspaces/$WorkspaceId/assignToCapacity" -BodyPath $request
$verifiedWorkspace = ./deployment/Invoke-FabricStep.ps1 -ConfigFile ./deployment/fabric-capacity.param.txt -Method GET -Path "workspaces/$WorkspaceId"
$verifiedWorkspace.body | Format-List id, displayName, capacityId
```

Assignment may return HTTP 202 without an operation URL; repeat the GET after the server's recommended interval and continue only when `capacityId` matches.
For other asynchronous operations, use the common status commands below rather than resubmitting the POST.

```powershell
$OperationId = '<operationId-from-receipt>'
$operation = ./deployment/Invoke-FabricStep.ps1 -ConfigFile ./deployment/fabric-capacity.param.txt -Method GET -Path "operations/$OperationId"
$operation.body | Format-List
```

When status is `Succeeded`, retrieve the result if the initiating API produces one:

```powershell
$result = ./deployment/Invoke-FabricStep.ps1 -ConfigFile ./deployment/fabric-capacity.param.txt -Method GET -Path "operations/$OperationId/result"
$result.body | Format-List
```

For HTTP 429, honor `Retry-After` before retrying; for permission or validation failures, correct the cause first.

**Checkpoint:** the workspace is assigned to the correct active capacity and can create Fabric items.

## 4. Create the Initial Lakehouses and Notebook

Use the Fabric portal for the first deployment; local Python and Azure CLI are not required for this path.

1. In the workspace, create Lakehouses named `nimbus_iq_bronze`, `nimbus_iq_silver`, and `nimbus_iq_gold`.
2. In the Bronze Lakehouse Files area, create `src/data_generator/config` and `landing/raw` folders.
3. Upload [generate.py](../src/data_generator/generate.py) and [validate_scenario.py](../src/data_generator/validate_scenario.py) into `Files/src/data_generator/`.
4. Upload [scenario_config.yaml](../src/data_generator/config/scenario_config.yaml) into `Files/src/data_generator/config/`.
5. Import [Generate_Nimbus_Scenario_Data.ipynb](../notebooks/Generate_Nimbus_Scenario_Data.ipynb) into the workspace and name the notebook `nimbus_iq_generate_scenario_data`.
6. Attach `nimbus_iq_bronze` as the notebook's default Lakehouse.

Alternatively, [Create-FabricAssets.ps1](../deployment/Create-FabricAssets.ps1) attempts item creation and file upload as described in the [script reference](../deployment/README.md).
It is not the recommended first-run path: placeholder creation is unverified for some item types, API long-running operations are not fully handled, and native CLI exit codes are not consistently checked.
It does not deploy notebook definitions, transformations, reports, or a working Activator rule.
If using it later, explicitly supply your own tenant/subscription values rather than relying on its existing defaults.

### CLI Option

Use the scoped helper rather than the older all-assets placeholder script for the first CLI deployment.
List items before creating them; these commands deliberately do not delete or automatically replace existing items.

```powershell
$items = ./deployment/Invoke-FabricStep.ps1 -ConfigFile ./deployment/fabric-capacity.param.txt -Method GET -Path "workspaces/$WorkspaceId/items"
$items.body.value | Format-Table id, displayName, type
foreach ($name in @('nimbus_iq_bronze', 'nimbus_iq_silver', 'nimbus_iq_gold')) {
	$existing = @($items.body.value | Where-Object { $_.displayName -eq $name })
	if ($existing.Count -gt 1) { throw "Ambiguous item name: $name" }
	if ($existing.Count -eq 1) {
		if ($existing[0].type -ne 'Lakehouse') { throw "Name is used by a non-Lakehouse: $name" }
		continue
	}
	$request = Write-DemoRequest "$name.json" @{ displayName = $name; type = 'Lakehouse' }
	./deployment/Invoke-FabricStep.ps1 -ConfigFile ./deployment/fabric-capacity.param.txt -Method POST -Path "workspaces/$WorkspaceId/items" -BodyPath $request
}
```

Complete any returned operations, then list items again and record the Bronze ID.
Upload sources (and optionally samples with `-IncludeSamples`) to OneLake by workspace/item GUID.

```powershell
$BronzeId = '<bronze-lakehouse-guid>'
./deployment/Upload-FabricGenerator.ps1 @FabricContext -WorkspaceId $WorkspaceId -LakehouseId $BronzeId -WhatIf
./deployment/Upload-FabricGenerator.ps1 @FabricContext -WorkspaceId $WorkspaceId -LakehouseId $BronzeId
```

Apply the local notebook corrections described in step 5 before import; no portal editing is required.
The import helper adds the default-Lakehouse metadata to the deployed copy without changing the local file.

```powershell
$notebookArgs = @{
	NotebookPath = './notebooks/Generate_Nimbus_Scenario_Data.ipynb'
	DisplayName = 'nimbus_iq_generate_scenario_data'
	LakehouseId = $BronzeId
	WorkspaceId = $WorkspaceId
}
./deployment/Invoke-FabricStep.ps1 -ConfigFile ./deployment/fabric-capacity.param.txt @notebookArgs -Method POST -Path "workspaces/$WorkspaceId/items" -WhatIf
$import = ./deployment/Invoke-FabricStep.ps1 -ConfigFile ./deployment/fabric-capacity.param.txt @notebookArgs -Method POST -Path "workspaces/$WorkspaceId/items"
```

If the notebook already exists, use `workspaces/$WorkspaceId/items/$NotebookId/updateDefinition` instead of the create path, after reviewing that replacement.
Never rerun a create request merely because it returned HTTP 202.

**Checkpoint:** three Lakehouses exist, the source files are in Bronze, and the imported notebook has the correct default Lakehouse.

## 5. Generate and Validate Bronze Data

1. Review the imported notebook before running it against any existing data; its Delta writes use overwrite mode.
2. In the parameters cell, set `output_mode = "both"` and `table_prefix = ""`.
3. Leave the scenario scale and seed at their defaults for the initial acceptance run.
4. In the source-loading cell, use `lakehouse_files_root = Path("/lakehouse/default/Files")` for the attached Spark Lakehouse.
5. Remove the preceding `getMountPath("/")` call for this default-Lakehouse path; it assumes a separately established mount that the notebook does not create.
6. Run the notebook top to bottom, allowing the session-scoped Faker/PyYAML installation or using an administrator-provided Fabric Environment if package installation is restricted.
7. Confirm the CSV landing files and managed Delta tables are present.
8. Confirm the validator prints `PASS: 21  FAIL: 0`; stop if any check fails.

The empty table prefix is intentional: filenames already begin with `raw_`, so the notebook's current default would create names such as `raw_raw_accounts`.
These are known setup corrections to the current notebook, not verified fixes committed to its code.
The acceptance checks validate generated CSVs, not Delta readback; also compare Delta row counts with the notebook's generation summary.
Expect 18 datasets, including both incident bridges and investigations.

For the alternative local generation path, follow the commands in the [generator guide](../src/data_generator/README.md), validate the CSVs, upload them to `Files/landing/raw`, and load them into Bronze Delta tables.
Do not regenerate locally if you already completed the Fabric-native path.

### CLI Option

After completing notebook creation and recording its ID, start a Fabric job:

```powershell
$NotebookId = '<generator-notebook-guid>'
$job = ./deployment/Invoke-FabricStep.ps1 -ConfigFile ./deployment/fabric-capacity.param.txt -Method POST -Path "workspaces/$WorkspaceId/items/$NotebookId/jobs/RunNotebook/instances"
$job | Format-List statusCode, location, retryAfter
```

After `Retry-After`, inspect the exact `location` returned by the job API:

```powershell
$jobStatus = ./deployment/Invoke-FabricStep.ps1 -ConfigFile ./deployment/fabric-capacity.param.txt -Method GET -Path $job.location
$jobStatus.body | Format-List
```

Continue only when the job reports `Completed`, not merely HTTP 202.
The scheduler status alone does not provide the 21-check report; inspect notebook outputs and reconcile table counts before accepting this stage.
The job uses the parameters saved in the imported notebook, including the overwrite behavior.

For local generation instead:

```powershell
uv sync
if ($LASTEXITCODE) { throw 'Dependency setup failed.' }
uv run python ./src/data_generator/generate.py --config ./src/data_generator/config/scenario_config.yaml --output ./sample_output
if ($LASTEXITCODE) { throw 'Generation failed.' }
uv run python ./src/data_generator/validate_scenario.py --data ./sample_output
if ($LASTEXITCODE) { throw 'Scenario validation failed.' }
./deployment/Upload-FabricGenerator.ps1 @FabricContext -WorkspaceId $WorkspaceId -LakehouseId $BronzeId -IncludeSamples
```

Uploading CSVs alone does not load Bronze Delta tables; run an implemented ingestion notebook to do that if skipping the generator notebook.

**Checkpoint:** 18 Bronze tables have the intended names and counts, CSV validation passes 21 checks, and the headline incident is `INC-2026-ONT-001`.

## 6. Create and Run Silver and Gold Transformations

The repository now includes [Bronze-to-Silver](../notebooks/Transform_Nimbus_Bronze_To_Silver.ipynb) and [Silver-to-Gold](../notebooks/Transform_Nimbus_Silver_To_Gold.ipynb) notebooks backed by [medallion.py](../src/data_generator/medallion.py).
Silver produces 18 conformed tables; Gold produces 24 tables, including both causal bridges, investigations, calendar, hourly telemetry, and impact/dispatch summaries.
Notebook creation alone does not create tables: run Silver successfully before running Gold.

1. Upload the current generator, validator, shared transformation module, and scenario config to Bronze `Files/src/data_generator/` using the source uploader below or the Fabric Files upload UI.
2. If Bronze was generated before these transformations were added, refresh it using the updated generator in step 5 after reviewing its overwrite behavior.
3. Import the Silver notebook as `nimbus_iq_silver_transform` and attach `nimbus_iq_silver` as its default lakehouse.
4. Import the Gold notebook as `nimbus_iq_gold_curate` and attach `nimbus_iq_gold` as its default lakehouse.
5. Review cell 2 in each notebook: names must match your lakehouses; an empty `source_workspace_id` uses the current workspace, and `source_schema = 'auto'` detects legacy or `dbo` source tables.
6. Run Silver from top to bottom and confirm its final `status: PASS` output, 18 table row counts, and headline incident totals.
7. Run Gold from top to bottom and confirm its final `status: PASS` output, 24 row counts, and reconciled incident-impact summary.

The generator now prevents reversed work-order timestamps, unrelated incident-service/alarm links, and support-case customers from another account.
Previously generated Bronze rows are not silently repaired by Silver; a failed check stops the run before any Silver write.
All timestamps are conformed to UTC; monetary columns use decimal types.
The notebooks discover source lakehouse GUIDs and read explicit OneLake Delta paths, while managed writes use the attached destination lakehouse's default namespace.
For a custom source schema, set `source_schema` explicitly instead of `auto`.

Existing destination tables are protected by default.
Set `allow_replace = True` in cell 2 only after approving a full refresh of that layer's named outputs.
This is a demo full-refresh implementation, not an incremental production pipeline; writes are individually atomic per Delta table, not atomic across all tables.
If a write fails halfway through, do not run the next layer; repair the failure and explicitly authorize replacement to rerun the failed layer.
Once both notebooks are verified, an orchestration pipeline can run Bronze, Silver, and Gold in dependency order; no pipeline definition is shipped by this step.

**Checkpoint:** 18 Silver and 24 Gold tables exist in the correct lakehouses, readback checks pass, and impact totals reconcile to the incident bridges and investigations.

### CLI Option

Upload the shared source module to Bronze, then preview both imports with the destination bindings.
Use the IDs from step 4; do not create new lakehouses for this step.

```powershell
$SilverId = '<silver-lakehouse-guid>'
$GoldId = '<gold-lakehouse-guid>'
./deployment/Upload-FabricGenerator.ps1 @FabricContext -WorkspaceId $WorkspaceId -LakehouseId $BronzeId -WhatIf
./deployment/Upload-FabricGenerator.ps1 @FabricContext -WorkspaceId $WorkspaceId -LakehouseId $BronzeId
$silverArgs = @{
	NotebookPath = './notebooks/Transform_Nimbus_Bronze_To_Silver.ipynb'
	DisplayName = 'nimbus_iq_silver_transform'
	WorkspaceId = $WorkspaceId
	LakehouseId = $SilverId
	LakehouseName = 'nimbus_iq_silver'
}
$goldArgs = @{
	NotebookPath = './notebooks/Transform_Nimbus_Silver_To_Gold.ipynb'
	DisplayName = 'nimbus_iq_gold_curate'
	WorkspaceId = $WorkspaceId
	LakehouseId = $GoldId
	LakehouseName = 'nimbus_iq_gold'
}
./deployment/Invoke-FabricStep.ps1 -ConfigFile ./deployment/fabric-capacity.param.txt @silverArgs -Method POST -Path "workspaces/$WorkspaceId/items" -WhatIf
./deployment/Invoke-FabricStep.ps1 -ConfigFile ./deployment/fabric-capacity.param.txt @goldArgs -Method POST -Path "workspaces/$WorkspaceId/items" -WhatIf
```

List workspace items first as in step 4 and confirm neither notebook name is already present before running these create requests.
For an existing notebook, use its `workspaces/$WorkspaceId/items/$NotebookId/updateDefinition` path instead, after approving the replacement.
The CLI import binds the default lakehouse; adjust cell 2 locally before import if you use non-default names or source workspaces.

```powershell
$silverImport = ./deployment/Invoke-FabricStep.ps1 -ConfigFile ./deployment/fabric-capacity.param.txt @silverArgs -Method POST -Path "workspaces/$WorkspaceId/items"
$goldImport = ./deployment/Invoke-FabricStep.ps1 -ConfigFile ./deployment/fabric-capacity.param.txt @goldArgs -Method POST -Path "workspaces/$WorkspaceId/items"
$silverImport, $goldImport | Format-List statusCode, operationId, location, retryAfter, body
```

Complete each creation operation using the status/result commands in step 3, and record the notebook IDs from the result or the workspace item list.
Before starting a job, check its recent runs; monitor a recent or active run instead of resubmitting it.

```powershell
$SilverNotebookId = '<silver-notebook-guid>'
$GoldNotebookId = '<gold-notebook-guid>'
$recentSilver = ./deployment/Invoke-FabricStep.ps1 -ConfigFile ./deployment/fabric-capacity.param.txt -Method GET -Path "workspaces/$WorkspaceId/items/$SilverNotebookId/jobs/instances"
$recentSilver.body.value | Format-Table id, status, startTimeUtc, endTimeUtc
```

Start Silver only when there is no active or recent run that needs monitoring.

```powershell
$silverJob = ./deployment/Invoke-FabricStep.ps1 -ConfigFile ./deployment/fabric-capacity.param.txt -Method POST -Path "workspaces/$WorkspaceId/items/$SilverNotebookId/jobs/RunNotebook/instances"
$silverJob | Format-List statusCode, location, retryAfter
```

After the receipt's `Retry-After`, check its exact location.

```powershell
./deployment/Invoke-FabricStep.ps1 -ConfigFile ./deployment/fabric-capacity.param.txt -Method GET -Path $silverJob.location
```

Wait for Silver to report `Completed` and pass its data checks before running Gold.

```powershell
$recentGold = ./deployment/Invoke-FabricStep.ps1 -ConfigFile ./deployment/fabric-capacity.param.txt -Method GET -Path "workspaces/$WorkspaceId/items/$GoldNotebookId/jobs/instances"
$recentGold.body.value | Format-Table id, status, startTimeUtc, endTimeUtc
```

Start Gold only when there is no active or recent Gold run that needs monitoring.

```powershell
$goldJob = ./deployment/Invoke-FabricStep.ps1 -ConfigFile ./deployment/fabric-capacity.param.txt -Method POST -Path "workspaces/$WorkspaceId/items/$GoldNotebookId/jobs/RunNotebook/instances"
$goldJob | Format-List statusCode, location, retryAfter
```

After `Retry-After`, check Gold's returned location.

```powershell
./deployment/Invoke-FabricStep.ps1 -ConfigFile ./deployment/fabric-capacity.param.txt -Method GET -Path $goldJob.location
```

Honor each receipt's `Retry-After` before status checks.
An authored pipeline definition can be imported using the definition mechanism below with `-ItemType DataPipeline`; empty pipeline creation is not orchestration.

## 7. Build, Validate, and Publish the Semantic Model and Report

Follow [Build the Nimbus Semantic Model and Report](09-semantic-model-for-iq.md) in order; it contains the exact table mapping, TMDL application instructions, DAX validation, and report creation steps.
This is a supported interactive first-run authoring workflow, not an unattended REST deployment of an empty model.

1. Confirm step 6 produced all 24 Gold tables, then check Desktop version, paid authoring license, lakehouse/model permissions, tenant XMLA enablement, and capacity XMLA **Read Write** access.
2. In Power BI Desktop's **OneLake catalog**, connect to the Gold **Lakehouse**, name the model `nimbus_iq_semantic_model`, select the 20 base tables in the detailed guide, and create it in the demo workspace.
3. In **Model view**, rename semantic tables to the exact business names in that mapping; leave physical Gold names, source bindings, and snake_case columns unchanged.
4. Back up the model using **Version history** or PBIP export, review/remove overlapping auto-detected relationships, and open **TMDL view**.
5. Script the complete existing semantic model in TMDL view, merge the properties from [model.tmdl](../semantic_model/tmdl/model.tmdl) under its ordinary `model` declaration while preserving all descendants/source bindings, and **Preview > Apply**; never apply this property fragment alone or put properties under `ref model`.
6. In separate tabs, paste and **Preview > Apply** [relationships.tmdl](../semantic_model/tmdl/relationships.tmdl), then [measures.tmdl](../semantic_model/tmdl/measures.tmdl).
7. Stop on any Problems/Output error, refresh/reframe the model, and run [validate_model.dax](../semantic_model/validate_model.dax) in **DAX query view**; require headline comparison flags to be `TRUE` and dispatch mismatches to be zero.
8. Create a separate **Blank report**, connect to the existing semantic model rather than live-editing it, build the four report pages described in the detailed guide, and publish `nimbus_iq_service_assurance_report` to the demo workspace.
9. Check model binding, headline totals, filter behavior, and viewer permissions/licensing in the published report before continuing to step 8.

The base model uses `fact_network_telemetry`, not the hourly aggregate, and includes `agg_dispatch_priority` as the semantic table **Dispatch Priority**.
Four Gold tables are optional and intentionally excluded from the 20-table base model: `dim_region`, `fact_network_telemetry_hourly`, `agg_service_health_daily`, and `agg_customer_impact_by_incident`.
An Incident slicer filters the incident facts and bridges; it does not automatically apply incident time windows to telemetry or incident attribution to global revenue/churn measures.
Do not sum repeated incident exposure from dispatch rows or enable bidirectional relationships globally to make visuals respond.
Desktop Direct Lake live editing saves semantic-model changes directly in Fabric, with no separate model Publish action; the thin report has its own Publish action.

**Checkpoint:** the 20-table model has 27 applied measures, DAX reconciliation passes against step 6, and the published report is correctly bound and verified with the intended viewer.

### CLI Option

For the first run, use Desktop/TMDL view above to generate actual table partitions, columns, credentials, and report visuals.
The CLI can inventory the resulting semantic model and report without creating duplicate placeholders:

```powershell
$step7Items = ./deployment/Invoke-FabricStep.ps1 -ConfigFile ./deployment/fabric-capacity.param.txt -Method GET -Path "workspaces/$WorkspaceId/items"
$step7Items.body.value | Where-Object { $_.type -in @('SemanticModel', 'Report') } | Format-Table id, displayName, type
```

For later API redeployment, export the complete authored model/report to PBIP and prepare only their supported public-definition parts with the correct target Gold bindings and report model ID.
Model parts include `definition.pbism` and serialized `definition/` metadata; report parts include `definition.pbir` and the authored report `definition/` metadata.
Exclude local `.pbi` caches, PBIP entry files, and `TMDLScripts` from the public-definition directories.
The repository's `semantic_model/tmdl` folder contains a merge-only property fragment and executable relationship/measure scripts, not these serialized public definitions; do not pass it to `-DefinitionDirectory`.

```powershell
$ModelParts = '<absolute-path-to-prepared-exported-model-public-parts>'
$ReportParts = '<absolute-path-to-prepared-exported-report-public-parts>'
$model = ./deployment/Invoke-FabricStep.ps1 -ConfigFile ./deployment/fabric-capacity.param.txt -Method POST -Path "workspaces/$WorkspaceId/items" -DefinitionDirectory $ModelParts -DisplayName nimbus_iq_semantic_model -ItemType SemanticModel -WhatIf
```

Remove `-WhatIf` to deploy after review, complete the operation, and bind the report definition to the resulting model ID before importing it.

```powershell
./deployment/Invoke-FabricStep.ps1 -ConfigFile ./deployment/fabric-capacity.param.txt -Method POST -Path "workspaces/$WorkspaceId/items" -DefinitionDirectory $ReportParts -DisplayName nimbus_iq_service_assurance_report -ItemType Report -WhatIf
```

For updates, use `items/<existing-item-id>/updateDefinition` with the same definition directory.
The helper omits `.platform` from updates because metadata updates are not requested.
API permissions, viewer licensing, DAX query validation, and report rendering still require verification after API redeployment.
These optional redeployment commands do not replace the executable first-run Desktop procedure or prove that a published model queries correctly.

## 8. Configure Ontology and Data Agent (Manual Gate)

1. Confirm the tenant, region, and selected capacity support the required preview/AI features before proceeding.
2. Create the ontology using the deployed Gold entities and relationships in [the ontology model](03-ontology-model.md).
3. Apply the business terminology in [iq_synonyms.yml](../semantic_model/iq_synonyms.yml).
4. Create a Data Agent, select its supported deployed data sources, and configure persona-specific instructions using [the use-case catalog](11-data-agent-use-cases.md).
5. Test the golden-scenario questions against known totals and with the intended user's permissions.
6. Require human approval for operational recommendations; an answer alone must not dispatch staff or create work orders.

**Checkpoint:** grounded answers reproduce the expected incident story without exposing data beyond the caller's access.

### CLI Option

Use this definition import pattern only if the target tenant/API supports the respective item type and you have authored valid public definitions with deployed data-source IDs.
Feature enablement and definition schemas are not inferred from the YAML design files.

```powershell
./deployment/Invoke-FabricStep.ps1 -ConfigFile ./deployment/fabric-capacity.param.txt -Method POST -Path "workspaces/$WorkspaceId/items" -DefinitionDirectory '<authored-ontology-parts-directory>' -DisplayName nimbus_iq_ontology -ItemType Ontology -WhatIf
./deployment/Invoke-FabricStep.ps1 -ConfigFile ./deployment/fabric-capacity.param.txt -Method POST -Path "workspaces/$WorkspaceId/items" -DefinitionDirectory '<authored-data-agent-parts-directory>' -DisplayName nimbus_iq_data_agent -ItemType DataAgent -WhatIf
```

Remove `-WhatIf` separately after schema and permission review, then complete each returned operation.
Where public definition import is unavailable, bootstrap that item in the portal and retain the CLI inventory/status checks; do not substitute undocumented APIs.
Automated golden-answer evaluation is not yet provided by this repository.

## 9. Add Real-Time Ingestion (Optional, Manual Gate)

1. Create an Eventhouse, then create its KQL database inside that Eventhouse using the Fabric portal.
2. Create telemetry/alarm tables and ingestion mappings matching the payloads from [stream_simulator.py](../src/data_generator/stream_simulator.py).
3. Create an Eventstream custom application source and configure routing to those KQL tables.
4. Keep connection strings in approved secret storage, never in committed scripts or notebook output.
5. Run the replay with the `eventhub` sink using the [streaming instructions](../src/data_generator/README.md).
6. Verify event counts and event-time values in Eventhouse before connecting alerts.

The current replay is a Python script and requires a runner with its optional Event Hub dependency.
The generation notebook is not a Fabric-native streaming replay implementation.
If local execution is restricted, a managed runner or an additional Fabric replay notebook must be implemented before this step is usable.

**Checkpoint:** telemetry arrives continuously with current/rebased timestamps and the expected asset IDs.

### CLI Option

Create an Eventhouse, complete provisioning, and record its ID.

```powershell
$request = Write-DemoRequest 'eventhouse.json' @{ displayName = 'nimbus_iq_eventhouse'; type = 'Eventhouse' }
$eventhouse = ./deployment/Invoke-FabricStep.ps1 -ConfigFile ./deployment/fabric-capacity.param.txt -Method POST -Path "workspaces/$WorkspaceId/items" -BodyPath $request
$EventhouseId = '<eventhouse-guid-after-completion>'
$request = Write-DemoRequest 'kql-database.json' @{
	displayName = 'nimbus_iq_kql'
	creationPayload = @{ databaseType = 'ReadWrite'; parentEventhouseItemId = $EventhouseId }
}
$database = ./deployment/Invoke-FabricStep.ps1 -ConfigFile ./deployment/fabric-capacity.param.txt -Method POST -Path "workspaces/$WorkspaceId/kqlDatabases" -BodyPath $request
```

Deploy an authored Eventstream topology and mappings using its documented public definition parts:

```powershell
./deployment/Invoke-FabricStep.ps1 -ConfigFile ./deployment/fabric-capacity.param.txt -Method POST -Path "workspaces/$WorkspaceId/items" -DefinitionDirectory '<authored-eventstream-parts-directory>' -DisplayName nimbus_iq_eventstream -ItemType Eventstream -WhatIf
```

The topology, KQL DDL/mappings, and routing must be authored and validated; the command is not a substitute for them.
For a CLI replay, install the optional SDK into an isolated uv execution environment and place the connection string in the environment without printing it.
The script reads `EVENTSTREAM_CONNECTION_STRING` and `EVENTSTREAM_EVENTHUB_NAME`; populate these through your approved secret mechanism, not command-line arguments or committed files.
Use the exact CLI option names from the streaming guide:

```powershell
if (-not $env:EVENTSTREAM_CONNECTION_STRING -or -not $env:EVENTSTREAM_EVENTHUB_NAME) {
	throw 'Set Eventstream credentials through your approved secret mechanism first.'
}
uv run --with azure-eventhub python ./src/data_generator/stream_simulator.py --data ./sample_output --incident INC-2026-ONT-001 --speed 60 --sink eventhub
```

This remains a foreground process until its replay ends (or indefinitely if `--loop` is supplied).
Do not start it until the Eventstream routing and secrets are configured.

## 10. Configure Activator (Optional, Unverified Template)

1. Mirror the asset-to-incident lookup into the KQL database as `network_incident_bridge` with the columns required by [the Activator source query](../deployment/activator/network_degradation_query.kql).
2. Confirm the lookup is scoped to the intended incident/service and does not join historical unrelated incidents into the live replay.
3. Execute the query with an explicit event-time window and verify its output before creating the rule.
4. Create an Activator item in Fabric and configure asset-keyed packet-loss tracking, threshold crossing above 5%, and the approved notification recipients.
5. Keep notifications disabled during initial testing; use a designated test recipient before enabling production recipients.
6. Use [ReflexEntities.template.json](../deployment/activator/ReflexEntities.template.json) only as a draft reference, not a proven import payload.
7. Before any API import, validate source-event wiring, per-asset state, real IDs, recipients, and the initial time window against the target tenant.
8. Test normal, critical, recovery, and repeated readings on multiple assets to verify alerts are neither missed nor triggered by another asset's state.

The template's rule/source wiring has not been accepted by a live Fabric service.
Its fixed June 2026 window must not be assumed correct for a now-rebased replay.
Work-order creation is not implemented; the current draft only describes Teams notifications.

**Checkpoint:** a test notification arrives for the correct asset/incident, and recovery/repeated readings behave as intended.

### CLI Option

Create a Reflex item using its item-specific endpoint:

```powershell
$request = Write-DemoRequest 'activator.json' @{ displayName = 'nimbus_iq_degradation_alert'; description = 'Nimbus packet-loss alert' }
$activator = ./deployment/Invoke-FabricStep.ps1 -ConfigFile ./deployment/fabric-capacity.param.txt -Method POST -Path "workspaces/$WorkspaceId/reflexes" -BodyPath $request
$ActivatorId = '<reflex-guid-after-completion>'
```

Build a validated `ReflexEntities.json` in an external definition-parts directory using Python JSON serialization, with source wiring, per-asset identity, real recipients, and `shouldRun: false` for the safe verification phase.
Do not import the current template directly or generate its nested JSON strings with PowerShell.

```powershell
./deployment/Invoke-FabricStep.ps1 -ConfigFile ./deployment/fabric-capacity.param.txt -Method POST -Path "workspaces/$WorkspaceId/reflexes/$ActivatorId/updateDefinition" -DefinitionDirectory '<validated-activator-parts-directory>' -WhatIf
```

Remove `-WhatIf` after validating the stopped definition, complete the operation, then read it back:

```powershell
$readback = ./deployment/Invoke-FabricStep.ps1 -ConfigFile ./deployment/fabric-capacity.param.txt -Method POST -Path "workspaces/$WorkspaceId/reflexes/$ActivatorId/getDefinition"
```

Enable notifications only after the disabled-rule checks and test-recipient approval.
No script here automatically starts the unverified alert draft.

## 11. Run the Demo and Pause the Capacity

1. Follow [the demo script](06-demo-script.md) and verify each answer against the deployed data.
2. Record which optional features were actually enabled; do not present placeholders as functioning services.
3. Stop any replay process and scheduled demo jobs when the session ends.
4. Confirm nobody is using other workspaces on the same capacity.
5. In Azure portal, open the Fabric capacity and select **Pause** when appropriate.
6. Resume it before the next session and verify workspace availability.

Pausing makes assigned content unavailable and can bill remaining smoothed usage/overages.
It does not mean all storage or other Azure service charges disappear.
See [pause/resume guidance][pause].

**Checkpoint:** the demonstrated stages are verified, and idle compute is paused without interrupting other users.

### CLI Option

Capture item inventory and final job status with the Fabric helper; these are operational checks, not proof of correct natural-language answers.
Run the demo questions separately against known totals.
Once no users or jobs require the shared capacity, suspend it through Azure ARM:

```powershell
Assert-DemoContext
az rest --method post --url "https://management.azure.com$CapacityArmId/suspend?api-version=2023-11-01"
if ($LASTEXITCODE) { throw 'Capacity suspend request failed.' }
az resource show --ids $CapacityArmId --api-version 2023-11-01 --query properties.state --output tsv
if ($LASTEXITCODE) { throw 'Capacity state check failed.' }
```

The suspend request may be asynchronous; verify state is `Paused` before treating it as complete.
To resume before the next session (billing restarts):

```powershell
Assert-DemoContext
az rest --method post --url "https://management.azure.com$CapacityArmId/resume?api-version=2023-11-01"
if ($LASTEXITCODE) { throw 'Capacity resume request failed.' }
az resource show --ids $CapacityArmId --api-version 2023-11-01 --query properties.state --output tsv
if ($LASTEXITCODE) { throw 'Capacity state check failed.' }
```

Wait for `Active` and verify workspace access before running jobs.
If you created capacity through the portal, set `$CapacityArmId` to its Azure resource ID before these commands.

[azure]: https://portal.azure.com/
[fabric]: https://app.fabric.microsoft.com/
[capacity]: https://learn.microsoft.com/en-us/fabric/enterprise/buy-capacity
[regions]: https://learn.microsoft.com/en-us/fabric/admin/region-availability
[pause]: https://learn.microsoft.com/en-us/fabric/enterprise/pause-resume