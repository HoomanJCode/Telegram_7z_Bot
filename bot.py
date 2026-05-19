#!/usr/bin/env python3
"""
FileBot - Telegram Bot for File Download & Management
Author: Open Source Project
License: MIT
"""

import asyncio
import json
import os
import sys
from pathlib import Path

from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

# Local imports
from config import Config
from handlers.commands import (
    start, set_password, my_password, bot_status,
    set_host_url, set_store_time, whitelist_add, whitelist_remove
)
from handlers.messages import handle_document, handle_text
from handlers.callbacks import handle_callback
from services.web_server import WebServer
from core.file_manager import FileManager
from core.archiver import SevenZipArchiver
from core.downloader import DownloadManager
from utils.logger import setup_logger

# Setup
logger = setup_logger("FileBot")
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

class FileBot:
    """Main bot application."""
    
    def __init__(self):
        self.config = Config()
        self.file_manager = FileManager()
        self.web_server = None
        
        # Load persistent data
        self.passwords = self._load_passwords()
    
    def _load_passwords(self) -> dict:
        """Load user passwords."""
        passwords_file = DATA_DIR / "passwords.json"
        if passwords_file.exists():
            try:
                with open(passwords_file) as f:
                    return json.load(f)
            except json.JSONDecodeError:
                pass
        return {}
    
    def _save_passwords(self):
        """Save user passwords."""
        with open(DATA_DIR / "passwords.json", "w") as f:
            json.dump(self.passwords, f, indent=2)
    
    async def initialize(self):
        """Initialize bot components."""
        # Validate token
        if not self.config.token:
            logger.error("Bot token not configured!")
            print("❌ Please configure your bot token in config.json")
            sys.exit(1)
        
        # Check dependencies
        if self.config.download_method == "aria2":
            if not DownloadManager.check_availability():
                logger.warning("aria2 not found, switching to direct download")
                self.config._config["download_method"] = "direct"
                self.config._save_config()
        
        if not await SevenZipArchiver.check_availability():
            logger.error("7z not found!")
            print("❌ Please install p7zip-full: sudo apt install p7zip-full")
            sys.exit(1)
        
        # Build application
        builder = ApplicationBuilder().token(self.config.token)
        
        if self.config.api_base_url:
            builder.base_url(self.config.api_base_url)
            if self.config.api_base_file_url:
                builder.base_file_url(self.config.api_base_file_url)
        
        self.app = builder.build()
        
        # Store references
        self.app.bot_data["config"] = self.config
        self.app.bot_data["passwords"] = self.passwords
        self.app.bot_data["file_manager"] = self.file_manager
        
        # Register handlers
        self._register_handlers()
        
        # Start web server if configured
        if self.config.is_host_enabled:
            self.web_server = WebServer("0.0.0.0", self.config.host_port)
            asyncio.create_task(self.web_server.start())
        
        # Start cleanup task
        asyncio.create_task(self._cleanup_loop())
        
        return self.app
    
    def _register_handlers(self):
        """Register all bot handlers."""
        # Commands
        self.app.add_handler(CommandHandler("start", start))
        self.app.add_handler(CommandHandler("help", start))
        self.app.add_handler(CommandHandler("setpassword", set_password))
        self.app.add_handler(CommandHandler("mypassword", my_password))
        self.app.add_handler(CommandHandler("status", bot_status))
        self.app.add_handler(CommandHandler("sethosturl", set_host_url))
        self.app.add_handler(CommandHandler("setstoretime", set_store_time))
        self.app.add_handler(CommandHandler("wladd", whitelist_add))
        self.app.add_handler(CommandHandler("wlremove", whitelist_remove))
        
        # Messages
        self.app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
        
        # Callbacks
        self.app.add_handler(CallbackQueryHandler(handle_callback))
        
        # Error handler
        async def error_handler(update, context):
            logger.error("Update error", exc_info=context.error)
        
        self.app.add_error_handler(error_handler)
    
    async def _cleanup_loop(self):
        """Periodic cleanup of expired files."""
        while True:
            await asyncio.sleep(3600)
            try:
                await self.file_manager.cleanup_expired(self.config.store_time_hours)
            except Exception as e:
                logger.error(f"Cleanup error: {e}")
    
    async def run(self):
        """Start the bot."""
        app = await self.initialize()
        
        await app.initialize()
        await app.start()
        await app.updater.start_polling()
        
        logger.info("🤖 FileBot is running!")
        print("✅ Bot started. Press Ctrl+C to stop.")
        
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            pass
        finally:
            await self.shutdown()
    
    async def shutdown(self):
        """Graceful shutdown."""
        logger.info("Shutting down...")
        
        if self.web_server:
            await self.web_server.stop()
        
        await self.app.updater.stop()
        await self.app.stop()
        await self.app.shutdown()
        
        logger.info("Bot stopped.")

async def main():
    """Entry point."""
    bot = FileBot()
    await bot.run()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user")
