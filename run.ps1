# Booking-Agent launcher (Windows).
#   .\run.ps1 full       # backend (:8000) + Next.js frontend (:3000/:3001)  ← recommended
#   .\run.ps1 web        # backend only; built-in static site on http://localhost:8000
#   .\run.ps1 frontend   # Next.js dev server only (needs backend running)
#   .\run.ps1 setup      # install deps + seed the demo catalog
#   .\run.ps1 test       # run the test suite
#   .\run.ps1 fresh      # wipe the demo DB and re-seed (resets sold seats)
param([string]$cmd = "web")
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot

function Setup {
    if (-not (Test-Path "$root\.venv")) { uv --directory "$root" venv --python 3.11 }
    uv --directory "$root" pip install -e ".[dev,api,ui,llm]"
    uv --directory "$root" run booking-agent init-db
    uv --directory "$root" run booking-agent seed
}

switch ($cmd) {
    "setup" { Setup }
    "test"  { uv --directory "$root" run pytest -q }
    "fresh" {
        Remove-Item "$root\booking.db" -ErrorAction SilentlyContinue
        Setup
        Write-Host "Demo data reset." -ForegroundColor Green
    }
    "web" {
        Setup
        Write-Host ""
        Write-Host "  ===============================================" -ForegroundColor Magenta
        Write-Host "   Open  http://localhost:8000   (click 'Book with AI')" -ForegroundColor Green
        Write-Host "  ===============================================" -ForegroundColor Magenta
        Write-Host ""
        uv --directory "$root" run uvicorn booking_agent.api.app:app --reload --reload-dir "$root\src" --port 8000
    }
    "frontend" {
        if (-not (Test-Path "$root\frontend\node_modules")) { Push-Location "$root\frontend"; npm install; Pop-Location }
        Write-Host "`n  Next.js starting — open the URL it prints (http://localhost:3000 or :3001).`n" -ForegroundColor Green
        Push-Location "$root\frontend"; npm run dev; Pop-Location
    }
    "full" {
        Setup
        if (-not (Test-Path "$root\frontend\node_modules")) { Push-Location "$root\frontend"; npm install; Pop-Location }
        Start-Process "$root\.venv\Scripts\python.exe" -ArgumentList @("-m", "uvicorn", "booking_agent.api.app:app", "--port", "8000", "--host", "127.0.0.1") -WorkingDirectory "$root" -WindowStyle Hidden
        Write-Host "`n  Backend running on :8000. Starting Next.js — open the URL it prints.`n" -ForegroundColor Green
        Push-Location "$root\frontend"; npm run dev; Pop-Location
    }
    default { Write-Host "Usage: .\run.ps1 [full|web|frontend|setup|test|fresh]" }
}
