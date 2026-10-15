@echo off
title Setup Academic Paper PDF Renamer
cd /d "%~dp0"
echo ====================================================================
echo Academic Paper PDF Renamer - Setup
echo ====================================================================
echo Checking for Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in your system PATH!
    echo Please install Python 3 (check "Add Python to PATH" during installation)
    echo Download from: https://www.python.org/downloads/
    echo ====================================================================
    pause
    exit /b 1
)

echo Python detected. Installing required packages (PyMuPDF, watchdog)...
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Package installation failed. Please check your internet connection.
    pause
    exit /b 1
)

echo ====================================================================
echo [SUCCESS] Setup complete! You can now use:
echo   - start_autoscan_watcher.bat    (to start auto-renaming new PDFs)
echo   - python rename_papers.py       (for manual dry-run preview)
echo   - python rename_papers.py --apply (to rename existing PDFs)
echo ====================================================================
pause
