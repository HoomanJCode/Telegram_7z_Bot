#!/bin/bash

# FileBot Quick Start Script

echo "🤖 FileBot - Quick Start"
echo "========================="
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "⚠️  .env file not found!"
    if [ -f env.example ]; then
        echo "📋 Creating .env from env.example..."
        cp env.example .env
        echo ""
        echo "⚠️  Please edit .env with your settings:"
        echo "   nano .env"
        echo ""
        echo "After editing, run: ./run.sh"
        exit 0
    else
        echo "❌ No env.example found."
        echo "Please create .env file manually."
        exit 1
    fi
fi

# Check if BOT_TOKEN is set
BOT_TOKEN=$(grep BOT_TOKEN .env | cut -d '=' -f2)
if [ -z "$BOT_TOKEN" ] || [ "$BOT_TOKEN" = "your_bot_token_here" ]; then
    echo "❌ BOT_TOKEN not set in .env file!"
    echo "Please edit .env and add your bot token."
    exit 1
fi

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 not found. Please install Python 3.8+"
    exit 1
fi

# Check 7z
if ! command -v 7z &> /dev/null; then
    echo "❌ 7z not found. Install with:"
    echo "   sudo apt install p7zip-full"
    exit 1
fi

# Setup virtual environment
if [ ! -d "venv" ]; then
    echo "🐍 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate and install
source venv/bin/activate
pip install -q -r requirements.txt

# Create data directories
mkdir -p data/hosted_files

# Run bot
echo "✅ Starting FileBot..."
echo ""
python3 bot.py