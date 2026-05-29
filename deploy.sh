#!/bin/bash

# ============================================
# Telegram7zBot - Manual Deployment Script
# ============================================
# Usage: bash deploy.sh [branch]
# Example: bash deploy.sh main

set -e

# Configuration
BRANCH=${1:-main}
PROJECT_DIR="/opt/Telegram7zBot"
SERVICE_NAME="telegram7zbot"
REPO_URL="https://github.com/HoomanJCode/Telegram7zBot.git"

echo "========================================"
echo "  Telegram7zBot Deployment"
echo "========================================"
echo "📦 Repository: $REPO_URL"
echo "🌿 Branch: $BRANCH"
echo "📁 Directory: $PROJECT_DIR"
echo "========================================"

# Stop service
if systemctl is-active --quiet $SERVICE_NAME; then
    echo "⏹️  Stopping $SERVICE_NAME..."
    systemctl stop $SERVICE_NAME
fi

# Backup
if [ -d "$PROJECT_DIR" ]; then
    BACKUP="${PROJECT_DIR}_backup_$(date +%Y%m%d_%H%M%S)"
    cp -r "$PROJECT_DIR" "$BACKUP"
    echo "💾 Backup: $BACKUP"
    ls -dt ${PROJECT_DIR}_backup_* 2>/dev/null | tail -n +4 | xargs -r rm -rf
fi

# Clone/pull
if [ -d "$PROJECT_DIR/.git" ]; then
    cd "$PROJECT_DIR"
    git fetch origin
    git reset --hard origin/$BRANCH
else
    rm -rf "$PROJECT_DIR"
    git clone --branch $BRANCH --single-branch $REPO_URL "$PROJECT_DIR"
    cd "$PROJECT_DIR"
fi

# System dependencies
echo "📦 Installing system dependencies..."
apt-get update -qq
apt-get install -y -qq python3 python3-pip python3-venv p7zip-full aria2

# Python setup
echo "🐍 Setting up Python..."
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q

# Create .env if not exists
if [ ! -f ".env" ]; then
    if [ -f "env.example" ]; then
        cp env.example .env
        echo "⚠️  .env created from env.example - please edit it!"
    fi
fi

# Directories
mkdir -p data/hosted_files /var/log/$SERVICE_NAME

# Systemd service
cat > /etc/systemd/system/$SERVICE_NAME.service << EOF
[Unit]
Description=Telegram7zBot - Telegram Download Manager
After=network.target

[Service]
Type=simple
WorkingDirectory=$PROJECT_DIR
ExecStart=$PROJECT_DIR/venv/bin/python $PROJECT_DIR/bot.py
Restart=always
RestartSec=10
StandardOutput=append:/var/log/$SERVICE_NAME/bot.log
StandardError=append:/var/log/$SERVICE_NAME/bot_error.log

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable $SERVICE_NAME
systemctl start $SERVICE_NAME

sleep 5

if systemctl is-active --quiet $SERVICE_NAME; then
    echo ""
    echo "✅ Telegram7zBot deployed successfully!"
    echo ""
    echo "📋 Commands:"
    echo "   systemctl status $SERVICE_NAME"
    echo "   journalctl -u $SERVICE_NAME -f"
    echo "   systemctl restart $SERVICE_NAME"
else
    echo "❌ Failed to start!"
    journalctl -u $SERVICE_NAME -n 20 --no-pager
    exit 1
fi