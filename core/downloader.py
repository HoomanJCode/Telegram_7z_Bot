import asyncio
import os
import re
from typing import List, Set
import aiohttp
from utils.logger import setup_logger
from utils.helpers import sanitize_filename

logger = setup_logger(__name__)

class Aria2Downloader:
    """Download files using aria2c."""
    
    @staticmethod
    async def download(urls: List[str], dest_dir: str) -> List[str]:
        """Download files using aria2c."""
        downloaded_files: Set[str] = set()
        
        for url in urls:
            try:
                cmd = [
                    "aria2c",
                    "--dir", dest_dir,
                    "--max-connection-per-server=16",
                    "--split=16",
                    "--min-split-size=1M",
                    "--continue=true",
                    "--timeout=600",
                    "--max-tries=5",
                    "--retry-wait=5",
                    "--console-log-level=error",
                    url
                ]
                
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                stdout, stderr = await process.communicate()
                
                if process.returncode == 0:
                    for file in os.listdir(dest_dir):
                        if file.endswith('.aria2'):
                            continue
                        file_path = os.path.join(dest_dir, file)
                        if os.path.isfile(file_path):
                            downloaded_files.add(file_path)
                else:
                    logger.error(f"aria2 failed: {stderr.decode()[:200]}")
                    
            except Exception as e:
                logger.error(f"aria2 download error: {e}")
        
        return list(downloaded_files)

class DirectDownloader:
    """Download files using aiohttp directly."""
    
    @staticmethod
    async def download(urls: List[str], dest_dir: str) -> List[str]:
        """Download files using direct HTTP requests."""
        downloaded: List[str] = []
        timeout = aiohttp.ClientTimeout(total=600)
        
        async with aiohttp.ClientSession(timeout=timeout) as session:
            for idx, url in enumerate(urls):
                try:
                    headers = {"User-Agent": "Mozilla/5.0"}
                    async with session.get(url, headers=headers) as resp:
                        resp.raise_for_status()
                        
                        cd = resp.headers.get("Content-Disposition")
                        fname = None
                        if cd and "filename=" in cd:
                            fname_match = re.findall(r'filename[^;=\n]*=((["\']).*?\2|[^;\n]*)', cd)
                            if fname_match:
                                fname = fname_match[0][0].strip('"\'')
                        
                        if not fname:
                            path = resp.url.path.rstrip("/")
                            fname = os.path.basename(path) or f"downloaded_{idx}"
                        
                        fname = sanitize_filename(fname)
                        filepath = os.path.join(dest_dir, fname)
                        
                        with open(filepath, "wb") as f:
                            async for chunk in resp.content.iter_chunked(8192):
                                f.write(chunk)
                        
                        downloaded.append(filepath)
                        logger.info(f"Downloaded: {fname}")
                        
                except Exception as e:
                    logger.error(f"Download failed: {e}")
        
        return downloaded

class DownloadManager:
    """Unified download interface."""
    
    def __init__(self, method: str = "aria2"):
        self.method = method
        self.downloader = Aria2Downloader() if method == "aria2" else DirectDownloader()
    
    async def download(self, urls: List[str], dest_dir: str) -> List[str]:
        """Download files using configured method."""
        return await self.downloader.download(urls, dest_dir)
    
    @staticmethod
    def check_availability() -> bool:
        """Check if aria2c is available."""
        import subprocess
        try:
            result = subprocess.run(
                ["aria2c", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False
