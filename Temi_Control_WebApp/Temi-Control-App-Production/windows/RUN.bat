@echo off
REM ============================================================================
REM Temi Robot Control WebApp - Windows Run Script
REM ============================================================================
REM This script starts the application
REM ============================================================================

setlocal enabledelayedexpansion

echo.
echo ============================================================================
echo  Temi Robot Control WebApp - Starting Application
echo ============================================================================
echo.

REM Check if virtual environment exists
if not exist venv (
    echo ERROR: Virtual environment not found
    echo Please run SETUP.bat first
    pause
    exit /b 1
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo ERROR: Failed to activate virtual environment
    pause
    exit /b 1
)
echo Virtual environment activated
echo.

REM Start the application
echo Starting Temi Robot Control WebApp...
echo.
echo ============================================================================
echo Application is running at: http://localhost:5000
echo ============================================================================
echo.
echo Press Ctrl+C to stop the application
echo.

cd app
python app.py

if errorlevel 1 (
    echo.
    echo ERROR: Application failed to start
    echo Check the error messages above
    echo.
    pause
)

cd ..
