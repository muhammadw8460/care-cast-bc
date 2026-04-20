$ErrorActionPreference = "Stop"

Set-Location (Join-Path $PSScriptRoot "..")

if (Test-Path ".venv\Scripts\python.exe") {
    $python = ".venv\Scripts\python.exe"
} else {
    $python = "python"
}

Write-Host "Using Python: $python"

& $python -m streamlit run dashboard/app.py --server.headless true --server.port 8501
