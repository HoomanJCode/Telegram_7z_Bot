from telegram import Update
from telegram.ext import ContextTypes
from core.decorators import restricted, admin_only
from core.file_manager import FileManager
from utils.logger import setup_logger
from utils.helpers import format_time, mask_string

logger = setup_logger(__name__)
file_manager = FileManager()

@restricted
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send welcome message."""
    config = context.application.bot_data["config"]
    
    await update.message.reply_text(
        "🤖 **FileBot - Download Manager**\n\n"
        "**Features:**\n"
        "• Send links → Download & pack to 7z\n"
        "• Send files → Archive & host\n"
        "• Multiple links → Batch to single 7z\n\n"
        "**Commands:**\n"
        "/setpassword - Set archive password\n"
        "/mypassword - Check password status\n"
        "/status - Bot statistics\n\n"
        "Send a link or file to begin!",
        parse_mode='Markdown'
    )

@restricted
async def set_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set 7z password for user."""
    user_id = str(update.effective_user.id)
    args = context.args
    
    if not args:
        await update.message.reply_text(
            "Usage: `/setpassword <password>`\n\n"
            "⚠️ Send this in **private chat** for security.",
            parse_mode='Markdown'
        )
        return
    
    password = " ".join(args)
    passwords = context.application.bot_data["passwords"]
    passwords[user_id] = password
    
    # Save passwords
    import json
    with open("data/passwords.json", "w") as f:
        json.dump(passwords, f, indent=2)
    
    await update.message.reply_text(
        f"✅ Password saved!\n"
        f"Password: `{mask_string(password)}`",
        parse_mode='Markdown'
    )

@restricted
async def my_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show password status."""
    user_id = str(update.effective_user.id)
    passwords = context.application.bot_data["passwords"]
    
    if user_id in passwords:
        await update.message.reply_text(
            f"✅ Password is set: `{mask_string(passwords[user_id])}`",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text("❌ No password set. Use /setpassword")

@restricted
async def bot_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show bot status."""
    config = context.application.bot_data["config"]
    metadata = file_manager.load_metadata()
    store_time = format_time(config.store_time_hours * 3600)
    
    status = (
        f"📊 **Bot Status**\n\n"
        f"• Download: `{config.download_method}`\n"
        f"• Hosted files: `{len(metadata)}`\n"
        f"• Storage time: `{store_time}`\n"
        f"• Max file: `{config.max_telegram_size_mb} MB`\n"
        f"• Whitelist: `{'On' if config.is_whitelist_enabled else 'Off'}`\n"
        f"• Hosting: `{'Active' if config.is_host_enabled else 'Inactive'}`"
    )
    
    await update.message.reply_text(status, parse_mode='Markdown')

@admin_only
async def set_host_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set hosting URL."""
    args = context.args
    if not args:
        await update.message.reply_text("Usage: `/sethosturl <url>`", parse_mode='Markdown')
        return
    
    config = context.application.bot_data["config"]
    config.host_base_url = args[0].rstrip("/")
    await update.message.reply_text("✅ Host URL updated. Restart required.")

@admin_only
async def set_store_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set file storage time."""
    args = context.args
    if not args or not args[0].isdigit():
        await update.message.reply_text("Usage: `/setstoretime <hours>`", parse_mode='Markdown')
        return
    
    hours = int(args[0])
    if hours < 1:
        await update.message.reply_text("❌ Minimum 1 hour required.")
        return
    
    config = context.application.bot_data["config"]
    config.store_time_hours = hours
    
    await update.message.reply_text(
        f"✅ Storage time: {format_time(hours * 3600)}"
    )

@admin_only
async def whitelist_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add user to whitelist."""
    args = context.args
    if not args or not args[0].isdigit():
        await update.message.reply_text("Usage: `/wladd <user_id>`", parse_mode='Markdown')
        return
    
    config = context.application.bot_data["config"]
    config.add_to_whitelist(int(args[0]))
    await update.message.reply_text("✅ User whitelisted.")

@admin_only
async def whitelist_remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remove user from whitelist."""
    args = context.args
    if not args or not args[0].isdigit():
        await update.message.reply_text("Usage: `/wlremove <user_id>`", parse_mode='Markdown')
        return
    
    config = context.application.bot_data["config"]
    config.remove_from_whitelist(int(args[0]))
    await update.message.reply_text("✅ User removed.")
