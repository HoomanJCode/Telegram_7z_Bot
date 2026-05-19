#!/usr/bin/env python3
import asyncio
import base64
import hashlib
import json
import logging
import os
import re
import secrets
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import List, Dict, Optional
from uuid import uuid4
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

import aiohttp
from aiohttp import web
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# ----------------------------------------------------------------------
# Logging Configuration
# ----------------------------------------------------------------------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ----------------------------------------------------------------------
# Password Encryption
# ----------------------------------------------------------------------
class PasswordEncryption:
    """Handle encrypted password storage using user ID and secret key."""
    
    def __init__(self, secret_key: str = None):
        """Initialize with optional secret key."""
        if secret_key:
            self.secret_key = secret_key
        else:
            self.secret_key = self._generate_secret_key()
    
    @staticmethod
    def _generate_secret_key() -> str:
        """Generate a random secret key."""
        return secrets.token_hex(32)
    
    def _derive_key(self, user_id: str) -> bytes:
        """Derive encryption key from user ID and secret key."""
        combined = f"{user_id}:{self.secret_key}".encode()
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b"filebot_salt_2024",
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(combined))
        return key
    
    def encrypt_password(self, user_id: str, password: str) -> str:
        """Encrypt password for a specific user."""
        if not password:
            return ""
        key = self._derive_key(user_id)
        f = Fernet(key)
        encrypted = f.encrypt(password.encode())
        return encrypted.decode()
    
    def decrypt_password(self, user_id: str, encrypted_password: str) -> str:
        """Decrypt password for a specific user."""
        if not encrypted_password:
            return ""
        try:
            key = self._derive_key(user_id)
            f = Fernet(key)
            decrypted = f.decrypt(encrypted_password.encode())
            return decrypted.decode()
        except Exception as e:
            logger.error(f"Failed to decrypt password for user {user_id}: {e}")
            return ""

# ----------------------------------------------------------------------
# Default config
# ----------------------------------------------------------------------
DEFAULT_CONFIG = {
    "token": "",
    "api_base_url": "",
    "api_base_file_url": "",
    "host_base_url": "",
    "host_port": 8080,
    "store_time_hours": 48,
    "max_telegram_size_mb": 50,
    "whitelist": [],
    "admin_ids": [],
    "download_method": "aria2",
    "aria2_rpc_url": "http://localhost:6800/jsonrpc",
    "aria2_secret": "",
    "enable_cache": True,
    "cache_db_file": "cache_db.json",
    "encryption_key": "",
}

CONFIG_FILE = "config.json"
PASSWORDS_FILE = "passwords.json"
HOSTED_FILES_DIR = "hosted_files"
HOSTED_META_FILE = os.path.join(HOSTED_FILES_DIR, "metadata.json")

# Global instances
password_encryption = None
file_cache = None

# ----------------------------------------------------------------------
# Cache/Deduplication System
# ----------------------------------------------------------------------
class FileCache:
    """Cache system to prevent duplicate file downloads and uploads."""
    
    def __init__(self, cache_file: str = "cache_db.json"):
        self.cache_file = cache_file
        self.cache = self._load_cache()
    
    def _load_cache(self) -> dict:
        """Load cache from file."""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, "r") as f:
                    return json.load(f)
            except:
                return {"urls": {}, "files": {}}
        return {"urls": {}, "files": {}}
    
    def _save_cache(self):
        """Save cache to file."""
        with open(self.cache_file, "w") as f:
            json.dump(self.cache, f, indent=2)
    
    def _clean_expired(self, max_age_hours: int):
        """Remove expired entries from cache."""
        now = time.time()
        max_age_seconds = max_age_hours * 3600
        
        expired_urls = []
        for url_hash, entry in self.cache["urls"].items():
            if now - entry["cached_at"] > max_age_seconds:
                expired_urls.append(url_hash)
        for url_hash in expired_urls:
            del self.cache["urls"][url_hash]
        
        expired_files = []
        for file_id, entry in self.cache["files"].items():
            if now - entry["cached_at"] > max_age_seconds:
                expired_files.append(file_id)
        for file_id in expired_files:
            del self.cache["files"][file_id]
        
        if expired_urls or expired_files:
            self._save_cache()
            logger.info(f"Cleaned {len(expired_urls)} URL and {len(expired_files)} file cache entries")
    
    def get_cached_url(self, url: str) -> Optional[dict]:
        """Check if URL result is cached."""
        url_hash = hashlib.sha256(url.encode()).hexdigest()
        return self.cache["urls"].get(url_hash)
    
    def cache_url(self, url: str, file_info: dict):
        """Cache URL download result."""
        url_hash = hashlib.sha256(url.encode()).hexdigest()
        self.cache["urls"][url_hash] = {
            **file_info,
            "cached_at": time.time()
        }
        self._save_cache()
    
    def get_cached_file(self, file_id: str) -> Optional[dict]:
        """Check if Telegram file is cached."""
        return self.cache["files"].get(file_id)
    
    def cache_file(self, file_id: str, file_info: dict):
        """Cache Telegram file result."""
        self.cache["files"][file_id] = {
            **file_info,
            "cached_at": time.time()
        }
        self._save_cache()
    
    def get_file_hash(self, file_path: str) -> str:
        """Calculate SHA256 hash of a file."""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

# ----------------------------------------------------------------------
# Helper Functions
# ----------------------------------------------------------------------
def load_config() -> dict:
    """Load configuration from file."""
    if not os.path.exists(CONFIG_FILE):
        return {}
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)

