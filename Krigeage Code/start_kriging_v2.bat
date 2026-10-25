@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ============================================================
echo   AeroKriging V2 - Interface Interactive Streamlit
echo ============================================================
echo.

REM 1. Verification des installations Python standards dans LOCALAPPDATA
for %%v in (314 313 312 311 310) do (
    if exist "%LOCALAPPDATA%\Python\pythoncore-%%v-64\python.exe" (
        "%LOCALAPPDATA%\Python\pythoncore-%%v-64\python.exe" -m streamlit run app.py
        goto finish
    )
    if exist "%LOCALAPPDATA%\Programs\Python\Python%%v\python.exe" (
        "%LOCALAPPDATA%\Programs\Python\Python%%v\python.exe" -m streamlit run app.py
        goto finish
    )
    if exist "C:\Program Files\Python%%v\python.exe" (
        "C:\Program Files\Python%%v\python.exe" -m streamlit run app.py
        goto finish
    )
)

if exist "%LOCALAPPDATA%\Python\bin\python.exe" (
    "%LOCALAPPDATA%\Python\bin\python.exe" -m streamlit run app.py
    goto finish
)

REM 2. Verification du lanceur officiel Python sous Windows (py)
py -3 --version >nul 2>&1
if !errorlevel! equ 0 (
    py -3 -m streamlit run app.py
    goto finish
)

REM 3. Python standard
python -m streamlit run app.py

:finish
pause
