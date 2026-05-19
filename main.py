#!/usr/bin/env python3
import asyncio
import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import List, Dict
from uuid import uuid4

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
# Default config
# ----------------------------------------------------------------------
DEFAULT_CONFIG = {
    "token": "",
    "api_base_url": "",
    "api_base_file_url": "",
    "host_base_url": "",
    "host_port": 8080,
    "store_time_hours": 48,  # Changed from days to hours
    "max_telegram_size_mb": 50,
    "whitelist": [],
    "admin_ids": [],
    "download_method": "aria2",
    "aria2_rpc_url": "http://localhost:6800/jsonrpc",
    "aria2_secret": "",
}

CONFIG_FILE = "config.json"
PASSWORDS_FILE = "passwords.json"
HOSTED_FILES_DIR = "hosted_files"
HOSTED_META_FILE = os.path.join(HOSTED_FILES_DIR, "metadata.json")

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
    
    save_config(cfg)
    print(f"Config saved to {CONFIG_FILE}.")
    return cfg

def load_passwords() -> Dict[str, str]:
    """Load user passwords."""
    if not os.path.exists(PASSWORDS_FILE):
        return {}
    with open(PASSWORDS_FILE, "r") as f:
        return json.load(f)

def save_passwords(passwords: Dict[str, str]):
    """Save user passwords."""
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

def format_store_time(hours: int) -> str:
    """Format storage time in human readable format."""
    if hours < 1:
        return "less than 1 hour"
    elif hours == 1:
        return "1 hour"
    elif hours < 24:
        return f"{hours} hours"
    elif hours == 24:
        return "1 day"
    else:
        days = hours // 24
        remaining_hours = hours % 24
        if remaining_hours == 0:
            return f"{days} day(s)"
        else:
            return f"{days} day(s) and {remaining_hours} hour(s)"

def mask_password(password: str) -> str:
    """Mask password for display."""
    if not password:
        return ""
    if len(password) <= 2:
        return "*" * len(password)
    return password[0] + "*" * (len(password) - 2) + password[-1]

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

