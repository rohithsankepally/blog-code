#!/bin/bash

# Quick Start Script for WebSocket Chat Demo
# This script automates the installation and demo execution

echo "=============================================="
echo "WebSocket Protocol Versioning Demo - Setup"
echo "=============================================="
echo ""

# Check Python version
echo "📋 Checking Python version..."
python_version=$(python3 --version 2>&1)
echo "   Found: $python_version"

if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.7 or higher."
    exit 1
fi

echo ""
echo "📦 Installing dependencies..."
pip3 install -r requirements.txt

if [ $? -ne 0 ]; then
    echo "❌ Failed to install dependencies."
    exit 1
fi

echo ""
echo "✅ Installation complete!"
echo ""
echo "=============================================="
echo "Running the demo..."
echo "=============================================="
echo ""

# Run the demo
python3 demo.py

echo ""
echo "=============================================="
echo "Demo complete!"
echo "=============================================="
echo ""
echo "📚 Next steps:"
echo "   - Read README.md for detailed documentation"
echo "   - Run 'python3 demo.py --manual' for manual testing instructions"
echo "   - Try interactive clients:"
echo "     Terminal 1: python3 server.py"
echo "     Terminal 2: python3 client_old.py --interactive"
echo "     Terminal 3: python3 client_new.py --interactive"
echo ""
