@echo off
cd /d "%~dp0"
echo Starting PyMIPS32 Studio...
python main.py
if errorlevel 1 (
    echo.
    echo ERROR: Could not start. Is Python installed?
    echo Try: py main.py
    pause
)
