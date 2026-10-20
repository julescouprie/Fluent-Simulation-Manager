# Fluent Simulation Manager - Lanceur universel PowerShell
Set-Location -Path $PSScriptRoot

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Fluent Simulation Manager - ANSYS Fluent 2026 R1" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

$candidates = @(
    "$PSScriptRoot\.venv\Scripts\python.exe",
    "$env:LOCALAPPDATA\Python\pythoncore-3.14-64\python.exe",
    "$env:LOCALAPPDATA\Python\pythoncore-3.13-64\python.exe",
    "$env:LOCALAPPDATA\Python\pythoncore-3.12-64\python.exe",
    "$env:LOCALAPPDATA\Python\pythoncore-3.11-64\python.exe",
    "$env:LOCALAPPDATA\Python\pythoncore-3.10-64\python.exe",
    "$env:LOCALAPPDATA\Python\bin\python.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python314\python.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
    "C:\Program Files\Python312\python.exe",
    "C:\Program Files\Python311\python.exe"
)

$found = $null
foreach ($p in $candidates) {
    if (Test-Path $p) {
        $found = $p
        break
    }
}

if (-not $found) {
    $whereCmd = (Get-Command python -ErrorAction SilentlyContinue).Source
    if ($whereCmd -and ($whereCmd -notmatch "WindowsApps")) {
        $found = $whereCmd
    }
}

if ($found) {
    Write-Host "Interpréteur Python détecté : $found" -ForegroundColor Green
    & $found "main.py"
} else {
    Write-Host "[ERREUR] Aucun interpréteur Python fonctionnel n'a été trouvé." -ForegroundColor Red
    Write-Host "Veuillez installer Python 3.10+ et les dépendances (pip install -r requirements.txt)." -ForegroundColor Yellow
    Pause
}
