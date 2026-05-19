
### `README.md`

# FileBot - Telegram Download Manager

A professional Telegram bot for downloading files, creating 7z archives, and hosting files with direct links.

## Features

- 📥 Download files from URLs (aria2 or direct)
- 📦 Automatic 7z archiving with optional password protection
- 🔗 Direct link hosting with configurable expiry
- 📤 File upload to 7z conversion
- 📚 Batch download multiple links into single archive
- 🔒 User whitelist support
- 🖥️ Built-in HTTP server for file hosting
- ⚙️ Highly configurable

## Installation

### Prerequisites

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install p7zip-full aria2

# Termux (Android)
pkg install p7zip aria2
```

### Python Dependencies

```bash
pip install -r requirements.txt
```

### Configuration

Run the bot once to create default configuration:

```bash
python bot.py
```

Or manually create `config.json`:

```json
{
    "token": "YOUR_BOT_TOKEN",
    "api_base_url": "",
    "host_base_url": "http://your-server.com:8080",
    "host_port": 8080,
    "store_time_hours": 48,
    "max_telegram_size_mb": 50,
    "whitelist": [],
    "admin_ids": [],
    "download_method": "aria2"
}
```

## Usage

1. Start bot: `python bot.py`
2. Send links to bot
3. Choose action: Telegram upload or Direct link
4. Files auto-expire based on configuration

## Commands

- `/start` - Show welcome message
- `/setpassword <pass>` - Set archive password
- `/mypassword` - Check password status
- `/status` - Bot statistics
- `/sethosturl <url>` - Set hosting URL (admin)
- `/setstoretime <hours>` - Set storage time (admin)
- `/wladd <id>` - Add to whitelist (admin)
- `/wlremove <id>` - Remove from whitelist (admin)

## Project Structure

```
filebot/
├── bot.py              # Entry point
├── config/             # Configuration
├── core/               # Business logic
├── handlers/           # Telegram handlers
├── services/           # Web server
├── utils/              # Utilities
├── data/               # Persistent data
└── requirements.txt    # Dependencies
```

## License

MIT License