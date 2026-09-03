<#
  Deploy-Connectors.ps1
  Bulk-creates the SAP MCP Gateway custom connectors in a Power Platform
  environment via the Power Platform CLI (`pac connector create`), one per
  endpoint definition produced by Generate-Connectors.py.

  Prereqs
    - pac auth create --name sap-mcp            (interactive SSO, done once)
    - python Generate-Connectors.py             (writes ./generated/<name>/...)
    - You know the SAP IAS App-2 client secret (entered securely at runtime;
      never stored, never committed).

  Usage
    # Canary first (recommended): one connector, verify OAuth in the maker portal.
    .\Deploy-Connectors.ps1 -Environment "<ENV_ID>" -Only MCP_SALES_SALES_ORDER_SRV

    # A whole functional area:
    .\Deploy-Connectors.ps1 -Environment "<ENV_ID>" -Area Sales

    # All 21:
    .\Deploy-Connectors.ps1 -Environment "<ENV_ID>"

    # Bundle into a Power Platform solution (recommended for ALM):
    .\Deploy-Connectors.ps1 -Environment "<ENV_ID>" -Solution "SAPMCPGateway"

    # Skip the embedded C# code (use when custom-code function-app capacity is
    # unavailable in your region — see guide 05 troubleshooting):
    .\Deploy-Connectors.ps1 -Environment "<ENV_ID>" -NoScript

  Notes
    - The embedded custom-connector-script.csx normalises the Content-Type header
      so the SAP MCP endpoint's strict check passes. It is attached to every
      connector unless -NoScript is given.
    - Provisioning the custom code occasionally fails transiently with
      "Unable to find an unassigned function app" — this script retries with
      backoff.
#>

param(
  [Parameter(Mandatory = $true)][string]$Environment,
  [string[]]$Only,
  [ValidateSet("Sales", "Finance", "Procurement")][string]$Area,
  [string]$Solution,
  [switch]$NoScript,
  [string]$GeneratedPath,
  [int]$MaxRetries = 3
)

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
if (-not $GeneratedPath) { $GeneratedPath = Join-Path $root "generated" }
$scriptFile = Join-Path $root "custom-connector-script.csx"

if (-not (Test-Path $GeneratedPath)) {
  throw "Generated definitions not found at '$GeneratedPath'. Run: python Generate-Connectors.py"
}

# Discover connector folders (each has apiDefinition.swagger.json + settings.json).
$dirs = Get-ChildItem -Path $GeneratedPath -Directory | Where-Object {
  Test-Path (Join-Path $_.FullName "apiDefinition.swagger.json")
}

# Filter by -Area (read functional area from settings.json).
if ($Area) {
  $dirs = $dirs | Where-Object {
    $sf = Join-Path $_.FullName "settings.json"
    (Test-Path $sf) -and ((Get-Content $sf -Raw | ConvertFrom-Json).area -eq $Area)
  }
}

# Filter by -Only (explicit connector names).
if ($Only) { $dirs = $dirs | Where-Object { $Only -contains $_.Name } }

if (-not $dirs) { Write-Warning "No matching connector definitions to deploy."; return }

# --- Secure secret prompt (in-memory only) -----------------------------------
$sec = Read-Host -AsSecureString "Enter SAP IAS App-2 client secret"
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec)
$plainSecret = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)

$created = 0
$total = @($dirs).Count

foreach ($dir in $dirs) {
  $name = $dir.Name
  $df = Join-Path $dir.FullName "apiDefinition.swagger.json"
  $pf = Join-Path $dir.FullName "apiProperties.json"
  $sf = Join-Path $dir.FullName "settings.json"

  $areaLabel = "?"
  if (Test-Path $sf) { $areaLabel = (Get-Content $sf -Raw | ConvertFrom-Json).area }

  $mode = if ($NoScript) { " [no custom code]" } else { "" }
  Write-Host "`n=== [$areaLabel] Creating connector: $name$mode ===" -ForegroundColor Cyan

  # Inject the secret into a temp copy of apiProperties.json (deleted in finally).
  $props = Get-Content $pf -Raw | ConvertFrom-Json
  $props.properties.connectionParameters.token.oAuthSettings |
    Add-Member -NotePropertyName clientSecret -NotePropertyValue $plainSecret -Force
  $tmp = Join-Path $dir.FullName "apiProperties.deploy.json"
  ($props | ConvertTo-Json -Depth 40) | Set-Content -Path $tmp -Encoding UTF8

  $pacArgs = @("connector", "create",
    "--api-definition-file", $df,
    "--api-properties-file", $tmp,
    "--environment", $Environment)
  if (-not $NoScript -and (Test-Path $scriptFile)) { $pacArgs += @("--script-file", $scriptFile) }
  if ($Solution) { $pacArgs += @("--solution-unique-name", $Solution) }

  $attempt = 0
  $ok = $false
  try {
    while (-not $ok) {
      $attempt++
      $output = & pac @pacArgs 2>&1 | Out-String
      Write-Host $output

      if ($output -match "Connector created with ID") {
        $ok = $true
        $created++
        Write-Host " OK: $name" -ForegroundColor Green
      }
      elseif ($output -match "FindAndAssignFunctionApp|CustomScriptProvisioningFailed" -and $attempt -le $MaxRetries) {
        $delay = 30 * $attempt
        Write-Host " Power Platform custom-code capacity issue. Retry $attempt/$MaxRetries in ${delay}s..." -ForegroundColor Yellow
        Start-Sleep -Seconds $delay
      }
      else {
        Write-Warning "Failed: $name"
        break
      }
    }
  }
  finally {
    Remove-Item $tmp -Force -ErrorAction SilentlyContinue
  }
}

# Scrub secret from memory.
$plainSecret = $null
[System.GC]::Collect()

Write-Host "`nDone. Created $created/$total connectors." -ForegroundColor Green
Write-Host "If SAP IAS App-2 uses a /** wildcard redirect, no per-connector redirect registration is needed." -ForegroundColor DarkGray
Write-Host "Otherwise run .\Collect-Redirects.ps1 -Environment `"$Environment`" and register each redirect URL in IAS." -ForegroundColor DarkGray
Write-Host "Last step (manual): add each connector as an MCP tool to your Copilot Studio agent." -ForegroundColor DarkGray
