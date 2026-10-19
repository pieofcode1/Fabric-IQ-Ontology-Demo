#Requires -Version 7.0
[CmdletBinding(SupportsShouldProcess, ConfirmImpact = 'High')]
param(
    [Parameter(Mandatory)]
    [ValidateSet('InitializeConfig', 'RegisterProvider', 'CreateResourceGroup', 'Validate', 'Preview', 'Deploy', 'Verify')]
    [string]$Action,
    [guid]$TenantId = [guid]::Empty,
    [guid]$SubscriptionId = [guid]::Empty,
    [string]$ConfigFile,
    [string]$ResourceGroupName,
    [string]$ParameterFile,
    [string]$ResourceGroupLocation,
    [string]$DeploymentName,
    [string]$TemplateFile
)

$ErrorActionPreference = 'Stop'

$exampleConfigPath = Join-Path $PSScriptRoot 'fabric-capacity.param.txt.example'
$exampleParameterPath = Join-Path $PSScriptRoot '../infra/fabric-capacity.bicepparam.example'
if (-not $ConfigFile) { $ConfigFile = Join-Path $PSScriptRoot 'fabric-capacity.param.txt' }
$configDestinationPath = if ([IO.Path]::IsPathRooted($ConfigFile)) { $ConfigFile } else { Join-Path (Get-Location).Path $ConfigFile }
$parameterDestinationPath = Join-Path $PSScriptRoot '../infra/fabric-capacity.bicepparam'

if ($Action -eq 'InitializeConfig') {
    if (-not (Test-Path -LiteralPath $configDestinationPath)) {
        Copy-Item -LiteralPath $exampleConfigPath -Destination $configDestinationPath
        Write-Output "Created deployment config: $configDestinationPath"
    }
    else {
        Write-Output "Preserved existing deployment config: $configDestinationPath"
    }
    if (-not (Test-Path -LiteralPath $parameterDestinationPath)) {
        Copy-Item -LiteralPath $exampleParameterPath -Destination $parameterDestinationPath
        Write-Output "Created Bicep parameter file: $parameterDestinationPath"
    }
    else {
        Write-Output "Preserved existing Bicep parameter file: $parameterDestinationPath"
    }
    return
}

$configValues = @{}
$configDirectory = (Get-Location).Path
if ($ConfigFile) {
    $resolvedConfig = (Resolve-Path -LiteralPath $ConfigFile).Path
    $configDirectory = Split-Path -Parent $resolvedConfig
    $allowedConfigKeys = @('tenantId', 'subscriptionId', 'resourceGroupName', 'resourceGroupLocation', 'workspaceName', 'assetPrefix', 'parameterFile', 'deploymentName', 'templateFile')
    foreach ($line in Get-Content -LiteralPath $resolvedConfig) {
        $trimmedLine = $line.Trim()
        if (-not $trimmedLine -or $trimmedLine.StartsWith('#')) { continue }
        $separator = $trimmedLine.IndexOf('=')
        if ($separator -lt 1) { throw "Invalid config line: $line. Expected key=value." }
        $key = $trimmedLine.Substring(0, $separator).Trim()
        $value = $trimmedLine.Substring($separator + 1).Trim()
        if ($key -notin $allowedConfigKeys) { throw "Unknown config key '$key'. Allowed keys: $($allowedConfigKeys -join ', ')" }
        if ($configValues.ContainsKey($key)) { throw "Duplicate config key '$key'." }
        if (-not $value) { throw "Config value for '$key' cannot be empty." }
        $configValues[$key] = $value
    }
}

if ($TenantId -eq [guid]::Empty -and $configValues.ContainsKey('tenantId')) {
    $TenantId = [guid]$configValues.tenantId
}
if ($SubscriptionId -eq [guid]::Empty -and $configValues.ContainsKey('subscriptionId')) {
    $SubscriptionId = [guid]$configValues.subscriptionId
}
if (-not $ResourceGroupName -and $configValues.ContainsKey('resourceGroupName')) { $ResourceGroupName = $configValues.resourceGroupName }
if (-not $ResourceGroupLocation -and $configValues.ContainsKey('resourceGroupLocation')) { $ResourceGroupLocation = $configValues.resourceGroupLocation }
if (-not $ParameterFile -and $configValues.ContainsKey('parameterFile')) { $ParameterFile = $configValues.parameterFile }
if (-not $DeploymentName -and $configValues.ContainsKey('deploymentName')) { $DeploymentName = $configValues.deploymentName }
if (-not $TemplateFile -and $configValues.ContainsKey('templateFile')) { $TemplateFile = $configValues.templateFile }
if (-not $DeploymentName) { $DeploymentName = 'nimbus-capacity' }
if (-not $TemplateFile) { $TemplateFile = Join-Path $PSScriptRoot '../infra/fabric-capacity.bicep' }

