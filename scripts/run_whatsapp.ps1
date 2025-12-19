$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$python = Join-Path $repoRoot 'venv\Scripts\python.exe'
if (-not (Test-Path $python)) {
  throw "Python venv not found at: $python. Create/activate venv and install requirements first."
}

function Wait-HttpOk {
  param(
    [Parameter(Mandatory=$true)][string]$Url,
    [int]$TimeoutSeconds = 20
  )

  $start = Get-Date
  while ((Get-Date) - $start -lt [TimeSpan]::FromSeconds($TimeoutSeconds)) {
    try {
      $resp = Invoke-WebRequest -Uri $Url -Method Get -UseBasicParsing -TimeoutSec 3
      if ($resp.StatusCode -ge 200 -and $resp.StatusCode -lt 300) { return $true }
    } catch {
      Start-Sleep -Milliseconds 500
    }
  }
  return $false
}

function Get-NgrokPublicHttps {
  try {
    $tunnels = Invoke-RestMethod -Uri 'http://127.0.0.1:4040/api/tunnels' -Method Get -TimeoutSec 2
    $https = ($tunnels.tunnels | Where-Object { $_.public_url -like 'https://*' } | Select-Object -First 1).public_url
    return $https
  } catch {
    return $null
  }
}

Write-Host "Starting Uvicorn (twilio_app:app) on :8001..." -ForegroundColor Cyan

# If a previous uvicorn is running, leave it alone (idempotent). We just verify health.
if (-not (Wait-HttpOk -Url 'http://127.0.0.1:8001/health' -TimeoutSeconds 1)) {
  Start-Process -FilePath $python -WorkingDirectory $repoRoot -ArgumentList @(
    '-m','uvicorn','twilio_app:app','--host','0.0.0.0','--port','8001','--reload'
  ) | Out-Null

  if (-not (Wait-HttpOk -Url 'http://127.0.0.1:8001/health' -TimeoutSeconds 25)) {
    throw 'Uvicorn did not become healthy on http://127.0.0.1:8001/health'
  }
}

Write-Host "Uvicorn is healthy: http://127.0.0.1:8001/health" -ForegroundColor Green

Write-Host "Starting ngrok tunnel for port 8001..." -ForegroundColor Cyan

# Start ngrok only if not already running/healthy.
$ngrokHttps = Get-NgrokPublicHttps
if (-not $ngrokHttps) {
  Start-Process -FilePath 'ngrok' -WorkingDirectory $repoRoot -ArgumentList @('http','8001') | Out-Null
  Start-Sleep -Seconds 2
  $ngrokHttps = Get-NgrokPublicHttps
}

if (-not $ngrokHttps) {
  throw 'ngrok is not reachable at http://127.0.0.1:4040. Is ngrok installed and allowed through firewall?'
}

$webhook = "$ngrokHttps/webhook/whatsapp"

Write-Host "" 
Write-Host "ngrok HTTPS: $ngrokHttps" -ForegroundColor Green
Write-Host "Twilio Sandbox 'When a message comes in' (POST):" -ForegroundColor Yellow
Write-Host "  $webhook" -ForegroundColor Yellow
Write-Host "" 
Write-Host "Tip: ngrok inspector UI: http://127.0.0.1:4040" -ForegroundColor DarkGray
