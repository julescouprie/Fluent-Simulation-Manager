@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0Krigeage Code"

echo ============================================================
echo   AeroKriging V2 - Interface Interactive Streamlit
echo ============================================================
echo.

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

py -3 --version >nul 2>&1
if !errorlevel! equ 0 (
    py -3 -m streamlit run app.py
    goto finish
)

python -m streamlit run app.py

:finish
pause