def save_config(cfg: dict):
    """Save configuration to file."""
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)

def create_config():
    """Create initial configuration file."""
    print("Config file not found. Creating a new one.")
    token = input("Enter your bot token: ").strip()
    api_base = input("Enter API base URL (press Enter for Telegram default): ").strip()
    
    cfg = DEFAULT_CONFIG.copy()
    cfg["token"] = token
    cfg["encryption_key"] = secrets.token_hex(32)
    
    if api_base:
        cfg["api_base_url"] = api_base
        if "/bot" in api_base:
            cfg["api_base_file_url"] = api_base.replace("/bot", "/file")
        else:
            cfg["api_base_file_url"] = api_base + "/file"
    
    dl_method = input("Download method (aria2/direct) [default: aria2]: ").strip().lower()
    if dl_method in ["direct"]:
        cfg["download_method"] = "direct"
    else:
        cfg["download_method"] = "aria2"
        aria_url = input("Aria2 RPC URL [default: http://localhost:6800/jsonrpc]: ").strip()
        if aria_url:
            cfg["aria2_rpc_url"] = aria_url
        aria_secret = input("Aria2 RPC secret (press Enter if none): ").strip()
        if aria_secret:
            cfg["aria2_secret"] = aria_secret
    
    store_hours = input("File storage time in hours [default: 48]: ").strip()
    if store_hours.isdigit():
        cfg["store_time_hours"] = int(store_hours)
    
    enable_cache = input("Enable file caching/deduplication? (yes/no) [default: yes]: ").strip().lower()
    if enable_cache in ["no", "n"]:
        cfg["enable_cache"] = False
    
    save_config(cfg)
    print(f"Config saved to {CONFIG_FILE}.")
    return cfg

def load_passwords() -> Dict[str, str]:
    """Load encrypted passwords."""
    if not os.path.exists(PASSWORDS_FILE):
        return {}
    with open(PASSWORDS_FILE, "r") as f:
        return json.load(f)

def save_passwords(passwords: Dict[str, str]):
    """Save encrypted passwords."""
    with open(PASSWORDS_FILE, "w") as f:
        json.dump(passwords, f, indent=2)

def ensure_directories():
    """Ensure required directories exist."""
    os.makedirs(HOSTED_FILES_DIR, exist_ok=True)

def load_hosted_meta() -> List[dict]:
    """Load hosted files metadata."""
    ensure_directories()
    if not os.path.exists(HOSTED_META_FILE):
        return []
    with open(HOSTED_META_FILE, "r") as f:
        return json.load(f)

def save_hosted_meta(meta: List[dict]):
    """Save hosted files metadata."""
    ensure_directories()
    with open(HOSTED_META_FILE, "w") as f:
        json.dump(meta, f, indent=2)

def get_config(context: ContextTypes.DEFAULT_TYPE) -> dict:
    """Get config from application bot_data."""
    return context.application.bot_data["config"]

def get_passwords(context: ContextTypes.DEFAULT_TYPE) -> dict:
    """Get passwords from application bot_data."""
    return context.application.bot_data["passwords"]

def get_hosted_meta(context: ContextTypes.DEFAULT_TYPE) -> list:
    """Get hosted meta from application bot_data."""
    return context.application.bot_data["hosted_meta"]

def get_user_password(context: ContextTypes.DEFAULT_TYPE, user_id: str) -> str:
    """Get decrypted password for user."""
    encrypted_passwords = get_passwords(context)
    encrypted = encrypted_passwords.get(user_id, "")
    if encrypted:
        return password_encryption.decrypt_password(user_id, encrypted)
    return ""

def set_user_password(context: ContextTypes.DEFAULT_TYPE, user_id: str, password: str):
    """Set encrypted password for user."""
    encrypted_passwords = get_passwords(context)
    if password:
        encrypted = password_encryption.encrypt_password(user_id, password)
        encrypted_passwords[user_id] = encrypted
    else:
        encrypted_passwords.pop(user_id, None)
    save_passwords(encrypted_passwords)

