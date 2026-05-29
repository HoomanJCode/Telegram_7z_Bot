#!/bin/bash

# FileBot Deployment Script
# This script is executed on the VPS by GitHub Actions

set -e  # Exit on error

# ======================
# Configuration
# ======================
PROJECT_DIR="/opt/filebot"
BACKUP_DIR="${PROJECT_DIR}/backup"
VENV_DIR="${PROJECT_DIR}/venv"
SERVICE_NAME="filebot"
LOG_DIR="/var/log/filebot"
DATA_DIR="${PROJECT_DIR}/data"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ======================
# Functions
# ======================
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_step() {
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${BLUE}[STEP]${NC} $1"
    echo -e "${BLUE}========================================${NC}\n"
}

# ======================
# Pre-deployment checks
# ======================
log_step "Pre-deployment checks"

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    log_error "Please run as root or with sudo"
    exit 1
fi

# Check required tools
for cmd in python3 pip3 systemctl tar; do
    if ! command -v $cmd &> /dev/null; then
        log_error "$cmd is required but not installed"
        exit 1
    fi
done

# ======================
# System dependencies
# ======================
log_step "Installing system dependencies"

apt-get update -qq

log_info "Installing required packages..."
apt-get install -y -qq \
    python3 \
    python3-pip \
    python3-venv \
    p7zip-full \
    p7zip-rar \
    aria2 \
    curl \
    ufw \
    || log_warn "Some packages may have failed to install"

# ======================
# Create directories
# ======================
log_step "Setting up directories"

log_info "Creating project directories..."
mkdir -p ${PROJECT_DIR}
mkdir -p ${BACKUP_DIR}
mkdir -p ${LOG_DIR}
mkdir -p ${DATA_DIR}/hosted_files

# ======================
# Backup existing installation
# ======================
log_step "Backup existing installation"

