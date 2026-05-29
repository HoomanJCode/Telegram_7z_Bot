from .commands import (
    start, help_cmd, set_password, my_password, bot_status,
    recent_files, set_host_url, set_store_time, whitelist_add, whitelist_remove
)
from .messages import handle_document, handle_text
from .callbacks import handle_callback