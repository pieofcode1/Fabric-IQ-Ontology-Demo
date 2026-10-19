#Requires -Version 7.0
[CmdletBinding(SupportsShouldProcess, ConfirmImpact = 'Medium')]
param(
    [string]$TenantId,
    [string]$SubscriptionId,
    [string]$ConfigFile,
    [Parameter(Mandatory)]
    [ValidateSet('GET', 'POST', 'PATCH')]
    [string]$Method,
    [Parameter(Mandatory)]
    [string]$Path,
    [string]$BodyPath,
    [string]$DefinitionDirectory,
    [string]$NotebookPath,
    [string]$DisplayName,
    [string]$ItemType,
    [guid]$LakehouseId,
    [guid]$WorkspaceId,
    [string]$LakehouseName = 'nimbus_iq_bronze',
    [string]$DefinitionFormat,
    [string]$OutputPath
)

$ErrorActionPreference = 'Stop'

function Resolve-DeploymentContext {
    param(
        [string]$TenantIdValue,
        [string]$SubscriptionIdValue,
        [string]$ConfigFileValue
    )

    $resolvedTenantId = $TenantIdValue
    $resolvedSubscriptionId = $SubscriptionIdValue

    if ($ConfigFileValue) {
        $resolvedConfigPath = (Resolve-Path -LiteralPath $ConfigFileValue).Path
        $allowedKeys = @('tenantId', 'subscriptionId')
        $configValues = @{}
        foreach ($line in Get-Content -LiteralPath $resolvedConfigPath) {
            $trimmedLine = $line.Trim()
            if (-not $trimmedLine -or $trimmedLine.StartsWith('#')) { continue }
            $separator = $trimmedLine.IndexOf('=')
            if ($separator -lt 1) { throw "Invalid config line: $line. Expected key=value." }
            $key = $trimmedLine.Substring(0, $separator).Trim()
            $value = $trimmedLine.Substring($separator + 1).Trim()
            if ($key -notin $allowedKeys) { continue }
            if (-not $value) { throw "Config value for '$key' cannot be empty." }
            $configValues[$key] = $value
        }
        if (-not $resolvedTenantId -and $configValues.ContainsKey('tenantId')) { $resolvedTenantId = $configValues.tenantId }
        if (-not $resolvedSubscriptionId -and $configValues.ContainsKey('subscriptionId')) { $resolvedSubscriptionId = $configValues.subscriptionId }
    }

    if (-not $resolvedTenantId -or -not $resolvedSubscriptionId) {
        throw 'TenantId and SubscriptionId are required. Provide them directly, pass -ConfigFile with tenantId/subscriptionId, or initialize the current session with: $DemoContext = . ./deployment/Initialize-env.ps1 -ConfigFile ./deployment/fabric-capacity.param.txt ; $FabricContext = $DemoContext.FabricContext'
    }

    $tenantGuid = [guid]::Empty
    $subscriptionGuid = [guid]::Empty
    if (-not [guid]::TryParse($resolvedTenantId, [ref]$tenantGuid)) {
        throw "TenantId '$resolvedTenantId' is not a valid GUID."
    }
    if (-not [guid]::TryParse($resolvedSubscriptionId, [ref]$subscriptionGuid)) {
        throw "SubscriptionId '$resolvedSubscriptionId' is not a valid GUID."
    }

    [pscustomobject]@{
        TenantId = $tenantGuid
        SubscriptionId = $subscriptionGuid
    }
}

$contextIds = Resolve-DeploymentContext -TenantIdValue $TenantId -SubscriptionIdValue $SubscriptionId -ConfigFileValue $ConfigFile
$TenantId = $contextIds.TenantId
$SubscriptionId = $contextIds.SubscriptionId

$apiRoot = 'https://api.fabric.microsoft.com/v1/'
$requestUri = [uri]::new([uri]$apiRoot, $Path)
if ($requestUri.Scheme -ne 'https' -or $requestUri.Host -ne 'api.fabric.microsoft.com' -or
    -not $requestUri.AbsolutePath.StartsWith('/v1/') -or $Path -match '#') {
    throw 'Path must be a Fabric v1 path without a fragment.'
}
if ($OutputPath) {
    $fullOutputPath = [IO.Path]::GetFullPath($OutputPath)
    if (Test-Path -LiteralPath $fullOutputPath) { throw 'OutputPath already exists; choose a new receipt filename.' }
}

$bodyInputs = @($BodyPath, $DefinitionDirectory, $NotebookPath) | Where-Object { $_ }
if (@($bodyInputs).Count -gt 1) {
    throw 'Use only one of BodyPath, DefinitionDirectory, or NotebookPath.'
}
if ($Method -eq 'GET' -and @($bodyInputs).Count -gt 0) {
    throw 'GET requests cannot have a request body.'
}

