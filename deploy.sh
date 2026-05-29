#!/bin/bash

# FileBot Manual Deployment Script
# Usage: bash deploy.sh [branch]

set -e

BRANCH=${1:-main}
PROJECT_DIR="/opt/filebot"
REPO_URL="https://github.com/YOUR_USERNAME/filebot.git"

echo "🚀 Deploying FileBot..."
echo "📦 Repository: $REPO_URL"
echo "🌿 Branch: $BRANCH"

# Stop service
if systemctl is-active --quiet filebot; then
    echo "⏹️  Stopping service..."
    systemctl stop filebot
fi

# Backup
if [ -d "$PROJECT_DIR" ]; then
    BACKUP="${PROJECT_DIR}_backup_$(date +%Y%m%d_%H%M%S)"
    cp -r "$PROJECT_DIR" "$BACKUP"
    echo "💾 Backup: $BACKUP"
    # Keep only last 3 backups
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

# Install system dependencies
echo "📦 Installing system dependencies..."
apt-get update -qq
apt-get install -y -qq python3 python3-pip python3-venv p7zip-full aria2

# Python virtual environment
echo "🐍 Setting up Python environment..."
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Setup .env file if not exists
if [ ! -f ".env" ]; then
    if [ -f "env.example" ]; then
        echo "📋 Creating .env from env.example..."
        cp env.example .env
        echo "⚠️  Please edit .env with your settings!"
        echo "   nano $PROJECT_DIR/.env"
    else
        echo "⚠️  No env.example found, creating empty .env..."
        touch .env
    fi
fi

# Create required directories
echo "📁 Creating directories..."
mkdir -p data/hosted_files
mkdir -p /var/log/filebot

# Setup systemd service
echo "🔧 Setting up systemd service..."
cat > /etc/systemd/system/filebot.service << EOF
[Unit]
Description=FileBot Telegram Bot
After=network.target
Wants=network.target

[Service]
Type=simple
WorkingDirectory=$PROJECT_DIR
Environment=PATH=$PROJECT_DIR/venv/bin:/usr/local/bin:/usr/bin:/bin
ExecStart=$PROJECT_DIR/venv/bin/python $PROJECT_DIR/bot.py
Restart=always
RestartSec=10
StandardOutput=append:/var/log/filebot/bot.log
StandardError=append:/var/log/filebot/bot_error.log

# Security hardening
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=strict
ProtectHome=yes
ReadWritePaths=$PROJECT_DIR/data /var/log/filebot
ReadOnlyPaths=$PROJECT_DIR

[Install]
WantedBy=multi-user.target
EOF

# Reload and enable service
systemctl daemon-reload
systemctl enable filebot

# Configure firewall if UFW is available
if command -v ufw &> /dev/null; then
    echo "🔥 Configuring firewall..."
    ufw allow ssh
    
    # Read port from .env if exists
    if [ -f ".env" ]; then
        HOST_PORT=$(grep HOST_PORT .env | cut -d '=' -f2)
        if [ -n "$HOST_PORT" ]; then
            ufw allow $HOST_PORT/tcp
            echo "   Opened port $HOST_PORT"
        fi
    fi
    
    if ! ufw status | grep -q "Status: active"; then
        ufw --force enable
        echo "   Firewall enabled"
    fi
fi

# Start service
echo "▶️  Starting FileBot..."
systemctl start filebot

# Wait and check
sleep 5
if systemctl is-active --quiet filebot; then
    echo ""
    echo "✅ FileBot deployed successfully!"
    echo ""
    echo "📋 Useful commands:"
    echo "   systemctl status filebot     # Check status"
    echo "   journalctl -u filebot -f     # View logs"
    echo "   systemctl restart filebot    # Restart bot"
    echo "   nano $PROJECT_DIR/.env       # Edit configuration"
    echo ""
else
    echo "❌ FileBot failed to start!"
    echo "Check logs: journalctl -u filebot -n 50"
    journalctl -u filebot -n 20 --no-pager
    exit 1
fi