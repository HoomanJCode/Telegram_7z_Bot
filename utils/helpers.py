import re
import os
from pathlib import Path
from typing import List, Optional

def extract_urls(text: str) -> List[str]:
    """Extract unique URLs from text."""
    urls = re.findall(r'https?://\S+', text)
    return list(set(urls))

def sanitize_filename(filename: str) -> str:
    """Remove invalid characters from filename."""
    return re.sub(r'[\\/*?:"<>|]', "_", filename)

def extract_filename_from_url(url: str, default: str = "downloaded") -> str:
    """Extract filename from URL path."""
    path = url.rstrip("/")
    filename = os.path.basename(path) or default
    return sanitize_filename(filename)

def format_file_size(size_bytes: int) -> str:
    """Format file size in human readable format."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.2f} PB"

def format_time(seconds: int) -> str:
    """Format time duration in human readable format."""
    if seconds < 60:
        return f"{seconds} seconds"
    elif seconds < 3600:
        return f"{seconds // 60} minutes"
    elif seconds < 86400:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours}h {minutes}m"
    else:
        days = seconds // 86400
        hours = (seconds % 86400) // 3600
        if hours == 0:
            return f"{days} day(s)"
        return f"{days} day(s) {hours}h"

def mask_string(text: str, visible_chars: int = 2) -> str:
    """Mask a string showing only first and last characters."""
    if not text:
        return ""
    if len(text) <= visible_chars * 2:
        return "*" * len(text)
    return text[:visible_chars] + "*" * (len(text) - visible_chars * 2) + text[-visible_chars:]
