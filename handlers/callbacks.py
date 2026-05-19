import asyncio
import os
import tempfile
import shutil
from uuid import uuid4
from pathlib import Path
import aiohttp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from core.decorators import restricted
from core.downloader import DownloadManager
from core.archiver import SevenZipArchiver
from core.file_manager import FileManager
from utils.logger import setup_logger
from utils.helpers import format_time, format_file_size

logger = setup_logger(__name__)
file_manager = FileManager()
archiver = SevenZipArchiver()

@restricted
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all callback queries."""
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if data == "cancel":
        context.user_data.clear()
        await query.edit_message_text("❌ Cancelled.")
        return
    
    if data.startswith("file:"):
        await _handle_file_callback(update, context, query, data)
    else:
        await _handle_url_callback(update, context, query, data)

async def _handle_file_callback(update, context, query, data):
    """Handle file action callbacks."""
    _, action = data.split(":", 1)
    
    if action == "cancel":
        context.user_data.pop("pending_file", None)
        await query.edit_message_text("❌ Cancelled.")
        return
    
    file_info = context.user_data.pop("pending_file", None)
    if not file_info:
        await query.edit_message_text("⏰ Session expired.")
        return
    
    await query.edit_message_text("⏳ Processing file...")
    asyncio.create_task(_process_file(update, context, file_info, action, query))

async def _handle_url_callback(update, context, query, data):
    """Handle URL action callbacks."""
    action_type, action = data.split(":", 1)
    
    urls = context.user_data.pop("pending_urls", None)
    if not urls:
        await query.edit_message_text("⏰ Session expired.")
        return
    
    await query.edit_message_text(f"⏳ Processing {len(urls)} link(s)...")
    asyncio.create_task(_process_urls(update, context, urls, action, query))

async def _process_file(update, context, file_info, action, query):
    """Process uploaded file."""
    config = context.application.bot_data["config"]
    passwords = context.application.bot_data["passwords"]
    password = passwords.get(str(update.effective_user.id), "")
    temp_dir = tempfile.mkdtemp(prefix="filebot_")
    
    try:
        # Download file
        await query.edit_message_text("📥 Downloading...")
        file = await context.bot.get_file(file_info["file_id"])
        dl_path = os.path.join(temp_dir, file_info["file_name"])
        
        await _download_telegram_file(file, dl_path)
        
        # Create archive
        await query.edit_message_text("📦 Archiving...")
        archive_name = f"{uuid4().hex}.7z"
        archive_path = os.path.join(temp_dir, archive_name)
        await archiver.create_archive([dl_path], archive_path, password)
        
        if action == "telegram":
            await _send_archive_telegram(context, query, archive_path, archive_name, password, config)
        elif action == "host":
            await _host_archive(context, query, archive_path, archive_name, password, config)
            
    except Exception as e:
        logger.error(f"File processing error: {e}")
        await query.edit_message_text("❌ Processing failed.")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

async def _process_urls(update, context, urls, action, query):
    """Process URLs."""
    config = context.application.bot_data["config"]
    passwords = context.application.bot_data["passwords"]
    password = passwords.get(str(update.effective_user.id), "")
    temp_dir = tempfile.mkdtemp(prefix="filebot_")
    
    try:
        # Download
        await query.edit_message_text("📥 Downloading...")
        downloader = DownloadManager(config.download_method)
        files = await downloader.download(urls, temp_dir)
        
        if not files:
            await query.edit_message_text("❌ Download failed.")
            return
        
        # Archive
        await query.edit_message_text("📦 Archiving...")
        archive_name = f"{uuid4().hex}.7z"
        archive_path = os.path.join(temp_dir, archive_name)
        await archiver.create_archive(files, archive_path, password)
        
        if action == "telegram":
            await _send_archive_telegram(context, query, archive_path, archive_name, password, config)
        elif action == "host":
            await _host_archive(context, query, archive_path, archive_name, password, config)
            
    except Exception as e:
        logger.error(f"URL processing error: {e}")
        await query.edit_message_text("❌ Processing failed.")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

async def _send_archive_telegram(context, query, archive_path, archive_name, password, config):
    """Send archive via Telegram."""
    max_size = (config.max_telegram_size_mb - 1) * 1024 * 1024
    
    if os.path.getsize(archive_path) > max_size:
        await query.edit_message_text("📦 Splitting...")
        temp_dir = os.path.dirname(archive_path)
        volumes = await archiver.create_split_archive(
            [archive_path],
            os.path.join(temp_dir, "split.7z"),
            password,
            config.max_telegram_size_mb - 1
        )
        
        total = len(volumes)
        for i, vol in enumerate(volumes, 1):
            caption = f"📦 Part {i}/{total}"
            if password:
                caption += "\n🔒 Protected"
            
            with open(vol, "rb") as f:
                await context.bot.send_document(
                    chat_id=query.message.chat_id,
                    document=f,
                    filename=vol.name,
                    caption=caption
                )
        
        await query.edit_message_text(f"✅ Sent in {total} parts")
    else:
        caption = "📦 Archive"
        if password:
            caption += "\n🔒 Protected"
        
        with open(archive_path, "rb") as f:
            await context.bot.send_document(
                chat_id=query.message.chat_id,
                document=f,
                filename=archive_name,
                caption=caption
            )
        
        await query.edit_message_text("✅ Sent successfully")

async def _host_archive(context, query, archive_path, archive_name, password, config):
    """Host archive and return direct link."""
    file_size = os.path.getsize(archive_path)
    file_manager.host_file(archive_path, archive_name)
    file_manager.add_file_record(archive_name, file_size)
    
    link = f"{config.host_base_url}/files/{archive_name}"
    
    message = (
        f"✅ **Hosted Successfully**\n\n"
        f"📎 `{link}`\n"
        f"🔗 [Open Link]({link})\n"
        f"📦 Size: `{format_file_size(file_size)}`\n"
    )
    if password:
        message += "🔒 Password protected\n"
    message += f"⏰ Expires: {format_time(config.store_time_hours * 3600)}"
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔗 Open Link", url=link)]
    ])
    
    await query.edit_message_text(
        message,
        parse_mode='Markdown',
        reply_markup=keyboard,
        disable_web_page_preview=False
    )

async def _download_telegram_file(file, dest_path: str) -> bool:
    """Download file from Telegram with fallback."""
    try:
        await file.download_to_drive(dest_path)
        return True
    except Exception as e:
        logger.error(f"Download error: {e}")
        try:
            bot = file.get_bot()
            base_url = getattr(bot, 'base_file_url', "https://api.telegram.org/file")
            url = f"{base_url}/bot{bot.token}/{file.file_path}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        with open(dest_path, "wb") as f:
                            async for chunk in resp.content.iter_chunked(8192):
                                f.write(chunk)
                        return True
        except Exception as e2:
            logger.error(f"Fallback failed: {e2}")
        return False
