#Requires -Version 7.0
[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$ConfigFile,
    [switch]$SkipLogin
)

if ($MyInvocation.InvocationName -ne '.') {
    throw 'Dot-source this file so its tenant context and helper functions remain available in the current PowerShell session: . ./deployment/Initialize-env.ps1 -ConfigFile ./deployment/fabric-capacity.param.txt'
}

$ErrorActionPreference = 'Stop'
$configPath = (Resolve-Path -LiteralPath $ConfigFile).Path
$configDirectory = Split-Path -Parent $configPath
$configValues = @{}
$allowedKeys = @(
    'tenantId', 'subscriptionId', 'resourceGroupName', 'resourceGroupLocation',
    'parameterFile', 'deploymentName', 'templateFile', 'workspaceName', 'assetPrefix'
)

foreach ($line in Get-Content -LiteralPath $configPath) {
    $trimmedLine = $line.Trim()
    if (-not $trimmedLine -or $trimmedLine.StartsWith('#')) { continue }
    $separator = $trimmedLine.IndexOf('=')
    if ($separator -lt 1) { throw "Invalid config line: $line. Expected key=value." }
    $key = $trimmedLine.Substring(0, $separator).Trim()
    $value = $trimmedLine.Substring($separator + 1).Trim()
    if ($key -notin $allowedKeys) { throw "Unknown config key '$key'. Allowed keys: $($allowedKeys -join ', ')" }
    if ($configValues.ContainsKey($key)) { throw "Duplicate config key '$key'." }
    if (-not $value) { throw "Config value for '$key' cannot be empty." }
    $configValues[$key] = $value
}

foreach ($requiredKey in @('tenantId', 'subscriptionId', 'resourceGroupName')) {
    if (-not $configValues.ContainsKey($requiredKey)) { throw "Config file is missing required key '$requiredKey'." }
}

$DemoContext = [pscustomobject]@{
    TenantId = [guid]$configValues.tenantId
    SubscriptionId = [guid]$configValues.subscriptionId
    ResourceGroup = $configValues.resourceGroupName
    Region = $configValues.resourceGroupLocation
    WorkspaceName = if ($configValues.ContainsKey('workspaceName')) { $configValues.workspaceName } else { 'nimbus-fabric-iq-demo-dev' }
    AssetPrefix = if ($configValues.ContainsKey('assetPrefix')) { $configValues.assetPrefix } else { 'nimbus_iq' }
    CapacityParameterFile = if ([IO.Path]::IsPathRooted($configValues.parameterFile)) {
        $configValues.parameterFile
    }
    else {
        [IO.Path]::GetFullPath((Join-Path $configDirectory $configValues.parameterFile))
    }
    CapacityDeploymentConfig = $configPath
    LocalRequests = Join-Path $HOME 'nimbus-demo-requests'
    FabricContext = @{
        TenantId = [guid]$configValues.tenantId
        SubscriptionId = [guid]$configValues.subscriptionId
    }
    LoginSkipped = [bool]$SkipLogin
}
if ($DemoContext.TenantId -eq [guid]::Empty -or $DemoContext.SubscriptionId -eq [guid]::Empty) {
    throw 'Tenant and subscription IDs must be nonzero GUIDs.'
}
$env:AZURE_CONFIG_DIR = Join-Path $HOME ".azure-tenants/$($DemoContext.TenantId)"
$env:AZD_CONFIG_DIR = Join-Path $HOME ".azd-tenants/$($DemoContext.TenantId)"
New-Item -ItemType Directory -Path $env:AZURE_CONFIG_DIR -Force | Out-Null
New-Item -ItemType Directory -Path $env:AZD_CONFIG_DIR -Force | Out-Null
New-Item -ItemType Directory -Path $DemoContext.LocalRequests -Force | Out-Null

function Assert-DemoContext {
    $accountJson = & az account show --output json
    if ($LASTEXITCODE -ne 0) { throw 'Azure CLI account check failed.' }
    $account = ($accountJson -join "`n") | ConvertFrom-Json
    if ($account.tenantId -ne $DemoContext.FabricContext.TenantId.ToString() -or $account.id -ne $DemoContext.FabricContext.SubscriptionId.ToString()) {
        throw 'Wrong Azure tenant or subscription.'
    }
}

function Write-DemoRequest([string]$Name, [object]$Body) {
    if ([IO.Path]::GetFileName($Name) -ne $Name) { throw 'Request name must be a filename, not a path.' }
    $path = Join-Path $DemoContext.LocalRequests $Name
    [IO.File]::WriteAllText($path, ($Body | ConvertTo-Json -Depth 100), [Text.UTF8Encoding]::new($false))
    return $path
}

if (-not $SkipLogin) {
    & az login --tenant $DemoContext.TenantId --output none
    if ($LASTEXITCODE -ne 0) { throw 'Azure CLI login failed.' }
    & az account set --subscription $DemoContext.SubscriptionId
    if ($LASTEXITCODE -ne 0) { throw 'Azure CLI subscription selection failed.' }
    Assert-DemoContext
}

$DemoContext
