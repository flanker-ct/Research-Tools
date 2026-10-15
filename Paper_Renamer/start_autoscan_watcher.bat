@echo off
title Academic Paper Auto-Scanner & Renamer
cd /d "%~dp0"
echo ====================================================================
python -c "import fitz, watchdog" >nul 2>&1
if errorlevel 1 (
    echo [INFO] Required packages not detected. Installing dependencies...
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] Failed to install dependencies. Please run install_requirements.bat manually.
        pause
        exit /b 1
    )
)

echo Starting Academic Paper PDF Auto-Scanner and Renamer...
echo Monitoring folder and subfolders for new academic PDFs.
echo Press Ctrl+C in this window to stop watching.
echo ====================================================================
python rename_papers.py --watch
pause
