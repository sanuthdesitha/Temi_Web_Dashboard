#!/bin/bash
################################################################################
# Temi Robot Control WebApp - Linux Setup Script
################################################################################
# This script sets up the application on Linux from scratch
################################################################################

set -e  # Exit on any error

echo ""
echo "================================================================================"
echo "  Temi Robot Control WebApp - Linux Setup"
echo "================================================================================"
echo ""

# Check Python installation
echo "[1/6] Checking Python installation..."
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python3 is not installed"
    echo "Please install Python 3.8+ using:"
    echo "  Ubuntu/Debian: sudo apt-get install python3 python3-venv python3-pip"
    echo "  CentOS/RHEL:   sudo yum install python3 python3-venv python3-pip"
    echo "  Fedora:        sudo dnf install python3 python3-venv python3-pip"
    exit 1
fi

python3 --version
echo "Python found!"
echo ""

# Check pip installation
echo "[2/6] Checking pip installation..."
if ! command -v pip3 &> /dev/null; then
    echo "ERROR: pip3 is not installed"
    echo "Please install pip using: sudo apt-get install python3-pip"
    exit 1
fi

pip3 --version
echo "pip found!"
echo ""

# Create virtual environment
echo "[3/6] Creating Python virtual environment..."
if [ -d "venv" ]; then
    echo "Virtual environment already exists, skipping creation"
else
    python3 -m venv venv
    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to create virtual environment"
        exit 1
    fi
    echo "Virtual environment created successfully"
fi
echo ""

# Activate virtual environment
echo "[4/6] Activating virtual environment..."
source venv/bin/activate
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to activate virtual environment"
    exit 1
fi
echo "Virtual environment activated"
echo ""

# Install dependencies
echo "[5/6] Installing Python dependencies..."
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to install dependencies"
    echo "Check that requirements.txt exists in the same directory"
    exit 1
fi
echo "Dependencies installed successfully"
echo ""

# Initialize database
echo "[6/6] Initializing database..."
cd app
python3 database.py --init 2>/dev/null || true
cd ..
echo "Database initialization complete"
echo ""

# Make scripts executable
chmod +x run.sh
echo "Setup Complete!"
echo ""

echo "================================================================================"
echo "Setup Complete!"
echo "================================================================================"
echo ""
echo "Next steps:"
echo "  1. Configure settings in app/config.py if needed"
echo "  2. Run: ./run.sh"
echo ""
echo "The application will start at http://localhost:5000"
echo ""