$body = $null
if ($BodyPath) {
    $body = Get-Content -LiteralPath $BodyPath -Raw | ConvertFrom-Json -AsHashtable
}
elseif ($DefinitionDirectory) {
    $directory = (Resolve-Path -LiteralPath $DefinitionDirectory).Path
    $parts = @(Get-ChildItem -LiteralPath $directory -Recurse -File | ForEach-Object {
        if ($_.Name -eq '.platform' -and $requestUri.AbsolutePath.EndsWith('/updateDefinition')) { return }
        @{
            path = [IO.Path]::GetRelativePath($directory, $_.FullName).Replace('\', '/')
            payload = [Convert]::ToBase64String([IO.File]::ReadAllBytes($_.FullName))
            payloadType = 'InlineBase64'
        }
    })
    if ($parts.Count -eq 0) { throw 'DefinitionDirectory contains no definition parts.' }
    $body = @{ definition = @{ parts = $parts } }
    if ($DefinitionFormat) { $body.definition.format = $DefinitionFormat }
    if (-not $requestUri.AbsolutePath.EndsWith('/updateDefinition')) {
        if (-not $DisplayName -or -not $ItemType) { throw 'Creating an item from definition parts requires DisplayName and ItemType.' }
        $body.displayName = $DisplayName
        $body.type = $ItemType
    }
}
elseif ($NotebookPath) {
    if (-not $DisplayName -or $LakehouseId -eq [guid]::Empty -or $WorkspaceId -eq [guid]::Empty) {
        throw 'Notebook import requires DisplayName, LakehouseId, and WorkspaceId.'
    }
    $notebook = Get-Content -LiteralPath $NotebookPath -Raw | ConvertFrom-Json -AsHashtable
    if ($notebook.nbformat -ne 4 -or -not $notebook.ContainsKey('cells')) {
        throw 'NotebookPath must contain a valid nbformat 4 notebook.'
    }
    if (-not $notebook.metadata) { $notebook.metadata = @{} }
    if (-not $notebook.metadata.dependencies) { $notebook.metadata.dependencies = @{} }
    $notebook.metadata.dependencies.lakehouse = @{
        default_lakehouse = $LakehouseId.ToString()
        default_lakehouse_name = $LakehouseName
        default_lakehouse_workspace_id = $WorkspaceId.ToString()
        known_lakehouses = @(@{ id = $LakehouseId.ToString() })
    }
    $notebookJson = $notebook | ConvertTo-Json -Depth 100 -Compress
    $body = @{
        displayName = $DisplayName
        type = 'Notebook'
        definition = @{
            format = 'ipynb'
            parts = @(@{
                path = 'notebook-content.ipynb'
                payload = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($notebookJson))
                payloadType = 'InlineBase64'
            })
        }
    }
    if ($requestUri.AbsolutePath.EndsWith('/updateDefinition')) {
        $body.Remove('displayName')
        $body.Remove('type')
    }
}

if (-not $PSCmdlet.ShouldProcess($requestUri.AbsoluteUri, $Method)) { return }
if (-not $env:AZURE_CONFIG_DIR -or -not $env:AZD_CONFIG_DIR) {
    throw 'Set per-tenant AZURE_CONFIG_DIR and AZD_CONFIG_DIR before running this script.'
}
$contextJson = & az account show --output json
if ($LASTEXITCODE -ne 0) { throw 'Azure CLI account check failed. Sign in to the intended tenant.' }
$context = ($contextJson -join "`n") | ConvertFrom-Json
if ($context.tenantId -ne $TenantId.ToString() -or $context.id -ne $SubscriptionId.ToString()) {
    throw 'Azure CLI tenant/subscription do not match the requested deployment context.'
}
$token = & az account get-access-token --resource https://api.fabric.microsoft.com --query accessToken --output tsv
if ($LASTEXITCODE -ne 0 -or -not $token) { throw 'Unable to acquire a Fabric access token.' }

$request = @{
    Uri = $requestUri
    Method = $Method
    Headers = @{ Authorization = "Bearer $token" }
    MaximumRedirection = 0
    SkipHttpErrorCheck = $true
}
if ($null -ne $body) {
    $request.ContentType = 'application/json; charset=utf-8'
    $request.Body = [Text.Encoding]::UTF8.GetBytes(($body | ConvertTo-Json -Depth 100 -Compress))
}
elseif ($Method -eq 'POST') {
    $request.ContentType = 'application/json'
    $request.Body = '{}'
}
$response = Invoke-WebRequest @request
$statusCode = [int]$response.StatusCode
if ($statusCode -lt 200 -or $statusCode -ge 300) {
    throw "Fabric returned HTTP $statusCode. $($response.Content)"
}
$result = @{
    statusCode = $statusCode
    location = (@($response.Headers['Location']) | Select-Object -First 1)
    retryAfter = (@($response.Headers['Retry-After']) | Select-Object -First 1)
    operationId = (@($response.Headers['x-ms-operation-id']) | Select-Object -First 1)
    body = if ($response.Content) { $response.Content | ConvertFrom-Json } else { $null }
}
if ($OutputPath) {
    [IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($fullOutputPath)) | Out-Null
    [IO.File]::WriteAllText($fullOutputPath, ($result | ConvertTo-Json -Depth 100), [Text.UTF8Encoding]::new($false))
}
if ($statusCode -eq 202) {
    Write-Warning 'Request accepted, not completed. Check the operation/job URL after Retry-After; do not resubmit the write.'
}
[pscustomobject]$result