from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes
from utils.logger import setup_logger

logger = setup_logger(__name__)

def restricted(func):
    """Decorator to enforce whitelist access control."""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        config = context.application.bot_data["config"]
        
        if config.is_whitelist_enabled:
            user_id = update.effective_user.id if update.effective_user else None
            if user_id and user_id not in config.whitelist:
                if update.callback_query:
                    await update.callback_query.answer("⛔ Access denied", show_alert=True)
                elif update.message:
                    await update.message.reply_text("⛔ Access denied. You are not authorized.")
                return
        
        return await func(update, context)
    return wrapper

def admin_only(func):
    """Decorator to restrict command to admins."""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        config = context.application.bot_data["config"]
        user_id = update.effective_user.id if update.effective_user else None
        
        if config.admin_ids and user_id not in config.admin_ids:
            await update.message.reply_text("⛔ Admin only command.")
            return
        
        return await func(update, context)
    return wrapper
