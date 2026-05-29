import asyncio
import os
import tempfile
import shutil
import time
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
from utils.helpers import format_time, format_file_size, mask_string

logger = setup_logger(__name__)
file_manager = FileManager()
archiver = SevenZipArchiver()

TELEGRAM_MAX_DOWNLOAD = 20 * 1024 * 1024
TELEGRAM_MAX_UPLOAD = 50 * 1024 * 1024

def get_settings(context: ContextTypes.DEFAULT_TYPE):
    """Get settings from bot_data."""
    return context.application.bot_data.get("settings") or context.application.bot_data.get("config")

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
    
    if data.startswith("menu:"):
        await _handle_menu_callback(update, context, query, data)
        return
    
    if data.startswith("file:"):
        await _handle_file_callback(update, context, query, data)
        return
    
    if ":" in data:
        await _handle_url_callback(update, context, query, data)
        return
    
    await query.edit_message_text("❌ Unknown action.")

async def _handle_menu_callback(update, context, query, data):
    """Handle main menu callbacks."""
    _, action = data.split(":", 1)
    settings = get_settings(context)
    
    if action == "recent":
        metadata = file_manager.load_metadata()
        if not metadata:
            await query.edit_message_text("📁 No hosted files found.")
            return
        
        recent = sorted(metadata, key=lambda x: x.get("created_at", 0), reverse=True)[:10]
        message = "📁 **Recent Files**\n\n"
        keyboard = []
        
        for i, entry in enumerate(recent):
            fname = entry.get("original_name", entry.get("filename", "Unknown"))
            fsize = format_file_size(entry.get("file_size", 0))
            t = int(time.time() - entry.get("created_at", 0))
            message += f"**{i+1}.** `{fname}`\n   📏 `{fsize}` • ⏰ `{format_time(t)} ago`\n\n"
            
            if settings and settings.is_host_enabled:
                link = f"{settings.host_base_url}/files/{entry.get('filename')}"
                keyboard.append([InlineKeyboardButton(f"📎 {fname[:30]}", url=link)])
        
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="menu:main")])
        await query.edit_message_text(message, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard[:11]))
    
    elif action == "status":
        metadata = file_manager.load_metadata()
        status = f"📊 **Status**\n\n• Files: `{len(metadata)}`\n• Storage: `{format_time(settings.store_time_hours * 3600)}`"
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="menu:main")]]
        await query.edit_message_text(status, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif action == "password":
        user_id = str(update.effective_user.id)
        passwords = context.application.bot_data["passwords"]
        text = f"✅ Password: `{mask_string(passwords[user_id])}`" if user_id in passwords else "❌ No password set."
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="menu:main")]]
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif action == "help":
        text = "🤖 **Help**\n\n• Send links → 7z archive\n• Send files → Convert\n• /start for menu"
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="menu:main")]]
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif action == "main":
        keyboard = [
            [InlineKeyboardButton("📁 Recent Files", callback_data="menu:recent")],
            [InlineKeyboardButton("📊 Bot Status", callback_data="menu:status")],
            [InlineKeyboardButton("🔒 My Password", callback_data="menu:password")],
            [InlineKeyboardButton("ℹ️ Help", callback_data="menu:help")]
        ]
        await query.edit_message_text("🤖 **Main Menu**", parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

async def _handle_file_callback(update, context, query, data):
    """Handle file action callbacks."""
    _, action = data.split(":", 1)
    
    if action == "cancel":
        context.user_data.pop("pending_file", None)
        await query.edit_message_text("❌ Cancelled.")
        return
    
    file_info = context.user_data.pop("pending_file", None)
    if not file_info:
        await query.edit_message_text("⏰ Session expired. Send file again.")
        return
    
    await query.edit_message_text("⏳ Processing...")
    asyncio.create_task(_process_file(update, context, file_info, action, query))

async def _handle_url_callback(update, context, query, data):
    """Handle URL action callbacks."""
    parts = data.split(":", 1)
    if len(parts) != 2:
        return
    _, action = parts
    
    urls = context.user_data.pop("pending_urls", None)
    if not urls:
        await query.edit_message_text("⏰ Session expired. Send links again.")
        return
    
    await query.edit_message_text(f"⏳ Processing {len(urls)} link(s)...")
    asyncio.create_task(_process_urls(update, context, urls, action, query))

async def _process_file(update, context, file_info, action, query):
    """Process uploaded file."""
    settings = get_settings(context)
    passwords = context.application.bot_data["passwords"]
    password = passwords.get(str(update.effective_user.id), "")
    temp_dir = tempfile.mkdtemp(prefix="fb_")
    
    try:
        file = await context.bot.get_file(file_info["file_id"])
        dl_path = os.path.join(temp_dir, file_info.get("file_name", "file"))
        await _download_telegram_file(file, dl_path)
        
        archive_name = f"{uuid4().hex}.7z"
        archive_path = os.path.join(temp_dir, archive_name)
        await archiver.create_archive([dl_path], archive_path, password)
        archive_size = os.path.getsize(archive_path)
        
        if action == "telegram":
            if archive_size > TELEGRAM_MAX_UPLOAD:
                volumes = await archiver.create_split_archive([archive_path], os.path.join(temp_dir, "part.7z"), password, settings.max_telegram_size_mb - 1)
                for i, vol in enumerate(volumes, 1):
                    with open(vol, "rb") as f:
                        await context.bot.send_document(chat_id=query.message.chat_id, document=f, filename=vol.name, caption=f"Part {i}/{len(volumes)}")
                    await asyncio.sleep(1)
                await query.edit_message_text(f"✅ Sent in {len(volumes)} parts")
            else:
                with open(archive_path, "rb") as f:
                    await context.bot.send_document(chat_id=query.message.chat_id, document=f, filename=archive_name)
                await query.edit_message_text("✅ Sent")
        
        elif action == "host" and settings.is_host_enabled:
            file_manager.host_file(archive_path, archive_name)
            file_manager.add_file_record(archive_name, archive_size, file_info.get("file_name", "file"))
            link = f"{settings.host_base_url}/files/{archive_name}"
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔗 Open", url=link)]])
            await query.edit_message_text(f"✅ Hosted!\n📎 `{link}`", parse_mode='Markdown', reply_markup=keyboard)
            
    except Exception as e:
        logger.error(f"Error: {e}")
        await query.edit_message_text(f"❌ Error: {str(e)[:200]}")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

async def _process_urls(update, context, urls, action, query):
    """Process URLs."""
    settings = get_settings(context)
    passwords = context.application.bot_data["passwords"]
    password = passwords.get(str(update.effective_user.id), "")
    temp_dir = tempfile.mkdtemp(prefix="fb_")
    
    try:
        downloader = DownloadManager(settings.download_method)
        files = await downloader.download(urls, temp_dir)
        
        if not files:
            await query.edit_message_text("❌ Download failed.")
            return
        
        archive_name = f"{uuid4().hex}.7z"
        archive_path = os.path.join(temp_dir, archive_name)
        await archiver.create_archive(files, archive_path, password)
        archive_size = os.path.getsize(archive_path)
        
        if action == "telegram":
            if archive_size > TELEGRAM_MAX_UPLOAD:
                volumes = await archiver.create_split_archive([archive_path], os.path.join(temp_dir, "part.7z"), password, settings.max_telegram_size_mb - 1)
                for i, vol in enumerate(volumes, 1):
                    with open(vol, "rb") as f:
                        await context.bot.send_document(chat_id=query.message.chat_id, document=f, filename=vol.name, caption=f"Part {i}/{len(volumes)}")
                    await asyncio.sleep(1)
                await query.edit_message_text(f"✅ Sent in {len(volumes)} parts")
            else:
                with open(archive_path, "rb") as f:
                    await context.bot.send_document(chat_id=query.message.chat_id, document=f, filename=archive_name)
                await query.edit_message_text("✅ Sent")
        
        elif action == "host" and settings.is_host_enabled:
            file_manager.host_file(archive_path, archive_name)
            file_manager.add_file_record(archive_name, archive_size)
            link = f"{settings.host_base_url}/files/{archive_name}"
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔗 Open", url=link)]])
            await query.edit_message_text(f"✅ Hosted!\n📎 `{link}`", parse_mode='Markdown', reply_markup=keyboard)
            
    except Exception as e:
        logger.error(f"Error: {e}")
        await query.edit_message_text(f"❌ Error: {str(e)[:200]}")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

async def _download_telegram_file(file, dest_path: str) -> bool:
    """Download file from Telegram."""
    try:
        await file.download_to_drive(dest_path)
        return True
    except Exception:
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
        except Exception:
            pass
        return False