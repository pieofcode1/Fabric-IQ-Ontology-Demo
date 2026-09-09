param(
    [Parameter(Mandatory = $true)]
    [string]$WorkspaceName,

    [Parameter(Mandatory = $false)]
    [string]$AssetPrefix = "nimbus_iq",

    [Parameter(Mandatory = $false)]
    [string]$CapacityId,

    [Parameter(Mandatory = $false)]
    [string]$TenantId = "0fd4406a-d774-4531-b099-d19828f5a597",

    [Parameter(Mandatory = $false)]
    [string]$SubscriptionId = "569c92fe-efb6-440d-9274-73860e3f69aa",

    [Parameter(Mandatory = $false)]
    [string]$SampleOutputPath = ".\sample_output"
)

$ErrorActionPreference = "Stop"

$FabricResource = "https://api.fabric.microsoft.com"
$FabricApi = "https://api.fabric.microsoft.com/v1"
$StorageResource = "https://storage.azure.com"
$OneLake = "https://onelake.dfs.fabric.microsoft.com"

function Invoke-FabricRest {
    param(
        [Parameter(Mandatory = $true)]
        [ValidateSet("GET", "POST", "PATCH", "DELETE")]
        [string]$Method,

        [Parameter(Mandatory = $true)]
        [string]$Url,

        [Parameter(Mandatory = $false)]
        [object]$Body
    )

    $args = @(
        "rest",
        "--method", $Method.ToLowerInvariant(),
        "--resource", $FabricResource,
        "--url", $Url,
        "--output", "json"
    )

    if ($null -ne $Body) {
        $bodyJson = $Body | ConvertTo-Json -Depth 20
        $tempFile = New-TemporaryFile
        Set-Content -Path $tempFile.FullName -Value $bodyJson -Encoding UTF8
        $args += @("--body", "@$($tempFile.FullName)")
    }

    try {
        $result = & az @args
        if ([string]::IsNullOrWhiteSpace($result)) {
            return $null
        }
        return $result | ConvertFrom-Json
    }
    finally {
        if ($tempFile -and (Test-Path $tempFile.FullName)) {
            Remove-Item $tempFile.FullName -Force
        }
    }
}

function Get-WorkspaceByName {
    param([string]$Name)

    $response = Invoke-FabricRest -Method GET -Url "$FabricApi/workspaces"
    return @($response.value) | Where-Object { $_.displayName -eq $Name } | Select-Object -First 1
}

function New-FabricWorkspaceIfMissing {
    param([string]$Name, [string]$Capacity)

    $existing = Get-WorkspaceByName -Name $Name
    if ($existing) {
        Write-Host "Workspace already exists: $Name ($($existing.id))"
        return $existing
    }

    $body = @{
        displayName = $Name
        description = "Nimbus Fabric IQ Ontology Demo workspace"
    }

    if (-not [string]::IsNullOrWhiteSpace($Capacity)) {
        $body.capacityId = $Capacity
    }

    $workspace = Invoke-FabricRest -Method POST -Url "$FabricApi/workspaces" -Body $body
    Write-Host "Created workspace: $Name ($($workspace.id))"
    return $workspace
}

function Get-ItemByName {
    param(
        [string]$WorkspaceId,
        [string]$ItemName,
        [string]$ItemType
    )

    $response = Invoke-FabricRest -Method GET -Url "$FabricApi/workspaces/$WorkspaceId/items?type=$ItemType"
    return @($response.value) | Where-Object { $_.displayName -eq $ItemName } | Select-Object -First 1
}

