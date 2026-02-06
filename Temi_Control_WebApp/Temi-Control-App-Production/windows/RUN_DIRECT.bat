@echo off
REM ============================================================================
REM Temi Robot Control WebApp - Direct Run (No Virtual Environment)
REM ============================================================================
REM This script runs the app using system Python (no venv)
REM Use this if you want to skip the virtual environment
REM ============================================================================

echo.
echo ============================================================================
echo  Temi Robot Control WebApp - Direct Run
echo ============================================================================
echo.

REM Check if in correct directory
if not exist "app" (
    echo ERROR: app folder not found!
    echo Make sure you run this script from the windows directory
    echo Expected: d:\...\windows\RUN_DIRECT.bat
    pause
    exit /b 1
)

REM Check Python installation
echo Checking Python installation...
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

REM Change to app directory
cd app

REM Start the application
echo Starting Temi Robot Control WebApp...
echo.
echo ============================================================================
echo Application is running at: http://localhost:5000
echo ============================================================================
echo.
echo Press Ctrl+C to stop the application
echo.

python app.py

if errorlevel 1 (
    echo.
    echo ERROR: Application failed to start
    echo Check the error messages above
    echo.
    pause
)

cd ..
