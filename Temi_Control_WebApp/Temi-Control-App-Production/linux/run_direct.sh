#!/bin/bash
# ============================================================================
# Temi Robot Control WebApp - Direct Run (No Virtual Environment)
# ============================================================================
# This script runs the app using system Python (no venv)
# Use this if you want to skip the virtual environment
# ============================================================================

echo ""
echo "============================================================================"
echo "  Temi Robot Control WebApp - Direct Run"
echo "============================================================================"
echo ""

# Check if in correct directory
if [ ! -d "app" ]; then
    echo "ERROR: app folder not found!"
    echo "Make sure you run this script from the linux directory"
    echo "Expected: ~/Temi-Control-App-Production/linux/run_direct.sh"
    read -p "Press Enter to continue..."
    exit 1
fi

# Check Python installation
echo "Checking Python 3 installation..."
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed"
    echo "Install with: sudo apt install python3"
    read -p "Press Enter to continue..."
    exit 1
fi

python3 --version
echo "Python 3 found!"
echo ""

# Change to app directory
cd app

# Start the application
echo "Starting Temi Robot Control WebApp..."
echo ""
echo "============================================================================"
echo "Application is running at: http://localhost:5000"
echo "============================================================================"
echo ""
echo "Press Ctrl+C to stop the application"
echo ""

python3 app.py

if [ $? -ne 0 ]; then
    echo ""
    echo "ERROR: Application failed to start"
    echo "Check the error messages above"
    echo ""
    read -p "Press Enter to continue..."
fi

cd ..
