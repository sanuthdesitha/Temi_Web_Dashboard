@echo off
REM ============================================================================
REM Temi Robot Control WebApp - Windows Setup Script
REM ============================================================================
REM This script sets up the application on Windows from scratch
REM ============================================================================

setlocal enabledelayedexpansion

echo.
echo ============================================================================
echo  Temi Robot Control WebApp - Windows Setup
echo ============================================================================
echo.

REM Cleanup option
if exist venv (
    echo.
    echo A virtual environment already exists.
    echo Do you want to delete it and start fresh? (Y/N)
    set /p cleanup="Your choice: "

    if /i "!cleanup!"=="Y" (
        echo Deleting existing virtual environment...
        rmdir /s /q venv >nul 2>&1
        echo Virtual environment deleted.
    ) else (
        echo Keeping existing virtual environment.
    )
    echo.
)

REM Check Python installation
echo [1/5] Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.8+ from https://www.python.org/
    echo Make sure to check "Add Python to PATH" during installation
    pause
    exit /b 1
)

python --version
echo Python found!
echo.

REM Create virtual environment
echo [2/5] Creating Python virtual environment...
if exist venv (
    echo Virtual environment already exists, skipping creation
) else (
    python -m venv venv
    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment
        pause
        exit /b 1
    )
    echo Virtual environment created successfully
)
echo.

REM Activate virtual environment
echo [3/5] Activating virtual environment...
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo ERROR: Failed to activate virtual environment
    pause
    exit /b 1
)
echo Virtual environment activated
echo.

REM Install dependencies
echo [4/5] Installing Python dependencies...
pip install --upgrade pip
pip install -r ..\requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install dependencies
    echo Check that requirements.txt exists in the parent directory
    pause
    exit /b 1
)
echo Dependencies installed successfully
echo.

REM Initialize database
echo [5/5] Initializing database...
cd app
python database.py --init
if errorlevel 1 (
    echo WARNING: Database initialization had issues, but setup continues
)
cd ..
echo Database initialization complete
echo.

echo ============================================================================
echo Setup Complete!
echo ============================================================================
echo.
echo Next steps:
echo   1. Configure settings in app/config.py if needed
echo   2. Run: run.bat
echo.
echo The application will start at http://localhost:5000
echo.
pause