def create_link_message(link: str, password: str = "", store_hours: int = 48) -> tuple:
    """Create message and keyboard for direct link display."""
    store_time = format_store_time(store_hours)
    
    message = (
        f"✅ File archived and hosted!\n\n"
        f"📎 **Direct Link:**\n"
        f"`{link}`\n\n"
        f"🔗 [Click to Open]({link})\n\n"
    )
    if password:
        message += f"🔒 Password protected\n"
    message += f"⏰ Expires in: {store_time}"
    
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
        download_method = config.get("download_method", "direct")
        
        await update.message.reply_text(
            "🤖 **File Download Bot**\n\n"
            "**Features:**\n"
            "• Send a link → Download and pack to 7z\n"
            "• Send multiple links → Batch download to single 7z\n"
            "• Send a file → Choose to send as 7z or get direct link\n\n"
            "**Commands:**\n"
            "/setpassword - Set your 7z password\n"
            "/mypassword - Show password status\n"
            "/status - Show bot status\n"
            f"Download method: **{download_method}**\n\n"
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
    """Set 7z password for user."""
    try:
        user_id = str(update.effective_user.id)
        args = context.args
        if not args:
            await update.message.reply_text(
                "Usage: `/setpassword <your_password>`\n\n"
                "Send this command in **private chat** for security.",
                parse_mode='Markdown'
            )
            return
        
        password = " ".join(args)
        passwords = get_passwords(context)
        passwords[user_id] = password
        save_passwords(passwords)
        
        await update.message.reply_text(
            f"✅ Your 7z password has been saved.\n"
            f"Password: `{mask_password(password)}`\n\n"
            "⚠️ For security, this message will not show the full password.",
            parse_mode='Markdown'
        )
        logger.info(f"User {user_id} set password")
    except Exception as e:
        logger.error(f"Error setting password: {e}", exc_info=True)
        await update.message.reply_text("❌ Failed to set password.")

@restricted
async def my_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show password status."""
    try:
        user_id = str(update.effective_user.id)
        passwords = get_passwords(context)
        if user_id in passwords:
            await update.message.reply_text(
                f"✅ Password is set: `{mask_password(passwords[user_id])}`\n"
                "Use /setpassword to change it.",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text("❌ No password set. Use /setpassword to set one.")
    except Exception as e:
        logger.error(f"Error showing password: {e}", exc_info=True)

@restricted
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show bot status."""
    try:
        config = get_config(context)
        hosted_meta = get_hosted_meta(context)
        store_time = format_store_time(config.get("store_time_hours", 48))
        
        status_text = (
            f"📊 **Bot Status**\n\n"
            f"Download method: `{config.get('download_method', 'direct')}`\n"
            f"Hosted files: `{len(hosted_meta)}`\n"
            f"File storage: `{store_time}`\n"
            f"Max file size: `{config.get('max_telegram_size_mb', 50)}` MB\n"
            f"Whitelist: `{'Enabled' if config.get('whitelist') else 'Disabled'}`\n"
        )
        await update.message.reply_text(status_text, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Error showing status: {e}", exc_info=True)

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
            f"✅ Host URL updated.\nRestart bot to apply web server changes.",
            parse_mode='Markdown'
        )
        logger.info(f"Host URL changed")
    except Exception as e:
        logger.error(f"Error setting host URL: {e}", exc_info=True)

@admin_only
async def set_store_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set file storage time in hours."""
    try:
        args = context.args
        if not args or not args[0].isdigit():
            await update.message.reply_text(
                "Usage: `/setstoretime <hours>`\n"
                "Example: `/setstoretime 48` for 2 days",
                parse_mode='Markdown'
            )
            return
        
        hours = int(args[0])
        if hours < 1:
            await update.message.reply_text("❌ Storage time must be at least 1 hour.")
            return
        
        config = get_config(context)
        config["store_time_hours"] = hours
        save_config(config)
        
        store_time = format_store_time(hours)
        await update.message.reply_text(f"✅ File storage time set to {store_time}.")
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
        await update.message.reply_text(f"✅ User added to whitelist.")
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
        await update.message.reply_text(f"✅ User removed from whitelist.")
    except Exception as e:
        logger.error(f"Error removing from whitelist: {e}", exc_info=True)

# ----------------------------------------------------------------------
# File Download Helper
# ----------------------------------------------------------------------
async def download_telegram_file(file, dest_path: str) -> bool:
    """Download a file from Telegram/Bale."""
    try:
        file_path = file.file_path
        bot = file.get_bot()
        
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
            logger.info(f"Trying fallback download URL")
            
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
        
        context.user_data["pending_file"] = {
            "file_id": file_id,
            "file_name": document.file_name or f"file_{uuid4().hex[:8]}",
            "file_size": document.file_size
        }
        
        keyboard = []
        config = get_config(context)
        host_available = bool(config.get("host_base_url"))
        
        keyboard.append([
            InlineKeyboardButton("📦 Send as 7z via Telegram", callback_data="file:telegram")
        ])
        
        if host_available:
            keyboard.append([
                InlineKeyboardButton("🔗 Get Direct Link", callback_data="file:host")
            ])
        
        keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="file:cancel")])
        
        file_size_mb = document.file_size / (1024 * 1024) if document.file_size else 0
        
        await update.message.reply_text(
            f"📁 **File Received**\n\n"
            f"Name: `{document.file_name}`\n"
            f"Size: `{file_size_mb:.2f} MB`\n\n"
            "Choose action:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Error handling file upload: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Failed to process file.")

@restricted
async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text messages with URLs."""
    try:
        text = update.message.text
        urls = list(set(re.findall(r'https?://\S+', text)))
        
        if not urls:
            await update.message.reply_text(
                "❌ No valid link found.\n"
                "Please send a message containing HTTP/HTTPS links."
            )
            return

        context.user_data["pending_urls"] = urls
        logger.info(f"User {update.effective_user.id} sent {len(urls)} URL(s)")
        
        keyboard = []
        config = get_config(context)
        host_available = bool(config.get("host_base_url"))
        
        if len(urls) > 1:
            keyboard.append([
                InlineKeyboardButton("📦 Send as 7z via Telegram", callback_data="batch:telegram")
            ])
            if host_available:
                keyboard.append([
                    InlineKeyboardButton("🔗 Host and Get Direct Links", callback_data="batch:host")
                ])
        else:
            keyboard.append([
                InlineKeyboardButton("📦 Send as 7z via Telegram", callback_data="single:telegram")
            ])
            if host_available:
                keyboard.append([
                    InlineKeyboardButton("🔗 Host and Get Direct Link", callback_data="single:host")
                ])
        
        keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel")])
        
        await update.message.reply_text(
            f"📎 Found **{len(urls)}** link(s)\n\n"
            "Choose action:",
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
            f"⏳ Processing **{len(pending_urls)}** link(s)...\n"
            f"This may take a while depending on file size.",
            parse_mode='Markdown'
        )

        asyncio.create_task(
            process_links(update, context, pending_urls, action_type, action, query)
        )
        
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
    
    await query.edit_message_text("⏳ Processing file...")
    
    asyncio.create_task(
        process_file(update, context, pending_file, action, query)
    )

async def process_file(update: Update, context, file_info, action, query):
    """Process uploaded file based on action."""
    user_id = update.effective_user.id
    config = get_config(context)
    passwords = get_passwords(context)
    password = passwords.get(str(user_id), "")
    temp_dir = tempfile.mkdtemp(prefix="file_")
    
    try:
        await query.edit_message_text("📥 Downloading file...")
        file = await context.bot.get_file(file_info["file_id"])
        dl_path = os.path.join(temp_dir, file_info["file_name"])
        
        success = await download_telegram_file(file, dl_path)
        if not success:
            await query.edit_message_text("❌ Failed to download file from server.")
            return
        
        if action == "telegram":
            await query.edit_message_text("📦 Creating 7z archive...")
            archive_name = f"{uuid4().hex}.7z"
            archive_path = os.path.join(temp_dir, archive_name)
            await create_7z_archive([dl_path], archive_path, password)
            
            max_vol = max(1, config.get("max_telegram_size_mb", 50) - 1)
            
            if os.path.getsize(archive_path) > max_vol * 1024 * 1024:
                await query.edit_message_text("📦 Splitting archive...")
                volumes = await create_split_7z(
                    [archive_path],
                    os.path.join(temp_dir, "split.7z"),
                    password,
                    max_vol
                )
                
                total = len(volumes)
                for i, vol in enumerate(volumes, 1):
                    try:
                        caption = f"📦 Part {i}/{total}"
                        if password:
                            caption += "\n🔒 Password protected"
                        
                        with open(vol, "rb") as fh:
                            await context.bot.send_document(
                                chat_id=query.message.chat_id,
                                document=fh,
                                filename=vol.name,
                                caption=caption
                            )
                    except Exception as e:
                        logger.error(f"Failed to send {vol.name}: {e}")
                
                await query.edit_message_text(
                    f"✅ 7z archive sent in {total} part(s)" +
                    ("\n🔒 Password protected" if password else "")
                )
            else:
                with open(archive_path, "rb") as fh:
                    caption = "📦 7z Archive"
                    if password:
                        caption += "\n🔒 Password protected"
                    
                    await context.bot.send_document(
                        chat_id=query.message.chat_id,
                        document=fh,
                        filename=archive_name,
                        caption=caption
                    )
                
                await query.edit_message_text(
                    "✅ 7z archive sent successfully" +
                    ("\n🔒 Password protected" if password else "")
                )
        
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
            meta.append({
                "filename": archive_name,
                "created_at": time.time(),
                "file_size": os.path.getsize(dest)
            })
            save_hosted_meta(meta)
            
            link = f"{host_base}/files/{archive_name}"
            store_hours = config.get("store_time_hours", 48)
            
            message, reply_markup = create_link_message(link, password, store_hours)
            
            await query.edit_message_text(
                message,
                parse_mode='Markdown',
                reply_markup=reply_markup,
                disable_web_page_preview=False
            )
            
    except Exception as e:
        logger.error(f"File processing error: {e}", exc_info=True)
        try:
            await query.edit_message_text("❌ Processing error occurred.")
        except:
            pass
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

# ----------------------------------------------------------------------
# Download Functions
# ----------------------------------------------------------------------
async def download_with_aria2(urls: List[str], dest_dir: str) -> List[str]:
    """Download files using aria2c."""
    downloaded_files = set()
    
    for idx, url in enumerate(urls):
        try:
            logger.info(f"Downloading with aria2: {url}")
            
            cmd = [
                "aria2c",
                "--dir", dest_dir,
                "--max-connection-per-server=16",
                "--split=16",
                "--min-split-size=1M",
                "--continue=true",
                "--timeout=600",
                "--max-tries=5",
                "--retry-wait=5",
                "--console-log-level=error",
                url
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                for file in os.listdir(dest_dir):
                    if file.endswith('.aria2'):
                        continue
                    file_path = os.path.join(dest_dir, file)
                    if os.path.isfile(file_path):
                        downloaded_files.add(file_path)
            else:
                logger.error(f"aria2 failed for URL")
                
        except Exception as e:
            logger.error(f"aria2 download failed")
    
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
                    
            except Exception as e:
                logger.error(f"Failed to download URL")
    
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
    
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
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
    
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    
    if process.returncode != 0:
        raise Exception(f"7z split failed: {stderr.decode().strip()}")
    
    output_dir = os.path.dirname(output_base)
    base_name = os.path.basename(output_base)
    volumes = sorted(
        [p for p in Path(output_dir).glob(base_name + "*") if not p.name.endswith('.tmp')],
        key=lambda p: p.name
    )
    
    return volumes

# ----------------------------------------------------------------------
# Main Processing for Links
# ----------------------------------------------------------------------
async def process_links(update: Update, context, urls, action_type, action, query):
    """Process downloaded links based on action."""
    user_id = update.effective_user.id
    config = get_config(context)
    passwords = get_passwords(context)
    password = passwords.get(str(user_id), "")
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
        
        await query.edit_message_text("📦 Creating 7z archive...")
        archive_name = f"{uuid4().hex}.7z"
        archive_path = os.path.join(temp_dir, archive_name)
        await create_7z_archive(files, archive_path, password)
        
        if action == "telegram":
            max_vol = max(1, config.get("max_telegram_size_mb", 50) - 1)
            
            if os.path.getsize(archive_path) > max_vol * 1024 * 1024:
                await query.edit_message_text("📦 Splitting archive...")
                volumes = await create_split_7z(
                    [archive_path],
                    os.path.join(temp_dir, "split.7z"),
                    password,
                    max_vol
                )
                
                total = len(volumes)
                for i, vol in enumerate(volumes, 1):
                    try:
                        caption = f"📦 Part {i}/{total}"
                        if password:
                            caption += "\n🔒 Password protected"
                        
                        with open(vol, "rb") as fh:
                            await context.bot.send_document(
                                chat_id=query.message.chat_id,
                                document=fh,
                                filename=vol.name,
                                caption=caption
                            )
                    except Exception as e:
                        logger.error(f"Failed to send {vol.name}: {e}")
                
                await query.edit_message_text(
                    f"✅ 7z archive sent in {total} part(s)" +
                    ("\n🔒 Password protected" if password else "")
                )
            else:
                with open(archive_path, "rb") as fh:
                    caption = "📦 7z Archive"
                    if password:
                        caption += "\n🔒 Password protected"
                    
                    await context.bot.send_document(
                        chat_id=query.message.chat_id,
                        document=fh,
                        filename=archive_name,
                        caption=caption
                    )
                
                await query.edit_message_text(
                    "✅ 7z archive sent successfully" +
                    ("\n🔒 Password protected" if password else "")
                )
        
        elif action == "host":
            host_base = config.get("host_base_url")
            if not host_base:
                await query.edit_message_text("❌ Direct link feature not configured.")
                return
            
            dest = os.path.join(HOSTED_FILES_DIR, archive_name)
            shutil.move(archive_path, dest)
            
            meta = get_hosted_meta(context)
            meta.append({
                "filename": archive_name,
                "created_at": time.time(),
                "file_size": os.path.getsize(dest)
            })
            save_hosted_meta(meta)
            
            link = f"{host_base}/files/{archive_name}"
            store_hours = config.get("store_time_hours", 48)
            
            message, reply_markup = create_link_message(link, password, store_hours)
            
            await query.edit_message_text(
                message,
                parse_mode='Markdown',
                reply_markup=reply_markup,
                disable_web_page_preview=False
            )
            
    except Exception as e:
        logger.error(f"Processing error: {e}", exc_info=True)
        try:
            await query.edit_message_text("❌ Processing error occurred.")
        except:
            pass
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

# ----------------------------------------------------------------------
# Cleanup Job
# ----------------------------------------------------------------------
async def cleanup_loop(application: Application):
    """Periodically delete expired hosted files."""
    while True:
        try:
            await asyncio.sleep(3600)
            
            config = application.bot_data.get("config", {})
            meta = application.bot_data.get("hosted_meta", [])
            
            if not meta:
                continue
            
            store_seconds = config.get("store_time_hours", 48) * 3600
            now = time.time()
            new_meta = []
            deleted = 0
            
            for entry in meta:
                if now - entry["created_at"] > store_seconds:
                    filepath = os.path.join(HOSTED_FILES_DIR, entry["filename"])
                    if os.path.exists(filepath):
                        os.remove(filepath)
                        logger.info(f"Deleted expired file: {entry['filename']}")
                        deleted += 1
                else:
                    new_meta.append(entry)
            
            if deleted > 0:
                application.bot_data["hosted_meta"] = new_meta
                save_hosted_meta(new_meta)
                
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
    try:
        if not os.path.exists(CONFIG_FILE):
            config = create_config()
        else:
            config = load_config()
            if not config.get("token"):
                config = create_config()
        
        # Migrate old config if needed
        if "store_time_days" in config and "store_time_hours" not in config:
            config["store_time_hours"] = config["store_time_days"] * 24
            del config["store_time_days"]
            save_config(config)
        
        for k, v in DEFAULT_CONFIG.items():
            config.setdefault(k, v)
        
        save_config(config)
        
        if config.get("download_method") == "aria2":
            check_aria2(config)
        
        try:
            proc = await asyncio.create_subprocess_exec(
                "7z", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            await proc.communicate()
        except Exception:
            print("❌ 7z is required but not found. Install it with: sudo apt install p7zip-full")
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
        
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_cmd))
        application.add_handler(CommandHandler("setpassword", set_password))
        application.add_handler(CommandHandler("mypassword", my_password))
        application.add_handler(CommandHandler("status", status))
        application.add_handler(CommandHandler("sethosturl", set_host_url))
        application.add_handler(CommandHandler("setstoretime", set_store_time))
        application.add_handler(CommandHandler("whitelist_add", whitelist_add))
        application.add_handler(CommandHandler("whitelist_remove", whitelist_remove))
        
        application.add_handler(MessageHandler(filters.Document.ALL, handle_file_upload))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
        application.add_handler(CallbackQueryHandler(handle_callback))
        
        async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
            logger.error(f"Update caused error", exc_info=context.error)
        
        application.add_error_handler(error_handler)
        
        web_task = None
        if config.get("host_base_url"):
            host = "0.0.0.0"
            port = config.get("host_port", 8080)
            web_task = asyncio.create_task(start_web_server(host, port))
        
        cleanup_task = asyncio.create_task(cleanup_loop(application))
        
        await application.initialize()
        await application.start()
        await application.updater.start_polling()
        
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
            
            try:
                await asyncio.gather(web_task, cleanup_task, return_exceptions=True)
            except asyncio.CancelledError:
                pass
            
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user")