function New-FabricItemIfMissing {
    param(
        [string]$WorkspaceId,
        [string]$ItemName,
        [string]$ItemType,
        [string]$Description
    )

    $existing = Get-ItemByName -WorkspaceId $WorkspaceId -ItemName $ItemName -ItemType $ItemType
    if ($existing) {
        Write-Host "$ItemType already exists: $ItemName ($($existing.id))"
        return $existing
    }

    $body = @{
        displayName = $ItemName
        type = $ItemType
        description = $Description
    }

    $item = Invoke-FabricRest -Method POST -Url "$FabricApi/workspaces/$WorkspaceId/items" -Body $body
    Write-Host "Created $ItemType`: $ItemName ($($item.id))"
    return $item
}

function Get-StorageToken {
    $token = & az account get-access-token --resource $StorageResource --query accessToken --output tsv
    if ([string]::IsNullOrWhiteSpace($token)) {
        throw "Unable to acquire OneLake storage token."
    }
    return $token
}

function New-OneLakeDirectory {
    param(
        [string]$WorkspaceId,
        [string]$LakehouseName,
        [string]$Directory,
        [hashtable]$Headers
    )

    $url = "$OneLake/$WorkspaceId/$LakehouseName.Lakehouse/$Directory`?resource=directory"
    try {
        Invoke-WebRequest -Method PUT -Uri $url -Headers $Headers -ContentType "application/octet-stream" -Body "" | Out-Null
    }
    catch {
        if ($_.Exception.Response.StatusCode.value__ -ne 409) {
            throw
        }
    }
}

function Upload-OneLakeFile {
    param(
        [string]$WorkspaceId,
        [string]$LakehouseName,
        [string]$LocalFile,
        [string]$RemotePath,
        [hashtable]$Headers
    )

    $fileInfo = Get-Item $LocalFile
    $fileSize = $fileInfo.Length
    $baseUrl = "$OneLake/$WorkspaceId/$LakehouseName.Lakehouse/$RemotePath"

    Invoke-WebRequest -Method PUT -Uri "$baseUrl`?resource=file" -Headers $Headers -ContentType "application/octet-stream" -Body "" | Out-Null
    Invoke-WebRequest -Method PATCH -Uri "$baseUrl`?action=append&position=0" -Headers $Headers -ContentType "application/octet-stream" -InFile $LocalFile | Out-Null
    Invoke-WebRequest -Method PATCH -Uri "$baseUrl`?action=flush&position=$fileSize" -Headers $Headers -ContentType "application/octet-stream" -Body "" | Out-Null
}

Write-Host "Checking Azure CLI sign-in..."
& az account show --output none

if (-not [string]::IsNullOrWhiteSpace($SubscriptionId)) {
    & az account set --subscription $SubscriptionId
}

$fabricToken = & az account get-access-token --resource $FabricResource --query accessToken --output tsv
if ([string]::IsNullOrWhiteSpace($fabricToken)) {
    throw "Unable to acquire Fabric token. Run az login first."
}

$workspace = New-FabricWorkspaceIfMissing -Name $WorkspaceName -Capacity $CapacityId
$workspaceId = $workspace.id

$bronzeLakehouseName = "$($AssetPrefix)_bronze"
$silverLakehouseName = "$($AssetPrefix)_silver"
$goldLakehouseName = "$($AssetPrefix)_gold"

