import asyncio
import os
import re
import time
from typing import List, Set, Optional, Callable
import aiohttp
from utils.logger import setup_logger
from utils.helpers import sanitize_filename, format_file_size

logger = setup_logger(__name__)

class ProgressTracker:
    """Track download progress and report changes."""
    
    def __init__(self, total_size: int = 0, callback: Optional[Callable] = None):
        self.total_size = total_size
        self.downloaded = 0
        self.last_percent = -1
        self.last_time = 0
        self.start_time = time.time()
        self.callback = callback
    
    def update(self, chunk_size: int):
        """Update progress and call callback if significant change."""
        self.downloaded += chunk_size
        
        if self.total_size <= 0:
            return
        
        percent = int((self.downloaded / self.total_size) * 100)
        now = time.time()
        
        # Report every 10% change OR every 5 seconds
        if percent >= self.last_percent + 10 or (now - self.last_time >= 5 and percent > self.last_percent):
            self.last_percent = percent
            self.last_time = now
            
            if self.callback:
                elapsed = now - self.start_time
                speed = self.downloaded / elapsed if elapsed > 0 else 0
                eta = (self.total_size - self.downloaded) / speed if speed > 0 else 0
                
                status = (
                    f"📥 Downloading... {percent}%\n"
                    f"📏 {format_file_size(self.downloaded)} / {format_file_size(self.total_size)}\n"
                    f"⚡ {format_file_size(int(speed))}/s\n"
                    f"⏰ ETA: {int(eta)}s"
                )
                asyncio.create_task(self.callback(status))

class Aria2Downloader:
    """Download files using aria2c."""
    
    @staticmethod
    async def download(urls: List[str], dest_dir: str, progress_callback: Optional[Callable] = None) -> List[str]:
        """Download files using aria2c with progress."""
        downloaded_files: Set[str] = set()
        
        for idx, url in enumerate(urls):
            try:
                if progress_callback:
                    await progress_callback(f"📥 Downloading {idx+1}/{len(urls)} with aria2...")
                
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
                    "--summary-interval=0",
                    url
                ]
                
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                # Read aria2 progress from stderr
                async def read_progress():
                    while True:
                        line = await process.stderr.readline()
                        if not line:
                            break
                        line = line.decode().strip()
                        if '%' in line and progress_callback:
                            # Parse aria2 progress line
                            await progress_callback(f"📥 {line[:100]}")
                
                progress_task = asyncio.create_task(read_progress())
                await process.wait()
                progress_task.cancel()
                
                if process.returncode == 0:
                    for file in os.listdir(dest_dir):
                        if file.endswith('.aria2'):
                            continue
                        file_path = os.path.join(dest_dir, file)
                        if os.path.isfile(file_path):
                            downloaded_files.add(file_path)
                            
            except Exception as e:
                logger.error(f"aria2 download error: {e}")
        
        return list(downloaded_files)

class DirectDownloader:
    """Download files using aiohttp directly with progress tracking."""
    
    @staticmethod
    async def download(urls: List[str], dest_dir: str, progress_callback: Optional[Callable] = None) -> List[str]:
        """Download files using direct HTTP requests with progress."""
        downloaded: List[str] = []
        timeout = aiohttp.ClientTimeout(total=600)
        
        async with aiohttp.ClientSession(timeout=timeout) as session:
            for idx, url in enumerate(urls):
                try:
                    headers = {"User-Agent": "Mozilla/5.0"}
                    async with session.get(url, headers=headers) as resp:
                        resp.raise_for_status()
                        
                        # Get filename
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
                        
                        total_size = int(resp.headers.get('Content-Length', 0))
                        tracker = ProgressTracker(
                            total_size,
                            callback=progress_callback
                        )
                        
                        with open(filepath, "wb") as f:
                            async for chunk in resp.content.iter_chunked(8192):
                                f.write(chunk)
                                tracker.update(len(chunk))
                        
                        downloaded.append(filepath)
                        
                        if progress_callback:
                            await progress_callback(f"✅ Downloaded: {fname}")
                        
                except Exception as e:
                    logger.error(f"Download failed: {e}")
                    if progress_callback:
                        await progress_callback(f"❌ Failed: {url[:50]}...")
        
        return downloaded

class DownloadManager:
    """Unified download interface with progress support."""
    
    def __init__(self, method: str = "aria2"):
        self.method = method
        self.downloader = Aria2Downloader() if method == "aria2" else DirectDownloader()
    
    async def download(self, urls: List[str], dest_dir: str, progress_callback: Optional[Callable] = None) -> List[str]:
        """Download files with progress reporting."""
        return await self.downloader.download(urls, dest_dir, progress_callback)
    
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