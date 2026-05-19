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

logger = setup_logger("FileBot")
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

class FileBot:
    """Main bot application."""
    
    def __init__(self):
        self.config = Config()
        self.file_manager = FileManager()
        self.web_server = None
        self._tasks = []
        
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
    
    def _validate_dependencies(self):
        """Check required dependencies."""
        if not self.config.token:
            logger.error("Bot token not configured!")
            print("❌ Please configure your bot token in config.json")
            sys.exit(1)
        
        if self.config.download_method == "aria2":
            if not DownloadManager.check_availability():
                logger.warning("aria2 not found, switching to direct download")
                self.config._config["download_method"] = "direct"
                self.config._save_config()
        
        if not asyncio.get_event_loop().run_until_complete(SevenZipArchiver.check_availability()):
            logger.error("7z not found!")
            print("❌ Please install p7zip-full: sudo apt install p7zip-full")
            sys.exit(1)
    
    def _register_handlers(self, app: Application):
        """Register all bot handlers."""
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("help", start))
        app.add_handler(CommandHandler("setpassword", set_password))
        app.add_handler(CommandHandler("mypassword", my_password))
        app.add_handler(CommandHandler("status", bot_status))
        app.add_handler(CommandHandler("sethosturl", set_host_url))
        app.add_handler(CommandHandler("setstoretime", set_store_time))
        app.add_handler(CommandHandler("wladd", whitelist_add))
        app.add_handler(CommandHandler("wlremove", whitelist_remove))
        
        app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
        app.add_handler(CallbackQueryHandler(handle_callback))
        
        async def error_handler(update, context):
            logger.error("Update error", exc_info=context.error)
        
        app.add_error_handler(error_handler)
    
    async def _cleanup_loop(self):
        """Periodic cleanup of expired files."""
        while True:
            try:
                await asyncio.sleep(3600)
                await self.file_manager.cleanup_expired(self.config.store_time_hours)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup error: {e}")
    
    async def start(self):
        """Initialize and start the bot."""
        # Validate dependencies
        if not self.config.token:
            logger.error("Bot token not configured!")
            print("❌ Please configure your bot token in config.json")
            sys.exit(1)
        
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
        
        app = builder.build()
        
        # Store references
        app.bot_data["config"] = self.config
        app.bot_data["passwords"] = self.passwords
        app.bot_data["file_manager"] = self.file_manager
        
        # Register handlers
        self._register_handlers(app)
        
        # Start web server if configured
        if self.config.is_host_enabled:
            self.web_server = WebServer("0.0.0.0", self.config.host_port)
            await self.web_server.start()
        
        # Start cleanup task
        cleanup_task = asyncio.create_task(self._cleanup_loop())
        self._tasks.append(cleanup_task)
        
        # Start bot
        await app.initialize()
        await app.start()
        await app.updater.start_polling()
        
        logger.info("🤖 FileBot is running!")
        print("✅ Bot started. Press Ctrl+C to stop.")
        
        self._app = app
        
        # Keep running
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            pass
    
    async def shutdown(self):
        """Graceful shutdown."""
        logger.info("Shutting down...")
        
        # Stop web server
        if self.web_server:
            await self.web_server.stop()
        
        # Cancel tasks
        for task in self._tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        # Stop bot
        if hasattr(self, '_app'):
            try:
                await self._app.updater.stop()
                await self._app.stop()
                await self._app.shutdown()
            except Exception as e:
                logger.error(f"Shutdown error: {e}")
        
        logger.info("Bot stopped.")

async def main():
    """Entry point."""
    bot = FileBot()
    try:
        await bot.start()
    except KeyboardInterrupt:
        pass
    finally:
        await bot.shutdown()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user")