$requiresTemplate = $Action -in @('Validate', 'Preview', 'Deploy')
if ($TenantId -eq [guid]::Empty -or $SubscriptionId -eq [guid]::Empty) {
    throw 'Provide TenantId and SubscriptionId using ConfigFile or command-line parameters.'
}
if ($Action -ne 'RegisterProvider' -and -not $ResourceGroupName) {
    throw 'Provide ResourceGroupName using ConfigFile or command-line parameters.'
}
if ($requiresTemplate) {
    if (-not $ParameterFile) { throw 'Provide ParameterFile using ConfigFile or command-line parameters.' }
    $parameterBaseDirectory = if ($ConfigFile -and -not $PSBoundParameters.ContainsKey('ParameterFile')) { $configDirectory } else { (Get-Location).Path }
    $templateBaseDirectory = if ($ConfigFile -and $configValues.ContainsKey('templateFile') -and -not $PSBoundParameters.ContainsKey('TemplateFile')) { $configDirectory } else { (Get-Location).Path }
    if (-not $PSBoundParameters.ContainsKey('TemplateFile') -and -not $configValues.ContainsKey('templateFile')) {
        $templateBaseDirectory = $PSScriptRoot
    }
    $parameterCandidate = if ([IO.Path]::IsPathRooted($ParameterFile)) { $ParameterFile } else { Join-Path $parameterBaseDirectory $ParameterFile }
    $templateCandidate = if ([IO.Path]::IsPathRooted($TemplateFile)) { $TemplateFile } else { Join-Path $templateBaseDirectory $TemplateFile }
    $parameterPath = (Resolve-Path -LiteralPath $parameterCandidate).Path
    $templatePath = (Resolve-Path -LiteralPath $templateCandidate).Path
    $parameterText = Get-Content -LiteralPath $parameterPath -Raw
    $capacityNameMatch = [regex]::Match($parameterText, "(?m)^\s*param\s+capacityName\s*=\s*'([^']+)'\s*$")
    if (-not $capacityNameMatch.Success -or $capacityNameMatch.Groups[1].Value -notmatch '^[a-z][a-z0-9]{2,62}$') {
        throw "Parameter file must contain a literal capacityName using 3-63 lowercase letters/digits, starting with a letter."
    }
}
if ($Action -eq 'CreateResourceGroup' -and [string]::IsNullOrWhiteSpace($ResourceGroupLocation)) {
    throw 'ResourceGroupLocation is required for CreateResourceGroup.'
}
if (-not $env:AZURE_CONFIG_DIR -or -not $env:AZD_CONFIG_DIR) {
    throw 'Set isolated AZURE_CONFIG_DIR and AZD_CONFIG_DIR before running Azure CLI commands.'
}

$contextJson = & az account show --output json
if ($LASTEXITCODE -ne 0) { throw 'Azure CLI account check failed. Sign in to the intended tenant.' }
$context = ($contextJson -join "`n") | ConvertFrom-Json
if ($context.tenantId -ne $TenantId.ToString() -or $context.id -ne $SubscriptionId.ToString()) {
    throw 'Azure CLI tenant/subscription do not match the requested deployment context.'
}

function Invoke-AzChecked {
    param([string[]]$Arguments)
    $output = & az @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Azure CLI command failed: az $($Arguments -join ' ')"
    }
    return $output
}

if ($requiresTemplate) {
    $deploymentArguments = @(
        'deployment', 'group', $null,
        '--resource-group', $ResourceGroupName,
        '--name', $DeploymentName,
        '--template-file', $templatePath,
        '--parameters', $parameterPath,
        '--output', 'json'
    )
}

switch ($Action) {
    'RegisterProvider' {
        if ($PSCmdlet.ShouldProcess('Microsoft.Fabric resource provider', 'Register and wait')) {
            Invoke-AzChecked @('provider', 'register', '--namespace', 'Microsoft.Fabric', '--wait') | Out-Host
        }
    }
    'CreateResourceGroup' {
        if ($PSCmdlet.ShouldProcess($ResourceGroupName, "Create resource group in $ResourceGroupLocation")) {
            Invoke-AzChecked @('group', 'create', '--name', $ResourceGroupName, '--location', $ResourceGroupLocation, '--output', 'json')
        }
    }
    'Validate' {
        $deploymentArguments[2] = 'validate'
        Invoke-AzChecked $deploymentArguments
    }
    'Preview' {
        $deploymentArguments[2] = 'what-if'
        Invoke-AzChecked $deploymentArguments
    }
    'Deploy' {
        $deploymentArguments[2] = 'create'
        if ($PSCmdlet.ShouldProcess("$ResourceGroupName/$DeploymentName", 'Deploy Fabric capacity (billable resource)')) {
            Invoke-AzChecked $deploymentArguments
        }
    }
    'Verify' {
        $deployment = Invoke-AzChecked @('deployment', 'group', 'show', '--resource-group', $ResourceGroupName, '--name', $DeploymentName, '--output', 'json') | ConvertFrom-Json
        $capacityArmId = $deployment.properties.outputs.capacityArmId.value
        if (-not $capacityArmId) { throw 'Deployment output capacityArmId is missing; verify the deployment completed successfully.' }
        Invoke-AzChecked @('resource', 'show', '--ids', $capacityArmId, '--api-version', '2026-08-01-preview', '--query', '{id:id,name:name,state:properties.state,sku:sku.name}', '--output', 'json')
    }
}