if [ -f "${PROJECT_DIR}/bot.py" ]; then
    log_info "Backing up existing installation..."
    rm -rf ${BACKUP_DIR}
    mkdir -p ${BACKUP_DIR}
    
    # Copy important files
    cp -r ${PROJECT_DIR}/* ${BACKUP_DIR}/ 2>/dev/null || true
    
    # Keep data directory
    if [ -d "${BACKUP_DIR}/data" ]; then
        log_info "Preserving data directory..."
        cp -r ${DATA_DIR} ${BACKUP_DIR}/data_backup 2>/dev/null || true
    fi
    
    log_info "Backup complete"
else
    log_info "No existing installation to backup"
fi

# ======================
# Deploy new version
# ======================
log_step "Deploying new version"

# Stop service if running
if systemctl is-active --quiet ${SERVICE_NAME}; then
    log_info "Stopping ${SERVICE_NAME} service..."
    systemctl stop ${SERVICE_NAME}
fi

# Extract deployment package
log_info "Extracting deployment package..."
rm -rf ${PROJECT_DIR}/*
tar -xzf /tmp/deploy.tar.gz -C ${PROJECT_DIR}/

# Restore data directory if it existed
if [ -d "${BACKUP_DIR}/data_backup" ]; then
    log_info "Restoring data directory..."
    cp -r ${BACKUP_DIR}/data_backup/* ${DATA_DIR}/ 2>/dev/null || true
fi

# ======================
# Setup virtual environment
# ======================
log_step "Setting up Python virtual environment"

log_info "Creating virtual environment..."
python3 -m venv ${VENV_DIR}

log_info "Installing Python dependencies..."
${VENV_DIR}/bin/pip install --upgrade pip
${VENV_DIR}/bin/pip install -r ${PROJECT_DIR}/requirements.txt

# ======================
# Configure environment
# ======================
log_step "Configuring environment"

log_info "Creating .env file..."

cat > ${PROJECT_DIR}/.env << EOF
# Telegram Bot Configuration
BOT_TOKEN=${BOT_TOKEN:-}

# API Configuration
API_BASE_URL=${API_BASE_URL:-}
API_BASE_FILE_URL=${API_BASE_FILE_URL:-}

# Host Configuration
HOST_BASE_URL=${HOST_BASE_URL:-}
HOST_PORT=${HOST_PORT:-8080}

# File Storage
STORE_TIME_HOURS=${STORE_TIME_HOURS:-48}
MAX_TELEGRAM_SIZE_MB=${MAX_TELEGRAM_SIZE_MB:-50}

# Download Method
DOWNLOAD_METHOD=${DOWNLOAD_METHOD:-aria2}
ARIA2_RPC_URL=${ARIA2_RPC_URL:-http://localhost:6800/jsonrpc}
ARIA2_SECRET=${ARIA2_SECRET:-}

# Access Control
WHITELIST=${WHITELIST:-}
ADMIN_IDS=${ADMIN_IDS:-}
EOF

# Set proper permissions
chmod 600 ${PROJECT_DIR}/.env

# ======================
# Setup firewall
# ======================
log_step "Configuring firewall"

if command -v ufw &> /dev/null; then
    log_info "Setting up UFW firewall..."
    
    # Allow SSH
    ufw allow ssh
    
    # Allow bot port if hosting is enabled
    if [ -n "${HOST_PORT}" ] && [ -n "${HOST_BASE_URL}" ]; then
        ufw allow ${HOST_PORT}/tcp
        log_info "Opened port ${HOST_PORT} for file hosting"
    fi
    
    # Enable firewall if not already enabled
    if ! ufw status | grep -q "Status: active"; then
        ufw --force enable
        log_info "Firewall enabled"
    fi
fi

# ======================
# Setup systemd service
# ======================
log_step "Setting up systemd service"

cat > /etc/systemd/system/${SERVICE_NAME}.service << EOF
[Unit]
Description=FileBot Telegram Bot
After=network.target
Wants=network.target

[Service]
Type=simple
User=root
WorkingDirectory=${PROJECT_DIR}
Environment=PATH=${VENV_DIR}/bin:/usr/local/bin:/usr/bin:/bin
ExecStart=${VENV_DIR}/bin/python ${PROJECT_DIR}/bot.py
Restart=always
RestartSec=10
StandardOutput=append:${LOG_DIR}/bot.log
StandardError=append:${LOG_DIR}/bot_error.log

# Security
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=strict
ProtectHome=yes
ReadWritePaths=${DATA_DIR} ${LOG_DIR}
ReadOnlyPaths=${PROJECT_DIR}

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd
systemctl daemon-reload

# ======================
# Start service
# ======================
log_step "Starting service"

log_info "Enabling ${SERVICE_NAME} service..."
systemctl enable ${SERVICE_NAME}

log_info "Starting ${SERVICE_NAME} service..."
systemctl start ${SERVICE_NAME}

# Wait for service to start
sleep 5

# Check service status
if systemctl is-active --quiet ${SERVICE_NAME}; then
    log_info "✅ ${SERVICE_NAME} service is running"
else
    log_error "❌ ${SERVICE_NAME} service failed to start"
    log_error "Check logs: journalctl -u ${SERVICE_NAME} -n 50"
    
    # Show last few log lines
    journalctl -u ${SERVICE_NAME} -n 20 --no-pager
    
    exit 1
fi

# ======================
# Post-deployment checks
# ======================
log_step "Post-deployment checks"

# Check if bot process is running
if pgrep -f "python.*bot.py" > /dev/null; then
    log_info "✅ Bot process is running"
else
    log_error "❌ Bot process not found"
    exit 1
fi

# Check web server if hosting is enabled
if [ -n "${HOST_BASE_URL}" ] && [ -n "${HOST_PORT}" ]; then
    log_info "Checking web server..."
    sleep 3
    if curl -sf http://localhost:${HOST_PORT}/health > /dev/null 2>&1; then
        log_info "✅ Web server is responding"
    else
        log_warn "⚠️ Web server health check failed"
    fi
fi

# ======================
# Cleanup
# ======================
log_step "Cleanup"

# Remove old backups (keep last 3)
if [ -d "${PROJECT_DIR}/backups" ]; then
    ls -t ${PROJECT_DIR}/backups/ | tail -n +4 | xargs -I {} rm -rf ${PROJECT_DIR}/backups/{}
fi

# Clean apt cache
apt-get clean

# ======================
# Summary
# ======================
log_step "Deployment Summary"

echo -e "${GREEN}✅ Deployment completed successfully!${NC}\n"
echo "📁 Project Directory: ${PROJECT_DIR}"
echo "📝 Logs: ${LOG_DIR}"
echo "🔧 Service: systemctl {start|stop|restart|status} ${SERVICE_NAME}"
echo "📊 View logs: journalctl -u ${SERVICE_NAME} -f"
echo ""

# Show service status
systemctl status ${SERVICE_NAME} --no-pager -l

exit 0