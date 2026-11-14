# One-command setup for Windows PowerShell:   .\setup.ps1
# Creates the Python environment, installs the libraries, creates .env, and checks everything.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "Python was not found. Install Python 3.11 or newer from https://www.python.org/downloads/ (tick 'Add Python to PATH'), then run this again." -ForegroundColor Red
    exit 1
}

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "1/3  Creating the Python environment..."
    python -m venv .venv
}
Write-Host "2/3  Installing libraries (5-10 minutes the first time; a red 'new release of pip' notice is not an error)..."
& .venv\Scripts\python -m pip install -q --disable-pip-version-check -r requirements.txt
if ($LASTEXITCODE -ne 0) { Write-Host "Install failed. Check your internet connection and run .\setup.ps1 again." -ForegroundColor Red; exit 1 }

if (-not (Test-Path ".env")) {
    Copy-Item .env.example .env
    Write-Host "3/3  Created .env. Notepad will open: replace sk-REPLACE_ME with your AI key, save, and close Notepad."
    Start-Process notepad ".env" -Wait
} else {
    Write-Host "3/3  .env already exists (left unchanged)."
}

Write-Host ""
& .venv\Scripts\python -m scripts.check_setup
Write-Host ""
Write-Host "To open the Triage Desk:  .\run.ps1" -ForegroundColor Green
