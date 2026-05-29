import os
from typing import List
from dotenv import load_dotenv
from pathlib import Path

# Load .env file
load_dotenv()

class Settings:
    """Bot configuration from environment variables."""
    
    def __init__(self):
        self._load_settings()
    
    def _load_settings(self):
        """Load all settings from environment variables."""
        # Bot Token (Required)
        self.token = os.getenv("BOT_TOKEN", "")
        
        # API Configuration
        self.api_base_url = os.getenv("API_BASE_URL", "")
        self.api_base_file_url = os.getenv("API_BASE_FILE_URL", "")
        
        # Host Configuration
        self.host_base_url = os.getenv("HOST_BASE_URL", "")
        self.host_port = int(os.getenv("HOST_PORT", "8080"))
        
        # File Storage
        self.store_time_hours = int(os.getenv("STORE_TIME_HOURS", "48"))
        self.max_telegram_size_mb = int(os.getenv("MAX_TELEGRAM_SIZE_MB", "50"))
        
        # Download Method
        self.download_method = os.getenv("DOWNLOAD_METHOD", "aria2")
        self.aria2_rpc_url = os.getenv("ARIA2_RPC_URL", "http://localhost:6800/jsonrpc")
        self.aria2_secret = os.getenv("ARIA2_SECRET", "")
        
        # Access Control
        self.whitelist = self._parse_list(os.getenv("WHITELIST", ""))
        self.admin_ids = self._parse_list(os.getenv("ADMIN_IDS", ""))
    
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
        """Check if whitelist is enabled."""
        return len(self.whitelist) > 0
    
    @property
    def is_host_enabled(self) -> bool:
        """Check if hosting is enabled."""
        return bool(self.host_base_url)
    
    def update_host_url(self, url: str):
        """Update host base URL in .env file."""
        self._update_env_file("HOST_BASE_URL", url)
        self.host_base_url = url
    
    def update_store_time(self, hours: int):
        """Update store time in .env file."""
        self._update_env_file("STORE_TIME_HOURS", str(hours))
        self.store_time_hours = hours
    
    def add_to_whitelist(self, user_id: int):
        """Add user to whitelist."""
        if user_id not in self.whitelist:
            self.whitelist.append(user_id)
            self._update_env_file("WHITELIST", ",".join(map(str, self.whitelist)))
    
    def remove_from_whitelist(self, user_id: int):
        """Remove user from whitelist."""
        if user_id in self.whitelist:
            self.whitelist.remove(user_id)
            self._update_env_file("WHITELIST", ",".join(map(str, self.whitelist)))
    
    def _update_env_file(self, key: str, value: str):
        """Update a single value in .env file."""
        env_path = Path(".env")
        
        if not env_path.exists():
            # Create new .env file
            with open(env_path, "w") as f:
                f.write(f"{key}={value}\n")
            return
        
        # Read existing lines
        with open(env_path, "r") as f:
            lines = f.readlines()
        
        # Update or append key
        found = False
        for i, line in enumerate(lines):
            if line.startswith(f"{key}=") or line.startswith(f"# {key}="):
                lines[i] = f"{key}={value}\n"
                found = True
                break
        
        if not found:
            lines.append(f"{key}={value}\n")
        
        # Write back
        with open(env_path, "w") as f:
            f.writelines(lines)
    
    def validate(self) -> List[str]:
        """Validate required settings."""
        errors = []
        
        if not self.token:
            errors.append("BOT_TOKEN is required in .env file")
        
        if self.store_time_hours < 1:
            errors.append("STORE_TIME_HOURS must be at least 1")
        
        if self.max_telegram_size_mb < 1 or self.max_telegram_size_mb > 50:
            errors.append("MAX_TELEGRAM_SIZE_MB must be between 1 and 50")
        
        if self.download_method not in ["aria2", "direct"]:
            errors.append("DOWNLOAD_METHOD must be 'aria2' or 'direct'")
        
        return errors
    
    def display(self) -> str:
        """Get display string for settings (without sensitive data)."""
        from utils.helpers import mask_string
        
        lines = [
            "📋 **Current Configuration**\n",
            f"• Token: `{mask_string(self.token, 4)}`",
            f"• API Base: `{self.api_base_url or 'Default'}`",
            f"• Host: `{self.host_base_url or 'Disabled'}`",
            f"• Port: `{self.host_port}`",
            f"• Storage: `{self.store_time_hours} hours`",
            f"• Max File: `{self.max_telegram_size_mb} MB`",
            f"• Download: `{self.download_method}`",
            f"• Whitelist: `{'On' if self.is_whitelist_enabled else 'Off'}`",
        ]
        
        return "\n".join(lines)