def check_aria2(config: dict) -> bool:
    """Check if aria2 is available."""
    if config.get("download_method") != "aria2":
        return True
    try:
        result = subprocess.run(["aria2c", "--version"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            logger.info(f"aria2 found: {result.stdout.split(chr(10))[0]}")
            return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    
    logger.warning("aria2c not found, falling back to direct download")
    config["download_method"] = "direct"
    return False

def format_storage_time(hours: int) -> str:
    """Format storage time in human readable format."""
    if hours < 1:
        return f"{int(hours * 60)} minutes"
    elif hours < 24:
        return f"{hours} hour(s)"
    else:
        days = hours / 24
        return f"{days:.1f} day(s)"

def create_link_message(link: str, has_password: bool = False, storage_hours: int = 48) -> tuple:
    """Create a message with clickable link and copy-able text."""
    message = (
        f"✅ File archived and hosted!\n\n"
        f"📎 **Direct Link:**\n"
        f"`{link}`\n\n"
        f"[Click Here to Open]({link})"
    )
    if has_password:
        message += f"\n\n🔒 **Password Protected** (use your set password to extract)"
    message += f"\n\n⏰ Expires in: {format_storage_time(storage_hours)}"
    
    keyboard = [[InlineKeyboardButton("🔗 Open Link", url=link)]]
    
    return message, InlineKeyboardMarkup(keyboard)

# ----------------------------------------------------------------------
# Access Control Decorators
# ----------------------------------------------------------------------
def restricted(func):
    """Decorator to enforce whitelist."""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        config = get_config(context)
        whitelist = config.get("whitelist", [])
        if whitelist and update.effective_user.id not in whitelist:
            if update.message:
                await update.message.reply_text("⛔ Access denied. You are not in whitelist.")
            elif update.callback_query:
                await update.callback_query.answer("Access denied", show_alert=True)
            return
        return await func(update, context)
    return wrapper

def admin_only(func):
    """Decorator to restrict command to admins."""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        config = get_config(context)
        admin_ids = config.get("admin_ids", [])
        if admin_ids and update.effective_user.id not in admin_ids:
            await update.message.reply_text("⛔ Admin only command.")
            return
        return await func(update, context)
    return wrapper

# ----------------------------------------------------------------------
# Command Handlers
# ----------------------------------------------------------------------
@restricted
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler."""
    try:
        config = get_config(context)
        storage_hours = config.get("store_time_hours", 48)
        
        await update.message.reply_text(
            "🤖 **File Download Bot**\n\n"
            "**Features:**\n"
            "• Send a link → Download and pack to 7z\n"
            "• Send multiple links → Batch download to single 7z\n"
            "• Send a file → Choose to send as 7z or get direct link\n\n"
            "**Commands:**\n"
            "/setpassword `<pass>` - Set your 7z password (encrypted)\n"
            "/mypassword - Check if password is set\n"
            "/removepassword - Remove your password\n"
            "/status - Show bot status\n"
            f"Storage time: **{format_storage_time(storage_hours)}**\n\n"
            "Just send me a link or file to get started!",
            parse_mode='Markdown'
        )
        logger.info(f"User {update.effective_user.id} started bot")
    except Exception as e:
        logger.error(f"Error in start command: {e}", exc_info=True)
        await update.message.reply_text("❌ Internal error occurred.")

@restricted
async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Help command."""
    await start(update, context)

@restricted
async def set_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set 7z password for user (encrypted storage)."""
    try:
        user_id = str(update.effective_user.id)
        args = context.args
        
        await update.message.delete()
        
        if not args:
            msg = await update.message.reply_text(
                "Usage: `/setpassword <your_password>`\n"
                "⚠️ This message will be deleted for privacy.",
                parse_mode='Markdown'
            )
            await asyncio.sleep(10)
            await msg.delete()
            return
        
        password = " ".join(args)
        set_user_password(context, user_id, password)
        
        msg = await update.message.reply_text("✅ Your 7z password has been saved (encrypted).")
        await asyncio.sleep(5)
        await msg.delete()
        
        logger.info(f"User {user_id} set password (encrypted)")
    except Exception as e:
        logger.error(f"Error setting password: {e}", exc_info=True)

@restricted
async def my_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show if password is set (never show the actual password)."""
    try:
        user_id = str(update.effective_user.id)
        encrypted_passwords = get_passwords(context)
        
        if user_id in encrypted_passwords and encrypted_passwords[user_id]:
            msg = await update.message.reply_text("✅ You have a password set.\nUse /removepassword to remove it.")
        else:
            msg = await update.message.reply_text("❌ No password set. Use /setpassword to set one.")
        
        await asyncio.sleep(10)
        await msg.delete()
    except Exception as e:
        logger.error(f"Error checking password: {e}", exc_info=True)

@restricted
async def remove_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remove user's password."""
    try:
        user_id = str(update.effective_user.id)
        set_user_password(context, user_id, "")
        
        msg = await update.message.reply_text("✅ Your password has been removed.")
        await asyncio.sleep(5)
        await msg.delete()
        
        logger.info(f"User {user_id} removed password")
    except Exception as e:
        logger.error(f"Error removing password: {e}", exc_info=True)

@admin_only
async def clear_cache(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Clear file cache (admin only)."""
    try:
        global file_cache
        cache_count = len(file_cache.cache["urls"]) + len(file_cache.cache["files"])
        file_cache = FileCache()
        await update.message.reply_text(f"✅ File cache cleared. ({cache_count} entries removed)")
        logger.info(f"Cache cleared by admin {update.effective_user.id} ({cache_count} entries)")
    except Exception as e:
        logger.error(f"Error clearing cache: {e}", exc_info=True)

@restricted
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show bot status (public info only)."""
    try:
        config = get_config(context)
        hosted_meta = get_hosted_meta(context)
        
        status_text = (
            f"📊 **Bot Status**\n\n"
            f"Hosted files: `{len(hosted_meta)}`\n"
            f"Storage time: `{format_storage_time(config.get('store_time_hours', 48))}`\n"
            f"Max file size: `{config.get('max_telegram_size_mb', 50)}` MB\n"
        )
        await update.message.reply_text(status_text, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Error showing status: {e}", exc_info=True)

@admin_only
async def admin_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show full bot status (admin only)."""
    try:
        config = get_config(context)
        hosted_meta = get_hosted_meta(context)
        
        cache_count = len(file_cache.cache["urls"]) + len(file_cache.cache["files"])
        
        status_text = (
            f"📊 **Admin Bot Status**\n\n"
            f"Download method: `{config.get('download_method', 'direct')}`\n"
            f"API base: `{config.get('api_base_url', 'default')}`\n"
            f"Host base: `{config.get('host_base_url', 'not set')}`\n"
            f"Hosted files: `{len(hosted_meta)}`\n"
            f"Cached entries: `{cache_count}`\n"
            f"Storage time: `{format_storage_time(config.get('store_time_hours', 48))}`\n"
            f"Max file size: `{config.get('max_telegram_size_mb', 50)}` MB\n"
            f"Whitelist enabled: `{'Yes' if config.get('whitelist') else 'No'}`\n"
            f"Whitelist count: `{len(config.get('whitelist', []))}`\n"
            f"Caching enabled: `{'Yes' if config.get('enable_cache', True) else 'No'}`\n"
            f"Encryption: `Active`\n"
        )
        await update.message.reply_text(status_text, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Error showing admin status: {e}", exc_info=True)

@admin_only
async def set_host_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set direct link host URL."""
    try:
        args = context.args
        if not args:
            await update.message.reply_text("Usage: `/sethosturl <url>`", parse_mode='Markdown')
            return
        
        url = args[0].strip().rstrip("/")
        config = get_config(context)
        config["host_base_url"] = url
        save_config(config)
        await update.message.reply_text(
            f"✅ Host URL set to: `{url}`\nRestart bot to apply web server changes.",
            parse_mode='Markdown'
        )
        logger.info(f"Host URL changed to {url}")
    except Exception as e:
        logger.error(f"Error setting host URL: {e}", exc_info=True)

@admin_only
async def set_store_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set file storage time in hours."""
    try:
        args = context.args
        if not args or not args[0].isdigit():
            await update.message.reply_text("Usage: `/setstoretime <hours>`", parse_mode='Markdown')
            return
        
        hours = int(args[0])
        config = get_config(context)
        config["store_time_hours"] = hours
        save_config(config)
        await update.message.reply_text(
            f"✅ File storage time set to {format_storage_time(hours)}."
        )
    except Exception as e:
        logger.error(f"Error setting store time: {e}", exc_info=True)

@admin_only
async def whitelist_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add user to whitelist."""
    try:
        args = context.args
        if not args or not args[0].isdigit():
            await update.message.reply_text("Usage: `/whitelist_add <user_id>`", parse_mode='Markdown')
            return
        
        uid = int(args[0])
        config = get_config(context)
        if "whitelist" not in config:
            config["whitelist"] = []
        if uid not in config["whitelist"]:
            config["whitelist"].append(uid)
            save_config(config)
        await update.message.reply_text(f"✅ User {uid} added to whitelist.")
        logger.info(f"User {uid} added to whitelist")
    except Exception as e:
        logger.error(f"Error adding to whitelist: {e}", exc_info=True)

@admin_only
async def whitelist_remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remove user from whitelist."""
    try:
        args = context.args
        if not args or not args[0].isdigit():
            await update.message.reply_text("Usage: `/whitelist_remove <user_id>`", parse_mode='Markdown')
            return
        
        uid = int(args[0])
        config = get_config(context)
        if uid in config.get("whitelist", []):
            config["whitelist"].remove(uid)
            save_config(config)
        await update.message.reply_text(f"✅ User {uid} removed from whitelist.")
    except Exception as e:
        logger.error(f"Error removing from whitelist: {e}", exc_info=True)

# ----------------------------------------------------------------------
# File Download Helper for Telegram/Bale
# ----------------------------------------------------------------------
async def download_telegram_file(file, dest_path: str) -> bool:
    """Download a file from Telegram/Bale using direct HTTP request."""
    try:
        await file.download_to_drive(dest_path)
        return True
    except Exception as e:
        logger.error(f"Error downloading Telegram file: {e}")
        try:
            bot = file.get_bot()
            file_path = file.file_path
            base_url = bot.base_file_url if hasattr(bot, 'base_file_url') else "https://api.telegram.org/file"
            token = bot.token
            download_url = f"{base_url}/bot{token}/{file_path}"
            logger.info(f"Trying fallback download URL: {download_url}")
            
            async with aiohttp.ClientSession() as session:
                async with session.get(download_url, timeout=aiohttp.ClientTimeout(total=300)) as resp:
                    if resp.status == 200:
                        with open(dest_path, "wb") as f:
                            async for chunk in resp.content.iter_chunked(8192):
                                f.write(chunk)
                        return True
                    else:
                        logger.error(f"Fallback download failed with status {resp.status}")
                        return False
        except Exception as e2:
            logger.error(f"Fallback download also failed: {e2}")
            return False

# ----------------------------------------------------------------------
# Message Handlers
# ----------------------------------------------------------------------
@restricted
async def handle_file_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle file upload from user - show options."""
    try:
        document = update.message.document
        file_id = document.file_id
        config = get_config(context)
        
        if config.get("enable_cache", True):
            cached = file_cache.get_cached_file(file_id)
            if cached:
                logger.info(f"Cache hit for file_id: {file_id}")
                host_base = config.get("host_base_url", "")
                if cached.get("hosted_file") and host_base:
                    link = f"{host_base}/files/{cached['hosted_file']}"
                    has_password = bool(cached.get("password", ""))
                    message, keyboard = create_link_message(link, has_password, config.get("store_time_hours", 48))
                    message = "🔄 **Cached File Found!**\n\n" + message
                    await update.message.reply_text(message, parse_mode='Markdown', reply_markup=keyboard, disable_web_page_preview=False)
                    return
        
        context.user_data["pending_file"] = {
            "file_id": file_id,
            "file_name": document.file_name or f"file_{uuid4().hex[:8]}",
            "file_size": document.file_size
        }
        
        keyboard = []
        host_available = bool(config.get("host_base_url"))
        
        keyboard.append([InlineKeyboardButton("📦 Send as 7z via Telegram", callback_data="file:telegram")])
        if host_available:
            keyboard.append([InlineKeyboardButton("🔗 Get Direct Link", callback_data="file:host")])
        keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="file:cancel")])
        
        file_size_mb = document.file_size / (1024 * 1024) if document.file_size else 0
        
        await update.message.reply_text(
            f"📁 **File Received**\n\nName: `{document.file_name}`\nSize: `{file_size_mb:.2f} MB`\n\nChoose action:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Error handling file upload: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Failed to process file: {str(e)[:200]}")

@restricted
async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text messages with URLs."""
    try:
        text = update.message.text
        urls = list(set(re.findall(r'https?://\S+', text)))
        
        if not urls:
            await update.message.reply_text("❌ No valid link found.\nPlease send a message containing HTTP/HTTPS links.")
            return

        config = get_config(context)
        
        if config.get("enable_cache", True):
            cached_results = []
            for url in urls:
                cached = file_cache.get_cached_url(url)
                if cached:
                    cached_results.append((url, cached))
            
            if cached_results:
                host_base = config.get("host_base_url", "")
                if host_base:
                    for url, cached in cached_results:
                        if cached.get("hosted_file"):
                            link = f"{host_base}/files/{cached['hosted_file']}"
                            has_password = bool(cached.get("password", ""))
                            message, keyboard = create_link_message(link, has_password, config.get("store_time_hours", 48))
                            message = f"🔄 **Cached result for:**\n`{url}`\n\n" + message
                            await update.message.reply_text(message, parse_mode='Markdown', reply_markup=keyboard, disable_web_page_preview=False)
                    
                    if len(cached_results) == len(urls):
                        return
                    urls = [url for url in urls if url not in [c[0] for c in cached_results]]

        context.user_data["pending_urls"] = urls
        logger.info(f"User {update.effective_user.id} sent {len(urls)} URL(s)")
        
        keyboard = []
        host_available = bool(config.get("host_base_url"))
        
        if len(urls) > 1:
            keyboard.append([InlineKeyboardButton("📦 Send as 7z via Telegram", callback_data="batch:telegram")])
            if host_available:
                keyboard.append([InlineKeyboardButton("🔗 Host and Get Direct Links", callback_data="batch:host")])
        else:
            keyboard.append([InlineKeyboardButton("📦 Send as 7z via Telegram", callback_data="single:telegram")])
            if host_available:
                keyboard.append([InlineKeyboardButton("🔗 Host and Get Direct Link", callback_data="single:host")])
        
        keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel")])
        
        await update.message.reply_text(
            f"📎 Found **{len(urls)}** link(s)\n\nChoose action:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Error handling text message: {e}", exc_info=True)
        await update.message.reply_text("❌ Failed to process your message.")

# ----------------------------------------------------------------------
# Callback Handler
# ----------------------------------------------------------------------
@restricted
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle callback queries from inline keyboards."""
    try:
        query = update.callback_query
        await query.answer()
        data = query.data

        if data == "cancel":
            context.user_data.pop("pending_urls", None)
            context.user_data.pop("pending_file", None)
            await query.edit_message_text("❌ Operation cancelled.")
            return

        if data.startswith("file:"):
            await handle_file_callback(update, context, query, data)
            return

        pending_urls = context.user_data.get("pending_urls")
        if not pending_urls:
            await query.edit_message_text("⏰ Session expired. Please send the links again.")
            return

        context.user_data.pop("pending_urls", None)
        action_type, action = data.split(":")
        
        await query.edit_message_text(
            f"⏳ Processing **{len(pending_urls)}** link(s)...\nMethod: **{action}**\n\nThis may take a while.",
            parse_mode='Markdown'
        )

        asyncio.create_task(process_links(update, context, pending_urls, action_type, action, query))
    except Exception as e:
        logger.error(f"Error handling callback: {e}", exc_info=True)
        await query.edit_message_text("❌ Failed to process callback.")

async def handle_file_callback(update: Update, context, query, data):
    """Handle file upload callbacks."""
    _, action = data.split(":", 1)
    
    if action == "cancel":
        context.user_data.pop("pending_file", None)
        await query.edit_message_text("❌ File operation cancelled.")
        return
    
    pending_file = context.user_data.get("pending_file")
    if not pending_file:
        await query.edit_message_text("⏰ Session expired. Please send the file again.")
        return
    
    context.user_data.pop("pending_file", None)
    await query.edit_message_text("⏳ Processing file...\nThis may take a while.")
    asyncio.create_task(process_file(update, context, pending_file, action, query))

async def process_file(update: Update, context, file_info, action, query):
    """Process uploaded file based on action."""
    user_id = update.effective_user.id
    config = get_config(context)
    password = get_user_password(context, str(user_id))
    temp_dir = tempfile.mkdtemp(prefix="file_")
    
    try:
        await query.edit_message_text("📥 Downloading file...")
        file = await context.bot.get_file(file_info["file_id"])
        dl_path = os.path.join(temp_dir, file_info["file_name"])
        
        success = await download_telegram_file(file, dl_path)
        if not success:
            await query.edit_message_text("❌ Failed to download file from server.")
            return
        
        file_hash = file_cache.get_file_hash(dl_path)
        
        if action == "telegram":
            await query.edit_message_text("📦 Creating 7z archive...")
            archive_name = f"{uuid4().hex}.7z"
            archive_path = os.path.join(temp_dir, archive_name)
            await create_7z_archive([dl_path], archive_path, password)
            
            if config.get("enable_cache", True):
                file_cache.cache_file(file_info["file_id"], {"file_hash": file_hash, "password": password, "hosted_file": None})
            
            max_vol = max(1, config.get("max_telegram_size_mb", 50) - 1)
            
            if os.path.getsize(archive_path) > max_vol * 1024 * 1024:
                await query.edit_message_text("📦 Splitting archive for Telegram...")
                volumes = await create_split_7z([archive_path], os.path.join(temp_dir, "split.7z"), password, max_vol)
                
                total = len(volumes)
                for i, vol in enumerate(volumes, 1):
                    caption = f"📦 Part {i}/{total}"
                    if password:
                        caption += "\n🔒 Password protected"
                    with open(vol, "rb") as fh:
                        await context.bot.send_document(chat_id=query.message.chat_id, document=fh, filename=vol.name, caption=caption)
                
                await query.edit_message_text(f"✅ 7z archive sent in {total} part(s)" + ("\n🔒 Password protected" if password else ""))
            else:
                caption = "📦 7z Archive"
                if password:
                    caption += "\n🔒 Password protected"
                with open(archive_path, "rb") as fh:
                    await context.bot.send_document(chat_id=query.message.chat_id, document=fh, filename=archive_name, caption=caption)
                await query.edit_message_text("✅ 7z archive sent successfully" + ("\n🔒 Password protected" if password else ""))
        
        elif action == "host":
            host_base = config.get("host_base_url")
            if not host_base:
                await query.edit_message_text("❌ Direct link feature not configured.")
                return
            
            await query.edit_message_text("📦 Creating 7z archive...")
            archive_name = f"{uuid4().hex}.7z"
            archive_path = os.path.join(temp_dir, archive_name)
            await create_7z_archive([dl_path], archive_path, password)
            
            dest = os.path.join(HOSTED_FILES_DIR, archive_name)
            shutil.move(archive_path, dest)
            
            meta = get_hosted_meta(context)
            meta.append({"filename": archive_name, "created_at": time.time(), "file_size": os.path.getsize(dest), "file_hash": file_hash})
            save_hosted_meta(meta)
            
            if config.get("enable_cache", True):
                file_cache.cache_file(file_info["file_id"], {"file_hash": file_hash, "password": password, "hosted_file": archive_name})
            
            link = f"{host_base}/files/{archive_name}"
            message, keyboard = create_link_message(link, bool(password), config.get("store_time_hours", 48))
            
            await query.edit_message_text(message, parse_mode='Markdown', reply_markup=keyboard, disable_web_page_preview=False)
            
    except Exception as e:
        logger.error(f"File processing error: {e}", exc_info=True)
        try:
            await query.edit_message_text(f"❌ Processing error: {str(e)[:200]}")
        except:
            await context.bot.send_message(chat_id=query.message.chat_id, text=f"❌ Processing error: {str(e)[:200]}")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

# ----------------------------------------------------------------------
# Download Functions
# ----------------------------------------------------------------------
async def download_with_aria2(urls: List[str], dest_dir: str) -> List[str]:
    """Download files using aria2c."""
    downloaded_files = set()
    for url in urls:
        try:
            logger.info(f"Downloading with aria2: {url}")
            cmd = ["aria2c", "--dir", dest_dir, "--max-connection-per-server=16", "--split=16", "--min-split-size=1M", "--continue=true", "--timeout=600", "--max-tries=5", "--retry-wait=5", "--console-log-level=error", url]
            
            process = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                for file in os.listdir(dest_dir):
                    if file.endswith('.aria2'):
                        continue
                    file_path = os.path.join(dest_dir, file)
                    if os.path.isfile(file_path):
                        downloaded_files.add(file_path)
                        logger.info(f"Downloaded: {file}")
            else:
                logger.error(f"aria2 failed for {url}: {stderr.decode()}")
        except Exception as e:
            logger.error(f"aria2 download failed for {url}: {e}")
    return list(downloaded_files)

async def download_direct(urls: List[str], dest_dir: str) -> List[str]:
    """Download files using aiohttp directly."""
    downloaded = []
    timeout = aiohttp.ClientTimeout(total=600)
    
    async with aiohttp.ClientSession(timeout=timeout) as session:
        for idx, url in enumerate(urls):
            try:
                logger.info(f"Downloading: {url}")
                headers = {"User-Agent": "Mozilla/5.0"}
                async with session.get(url, headers=headers) as resp:
                    resp.raise_for_status()
                    cd = resp.headers.get("Content-Disposition")
                    fname = None
                    if cd and "filename=" in cd:
                        fname_match = re.findall(r'filename[^;=\n]*=((["\']).*?\2|[^;\n]*)', cd)
                        if fname_match:
                            fname = fname_match[0][0].strip('"\'')
                    if not fname:
                        path = resp.url.path.rstrip("/")
                        fname = os.path.basename(path) or f"downloaded_{idx}"
                    fname = re.sub(r'[\\/*?:"<>|]', "_", fname)
                    filepath = os.path.join(dest_dir, fname)
                    with open(filepath, "wb") as f:
                        async for chunk in resp.content.iter_chunked(8192):
                            f.write(chunk)
                    downloaded.append(filepath)
                    logger.info(f"Downloaded: {fname}")
            except Exception as e:
                logger.error(f"Failed to download {url}: {e}")
    return downloaded

# ----------------------------------------------------------------------
# 7z Archive Creation
# ----------------------------------------------------------------------
async def create_7z_archive(files: List[str], output_path: str, password: str = ""):
    """Create a 7z archive."""
    cmd = ["7z", "a", "-t7z", "-mx=1", output_path]
    if password:
        cmd.extend([f"-p{password}", "-mhe=on"])
    cmd.extend(files)
    
    logger.info("Running 7z: 7z a -t7z -mx=1 [archive] [files]")
    process = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    stdout, stderr = await process.communicate()
    
    if process.returncode != 0:
        raise Exception(f"7z failed: {stderr.decode().strip()}")
    return output_path

async def create_split_7z(files: List[str], output_base: str, password: str, max_vol_mb: int) -> List[Path]:
    """Create split 7z archive for Telegram."""
    cmd = ["7z", "a", "-t7z", "-mx=0", f"-v{max_vol_mb}m"]
    if password:
        cmd.extend([f"-p{password}", "-mhe=on"])
    cmd.append(output_base)
    cmd.extend(files)
    
    logger.info(f"Running 7z split: 7z a -t7z -mx=0 -v{max_vol_mb}m [archive] [files]")
    process = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    stdout, stderr = await process.communicate()
    
    if process.returncode != 0:
        raise Exception(f"7z split failed: {stderr.decode().strip()}")
    
    output_dir = os.path.dirname(output_base)
    base_name = os.path.basename(output_base)
    volumes = sorted([p for p in Path(output_dir).glob(base_name + "*") if not p.name.endswith('.tmp')], key=lambda p: p.name)
    return volumes

# ----------------------------------------------------------------------
# Main Processing for Links
# ----------------------------------------------------------------------
async def process_links(update: Update, context, urls, action_type, action, query):
    """Process downloaded links based on action."""
    user_id = update.effective_user.id
    config = get_config(context)
    password = get_user_password(context, str(user_id))
    temp_dir = tempfile.mkdtemp(prefix="dl_")
    
    try:
        await query.edit_message_text("📥 Downloading files...")
        
        if config.get("download_method") == "aria2":
            files = await download_with_aria2(urls, temp_dir)
        else:
            files = await download_direct(urls, temp_dir)
        
        if not files:
            await query.edit_message_text("❌ Failed to download any file.")
            return
        
        file_hashes = [file_cache.get_file_hash(f) for f in files]
        
        await query.edit_message_text("📦 Creating 7z archive...")
        archive_name = f"{uuid4().hex}.7z"
        archive_path = os.path.join(temp_dir, archive_name)
        await create_7z_archive(files, archive_path, password)
        
        if config.get("enable_cache", True):
            for i, url in enumerate(urls):
                file_cache.cache_url(url, {
                    "file_hash": file_hashes[i] if i < len(file_hashes) else "",
                    "password": password,
                    "hosted_file": None if action == "telegram" else archive_name
                })
        
        if action == "telegram":
            max_vol = max(1, config.get("max_telegram_size_mb", 50) - 1)
            
            if os.path.getsize(archive_path) > max_vol * 1024 * 1024:
                await query.edit_message_text("📦 Splitting archive for Telegram...")
                volumes = await create_split_7z([archive_path], os.path.join(temp_dir, "split.7z"), password, max_vol)
                
                for i, vol in enumerate(volumes, 1):
                    caption = f"📦 Part {i}/{len(volumes)}"
                    if password:
                        caption += "\n🔒 Password protected"
                    with open(vol, "rb") as fh:
                        await context.bot.send_document(chat_id=query.message.chat_id, document=fh, filename=vol.name, caption=caption)
                
                await query.edit_message_text(f"✅ 7z archive sent in {len(volumes)} part(s)" + ("\n🔒 Password protected" if password else ""))
            else:
                caption = "📦 7z Archive"
                if password:
                    caption += "\n🔒 Password protected"
                with open(archive_path, "rb") as fh:
                    await context.bot.send_document(chat_id=query.message.chat_id, document=fh, filename=archive_name, caption=caption)
                await query.edit_message_text("✅ 7z archive sent successfully" + ("\n🔒 Password protected" if password else ""))
        
        elif action == "host":
            host_base = config.get("host_base_url")
            if not host_base:
                await query.edit_message_text("❌ Direct link feature not configured.")
                return
            
            dest = os.path.join(HOSTED_FILES_DIR, archive_name)
            shutil.move(archive_path, dest)
            
            meta = get_hosted_meta(context)
            meta.append({"filename": archive_name, "created_at": time.time(), "file_size": os.path.getsize(dest), "file_hash": file_hashes[0] if file_hashes else ""})
            save_hosted_meta(meta)
            
            link = f"{host_base}/files/{archive_name}"
            message, keyboard = create_link_message(link, bool(password), config.get("store_time_hours", 48))
            
            await query.edit_message_text(message, parse_mode='Markdown', reply_markup=keyboard, disable_web_page_preview=False)
            
    except Exception as e:
        logger.error(f"Processing error: {e}", exc_info=True)
        try:
            await query.edit_message_text(f"❌ Processing error: {str(e)[:200]}")
        except:
            await context.bot.send_message(chat_id=query.message.chat_id, text=f"❌ Processing error: {str(e)[:200]}")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

# ----------------------------------------------------------------------
# Cleanup Job
# ----------------------------------------------------------------------
async def cleanup_loop(application: Application):
    """Periodically delete expired hosted files and clean cache."""
    while True:
        try:
            await asyncio.sleep(3600)
            
            config = application.bot_data.get("config", {})
            meta = application.bot_data.get("hosted_meta", [])
            storage_hours = config.get("store_time_hours", 48)
            
            if meta:
                store_seconds = storage_hours * 3600
                now = time.time()
                new_meta = []
                
                for entry in meta:
                    if now - entry["created_at"] > store_seconds:
                        filepath = os.path.join(HOSTED_FILES_DIR, entry["filename"])
                        if os.path.exists(filepath):
                            os.remove(filepath)
                            logger.info(f"Deleted expired file: {entry['filename']}")
                    else:
                        new_meta.append(entry)
                
                application.bot_data["hosted_meta"] = new_meta
                save_hosted_meta(new_meta)
            
            if config.get("enable_cache", True):
                file_cache._clean_expired(storage_hours)
                
        except Exception as e:
            logger.error(f"Cleanup error: {e}", exc_info=True)

# ----------------------------------------------------------------------
# Web Server
# ----------------------------------------------------------------------
async def handle_web_file(request: web.Request):
    """Serve hosted files."""
    try:
        filename = request.match_info["filename"]
        if ".." in filename or filename.startswith("/"):
            raise web.HTTPForbidden()
        
        file_path = os.path.join(HOSTED_FILES_DIR, filename)
        if not os.path.isfile(file_path):
            raise web.HTTPNotFound()
        
        logger.info(f"Serving file: {filename}")
        return web.FileResponse(file_path)
    except web.HTTPException:
        raise
    except Exception as e:
        logger.error(f"Web server error: {e}")
        raise web.HTTPInternalServerError()

async def start_web_server(host: str, port: int):
    """Start HTTP server for direct links."""
    try:
        app = web.Application()
        app.router.add_get("/files/{filename}", handle_web_file)
        app.router.add_get("/health", lambda r: web.Response(text="OK"))
        
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, host, port)
        await site.start()
        
        logger.info(f"✅ Web server started on {host}:{port}")
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            pass
        finally:
            await runner.cleanup()
    except Exception as e:
        logger.error(f"Failed to start web server: {e}")

# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------
async def main():
    """Main bot initialization and startup."""
    global password_encryption, file_cache
    
    try:
        if not os.path.exists(CONFIG_FILE):
            config = create_config()
        else:
            config = load_config()
            if not config.get("token"):
                config = create_config()
        
        if "store_time_days" in config and "store_time_hours" not in config:
            config["store_time_hours"] = config["store_time_days"] * 24
            del config["store_time_days"]
        
        if not config.get("encryption_key"):
            config["encryption_key"] = secrets.token_hex(32)
        
        for k, v in DEFAULT_CONFIG.items():
            config.setdefault(k, v)
        
        save_config(config)
        
        password_encryption = PasswordEncryption(config["encryption_key"])
        file_cache = FileCache(config.get("cache_db_file", "cache_db.json"))
        
        if config.get("download_method") == "aria2":
            check_aria2(config)
        
        try:
            proc = await asyncio.create_subprocess_exec("7z", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            await proc.communicate()
        except Exception:
            logger.error("7z not found!")
            print("❌ 7z is required. Install: sudo apt install p7zip-full")
            return
        
        passwords = load_passwords()
        hosted_meta = load_hosted_meta()
        
        builder = ApplicationBuilder().token(config["token"])
        if config.get("api_base_url"):
            builder.base_url(config["api_base_url"])
            if config.get("api_base_file_url"):
                builder.base_file_url(config["api_base_file_url"])
        
        application = builder.build()
        application.bot_data["config"] = config
        application.bot_data["passwords"] = passwords
        application.bot_data["hosted_meta"] = hosted_meta
        
        # Command handlers
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_cmd))
        application.add_handler(CommandHandler("setpassword", set_password))
        application.add_handler(CommandHandler("mypassword", my_password))
        application.add_handler(CommandHandler("removepassword", remove_password))
        application.add_handler(CommandHandler("status", status))
        application.add_handler(CommandHandler("adminstatus", admin_status))
        application.add_handler(CommandHandler("clearcache", clear_cache))
        application.add_handler(CommandHandler("sethosturl", set_host_url))
        application.add_handler(CommandHandler("setstoretime", set_store_time))
        application.add_handler(CommandHandler("whitelist_add", whitelist_add))
        application.add_handler(CommandHandler("whitelist_remove", whitelist_remove))
        
        # Message handlers
        application.add_handler(MessageHandler(filters.Document.ALL, handle_file_upload))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
        application.add_handler(CallbackQueryHandler(handle_callback))
        
        async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
            logger.error(f"Update caused error: {context.error}", exc_info=context.error)
        
        application.add_error_handler(error_handler)
        
        web_task = None
        if config.get("host_base_url"):
            web_task = asyncio.create_task(start_web_server("0.0.0.0", config.get("host_port", 8080)))
        
        cleanup_task = asyncio.create_task(cleanup_loop(application))
        
        await application.initialize()
        await application.start()
        await application.updater.start_polling()
        
        logger.info("🤖 Bot started successfully!")
        print("✅ Bot is running. Press Ctrl+C to stop.")
        
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            pass
        finally:
            if web_task:
                web_task.cancel()
            cleanup_task.cancel()
            await application.updater.stop()
            await application.stop()
            await application.shutdown()
            logger.info("Bot stopped")
            
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        print(f"❌ Fatal error: {e}")

if __name__ == "__main__":
    asyncio.run(main())