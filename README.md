# 🤖 Telegram_7z_Bot

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)
[![Telegram](https://img.shields.io/badge/Telegram-Bot-blue)](https://core.telegram.org/bots)
[![GitHub Actions](https://img.shields.io/badge/CI%2FCD-GitHub_Actions-blue)](https://github.com/HoomanJCode/Telegram_7z_Bot/actions)

A powerful, modular Telegram bot that downloads files from URLs, creates password-protected 7z archives, and provides direct download links with automatic file expiration. Built for reliability, security, and ease of use.

## ✨ Features

- **📥 Smart Downloads**: Download files using aria2 (multi-connection) or direct HTTP
- **📦 Automatic Archiving**: All files automatically packed into 7z format
- **🔒 Password Protection**: Optional AES-256 encryption for archives
- **🔗 Direct Links**: Built-in HTTP server for file hosting with configurable expiry
- **🔒 Automatic HTTPS**: Caddy reverse proxy with auto Let's Encrypt certificates
- **📤 File Conversion**: Upload files to get 7z archives or direct links
- **📚 Batch Processing**: Multiple URLs merged into single archive
- **🔄 Split Archives**: Large files automatically split for Telegram limits
- **📁 Recent Files Menu**: Browse and download recent hosted files
- **⏰ Auto Cleanup**: Expired files automatically deleted
- **👥 Access Control**: Optional whitelist to restrict bot usage
- **📊 Status Monitoring**: Real-time bot statistics and file management
- **🚀 CI/CD**: Tests, Docker images, releases, and auto-deployment via GitHub Actions

## ⚠️ Disclaimer

**This bot is provided for educational and legitimate purposes only.**

- **Respect Copyright**: Only download content you have legal rights to access
- **Terms of Service**: Ensure compliance with Telegram's Terms of Service and your local laws
- **No Warranty**: This software is provided "as is" without any warranty
- **User Responsibility**: You are solely responsible for how you use this bot
- **Data Security**: Passwords are stored locally, not transmitted to third parties

The developers assume no liability for misuse of this software.

## 📋 Prerequisites

### System Requirements

- **Python**: 3.8 or higher
- **7-Zip**: For archive creation and encryption
- **aria2** (optional): For faster multi-threaded downloads
- **VPS/Server**: Required for direct link feature with public IP
- **Bot Token**: From [@BotFather](https://t.me/BotFather) on Telegram

### Supported Platforms

- ✅ Linux (Ubuntu, Debian, CentOS, etc.)
- ✅ Termux (Android)
- ✅ macOS
- ✅ Windows (via WSL)

## 🚀 Quick Start

```bash
# 1. Clone repository
git clone https://github.com/HoomanJCode/Telegram_7z_Bot.git
cd Telegram_7z_Bot

# 2. Create configuration from template
cp env.example .env

# 3. Edit .env with your bot token (required)
nano .env

# 4. Run with quick start script
chmod +x run.sh
./run.sh
```

**Or use Make:**
```bash
make setup    # Create .env and install dependencies
nano .env     # Edit configuration
make run      # Start bot
```

### 🐳 Docker + Automatic HTTPS

The fastest way to deploy with automatic HTTPS (Let's Encrypt) is via Docker Compose. You need a domain pointed at your server's public IP.

```bash
# 1. Clone repository
git clone https://github.com/HoomanJCode/Telegram_7z_Bot.git
cd Telegram_7z_Bot

# 2. Create .env from template
cp env.example .env
nano .env  # Fill in BOT_TOKEN, ORIGIN_DOMAIN, and HOST_BASE_URL

# 3. Start with HTTPS
docker compose up -d
```

**Required `.env` values for HTTPS:**

| Variable | Example | Purpose |
|----------|---------|--------|
| `ORIGIN_DOMAIN` | `files.yourdomain.com` | Domain for Caddy to issue an SSL cert |
| `HOST_BASE_URL` | `https://files.yourdomain.com` | URL used in generated links |

Caddy automatically provisions and renews a Let's Encrypt certificate for `ORIGIN_DOMAIN`. No manual cert management needed.

**Without a domain** — just set `HOST_BASE_URL` to your server IP and leave `ORIGIN_DOMAIN` empty. The bot will be exposed directly on port 8080 over HTTP.

## 📦 Installation

### Linux (Ubuntu/Debian)

```bash
# 1. Update system
sudo apt update && sudo apt upgrade -y

# 2. Install system dependencies
sudo apt install -y python3 python3-pip p7zip-full aria2 git

# 3. Clone repository
git clone https://github.com/HoomanJCode/Telegram_7z_Bot.git
cd Telegram_7z_Bot

# 4. Setup environment
cp env.example .env
nano .env  # Add your BOT_TOKEN

# 5. Install Python dependencies
pip3 install -r requirements.txt

# 6. Create data directories
mkdir -p data/hosted_files

# 7. Run bot
python3 bot.py
```

### Termux (Android)

```bash
# 1. Update Termux
pkg update && pkg upgrade -y

# 2. Install dependencies
pkg install python python-pip p7zip aria2 git -y

# 3. Clone repository
git clone https://github.com/HoomanJCode/Telegram_7z_Bot.git
cd Telegram_7z_Bot

# 4. Setup environment
cp env.example .env
nano .env  # Add your BOT_TOKEN

# 5. Install Python dependencies
pip install -r requirements.txt

# 6. Create data directories
mkdir -p data/hosted_files

# 7. Run bot
python bot.py
```

### Manual Deployment on VPS

```bash
# Clone and deploy
git clone https://github.com/HoomanJCode/Telegram_7z_Bot.git
cd Telegram_7z_Bot
bash deploy.sh
```

## ⚙️ Configuration

Configuration is managed via `.env` file. Copy `env.example` to `.env` and edit:

### env.example

```env
# Telegram Bot Token (Required)
BOT_TOKEN=your_bot_token_here

# Custom API Base URL (Optional - for Bale messenger)
API_BASE_URL=

# Direct Link Host Configuration (Optional)
# Use https:// if you have HTTPS via Caddy
HOST_BASE_URL=http://your-server-ip:8080
HOST_PORT=8080

# Domain for automatic HTTPS via Caddy (Docker only)
# Set to your domain, e.g. files.yourdomain.com
# Leave empty to skip HTTPS and expose on port 8080 directly.
ORIGIN_DOMAIN=

# Caddy External Ports (Docker only)
# Change these if another server already uses 80/443.
CADDY_PORT_HTTP=80
CADDY_PORT_HTTPS=443

# File Storage Time in Hours
STORE_TIME_HOURS=48

# Maximum File Size for Telegram Upload in MB
MAX_TELEGRAM_SIZE_MB=50

# Download Method (aria2 or direct)
DOWNLOAD_METHOD=aria2

# Aria2 Configuration
ARIA2_RPC_URL=http://localhost:6800/jsonrpc
ARIA2_SECRET=

# Access Control (comma-separated IDs)
WHITELIST=
ADMIN_IDS=
```

### Configuration Options

| Option | Description | Default |
|--------|-------------|---------|
| `BOT_TOKEN` | Bot token from @BotFather | **Required** |
| `API_BASE_URL` | Custom API URL (for Bale, etc.) | Telegram default |
| `API_BASE_FILE_URL` | Custom file API URL | Telegram default |
| `HOST_BASE_URL` | Your server URL for direct links | Empty (disabled) |
| `HOST_PORT` | Web server port | 8080 |
| `ORIGIN_DOMAIN` | Domain for Caddy HTTPS (Docker only) | Empty (HTTP only) |
| `CADDY_PORT_HTTP` | Caddy HTTP port | 80 |
| `CADDY_PORT_HTTPS` | Caddy HTTPS port | 443 |
| `STORE_TIME_HOURS` | File retention period in hours | 48 (2 days) |
| `MAX_TELEGRAM_SIZE_MB` | Max file size for Telegram upload | 50 |
| `DOWNLOAD_METHOD` | Download method (aria2/direct) | aria2 |
| `WHITELIST` | Comma-separated allowed user IDs | Empty (all allowed) |
| `ADMIN_IDS` | Comma-separated admin user IDs | Empty |

### Getting Bot Token

1. Open Telegram and search for [@BotFather](https://t.me/BotFather)
2. Send `/newbot` and follow instructions
3. Copy the token provided
4. Add to `.env`: `BOT_TOKEN=your_token_here`

### Setting Up Direct Links

For direct link feature, you need a VPS with public IP.

**With HTTPS (recommended):**

```bash
# 1. Point a subdomain to your VPS (e.g. files.yourdomain.com → YOUR_VPS_IP)
# 2. Set .env values
ORIGIN_DOMAIN=files.yourdomain.com
HOST_BASE_URL=https://files.yourdomain.com

# 3. Open ports in firewall
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# 4. Run with Docker
sudo docker compose up -d

# Links will be: https://files.yourdomain.com/files/filename.7z
```

**Without HTTPS:**

```bash
# 1. Set your VPS IP in .env
HOST_BASE_URL=http://YOUR_VPS_IP:8080

# 2. Open port in firewall
sudo ufw allow 8080/tcp

# 3. Run bot
python3 bot.py

# Links will be: http://YOUR_VPS_IP:8080/files/filename.7z
```

### GitHub Actions Deployment (Docker)

The project ships with three GitHub Actions workflows that test, build, and deploy the bot as a Docker container:

| Workflow | Trigger | What it does |
|----------|---------|--------------|
| `ci.yml` | Push / PR to `master` | Installs dependencies and runs the test suite |
| `release.yml` | Push tag `v*` (e.g. `v1.0.0`) | Runs tests → builds & pushes the Docker image to GHCR → creates a GitHub Release with changelog → deploys to the VPS |
| `deploy-manual.yml` | Manual (`workflow_dispatch`) | Deploys any released image tag to the VPS without rebuilding |

The bot image is published to **GitHub Container Registry (GHCR)** as `ghcr.io/<owner>/<repo>:<tag>` (plus `latest`) and deployed on the VPS with Docker Compose into `/opt/telegram-7z-bot` (container `telegram-7z-bot`). Persistent data (hosted files, passwords) lives in `./data`.

#### Release flow

```bash
# Create and push a tag — tests, image build, release, and deploy run automatically
git tag v1.0.0
git push origin v1.0.0
```

The deploy step is skipped automatically when no VPS secrets are configured, so the workflows can be used for CI and image publishing alone.

#### Required secrets

Set these in **Settings → Secrets and variables → Actions**:

| Secret | Description |
|--------|-------------|
| `VPS_HOST` | Your VPS IP or domain |
| `VPS_USER` | SSH username (defaults to `root`) |
| `VPS_SSH_PRIVATE_KEY` | SSH private key for the VPS |
| `BOT_TOKEN` | Telegram bot token |
| `HOST_BASE_URL` | Your VPS URL for direct links |
| `ORIGIN_DOMAIN` | Domain for automatic HTTPS via Caddy |
| `API_BASE_URL` | Optional custom Telegram API URL |
| `API_BASE_FILE_URL` | Optional custom file API URL |
| `ARIA2_SECRET` | Optional aria2 RPC secret |
| `WHITELIST` | Optional comma-separated allowed user IDs |
| `ADMIN_IDS` | Optional comma-separated admin user IDs |

#### Optional variables

Tunables can also be set as Actions **variables** (otherwise they fall back to their defaults):

| Variable | Default |
|----------|---------|
| `HOST_PORT` | `8080` |
| `CADDY_PORT_HTTP` | `80` |
| `CADDY_PORT_HTTPS` | `443` |
| `STORE_TIME_HOURS` | `48` |
| `MAX_TELEGRAM_SIZE_MB` | `50` |
| `DOWNLOAD_METHOD` | `aria2` |
| `ARIA2_RPC_URL` | `http://localhost:6800/jsonrpc` |

#### VPS requirements

Only Docker is needed on the VPS — it is installed automatically on the first deploy:

```bash
# Verify the running container after a deploy
docker ps --filter name=telegram-7z-bot
docker logs -f telegram-7z-bot
```

## 📱 Usage

### Basic Usage

1. **Start the bot**: Send `/start` to your bot
2. **Use the menu**: Interactive buttons for navigation
3. **Send a URL**: Paste any direct download link
4. **Choose action**: 
   - 📦 Send as 7z via Telegram (auto-split if >50MB)
   - 🔗 Get Direct Link (no size limit)
5. **Multiple links**: Send multiple URLs, all packed in one archive
6. **Upload files**: Send any file (<20MB) to convert to 7z
7. **Browse files**: Use 📁 Recent Files menu to see hosted files

### Commands

#### User Commands
| Command | Description |
|---------|-------------|
| `/start` | Show main menu |
| `/recent` | View recent hosted files |
| `/files` | Same as /recent |
| `/setpassword <pass>` | Set password for your archives |
| `/mypassword` | Check if password is set |
| `/status` | View bot statistics |

#### Admin Commands
| Command | Description |
|---------|-------------|
| `/sethosturl <url>` | Set hosting URL |
| `/setstoretime <hours>` | Change file retention period |
| `/wladd <user_id>` | Add user to whitelist |
| `/wlremove <user_id>` | Remove user from whitelist |
| `/config` | View current configuration |
| `/reload` | Reload .env configuration |

### Password Protection

Set a password for encrypted archives:

```bash
# In private chat with bot
/setpassword MySecretPass123
```

All your archives will be encrypted with AES-256. Recipients need the password to extract.

### Batch Downloads

Send multiple URLs in one message:
```
https://example.com/file1.zip
https://example.com/file2.pdf
https://example.com/file3.mp4
```

All files will be downloaded and packed into a single 7z archive.

### File Size Limits

| Method | Limit | Behavior |
|--------|-------|----------|
| Upload to bot | 20 MB | Telegram API limit |
| Download from URL | Unlimited | No restrictions |
| Send via Telegram | Auto-split | Split into 50MB parts |
| Direct Link | Unlimited | No restrictions |

## 🏗️ Project Structure

```
Telegram_7z_Bot/
├── .github/workflows/     # CI/CD workflows
│   ├── ci.yml             # Tests on push/PR
│   ├── release.yml        # Docker image, release & deploy on tags
│   └── deploy-manual.yml  # Manual deploy from the Actions tab
├── bot.py                 # Main entry point
├── config/                # Configuration management
│   ├── __init__.py
│   └── settings.py        # Settings from .env
├── core/                  # Core business logic
│   ├── __init__.py
│   ├── archiver.py        # 7z archive operations
│   ├── decorators.py      # Access control decorators
│   ├── downloader.py      # Download managers (aria2/direct)
│   └── file_manager.py    # File hosting & cleanup
├── handlers/              # Telegram update handlers
│   ├── __init__.py
│   ├── callbacks.py       # Inline keyboard callbacks
│   ├── commands.py        # Bot commands
│   └── messages.py        # Message handlers
├── services/              # Additional services
│   ├── __init__.py
│   └── web_server.py      # HTTP server for direct links
├── utils/                 # Utility functions
│   ├── __init__.py
│   ├── helpers.py         # Formatting & text utilities
│   └── logger.py          # Logging configuration
├── data/                  # Persistent data
│   ├── passwords.json     # User passwords
│   └── hosted_files/      # Temporary file storage
├── docker-compose.yml     # Docker Compose (bot + Caddy HTTPS)
├── Caddyfile              # Caddy reverse proxy config
├── env.example            # Configuration template
├── requirements.txt       # Python dependencies
├── run.sh                 # Quick start script
├── deploy.sh              # Manual deployment script
├── Makefile               # Development commands
├── README.md              # This file
└── LICENSE                # MIT License
```

### Architecture

The bot follows a modular architecture with clear separation of concerns:

- **Config**: Environment-based configuration via `.env`
- **Core**: Business logic (download, archive, file management)
- **Handlers**: Telegram-specific update handlers
- **Services**: Long-running services (web server)
- **Utils**: Shared utilities and helpers
- **Workflows**: GitHub Actions for CI/CD

## 🤝 Contributing

Contributions are welcome! Here's how you can help:

### Getting Started

1. **Fork** the repository
2. **Clone** your fork:
   ```bash
   git clone https://github.com/YOUR_USERNAME/Telegram_7z_Bot.git
   ```
3. **Setup environment**:
   ```bash
   cp env.example .env
   # Edit .env with test bot token
   ```
4. **Create a branch**:
   ```bash
   git checkout -b feature/amazing-feature
   ```
5. **Make changes** and test thoroughly
6. **Commit** with clear messages:
   ```bash
   git commit -m "feat: add amazing feature"
   ```
7. **Push** to your fork:
   ```bash
   git push origin feature/amazing-feature
   ```
8. **Open a Pull Request**

### Code Style

- Follow [PEP 8](https://www.python.org/dev/peps/pep-0008/)
- Use type hints where possible
- Add docstrings to functions and classes
- Keep functions small and focused
- Use meaningful variable names

### Commit Convention

We use [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation changes
- `refactor:` Code restructuring
- `style:` Formatting changes
- `test:` Adding tests
- `chore:` Maintenance tasks
- `ci:` CI/CD changes

### Feature Requests & Bug Reports

Open an issue on GitHub with:
- Clear title and description
- Steps to reproduce (for bugs)
- Expected vs actual behavior
- Screenshots if applicable
- Your environment details

## 🔧 Troubleshooting

### Common Issues

**Bot not responding:**
```bash
# Check if bot is running
ps aux | grep bot.py

# Check logs
tail -f bot.log

# If using systemd
systemctl status filebot
journalctl -u filebot -f
```

**BOT_TOKEN not set:**
```bash
# Check .env file
cat .env | grep BOT_TOKEN

# Edit and add token
nano .env
```

**7z not found:**
```bash
# Install 7z
sudo apt install p7zip-full  # Linux
pkg install p7zip             # Termux
```

**aria2 not working:**
```bash
# Check aria2 installation
aria2c --version

# Switch to direct download in .env
DOWNLOAD_METHOD=direct
```

**Port already in use:**
```bash
# Change port in .env
HOST_PORT=8888
```

**File download fails:**
- Check if URL is accessible
- Ensure enough disk space
- Check network connectivity

**Caddy HTTPS not working:**
```bash
# Check Caddy logs
docker compose logs caddy

# Common causes:
# - Domain DNS not pointing to your server
# - Ports 80/443 blocked by firewall
# - Another service already using ports 80/443

# Solution: change Caddy ports in .env
CADDY_PORT_HTTP=8080
CADDY_PORT_HTTPS=8443
```

**Port conflict with another web server:**
```bash
# Option 1: Change Caddy ports
CADDY_PORT_HTTP=8080
CADDY_PORT_HTTPS=8443

# Option 2: Use Cloudflare proxy (no Caddy needed)
# Just set HOST_BASE_URL=https://files.yourdomain.com
# and leave ORIGIN_DOMAIN empty
```

## 📊 Performance Tips

1. **Use aria2**: Faster downloads with multi-connection support
2. **VPS Location**: Choose server close to your users
3. **Disk Space**: Monitor available space for hosted files
4. **Cleanup Interval**: Adjust `STORE_TIME_HOURS` based on usage
5. **File Size Limits**: Files auto-split for Telegram, unlimited for direct links

## 🔒 Security

- `.env` file excluded from git (contains secrets)
- Passwords stored locally, never transmitted
- File access via random UUIDs, not guessable
- Whitelist feature for restricted access
- Web server serves only `hosted_files` directory
- Systemd service with security hardening

### Production Recommendations

```bash
# Docker (recommended): automatic restart + HTTPS via Caddy
sudo docker compose up -d

# Or systemd for bare-metal installs
sudo systemctl enable filebot
sudo systemctl start filebot

# Regular security updates: sudo apt update && sudo apt upgrade
# Monitor disk usage: df -h
# View logs: docker compose logs -f  (Docker) or journalctl -u filebot -f (systemd)
```

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

```
MIT License

Copyright (c) 2024 Telegram_7z_Bot Contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
```

## 🧠 DeepSeek Vibe Coding

This project was developed with the assistance of **DeepSeek AI**, showcasing the power of AI-assisted development ("vibe coding"). The entire codebase was iteratively refined through human-AI collaboration, demonstrating how AI can accelerate software development while maintaining high code quality standards.

### Development Process

- **AI-Assisted Architecture**: Project structure and patterns designed with AI guidance
- **Iterative Refinement**: Code improved through multiple AI-human feedback loops
- **Best Practices**: AI ensured adherence to Python standards and patterns
- **Rapid Prototyping**: Features implemented and tested quickly with AI assistance
- **Documentation**: Comprehensive docs generated and refined with AI

This project serves as an example of effective human-AI collaboration in software development.

## 🙏 Acknowledgments

- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) - Telegram Bot API wrapper
- [aiohttp](https://github.com/aio-libs/aiohttp) - Async HTTP client/server
- [7-Zip](https://www.7-zip.org/) - File archiver with high compression
- [aria2](https://aria2.github.io/) - Multi-protocol download utility
- [python-dotenv](https://github.com/theskumar/python-dotenv) - Environment variable management
- [DeepSeek](https://deepseek.com/) - AI assistant for development

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/HoomanJCode/Telegram_7z_Bot/issues)
- **Discussions**: [GitHub Discussions](https://github.com/HoomanJCode/Telegram_7z_Bot/discussions)

## 🗺️ Roadmap

- [ ] Database storage for passwords
- [ ] Web dashboard for file management
- [x] Docker support
- [ ] Multiple language support
- [ ] Progress tracking for downloads
- [ ] File preview support
- [ ] API for external integration
- [ ] Rate limiting
- [ ] Statistics and analytics

---

<div align="center">

**[⬆ Back to Top](#-telegram_7z_bot)**

Made with ❤️ by [HoomanJCode](https://github.com/HoomanJCode) | Powered by DeepSeek AI

</div>
