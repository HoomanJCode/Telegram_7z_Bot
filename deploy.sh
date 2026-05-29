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

# Install dependencies
apt-get install -y -qq python3 python3-pip python3-venv p7zip-full aria2

# Python setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Create directories
mkdir -p data/hosted_files /var/log/filebot

# Start service
systemctl daemon-reload
systemctl enable filebot
systemctl start filebot

echo "✅ Deployment complete!"
systemctl status filebot --no-pager