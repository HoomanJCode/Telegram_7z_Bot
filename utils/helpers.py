import re
import os
from pathlib import Path
from typing import List, Optional

def extract_urls(text: str) -> List[str]:
    """Extract unique URLs from text."""
    urls = re.findall(r'https?://[^\s\n\r,;]+', text)
    # Clean up URLs (remove trailing punctuation)
    cleaned = []
    for url in urls:
        url = url.rstrip('.,;:!?)]}')
        if url not in cleaned:
            cleaned.append(url)
    return cleaned

def extract_urls_from_file(file_path: str) -> List[str]:
    """Extract URLs from a file."""
    urls = []
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            urls = extract_urls(content)
    except Exception:
        pass
    return urls

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
        return f"{seconds}s"
    elif seconds < 3600:
        return f"{seconds // 60}m"
    elif seconds < 86400:
        h = seconds // 3600
        m = (seconds % 3600) // 60
        return f"{h}h {m}m"
    else:
        d = seconds // 86400
        h = (seconds % 86400) // 3600
        if h == 0:
            return f"{d}d"
        return f"{d}d {h}h"

def mask_string(text: str, visible_chars: int = 2) -> str:
    """Mask a string showing only first and last characters."""
    if not text:
        return ""
    if len(text) <= visible_chars * 2:
        return "*" * len(text)
    return text[:visible_chars] + "*" * (len(text) - visible_chars * 2) + text[-visible_chars:]