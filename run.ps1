# Open the Triage Desk in your browser:   .\run.ps1      (close this window to stop it)
Set-Location $PSScriptRoot
if (-not (Test-Path ".venv\Scripts\streamlit.exe")) {
    Write-Host "Not set up yet. Run .\setup.ps1 first." -ForegroundColor Red
    exit 1
}
& .venv\Scripts\streamlit run app/review.py
