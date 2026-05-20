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
        
        file_size = document.file_size or 0
        file_size_mb = file_size / (1024 * 1024)
        
        context.user_data["pending_file"] = {
            "file_id": document.file_id,
            "file_name": document.file_name or f"file_{document.file_id[:8]}",
            "file_size": file_size
        }
        
        config = context.application.bot_data["config"]
        keyboard = [
            [InlineKeyboardButton("📦 Send as 7z via Telegram", callback_data="file:telegram")]
        ]
        
        if config.is_host_enabled:
            keyboard.append([
                InlineKeyboardButton("🔗 Get Direct Link (No Size Limit)", callback_data="file:host")
            ])
        
        keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="file:cancel")])
        
        # Show size warning for Telegram option
        warning = ""
        if file_size_mb > 50:
            warning = (
                "\n⚠️ **Large File Detected**\n"
                "• Telegram: Will be automatically split\n"
                "• Direct Link: No size limit\n"
            )
        
        await update.message.reply_text(
            f"📁 **File Received**\n\n"
            f"• Name: `{document.file_name}`\n"
            f"• Size: `{format_file_size(file_size)}`\n"
            f"{warning}\n"
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
            InlineKeyboardButton(
                "📦 Send as 7z via Telegram",
                callback_data=f"{prefix}:telegram"
            )
        ])
        
        if config.is_host_enabled:
            keyboard.append([
                InlineKeyboardButton(
                    "🔗 Get Direct Link (No Size Limit)",
                    callback_data=f"{prefix}:host"
                )
            ])
        
        keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel")])
        
        message = f"📎 Found **{len(urls)}** link(s)\n\n"
        message += "• **Telegram**: Auto-split if too large\n"
        message += "• **Direct Link**: No size restrictions\n\n"
        message += "Select action:"
        
        await update.message.reply_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Text handler error: {e}")
        await update.message.reply_text("❌ Failed to process message.")