$assets = @{}
$assets.BronzeLakehouse = New-FabricItemIfMissing -WorkspaceId $workspaceId -ItemName $bronzeLakehouseName -ItemType "Lakehouse" -Description "Bronze raw landing lakehouse for fabricated telecom data."
$assets.SilverLakehouse = New-FabricItemIfMissing -WorkspaceId $workspaceId -ItemName $silverLakehouseName -ItemType "Lakehouse" -Description "Silver conformed telecom entity lakehouse."
$assets.GoldLakehouse = New-FabricItemIfMissing -WorkspaceId $workspaceId -ItemName $goldLakehouseName -ItemType "Lakehouse" -Description "Gold curated lakehouse for IQ and Power BI."
$assets.Eventhouse = New-FabricItemIfMissing -WorkspaceId $workspaceId -ItemName "$($AssetPrefix)_eventhouse" -ItemType "Eventhouse" -Description "Eventhouse for simulated network telemetry and alarms."
$assets.KqlDatabase = New-FabricItemIfMissing -WorkspaceId $workspaceId -ItemName "$($AssetPrefix)_kql" -ItemType "KQLDatabase" -Description "KQL database for real-time network analytics."
$assets.BronzeNotebook = New-FabricItemIfMissing -WorkspaceId $workspaceId -ItemName "$($AssetPrefix)_bronze_ingestion" -ItemType "Notebook" -Description "Bronze ingestion notebook placeholder."
$assets.SilverNotebook = New-FabricItemIfMissing -WorkspaceId $workspaceId -ItemName "$($AssetPrefix)_silver_transform" -ItemType "Notebook" -Description "Silver transformation notebook placeholder."
$assets.GoldNotebook = New-FabricItemIfMissing -WorkspaceId $workspaceId -ItemName "$($AssetPrefix)_gold_curate" -ItemType "Notebook" -Description "Gold curation notebook placeholder."
$assets.Pipeline = New-FabricItemIfMissing -WorkspaceId $workspaceId -ItemName "$($AssetPrefix)_orchestration" -ItemType "DataPipeline" -Description "Bronze to Silver to Gold orchestration pipeline placeholder."
$assets.SemanticModel = New-FabricItemIfMissing -WorkspaceId $workspaceId -ItemName "$($AssetPrefix)_semantic_model" -ItemType "SemanticModel" -Description "Direct Lake semantic model target for Fabric IQ."
$assets.Report = New-FabricItemIfMissing -WorkspaceId $workspaceId -ItemName "$($AssetPrefix)_service_assurance_report" -ItemType "Report" -Description "Power BI report target for service assurance demo."

$samplePath = Resolve-Path $SampleOutputPath -ErrorAction SilentlyContinue
if ($samplePath) {
    Write-Host "Uploading generated CSV files to Bronze Lakehouse..."
    $storageToken = Get-StorageToken
    $storageHeaders = @{
        Authorization = "Bearer $storageToken"
        "x-ms-version" = "2021-06-08"
    }

    New-OneLakeDirectory -WorkspaceId $workspaceId -LakehouseName $bronzeLakehouseName -Directory "Files" -Headers $storageHeaders
    New-OneLakeDirectory -WorkspaceId $workspaceId -LakehouseName $bronzeLakehouseName -Directory "Files/landing" -Headers $storageHeaders
    New-OneLakeDirectory -WorkspaceId $workspaceId -LakehouseName $bronzeLakehouseName -Directory "Files/landing/raw" -Headers $storageHeaders

    Get-ChildItem -Path $samplePath.Path -Filter "*.csv" -File | ForEach-Object {
        $remotePath = "Files/landing/raw/$($_.Name)"
        Upload-OneLakeFile -WorkspaceId $workspaceId -LakehouseName $bronzeLakehouseName -LocalFile $_.FullName -RemotePath $remotePath -Headers $storageHeaders
        Write-Host "Uploaded $($_.Name)"
    }
}
else {
    Write-Warning "Sample output path not found: $SampleOutputPath. Skipping CSV upload."
}

$manifest = [ordered]@{
    workspaceName = $WorkspaceName
    workspaceId = $workspaceId
    assetPrefix = $AssetPrefix
    createdAt = (Get-Date).ToString("o")
    assets = $assets
}

$manifestPath = Join-Path (Get-Location) "deployment\fabric-assets.manifest.json"
$manifest | ConvertTo-Json -Depth 20 | Set-Content -Path $manifestPath -Encoding UTF8

Write-Host ""
Write-Host "Fabric asset creation complete."
Write-Host "Workspace: $WorkspaceName ($workspaceId)"
Write-Host "Manifest: $manifestPath"
Write-Host ""
Write-Host "Next: implement notebooks, materialize Gold tables, then deploy relationships/measures from semantic_model."

