import os
from typing import List, Optional
from urllib.parse import urlparse
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

class Settings:
    """Bot configuration from environment variables."""
    
    def __init__(self):
        self._load_settings()
    
    def _get_int(self, key: str, default: int) -> int:
        """Get integer from env, handling empty strings."""
        value = os.getenv(key, "")
        if value is None or value.strip() == "":
            return default
        try:
            return int(value.strip())
        except ValueError:
            return default
    
    def _get_str(self, key: str, default: str = "") -> str:
        """Get string from env, handling None."""
        value = os.getenv(key)
        if value is None or value.strip() == "":
            return default
        return value.strip()
    
    def _load_settings(self):
        """Load all settings from environment variables."""
        # Bot Token (Required)
        self.token = self._get_str("BOT_TOKEN")
        
        # API Configuration
        self.api_base_url = self._get_str("API_BASE_URL")
        self.api_base_file_url = self._get_str("API_BASE_FILE_URL")
        
        # Host Configuration
        self.host_base_url = self._get_str("HOST_BASE_URL")
        self.host_port = self._get_int("HOST_PORT", 8080)
        # Auto-detect the port when HOST_BASE_URL specifies one explicitly
        detected_port = self._extract_port(self.host_base_url)
        if detected_port is not None:
            self.host_port = detected_port
        
        # File Storage
        self.store_time_hours = self._get_int("STORE_TIME_HOURS", 48)
        self.max_telegram_size_mb = self._get_int("MAX_TELEGRAM_SIZE_MB", 50)
        
        # Download Method
        self.download_method = self._get_str("DOWNLOAD_METHOD", "aria2")
        self.aria2_rpc_url = self._get_str("ARIA2_RPC_URL", "http://localhost:6800/jsonrpc")
        self.aria2_secret = self._get_str("ARIA2_SECRET")
        
        # Access Control
        self.whitelist = self._parse_list(self._get_str("WHITELIST"))
        self.admin_ids = self._parse_list(self._get_str("ADMIN_IDS"))
    
    def _parse_list(self, value: str) -> List[int]:
        """Parse comma-separated string to list of integers."""
        if not value or not value.strip():
            return []
        try:
            return [int(x.strip()) for x in value.split(",") if x.strip()]
        except ValueError:
            return []
    
    @property
    def is_whitelist_enabled(self) -> bool:
        return len(self.whitelist) > 0
    
    @property
    def is_host_enabled(self) -> bool:
        return bool(self.host_base_url)
    
    @staticmethod
    def _extract_port(url: str) -> Optional[int]:
        """Return the explicit port in a URL, or None if absent/invalid."""
        if not url:
            return None
        if "://" not in url:
            url = f"http://{url}"
        try:
            return urlparse(url).port
        except ValueError:
            return None
    
    def update_host_url(self, url: str) -> Optional[int]:
        self._update_env_file("HOST_BASE_URL", url)
        self.host_base_url = url
        # Keep the web server port in sync when the URL specifies one explicitly
        detected_port = self._extract_port(url)
        if detected_port is not None:
            self.host_port = detected_port
            self._update_env_file("HOST_PORT", str(detected_port))
        return detected_port
    
    def update_store_time(self, hours: int):
        self._update_env_file("STORE_TIME_HOURS", str(hours))
        self.store_time_hours = hours
    
    def add_to_whitelist(self, user_id: int):
        if user_id not in self.whitelist:
            self.whitelist.append(user_id)
            self._update_env_file("WHITELIST", ",".join(map(str, self.whitelist)))
    
    def remove_from_whitelist(self, user_id: int):
        if user_id in self.whitelist:
            self.whitelist.remove(user_id)
            self._update_env_file("WHITELIST", ",".join(map(str, self.whitelist)))
    
    def _update_env_file(self, key: str, value: str):
        env_path = Path(".env")
        if not env_path.exists():
            with open(env_path, "w") as f:
                f.write(f"{key}={value}\n")
            return
        
        with open(env_path, "r") as f:
            lines = f.readlines()
        
        found = False
        for i, line in enumerate(lines):
            if line.startswith(f"{key}="):
                lines[i] = f"{key}={value}\n"
                found = True
                break
        
        if not found:
            lines.append(f"{key}={value}\n")
        
        with open(env_path, "w") as f:
            f.writelines(lines)
    
    def validate(self) -> List[str]:
        errors = []
        if not self.token:
            errors.append("BOT_TOKEN is required in .env file")
        return errors
    
    def display(self) -> str:
        lines = [
            "📋 Configuration:",
            f"  Token: {'✅ Set' if self.token else '❌ MISSING'}",
            f"  API: {self.api_base_url or 'Default'}",
            f"  Host: {self.host_base_url or 'Disabled'}",
            f"  Port: {self.host_port}",
            f"  Storage: {self.store_time_hours}h",
            f"  Max Size: {self.max_telegram_size_mb}MB",
            f"  Download: {self.download_method}",
            f"  Whitelist: {'On' if self.is_whitelist_enabled else 'Off'}",
        ]
        return "\n".join(lines)