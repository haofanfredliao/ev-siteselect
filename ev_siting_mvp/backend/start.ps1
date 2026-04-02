# ============================================================
#  start.ps1  –  Launch the HK EV Siting backend
#  Run from:  ev_siting_mvp\backend\
#  Requires:  conda activate arcgispro-py3-clone  (or similar ArcGIS Pro env)
# ============================================================

$ErrorActionPreference = "Stop"

$backendDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $backendDir

Write-Host ""
Write-Host "===================================================" -ForegroundColor Cyan
Write-Host "  HK EV Charging Station Site Selection – Backend  " -ForegroundColor Cyan
Write-Host "===================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Working directory : $backendDir" -ForegroundColor Gray
Write-Host ""

# Optional: install Python deps if not already present
$pipCheck = & pip show fastapi 2>$null
if (-not $pipCheck) {
    Write-Host "Installing Python dependencies..." -ForegroundColor Yellow
    pip install -r requirements.txt
}

Write-Host "Starting uvicorn on http://localhost:8000 ..." -ForegroundColor Green
Write-Host "Open  http://localhost:8000/app  in your browser." -ForegroundColor Green
Write-Host "Press Ctrl+C to stop." -ForegroundColor Gray
Write-Host ""

uvicorn main:app --host 0.0.0.0 --port 8000 --reload
