<#
  Collect-Redirects.ps1
  Optional helper. Lists the OAuth redirect (reply) URL for each SAP MCP Gateway
  custom connector in a Power Platform environment, so you can register them in
  the SAP IAS OAuth client.

  You only need this when the IAS App-2 OAuth client does NOT use a wildcard
  (/**) redirect. With a wildcard redirect configured in IAS, Copilot Studio's
  per-connector redirect URLs are already covered and this step can be skipped.

  Prereqs
    - pac auth create --name sap-mcp     (interactive SSO, done once)
    - Connectors already created (see Deploy-Connectors.ps1)

  Usage
    .\Collect-Redirects.ps1 -Environment "<ENV_ID>"
    .\Collect-Redirects.ps1 -Environment "<ENV_ID>" -NameLike MCP_SALES
    .\Collect-Redirects.ps1 -Environment "<ENV_ID>" -Csv redirects.csv

  The redirect URL for an API-based custom connector follows the standard
  Power Platform pattern:
    https://global.consent.azure-apim.net/redirect/<connector-logical-name>
#>

param(
  [Parameter(Mandatory = $true)][string]$Environment,
  [string]$NameLike,
  [string]$Csv
)

$ErrorActionPreference = "Stop"
$redirectBase = "https://global.consent.azure-apim.net/redirect"

Write-Host "Listing connectors in environment $Environment ..." -ForegroundColor Cyan
$raw = & pac connector list --environment $Environment 2>&1 | Out-String
Write-Host $raw

# Parse the CLI table: rows look like  <Name>  <ConnectorId>  <...>
$rows = @()
foreach ($line in ($raw -split "`r?`n")) {
  if ($line -match '(MCP_[A-Z0-9_]+)\s+([0-9a-fA-F-]{36})') {
    $rows += [pscustomobject]@{
      Name        = $matches[1]
      ConnectorId = $matches[2]
      RedirectUrl = "$redirectBase/$($matches[2])"
    }
  }
}

if ($NameLike) { $rows = $rows | Where-Object { $_.Name -like "*$NameLike*" } }

if (-not $rows) {
  Write-Warning "No MCP connectors parsed from 'pac connector list'. Check the environment id and that connectors exist."
  return
}

Write-Host "`nRedirect URLs (register these in the SAP IAS OAuth client if no /** wildcard is used):" -ForegroundColor Green
$rows | Sort-Object Name | Format-Table -AutoSize

if ($Csv) {
  $rows | Sort-Object Name | Export-Csv -Path $Csv -NoTypeInformation -Encoding UTF8
  Write-Host "Written to $Csv" -ForegroundColor DarkGray
}
