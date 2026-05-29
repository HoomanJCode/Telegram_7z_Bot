#!/bin/bash

# FileBot Startup Script

echo "🤖 Starting FileBot..."
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "⚠️  .env file not found!"
    if [ -f .env.example ]; then
        echo "📋 Creating .env from .env.example..."
        cp .env.example .env
        echo "⚠️  Please edit .env with your settings, especially BOT_TOKEN"
        exit 1
    else
        echo "❌ No .env.example found. Please create .env file manually."
        exit 1
    fi
fi

# Activate virtual environment if exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Check dependencies
if ! python3 -c "import telegram" 2>/dev/null; then
    echo "📦 Installing dependencies..."
    pip install -r requirements.txt
fi

# Run bot
python3 bot.py