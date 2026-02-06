#!/bin/bash
################################################################################
# Temi Robot Control WebApp - Linux Run Script
################################################################################
# This script starts the application
################################################################################

set -e  # Exit on any error

echo ""
echo "================================================================================"
echo "  Temi Robot Control WebApp - Starting Application"
echo "================================================================================"
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "ERROR: Virtual environment not found"
    echo "Please run ./setup.sh first"
    exit 1
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to activate virtual environment"
    exit 1
fi
echo "Virtual environment activated"
echo ""

# Start the application
echo "Starting Temi Robot Control WebApp..."
echo ""
echo "================================================================================"
echo "Application is running at: http://localhost:5000"
echo "================================================================================"
echo ""
echo "Press Ctrl+C to stop the application"
echo ""

cd app
python3 app.py

if [ $? -ne 0 ]; then
    echo ""
    echo "ERROR: Application failed to start"
    echo "Check the error messages above"
    echo ""
fi

cd ..
