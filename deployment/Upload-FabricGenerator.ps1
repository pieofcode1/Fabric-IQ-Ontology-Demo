#Requires -Version 7.0
[CmdletBinding(SupportsShouldProcess)]
param(
    [Parameter(Mandatory)]
    [guid]$TenantId,
    [Parameter(Mandatory)]
    [guid]$SubscriptionId,
    [Parameter(Mandatory)]
    [guid]$WorkspaceId,
    [Parameter(Mandatory)]
    [guid]$LakehouseId,
    [string]$SourceDirectory = (Join-Path $PSScriptRoot '../src/data_generator'),
    [switch]$IncludeSamples,
    [string]$SampleOutputPath = (Join-Path $PSScriptRoot '../sample_output')
)

$ErrorActionPreference = 'Stop'
$files = @(
    @{ Local = (Join-Path $SourceDirectory 'generate.py'); Remote = 'Files/src/data_generator/generate.py' },
    @{ Local = (Join-Path $SourceDirectory 'validate_scenario.py'); Remote = 'Files/src/data_generator/validate_scenario.py' },
    @{ Local = (Join-Path $SourceDirectory 'medallion.py'); Remote = 'Files/src/data_generator/medallion.py' },
    @{ Local = (Join-Path $SourceDirectory 'config/scenario_config.yaml'); Remote = 'Files/src/data_generator/config/scenario_config.yaml' }
)
if ($IncludeSamples) {
    $samples = @(Get-ChildItem -LiteralPath $SampleOutputPath -Filter '*.csv' -File)
    if (-not $samples.Count) { throw 'SampleOutputPath contains no CSV files.' }
    $files += @($samples | ForEach-Object { @{ Local = $_.FullName; Remote = "Files/landing/raw/$($_.Name)" } })
}
foreach ($file in $files) {
    if (-not (Test-Path -LiteralPath $file.Local -PathType Leaf)) { throw "Missing upload source: $($file.Local)" }
}
if (-not $PSCmdlet.ShouldProcess("$WorkspaceId/$LakehouseId", 'Upload source files; overwrite matching paths')) { return }
if (-not $env:AZURE_CONFIG_DIR -or -not $env:AZD_CONFIG_DIR) { throw 'Set isolated Azure configuration directories first.' }
$contextJson = & az account show --output json
if ($LASTEXITCODE -ne 0) { throw 'Azure CLI account check failed.' }
$context = ($contextJson -join "`n") | ConvertFrom-Json
if ($context.tenantId -ne $TenantId.ToString() -or $context.id -ne $SubscriptionId.ToString()) {
    throw 'Azure CLI tenant/subscription do not match the requested deployment context.'
}
$token = & az account get-access-token --resource https://storage.azure.com --query accessToken --output tsv
if ($LASTEXITCODE -ne 0 -or -not $token) { throw 'Unable to acquire a OneLake storage token.' }
$headers = @{ Authorization = "Bearer $token"; 'x-ms-version' = '2021-06-08' }
$baseUrl = "https://onelake.dfs.fabric.microsoft.com/$WorkspaceId/$LakehouseId"
$directories = @('Files', 'Files/src', 'Files/src/data_generator', 'Files/src/data_generator/config', 'Files/landing', 'Files/landing/raw')
foreach ($directory in $directories) {
    $response = Invoke-WebRequest -Method PUT -Uri "$baseUrl/$directory`?resource=directory" -Headers $headers -Body '' -SkipHttpErrorCheck
    if ([int]$response.StatusCode -notin @(200, 201, 409)) {
        throw "Unable to create directory $directory : HTTP $($response.StatusCode). $($response.Content)"
    }
}
foreach ($file in $files) {
    $url = "$baseUrl/$($file.Remote)"
    Invoke-WebRequest -Method PUT -Uri "$url`?resource=file" -Headers $headers -Body '' | Out-Null
    $stream = [IO.File]::OpenRead((Resolve-Path -LiteralPath $file.Local).Path)
    try {
        $buffer = [byte[]]::new(4 * 1024 * 1024)
        $position = 0L
        while (($count = $stream.Read($buffer, 0, $buffer.Length)) -gt 0) {
            $chunk = [byte[]]::new($count)
            [Array]::Copy($buffer, $chunk, $count)
            Invoke-WebRequest -Method PATCH -Uri "$url`?action=append&position=$position" -Headers $headers -ContentType 'application/octet-stream' -Body $chunk | Out-Null
            $position += $count
        }
        Invoke-WebRequest -Method PATCH -Uri "$url`?action=flush&position=$position" -Headers $headers -Body '' | Out-Null
    }
    finally { $stream.Dispose() }
    Write-Output "Uploaded $($file.Remote) ($position bytes)"
}