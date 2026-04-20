# Start the EV Siting backend from the repo root backend/ folder
# Usage: .\backend\start.ps1
#        or cd backend ; .\start.ps1

$condaEnv = "C:\Users\Fred\AppData\Local\ESRI\conda\envs\arcgispro-py3-clone"
$backendDir = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "Activating conda env: $condaEnv" -ForegroundColor Cyan
& "D:\Users\Fred\Miniconda3\shell\condabin\conda-hook.ps1"
conda activate $condaEnv

Write-Host "Starting FastAPI backend from: $backendDir" -ForegroundColor Cyan
Set-Location $backendDir
uvicorn main:app --reload --port 8000
