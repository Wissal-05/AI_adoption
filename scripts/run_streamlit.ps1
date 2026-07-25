$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot

$Python = Join-Path $ProjectRoot ".venv/Scripts/python.exe"
if (-not (Test-Path $Python)) {
    throw "Virtual environment not found. Create it with: python -m venv .venv"
}

& $Python -m streamlit run app.py --server.port 8501 --server.headless true
