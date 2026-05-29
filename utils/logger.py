import logging
import sys
from pathlib import Path

def setup_logger(name: str = "filebot", log_file: str = "bot.log") -> logging.Logger:
    """Configure and return a logger instance."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)
    
    # File handler - try multiple locations
    log_paths = [
        Path("data") / log_file,
        Path("/var/log/telegram7zbot") / log_file,
        Path("/tmp") / log_file,
    ]
    
    for log_path in log_paths:
        try:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(log_path)
            file_format = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            file_handler.setFormatter(file_format)
            logger.addHandler(file_handler)
            print(f"📝 Logging to: {log_path}")
            break
        except (OSError, PermissionError):
            continue
    
    return logger