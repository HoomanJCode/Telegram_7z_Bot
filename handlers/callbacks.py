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

# Telegram Bot API limits
TELEGRAM_MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB for bots

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
    
    # For hosting, no size limit - proceed directly
    if action == "host":
        await query.edit_message_text("⏳ Processing file for hosting...")
        asyncio.create_task(_process_file(update, context, file_info, action, query))
        return
    
    # For Telegram sending, warn about large files but still process
    if action == "telegram":
        file_size_mb = file_info["file_size"] / (1024 * 1024) if file_info.get("file_size") else 0
        if file_size_mb > 50:
            await query.edit_message_text(
                f"⚠️ File is {file_size_mb:.1f} MB\n"
                f"Will be automatically split into parts.\n\n"
                "⏳ Processing...",
                parse_mode='Markdown'
            )
        else:
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
        await query.edit_message_text("📥 Downloading file...")
        file = await context.bot.get_file(file_info["file_id"])
        dl_path = os.path.join(temp_dir, file_info["file_name"])
        
        success = await _download_telegram_file(file, dl_path)
        if not success:
            await query.edit_message_text("❌ Failed to download file.")
            return
        
        file_size = os.path.getsize(dl_path)
        file_size_mb = file_size / (1024 * 1024)
        
        if action == "telegram":
            # Check if file needs splitting
            if file_size > TELEGRAM_MAX_FILE_SIZE:
                await query.edit_message_text(
                    f"📦 File is {file_size_mb:.1f} MB\n"
                    "Creating split archive for Telegram..."
                )
                
                # Create 7z archive first (no split)
                archive_name = f"{uuid4().hex}.7z"
                archive_path = os.path.join(temp_dir, archive_name)
                await archiver.create_archive([dl_path], archive_path, password)
                
                # Split the archive
                split_volumes = await archiver.create_split_archive(
                    [archive_path],
                    os.path.join(temp_dir, "part.7z"),
                    password,
                    config.max_telegram_size_mb - 1  # Leave 1MB margin
                )
                
                # Send all parts
                total = len(split_volumes)
                for i, vol in enumerate(split_volumes, 1):
                    caption = f"📦 {file_info['file_name']} - Part {i}/{total}"
                    if password:
                        caption += "\n🔒 Password protected"
                    
                    with open(vol, "rb") as f:
                        await context.bot.send_document(
                            chat_id=query.message.chat_id,
                            document=f,
                            filename=vol.name,
                            caption=caption,
                            read_timeout=120,
                            write_timeout=120
                        )
                
                await query.edit_message_text(
                    f"✅ File sent in {total} parts\n"
                    f"📦 Original: {file_info['file_name']}\n"
                    f"📏 Size: {file_size_mb:.1f} MB" +
                    ("\n🔒 Password protected" if password else "")
                )
            else:
                # File fits in one part
                await query.edit_message_text("📦 Creating 7z archive...")
                archive_name = f"{uuid4().hex}.7z"
                archive_path = os.path.join(temp_dir, archive_name)
                await archiver.create_archive([dl_path], archive_path, password)
                
                caption = f"📦 {file_info['file_name']}"
                if password:
                    caption += "\n🔒 Password protected"
                
                with open(archive_path, "rb") as f:
                    await context.bot.send_document(
                        chat_id=query.message.chat_id,
                        document=f,
                        filename=archive_name,
                        caption=caption,
                        read_timeout=120,
                        write_timeout=120
                    )
                
                await query.edit_message_text(
                    f"✅ File sent successfully\n"
                    f"📏 Size: {file_size_mb:.1f} MB" +
                    ("\n🔒 Password protected" if password else "")
                )
        
        elif action == "host":
            # Hosting - no size limit
            await query.edit_message_text("📦 Creating 7z archive for hosting...")
            
            archive_name = f"{uuid4().hex}.7z"
            archive_path = os.path.join(temp_dir, archive_name)
            await archiver.create_archive([dl_path], archive_path, password)
            
            archive_size = os.path.getsize(archive_path)
            
            dest = file_manager.host_file(archive_path, archive_name)
            file_manager.add_file_record(archive_name, archive_size)
            
            link = f"{config.host_base_url}/files/{archive_name}"
            
            message = (
                f"✅ **File Hosted Successfully**\n\n"
                f"📁 Original: `{file_info['file_name']}`\n"
                f"📦 Archive: `{archive_name}`\n"
                f"📏 Size: `{format_file_size(archive_size)}`\n\n"
                f"📎 **Direct Link:**\n`{link}`\n"
                f"🔗 [Click to Open]({link})\n"
            )
            if password:
                message += "🔒 Password protected\n"
            message += f"⏰ Expires: {format_time(config.store_time_hours * 3600)}"
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔗 Open Link", url=link)],
                [InlineKeyboardButton("📋 Copy Link", callback_data=f"copy:{link}")]
            ])
            
            await query.edit_message_text(
                message,
                parse_mode='Markdown',
                reply_markup=keyboard,
                disable_web_page_preview=False
            )
            
    except Exception as e:
        logger.error(f"File processing error: {e}", exc_info=True)
        await query.edit_message_text(f"❌ Processing failed: {str(e)[:200]}")
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
        await query.edit_message_text("📥 Downloading files...")
        downloader = DownloadManager(config.download_method)
        files = await downloader.download(urls, temp_dir)
        
        if not files:
            await query.edit_message_text("❌ No files downloaded.")
            return
        
        # Calculate total size
        total_size = sum(os.path.getsize(f) for f in files)
        total_size_mb = total_size / (1024 * 1024)
        
        # Create archive
        await query.edit_message_text(f"📦 Creating archive ({total_size_mb:.1f} MB)...")
        archive_name = f"{uuid4().hex}.7z"
        archive_path = os.path.join(temp_dir, archive_name)
        await archiver.create_archive(files, archive_path, password)
        
        archive_size = os.path.getsize(archive_path)
        
        if action == "telegram":
            # Check if archive needs splitting
            if archive_size > TELEGRAM_MAX_FILE_SIZE:
                await query.edit_message_text(
                    f"📦 Archive is {archive_size/(1024*1024):.1f} MB\n"
                    "Splitting for Telegram..."
                )
                
                split_volumes = await archiver.create_split_archive(
                    [archive_path],
                    os.path.join(temp_dir, "part.7z"),
                    password,
                    config.max_telegram_size_mb - 1
                )
                
                total = len(split_volumes)
                for i, vol in enumerate(split_volumes, 1):
                    caption = f"📦 Archive Part {i}/{total}"
                    if password:
                        caption += "\n🔒 Password protected"
                    
                    with open(vol, "rb") as f:
                        await context.bot.send_document(
                            chat_id=query.message.chat_id,
                            document=f,
                            filename=vol.name,
                            caption=caption,
                            read_timeout=120,
                            write_timeout=120
                        )
                
                await query.edit_message_text(
                    f"✅ Archive sent in {total} parts\n"
                    f"📏 Total: {format_file_size(archive_size)}" +
                    ("\n🔒 Password protected" if password else "")
                )
            else:
                caption = f"📦 Archive ({len(files)} files)"
                if password:
                    caption += "\n🔒 Password protected"
                
                with open(archive_path, "rb") as f:
                    await context.bot.send_document(
                        chat_id=query.message.chat_id,
                        document=f,
                        filename=archive_name,
                        caption=caption,
                        read_timeout=120,
                        write_timeout=120
                    )
                
                await query.edit_message_text(
                    f"✅ Archive sent\n"
                    f"📏 Size: {format_file_size(archive_size)}" +
                    ("\n🔒 Password protected" if password else "")
                )
        
        elif action == "host":
            # Hosting - no size limit
            dest = file_manager.host_file(archive_path, archive_name)
            file_manager.add_file_record(archive_name, archive_size)
            
            link = f"{config.host_base_url}/files/{archive_name}"
            
            message = (
                f"✅ **Files Hosted Successfully**\n\n"
                f"📁 Files: `{len(files)}`\n"
                f"📦 Archive: `{archive_name}`\n"
                f"📏 Size: `{format_file_size(archive_size)}`\n\n"
                f"📎 **Direct Link:**\n`{link}`\n"
                f"🔗 [Click to Open]({link})\n"
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
            
    except Exception as e:
        logger.error(f"URL processing error: {e}", exc_info=True)
        await query.edit_message_text(f"❌ Processing failed: {str(e)[:200]}")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

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
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=600)) as resp:
                    if resp.status == 200:
                        with open(dest_path, "wb") as f:
                            async for chunk in resp.content.iter_chunked(8192):
                                f.write(chunk)
                        return True
        except Exception as e2:
            logger.error(f"Fallback failed: {e2}")
        return False