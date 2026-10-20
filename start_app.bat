@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ============================================================
echo   Fluent Simulation Manager - ANSYS Fluent 2026 R1
echo ============================================================
echo.

REM 1. Verification des installations Python standards dans LOCALAPPDATA
for %%v in (314 313 312 311 310) do (
    if exist "%LOCALAPPDATA%\Python\pythoncore-%%v-64\python.exe" (
        "%LOCALAPPDATA%\Python\pythoncore-%%v-64\python.exe" main.py
        goto finish
    )
    if exist "%LOCALAPPDATA%\Programs\Python\Python%%v\python.exe" (
        "%LOCALAPPDATA%\Programs\Python\Python%%v\python.exe" main.py
        goto finish
    )
    if exist "C:\Program Files\Python%%v\python.exe" (
        "C:\Program Files\Python%%v\python.exe" main.py
        goto finish
    )
)

if exist "%LOCALAPPDATA%\Python\bin\python.exe" (
    "%LOCALAPPDATA%\Python\bin\python.exe" main.py
    goto finish
)

REM 2. Verification de l'environnement virtuel local .venv s'il existe
if exist "%~dp0.venv\Scripts\python.exe" (
    "%~dp0.venv\Scripts\python.exe" main.py
    goto finish
)

REM 3. Verification du lanceur officiel Python sous Windows (py)
py -3 --version >nul 2>&1
if !errorlevel! equ 0 (
    py -3 main.py
    goto finish
)

REM 4. Verification de python dans le PATH (hors alias WindowsApps)
for /f "tokens=*" %%i in ('where python 2^>nul') do (
    echo %%i | findstr /i "WindowsApps" >nul
    if errorlevel 1 (
        "%%i" main.py
        goto finish
    )
)

echo [ERREUR] Aucun interpreteur Python valide n'a ete detecte sur ce PC.
echo.
echo Pour faire fonctionner l'application :
echo 1. Installez Python 3.10 ou superieur (depuis python.org)
echo 2. Cochez "Add python.exe to PATH" lors de l'installation.
echo 3. Installez les dependances : pip install -r requirements.txt
echo.
pause

:finish
endlocal