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
TELEGRAM_MAX_DOWNLOAD = 20 * 1024 * 1024  # 20 MB - Bot can receive
TELEGRAM_MAX_UPLOAD = 50 * 1024 * 1024    # 50 MB - Bot can send

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
    
    # Additional size check before processing
    if file_info.get("file_size", 0) > TELEGRAM_MAX_DOWNLOAD:
        await query.edit_message_text(
            f"⚠️ **File Too Large**\n\n"
            f"Telegram bots cannot process files >20 MB sent directly.\n\n"
            f"**Solution:** Upload your file somewhere and send me the **download link**.\n"
            f"I can handle files of ANY size from URLs!",
            parse_mode='Markdown'
        )
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
    """Process uploaded file (under 20MB)."""
    config = context.application.bot_data["config"]
    passwords = context.application.bot_data["passwords"]
    password = passwords.get(str(update.effective_user.id), "")
    temp_dir = tempfile.mkdtemp(prefix="filebot_")
    
    try:
        # Download file from Telegram (already validated <20MB)
        await query.edit_message_text("📥 Downloading file...")
        file = await context.bot.get_file(file_info["file_id"])
        dl_path = os.path.join(temp_dir, file_info["file_name"])
        
        success = await _download_telegram_file(file, dl_path)
        if not success:
            await query.edit_message_text("❌ Failed to download file.")
            return
        
        file_size = os.path.getsize(dl_path)
        
        if action == "telegram":
            # Create 7z archive and send via Telegram
            await query.edit_message_text("📦 Creating 7z archive...")
            archive_name = f"{uuid4().hex}.7z"
            archive_path = os.path.join(temp_dir, archive_name)
            await archiver.create_archive([dl_path], archive_path, password)
            
            archive_size = os.path.getsize(archive_path)
            
            # Check if archive exceeds Telegram upload limit
            if archive_size > TELEGRAM_MAX_UPLOAD:
                await query.edit_message_text(
                    f"📦 Splitting archive ({format_file_size(archive_size)})..."
                )
                
                volumes = await archiver.create_split_archive(
                    [archive_path],
                    os.path.join(temp_dir, "part.7z"),
                    password,
                    config.max_telegram_size_mb - 1
                )
                
                total = len(volumes)
                await query.edit_message_text(f"📤 Uploading {total} parts...")
                
                for i, vol in enumerate(volumes, 1):
                    caption = f"📦 {file_info['file_name']}\nPart {i}/{total}"
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
                    
                    if i < total:
                        await asyncio.sleep(1)
                
                await query.edit_message_text(
                    f"✅ File sent in {total} parts\n"
                    f"📏 Size: {format_file_size(archive_size)}" +
                    ("\n🔒 Password protected" if password else "")
                )
            else:
                # Single file upload
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
                    f"📏 Size: {format_file_size(archive_size)}" +
                    ("\n🔒 Password protected" if password else "")
                )
        
        elif action == "host":
            # Host the file - no upload limits for hosting
            await query.edit_message_text("📦 Creating 7z archive for hosting...")
            
            archive_name = f"{uuid4().hex}.7z"
            archive_path = os.path.join(temp_dir, archive_name)
            await archiver.create_archive([dl_path], archive_path, password)
            
            archive_size = os.path.getsize(archive_path)
            
            file_manager.host_file(archive_path, archive_name)
            file_manager.add_file_record(archive_name, archive_size)
            
            link = f"{config.host_base_url}/files/{archive_name}"
            
            message = (
                f"✅ **File Hosted Successfully**\n\n"
                f"📁 Original: `{file_info['file_name']}`\n"
                f"📏 Size: `{format_file_size(archive_size)}`\n\n"
                f"📎 **Direct Link:**\n`{link}`\n"
                f"🔗 [Click to Open]({link})\n"
            )
            if password:
                message += "\n🔒 Password protected"
            message += f"\n⏰ Expires: {format_time(config.store_time_hours * 3600)}"
            
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
        logger.error(f"File processing error: {e}", exc_info=True)
        await query.edit_message_text(f"❌ Processing failed: {str(e)[:200]}")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

async def _process_urls(update, context, urls, action, query):
    """Process URLs - NO size limits for downloads."""
    config = context.application.bot_data["config"]
    passwords = context.application.bot_data["passwords"]
    password = passwords.get(str(update.effective_user.id), "")
    temp_dir = tempfile.mkdtemp(prefix="filebot_")
    
    try:
        # Download files from URLs (any size)
        await query.edit_message_text("📥 Downloading files...")
        downloader = DownloadManager(config.download_method)
        files = await downloader.download(urls, temp_dir)
        
        if not files:
            await query.edit_message_text("❌ No files downloaded.")
            return
        
        total_size = sum(os.path.getsize(f) for f in files)
        
        # Create archive
        await query.edit_message_text(
            f"📦 Creating archive ({format_file_size(total_size)})..."
        )
        archive_name = f"{uuid4().hex}.7z"
        archive_path = os.path.join(temp_dir, archive_name)
        await archiver.create_archive(files, archive_path, password)
        
        archive_size = os.path.getsize(archive_path)
        
        if action == "telegram":
            # Check if needs splitting for Telegram
            if archive_size > TELEGRAM_MAX_UPLOAD:
                await query.edit_message_text(
                    f"📦 Splitting archive ({format_file_size(archive_size)})..."
                )
                
                volumes = await archiver.create_split_archive(
                    [archive_path],
                    os.path.join(temp_dir, "part.7z"),
                    password,
                    config.max_telegram_size_mb - 1
                )
                
                total = len(volumes)
                await query.edit_message_text(f"📤 Uploading {total} parts...")
                
                for i, vol in enumerate(volumes, 1):
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
                    
                    if i < total:
                        await asyncio.sleep(1)
                
                await query.edit_message_text(
                    f"✅ Archive sent in {total} parts\n"
                    f"📁 {len(files)} file(s)\n"
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
            # Hosting - NO size limit
            file_manager.host_file(archive_path, archive_name)
            file_manager.add_file_record(archive_name, archive_size)
            
            link = f"{config.host_base_url}/files/{archive_name}"
            
            message = (
                f"✅ **Files Hosted Successfully**\n\n"
                f"📁 Files: `{len(files)}`\n"
                f"📏 Size: `{format_file_size(archive_size)}`\n\n"
                f"📎 **Direct Link:**\n`{link}`\n"
                f"🔗 [Click to Open]({link})\n"
            )
            if password:
                message += "\n🔒 Password protected"
            message += f"\n⏰ Expires: {format_time(config.store_time_hours * 3600)}"
            
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
                async with session.get(
                    url,
                    timeout=aiohttp.ClientTimeout(total=600)
                ) as resp:
                    if resp.status == 200:
                        with open(dest_path, "wb") as f:
                            async for chunk in resp.content.iter_chunked(8192):
                                f.write(chunk)
                        return True
        except Exception as e2:
            logger.error(f"Fallback failed: {e2}")
        return False