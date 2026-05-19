import asyncio
import json
import os
import shutil
import time
from typing import List, Dict, Optional
from pathlib import Path
from utils.logger import setup_logger

logger = setup_logger(__name__)

HOSTED_FILES_DIR = "data/hosted_files"
METADATA_FILE = os.path.join(HOSTED_FILES_DIR, "metadata.json")

class FileManager:
    """Manage hosted files and their metadata."""
    
    def __init__(self):
        self._ensure_directories()
    
    def _ensure_directories(self):
        """Create required directories."""
        os.makedirs(HOSTED_FILES_DIR, exist_ok=True)
    
    def load_metadata(self) -> List[Dict]:
        """Load hosted files metadata."""
        if not os.path.exists(METADATA_FILE):
            return []
        try:
            with open(METADATA_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []
    
    def save_metadata(self, metadata: List[Dict]):
        """Save hosted files metadata."""
        self._ensure_directories()
        with open(METADATA_FILE, "w") as f:
            json.dump(metadata, f, indent=2)
    
    def host_file(self, source_path: str, filename: str) -> str:
        """Move file to hosted directory."""
        self._ensure_directories()
        dest_path = os.path.join(HOSTED_FILES_DIR, filename)
        shutil.move(source_path, dest_path)
        return dest_path
    
    def add_file_record(self, filename: str, file_size: int):
        """Add file metadata record."""
        metadata = self.load_metadata()
        metadata.append({
            "filename": filename,
            "created_at": time.time(),
            "file_size": file_size
        })
        self.save_metadata(metadata)
    
    def get_file_path(self, filename: str) -> Optional[str]:
        """Get full path to hosted file."""
        file_path = os.path.join(HOSTED_FILES_DIR, filename)
        if os.path.isfile(file_path):
            return file_path
        return None
    
    def delete_file(self, filename: str) -> bool:
        """Delete a hosted file."""
        file_path = os.path.join(HOSTED_FILES_DIR, filename)
        if os.path.exists(file_path):
            os.remove(file_path)
            return True
        return False
    
    async def cleanup_expired(self, store_time_hours: int):
        """Delete expired files."""
        metadata = self.load_metadata()
        if not metadata:
            return
        
        store_seconds = store_time_hours * 3600
        now = time.time()
        new_metadata = []
        deleted_count = 0
        
        for entry in metadata:
            if now - entry["created_at"] > store_seconds:
                if self.delete_file(entry["filename"]):
                    deleted_count += 1
                    logger.info(f"Deleted expired: {entry['filename']}")
            else:
                new_metadata.append(entry)
        
        if deleted_count > 0:
            self.save_metadata(new_metadata)
            logger.info(f"Cleanup: removed {deleted_count} file(s)")
