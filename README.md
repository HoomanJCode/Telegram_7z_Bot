# 🤖 Telegram_7z_Bot

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)
[![Telegram](https://img.shields.io/badge/Telegram-Bot-blue)](https://core.telegram.org/bots)

A powerful, modular Telegram bot that downloads files from URLs, creates password-protected 7z archives, and provides direct download links with automatic file expiration. Built for reliability, security, and ease of use.

## ✨ Features

- **📥 Smart Downloads**: Download files using aria2 (multi-connection) or direct HTTP
- **📦 Automatic Archiving**: All files automatically packed into 7z format
- **🔒 Password Protection**: Optional AES-256 encryption for archives
- **🔗 Direct Links**: Built-in HTTP server for file hosting with configurable expiry
- **📤 File Conversion**: Upload files to get 7z archives or direct links
- **📚 Batch Processing**: Multiple URLs merged into single archive
- **⏰ Auto Cleanup**: Expired files automatically deleted
- **👥 Access Control**: Optional whitelist to restrict bot usage
- **🔄 Split Archives**: Large files automatically split for Telegram limits
- **📊 Status Monitoring**: Real-time bot statistics and file management

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

## 🚀 Installation

### Linux (Ubuntu/Debian)

```bash
# 1. Update system
sudo apt update && sudo apt upgrade -y

# 2. Install system dependencies
sudo apt install -y python3 python3-pip p7zip-full aria2

# 3. Clone repository
git clone https://github.com/hoomanJCode/Telegram_7z_Bot.git
cd Telegram_7z_Bot

# 4. Install Python dependencies
pip3 install -r requirements.txt

# 5. Create data directories
mkdir -p data/hosted_files

# 6. Run bot (creates config.json)
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

# 4. Install Python dependencies
pip install -r requirements.txt

# 5. Create data directories
mkdir -p data/hosted_files

# 6. Run bot
python bot.py
```

### Quick Install (One-Liner)

```bash
git clone https://github.com/HoomanJCode/Telegram_7z_Bot.git && cd Telegram_7z_Bot && pip install -r requirements.txt && mkdir -p data/hosted_files && python bot.py
```

## ⚙️ Configuration

On first run, the bot will create `config.json` interactively. You can also create it manually:

### config.json

```json
{
    "token": "YOUR_BOT_TOKEN_HERE",
    "api_base_url": "",
    "api_base_file_url": "",
    "host_base_url": "http://your-server-ip:8080",
    "host_port": 8080,
    "store_time_hours": 48,
    "max_telegram_size_mb": 50,
    "whitelist": [],
    "admin_ids": [],
    "download_method": "aria2",
    "aria2_rpc_url": "http://localhost:6800/jsonrpc",
    "aria2_secret": ""
}
```

### Configuration Options

| Option | Description | Default |
|--------|-------------|---------|
| `token` | Bot token from @BotFather | Required |
| `api_base_url` | Custom API URL (for Bale, etc.) | Telegram default |
| `api_base_file_url` | Custom file API URL | Telegram default |
| `host_base_url` | Your server URL for direct links | Empty (disabled) |
| `host_port` | Web server port | 8080 |
| `store_time_hours` | File retention period in hours | 48 (2 days) |
| `max_telegram_size_mb` | Max file size for Telegram upload | 50 |
| `whitelist` | Allowed user IDs (empty = all) | [] |
| `admin_ids` | Admin user IDs for commands | [] |
| `download_method` | aria2 or direct | aria2 |

### Getting Bot Token

1. Open Telegram and search for [@BotFather](https://t.me/BotFather)
2. Send `/newbot` and follow instructions
3. Copy the token provided
4. Paste it in config.json

### Setting Up Direct Links

For direct link feature, you need a VPS with public IP:

```bash
# Open port in firewall
sudo ufw allow 8080/tcp

# Run bot
python bot.py

# Links will be: http://YOUR_VPS_IP:8080/files/filename.7z
```

## 📱 Usage

### Basic Usage

1. **Start the bot**: Send `/start` to your bot
2. **Send a URL**: Paste any direct download link
3. **Choose action**: 
   - 📦 Send as 7z via Telegram
   - 🔗 Get Direct Link (if configured)
4. **For multiple links**: Send multiple URLs, all packed in one archive
5. **Upload files**: Send any file to convert to 7z

### Commands

#### User Commands
| Command | Description |
|---------|-------------|
| `/start` | Show welcome message and features |
| `/help` | Same as start |
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

## 🏗️ Project Structure

```
Telegram_7z_Bot/
├── bot.py                 # Main entry point
├── config/                # Configuration management
│   ├── __init__.py
│   ├── settings.py        # Config class with validation
│   └── default_config.json
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
│   ├── passwords.json     # User passwords (encrypted at rest)
│   └── hosted_files/      # Temporary file storage
├── requirements.txt       # Python dependencies
├── README.md             # This file
└── LICENSE               # MIT License
```

### Architecture

The bot follows a modular architecture with clear separation of concerns:

- **Config**: Centralized configuration management
- **Core**: Business logic (download, archive, file management)
- **Handlers**: Telegram-specific update handlers
- **Services**: Long-running services (web server)
- **Utils**: Shared utilities and helpers

## 🤝 Contributing

Contributions are welcome! Here's how you can help:

### Getting Started

1. **Fork** the repository
2. **Clone** your fork:
   ```bash
   git clone https://github.com/HoomanJCode/Telegram_7z_Bot.git
   ```
3. **Create a branch**:
   ```bash
   git checkout -b feature/amazing-feature
   ```
4. **Make changes** and test thoroughly
5. **Commit** with clear messages:
   ```bash
   git commit -m "feat: add amazing feature"
   ```
6. **Push** to your fork:
   ```bash
   git push origin feature/amazing-feature
   ```
7. **Open a Pull Request**

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

# Fallback to direct download in config.json
"download_method": "direct"
```

**Port already in use:**
```bash
# Change port in config.json
"host_port": 8888
```

**File download fails:**
- Check if URL is accessible
- Ensure enough disk space
- Check network connectivity

## 📊 Performance Tips

1. **Use aria2**: Faster downloads with multi-connection support
2. **VPS Location**: Choose server close to your users
3. **Disk Space**: Monitor available space for hosted files
4. **Cleanup Interval**: Adjust `store_time_hours` based on usage
5. **File Size Limits**: Set appropriate `max_telegram_size_mb`

## 🔒 Security

- Passwords stored locally in JSON (consider encryption for production)
- File access via random UUIDs, not guessable
- Whitelist feature for restricted access
- No external API calls except configured ones
- Web server serves only `hosted_files` directory

### Production Recommendations

```bash
# Use environment variables for sensitive data
export BOT_TOKEN="your_token"

# Set up reverse proxy with Nginx for HTTPS
# Run as systemd service
# Regular security updates
# Monitor disk usage
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
- [DeepSeek](https://deepseek.com/) - AI assistant for development

## 🗺️ Roadmap

- [ ] Database storage for passwords
- [ ] Web dashboard for file management
- [ ] Docker support
- [ ] Multiple language support
- [ ] Progress tracking for downloads
- [ ] File preview support
- [ ] API for external integration
- [ ] Rate limiting
- [ ] Statistics and analytics

---

<div align="center">

**[⬆ Back to Top](#Telegram_7z_Bot---telegram-download-manager)**

Made with ❤️ by HoomanJCode | Powered by DeepSeek AI

</div>