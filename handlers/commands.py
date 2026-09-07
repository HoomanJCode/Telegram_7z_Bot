from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from core.decorators import restricted, admin_only
from core.file_manager import FileManager
from utils.logger import setup_logger
from utils.helpers import format_time, mask_string, format_file_size

logger = setup_logger(__name__)
file_manager = FileManager()

def get_settings(context: ContextTypes.DEFAULT_TYPE):
    """Get settings from bot_data (supports both 'settings' and 'config' keys)."""
    return context.application.bot_data.get("settings") or context.application.bot_data.get("config")

@restricted
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send welcome message with menu."""
    settings = get_settings(context)
    
    keyboard = [
        [InlineKeyboardButton("📁 Recent Files", callback_data="menu:recent")],
        [InlineKeyboardButton("📊 Bot Status", callback_data="menu:status")],
        [InlineKeyboardButton("🔒 My Password", callback_data="menu:password")],
        [InlineKeyboardButton("ℹ️ Help", callback_data="menu:help")]
    ]
    
    await update.message.reply_text(
        "🤖 **FileBot - Download Manager**\n\n"
        "**Features:**\n"
        "• Send links → Download & pack to 7z (ANY size)\n"
        "• Send files (<20MB) → Archive & host\n"
        "• Multiple links → Batch to single 7z\n\n"
        "**Telegram Limits:**\n"
        "• File upload to bot: Max **20 MB**\n"
        "• Download from links: **Unlimited**\n\n"
        "Use menu below or send me a link/file!",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

@restricted
async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Help command."""
    await start(update, context)

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
    
    import json
    from pathlib import Path
    DATA_DIR = Path("data")
    DATA_DIR.mkdir(exist_ok=True)
    with open(DATA_DIR / "passwords.json", "w") as f:
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
    settings = get_settings(context)
    metadata = file_manager.load_metadata()
    store_time = format_time(settings.store_time_hours * 3600)
    
    status = (
        f"📊 **Bot Status**\n\n"
        f"• Download: `{settings.download_method}`\n"
        f"• Hosted files: `{len(metadata)}`\n"
        f"• Storage time: `{store_time}`\n"
        f"• Max file: `{settings.max_telegram_size_mb} MB`\n"
        f"• Whitelist: `{'On' if settings.is_whitelist_enabled else 'Off'}`\n"
        f"• Hosting: `{'Active' if settings.is_host_enabled else 'Inactive'}`\n"
        f"• Host URL: `{settings.host_base_url or 'Not set'}`"
    )
    
    await update.message.reply_text(status, parse_mode='Markdown')

@restricted
async def recent_files(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show recent hosted files."""
    settings = get_settings(context)
    metadata = file_manager.load_metadata()
    
    if not metadata:
        await update.message.reply_text("📁 No hosted files found.")
        return
    
    # Sort by creation time (newest first) and take last 20
    recent = sorted(metadata, key=lambda x: x.get("created_at", 0), reverse=True)[:20]
    
    if not recent:
        await update.message.reply_text("📁 No recent files.")
        return
    
    message = "📁 **Recent Hosted Files**\n\n"
    keyboard = []
    
    import time
    for i, entry in enumerate(recent):
        filename = entry.get("filename", "Unknown")
        file_size = entry.get("file_size", 0)
        created_at = entry.get("created_at", 0)
        original_name = entry.get("original_name", filename)
        
        time_ago = format_time(int(time.time() - created_at))
        
        message += (
            f"**{i+1}.** `{original_name}`\n"
            f"   📏 `{format_file_size(file_size)}` • ⏰ `{time_ago} ago`\n\n"
        )
        
        if settings.is_host_enabled:
            link = f"{settings.host_base_url}/files/{filename}"
            keyboard.append([
                InlineKeyboardButton(
                    f"📎 {original_name[:30]}",
                    url=link
                )
            ])
    
    if len(recent) > 5:
        message += f"Showing last {len(recent)} files."
    
    if keyboard:
        await update.message.reply_text(
            message,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard[:10]),  # Max 10 buttons
            disable_web_page_preview=True
        )
    else:
        await update.message.reply_text(message, parse_mode='Markdown')

@admin_only
async def set_host_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set hosting URL."""
    args = context.args
    if not args:
        await update.message.reply_text(
            "Usage: `/sethosturl <url>`\n"
            "Example: `/sethosturl http://your-server.com:8080`",
            parse_mode='Markdown'
        )
        return
    
    settings = get_settings(context)
    url = args[0].rstrip("/")
    detected_port = settings.update_host_url(url)
    message = f"✅ Host URL updated to: `{url}`\n"
    if detected_port is not None:
        message += f"🌐 Port detected from URL: `{detected_port}`\n"
    message += "Restart bot to apply changes."
    await update.message.reply_text(
        message,
        parse_mode='Markdown'
    )

@admin_only
async def set_store_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set file storage time."""
    args = context.args
    if not args or not args[0].isdigit():
        await update.message.reply_text(
            "Usage: `/setstoretime <hours>`\n"
            "Example: `/setstoretime 72` for 3 days",
            parse_mode='Markdown'
        )
        return
    
    hours = int(args[0])
    if hours < 1:
        await update.message.reply_text("❌ Minimum 1 hour required.")
        return
    
    settings = get_settings(context)
    settings.update_store_time(hours)
    
    await update.message.reply_text(
        f"✅ Storage time set to: {format_time(hours * 3600)}"
    )

@admin_only
async def whitelist_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add user to whitelist."""
    args = context.args
    if not args or not args[0].isdigit():
        await update.message.reply_text(
            "Usage: `/wladd <user_id>`\n"
            "Example: `/wladd 123456789`",
            parse_mode='Markdown'
        )
        return
    
    settings = get_settings(context)
    user_id = int(args[0])
    settings.add_to_whitelist(user_id)
    await update.message.reply_text(f"✅ User `{user_id}` added to whitelist.", parse_mode='Markdown')

@admin_only
async def whitelist_remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remove user from whitelist."""
    args = context.args
    if not args or not args[0].isdigit():
        await update.message.reply_text(
            "Usage: `/wlremove <user_id>`\n"
            "Example: `/wlremove 123456789`",
            parse_mode='Markdown'
        )
        return
    
    settings = get_settings(context)
    user_id = int(args[0])
    settings.remove_from_whitelist(user_id)
    await update.message.reply_text(f"✅ User `{user_id}` removed from whitelist.", parse_mode='Markdown')

@admin_only
async def show_config(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show current configuration."""
    settings = get_settings(context)
    config_text = settings.display()
    await update.message.reply_text(config_text, parse_mode='Markdown')

@admin_only
async def reload_config(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Reload configuration from .env file."""
    from config import Settings
    settings = get_settings(context)
    
    # Create new settings instance (reloads from .env)
    new_settings = Settings()
    
    # Update bot_data
    context.application.bot_data["settings"] = new_settings
    context.application.bot_data["config"] = new_settings
    
    await update.message.reply_text(
        "✅ Configuration reloaded from .env file.\n\n"
        f"{new_settings.display()}",
        parse_mode='Markdown'
    )