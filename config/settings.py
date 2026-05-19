import json
import os
from pathlib import Path
from typing import Dict, List, Any

CONFIG_FILE = "config.json"
DEFAULT_CONFIG_PATH = Path(__file__).parent / "default_config.json"

class Config:
    """Bot configuration manager."""
    
    def __init__(self, config_path: str = CONFIG_FILE):
        self.config_path = config_path
        self._config = self._load_config()
    
    def _load_defaults(self) -> dict:
        """Load default configuration."""
        if DEFAULT_CONFIG_PATH.exists():
            with open(DEFAULT_CONFIG_PATH, "r") as f:
                return json.load(f)
        return {
            "token": "",
            "api_base_url": "",
            "api_base_file_url": "",
            "host_base_url": "",
            "host_port": 8080,
            "store_time_hours": 48,
            "max_telegram_size_mb": 50,
            "whitelist": [],
            "admin_ids": [],
            "download_method": "aria2",
            "aria2_rpc_url": "http://localhost:6800/jsonrpc",
            "aria2_secret": "",
        }
    
    def _load_config(self) -> dict:
        """Load configuration from file or create default."""
        if not os.path.exists(self.config_path):
            return self._create_config()
        
        with open(self.config_path, "r") as f:
            config = json.load(f)
        
        # Migrate old config
        if "store_time_days" in config and "store_time_hours" not in config:
            config["store_time_hours"] = config["store_time_days"] * 24
            del config["store_time_days"]
            self._save_config(config)
        
        # Ensure all defaults exist
        defaults = self._load_defaults()
        for key, value in defaults.items():
            config.setdefault(key, value)
        
        return config
    
    def _create_config(self) -> dict:
        """Create initial configuration interactively."""
        print("🔧 Configuration file not found. Creating a new one.\n")
        
        config = self._load_defaults()
        
        config["token"] = input("Bot Token: ").strip()
        
        api_base = input("API Base URL (Enter for default): ").strip()
        if api_base:
            config["api_base_url"] = api_base
            if "/bot" in api_base:
                config["api_base_file_url"] = api_base.replace("/bot", "/file")
            else:
                config["api_base_file_url"] = api_base + "/file"
        
        dl_method = input("Download method (aria2/direct) [aria2]: ").strip().lower()
        if dl_method == "direct":
            config["download_method"] = "direct"
        
        self._save_config(config)
        print(f"\n✅ Configuration saved to {self.config_path}")
        return config
    
    def _save_config(self, config: dict = None):
        """Save configuration to file."""
        if config is None:
            config = self._config
        with open(self.config_path, "w") as f:
            json.dump(config, f, indent=2)
    
    @property
    def token(self) -> str:
        return self._config.get("token", "")
    
    @property
    def api_base_url(self) -> str:
        return self._config.get("api_base_url", "")
    
    @property
    def api_base_file_url(self) -> str:
        return self._config.get("api_base_file_url", "")
    
    @property
    def host_base_url(self) -> str:
        return self._config.get("host_base_url", "")
    
    @host_base_url.setter
    def host_base_url(self, value: str):
        self._config["host_base_url"] = value
        self._save_config()
    
    @property
    def host_port(self) -> int:
        return self._config.get("host_port", 8080)
    
    @property
    def store_time_hours(self) -> int:
        return self._config.get("store_time_hours", 48)
    
    @store_time_hours.setter
    def store_time_hours(self, value: int):
        self._config["store_time_hours"] = value
        self._save_config()
    
    @property
    def max_telegram_size_mb(self) -> int:
        return self._config.get("max_telegram_size_mb", 50)
    
    @property
    def whitelist(self) -> List[int]:
        return self._config.get("whitelist", [])
    
    @property
    def admin_ids(self) -> List[int]:
        return self._config.get("admin_ids", [])
    
    @property
    def download_method(self) -> str:
        return self._config.get("download_method", "aria2")
    
    @property
    def is_whitelist_enabled(self) -> bool:
        return len(self.whitelist) > 0
    
    @property
    def is_host_enabled(self) -> bool:
        return bool(self.host_base_url)
    
    def add_to_whitelist(self, user_id: int):
        """Add user to whitelist."""
        if user_id not in self._config["whitelist"]:
            self._config["whitelist"].append(user_id)
            self._save_config()
    
    def remove_from_whitelist(self, user_id: int):
        """Remove user from whitelist."""
        if user_id in self._config["whitelist"]:
            self._config["whitelist"].remove(user_id)
            self._save_config()
    
    def to_dict(self) -> dict:
        return self._config.copy()

def create_default_config(config_path: str = CONFIG_FILE) -> Config:
    """Create and return a Config instance."""
    return Config(config_path)
