import os
import tempfile
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from core.decorators import restricted
from utils.helpers import extract_urls, extract_urls_from_file, format_file_size
from utils.logger import setup_logger

logger = setup_logger(__name__)

TELEGRAM_UPLOAD_LIMIT = 20 * 1024 * 1024  # 20 MB

def get_settings(context: ContextTypes.DEFAULT_TYPE):
    """Get settings from bot_data."""
    return context.application.bot_data.get("settings") or context.application.bot_data.get("config")

@restricted
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle received files - check for URLs in text files."""
    try:
        document = update.message.document
        
        file_size = document.file_size or 0
        file_name = document.file_name or f"file_{document.file_id[:8]}"
        
        # Check if it's a text file that might contain URLs
        text_extensions = ['.txt', '.csv', '.log', '.json', '.xml', '.html', '.htm', '.md', '.list']
        _, ext = os.path.splitext(file_name.lower())
        
        if ext in text_extensions and file_size < 5 * 1024 * 1024:  # Under 5MB
            # Download and check for URLs
            try:
                file = await context.bot.get_file(document.file_id)
                temp_dir = tempfile.mkdtemp(prefix="fb_")
                temp_path = os.path.join(temp_dir, file_name)
                await file.download_to_drive(temp_path)
                
                urls = extract_urls_from_file(temp_path)
                
                # Clean up temp file
                import shutil
                shutil.rmtree(temp_dir, ignore_errors=True)
                
                if urls:
                    context.user_data["pending_urls"] = urls
                    
                    config = get_settings(context)
                    keyboard = []
                    prefix = "batch" if len(urls) > 1 else "single"
                    
                    keyboard.append([
                        InlineKeyboardButton("📦 Send as 7z via Telegram", callback_data=f"{prefix}:telegram")
                    ])
                    
                    if config and config.is_host_enabled:
                        keyboard.append([
                            InlineKeyboardButton("🔗 Get Direct Link (No Size Limit)", callback_data=f"{prefix}:host")
                        ])
                    
                    keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel")])
                    
                    await update.message.reply_text(
                        f"📄 Found **{len(urls)}** link(s) in file:\n"
                        f"`{file_name}`\n\n"
                        f"Links preview:\n" + "\n".join([f"• `{url[:50]}...`" if len(url) > 50 else f"• `{url}`" for url in urls[:5]]) +
                        (f"\n... and {len(urls) - 5} more" if len(urls) > 5 else "") +
                        "\n\nSelect action:",
                        parse_mode='Markdown',
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
                    return
                    
            except Exception as e:
                logger.error(f"Error reading file for URLs: {e}")
        
        # Regular file handling (not a text file or no URLs found)
        if file_size > TELEGRAM_UPLOAD_LIMIT:
            await update.message.reply_text(
                f"⚠️ **File Too Large**\n\n"
                f"📁 File: `{file_name}`\n"
                f"📏 Size: `{format_file_size(file_size)}`\n\n"
                f"❌ Telegram bots cannot process files larger than **20 MB**.\n\n"
                f"**Solutions:**\n"
                f"1. Upload your file to a hosting service and send me the **link**\n"
                f"2. Use a file sharing service (Google Drive, Dropbox, etc.)\n"
                f"3. Compress the file before sending\n\n"
                f"I can download files of ANY size from links!",
                parse_mode='Markdown'
            )
            return
        
        context.user_data["pending_file"] = {
            "file_id": document.file_id,
            "file_name": file_name,
            "file_size": file_size
        }
        
        config = get_settings(context)
        keyboard = [
            [InlineKeyboardButton("📦 Send as 7z via Telegram", callback_data="file:telegram")]
        ]
        
        if config and config.is_host_enabled:
            keyboard.append([
                InlineKeyboardButton("🔗 Get Direct Link", callback_data="file:host")
            ])
        
        keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="file:cancel")])
        
        await update.message.reply_text(
            f"📁 **File Received**\n\n"
            f"• Name: `{file_name}`\n"
            f"• Size: `{format_file_size(file_size)}`\n\n"
            "Choose action:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Document handler error: {e}")
        await update.message.reply_text("❌ Failed to process file.")

@restricted
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text messages with URLs - supports multiple formats."""
    try:
        text = update.message.text
        
        # Extract URLs from text
        urls = extract_urls(text)
        
        if not urls:
            # Show main menu if no URLs
            keyboard = [
                [InlineKeyboardButton("📁 Recent Files", callback_data="menu:recent")],
                [InlineKeyboardButton("📊 Bot Status", callback_data="menu:status")],
                [InlineKeyboardButton("🔒 My Password", callback_data="menu:password")],
                [InlineKeyboardButton("ℹ️ Help", callback_data="menu:help")]
            ]
            await update.message.reply_text(
                "Send me download links or use the menu:\n\n"
                "**Supported formats:**\n"
                "• Single link: `https://example.com/file.zip`\n"
                "• Multiple links (newlines):\n"
                "  `link1`\n"
                "  `link2`\n"
                "• Multiple links (commas): `link1, link2`\n"
                "• Links in text: I'll extract them automatically\n"
                "• Text files: Send .txt/.csv/.log files with links",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return
        
        # Store URLs
        context.user_data["pending_urls"] = urls
        
        config = get_settings(context)
        keyboard = []
        prefix = "batch" if len(urls) > 1 else "single"
        
        keyboard.append([
            InlineKeyboardButton("📦 Send as 7z via Telegram", callback_data=f"{prefix}:telegram")
        ])
        
        if config and config.is_host_enabled:
            keyboard.append([
                InlineKeyboardButton("🔗 Get Direct Link (No Size Limit)", callback_data=f"{prefix}:host")
            ])
        
        keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel")])
        
        # Build message with link preview
        if len(urls) == 1:
            message = f"📎 **Found 1 link:**\n\n`{urls[0]}`\n\n"
        else:
            message = f"📎 **Found {len(urls)} links:**\n\n"
            for i, url in enumerate(urls[:10]):
                if len(url) > 60:
                    message += f"{i+1}. `{url[:57]}...`\n"
                else:
                    message += f"{i+1}. `{url}`\n"
            if len(urls) > 10:
                message += f"\n... and {len(urls) - 10} more links\n"
            message += "\n"
        
        message += "• **Telegram**: Auto-split into parts\n"
        message += "• **Direct Link**: No size restrictions\n\n"
        message += "Select action:"
        
        await update.message.reply_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown',
            disable_web_page_preview=True
        )
        
    except Exception as e:
        logger.error(f"Text handler error: {e}")
        await update.message.reply_text("❌ Failed to process message.")