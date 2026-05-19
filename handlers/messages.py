from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from core.decorators import restricted
from utils.helpers import extract_urls, format_file_size
from utils.logger import setup_logger

logger = setup_logger(__name__)

@restricted
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle received files."""
    try:
        document = update.message.document
        
        context.user_data["pending_file"] = {
            "file_id": document.file_id,
            "file_name": document.file_name or f"file_{document.file_id[:8]}",
            "file_size": document.file_size
        }
        
        config = context.application.bot_data["config"]
        keyboard = [
            [InlineKeyboardButton("📦 Send as 7z", callback_data="file:telegram")]
        ]
        
        if config.is_host_enabled:
            keyboard.append([InlineKeyboardButton("🔗 Get Direct Link", callback_data="file:host")])
        
        keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="file:cancel")])
        
        await update.message.reply_text(
            f"📁 **File Received**\n\n"
            f"• Name: `{document.file_name}`\n"
            f"• Size: `{format_file_size(document.file_size)}`\n\n"
            "Choose action:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Document handler error: {e}")
        await update.message.reply_text("❌ Failed to process file.")

@restricted
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text messages with URLs."""
    try:
        urls = extract_urls(update.message.text)
        
        if not urls:
            await update.message.reply_text(
                "❌ No links found.\n"
                "Send HTTP/HTTPS links to download."
            )
            return
        
        context.user_data["pending_urls"] = urls
        
        config = context.application.bot_data["config"]
        keyboard = []
        
        prefix = "batch" if len(urls) > 1 else "single"
        
        keyboard.append([
            InlineKeyboardButton("📦 7z via Telegram", callback_data=f"{prefix}:telegram")
        ])
        
        if config.is_host_enabled:
            keyboard.append([
                InlineKeyboardButton("🔗 Direct Link", callback_data=f"{prefix}:host")
            ])
        
        keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel")])
        
        await update.message.reply_text(
            f"📎 Found **{len(urls)}** link(s)\n\n"
            "Select action:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Text handler error: {e}")
        await update.message.reply_text("❌ Failed to process message.")
