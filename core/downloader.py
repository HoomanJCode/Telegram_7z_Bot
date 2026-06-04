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
    
    def __init__(self, total_size: int = 0, callback: Optional[Callable] = None, show_detail: bool = True):
        self.total_size = total_size
        self.downloaded = 0
        self.last_percent = -1
        self.last_time = 0
        self.start_time = time.time()
        self.callback = callback
        self.show_detail = show_detail  # Show detailed progress for single files
    
    def update(self, chunk_size: int):
        """Update progress and call callback if significant change."""
        self.downloaded += chunk_size
        
        if self.total_size <= 0:
            return
        
        percent = int((self.downloaded / self.total_size) * 100)
        now = time.time()
        
        if percent >= self.last_percent + 10 or (now - self.last_time >= 3 and percent > self.last_percent):
            self.last_percent = percent
            self.last_time = now
            
            if self.callback:
                if self.show_detail:
                    # Single file: show detailed progress
                    status = (
                        f"📥 Downloading... {percent}%\n"
                        f"📏 {format_file_size(self.downloaded)} / {format_file_size(self.total_size)}"
                    )
                else:
                    # Multiple files: just show percentage
                    status = f"📥 Downloading... {percent}%"
                asyncio.create_task(self.callback(status))


class Aria2Downloader:
    """Download files using aria2c."""
    
    @staticmethod
    async def download(
        urls: List[str],
        dest_dir: str,
        progress_callback: Optional[Callable] = None
    ) -> List[str]:
        """Download files using aria2c."""
        downloaded_files: Set[str] = set()
        total_urls = len(urls)
        is_single = total_urls == 1
        
        for idx, url in enumerate(urls):
            try:
                if progress_callback:
                    if is_single:
                        await progress_callback("📥 Starting download...")
                    else:
                        await progress_callback(f"📥 Downloading {idx+1}/{total_urls}...")
                
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
                    stderr=asyncio.subprocess.STDOUT
                )
                
                last_percent = 0
                while True:
                    line = await process.stdout.readline()
                    if not line:
                        break
                    
                    line_text = line.decode().strip()
                    
                    if progress_callback and '(' in line_text and '%)' in line_text:
                        try:
                            percent_match = re.search(r'\((\d+)%\)', line_text)
                            if percent_match:
                                percent = int(percent_match.group(1))
                                
                                if percent >= last_percent + 5:
                                    last_percent = percent
                                    
                                    if is_single:
                                        # Single file: show size progress
                                        size_match = re.search(r'(\d+\w+)/(\d+\w+)', line_text)
                                        if size_match:
                                            downloaded = size_match.group(1)
                                            total = size_match.group(2)
                                            await progress_callback(
                                                f"📥 Downloading... {percent}%\n"
                                                f"📏 {downloaded} / {total}"
                                            )
                                        else:
                                            await progress_callback(f"📥 Downloading... {percent}%")
                                    else:
                                        # Multiple files: show file count
                                        await progress_callback(
                                            f"📥 {idx+1}/{total_urls} - {percent}%"
                                        )
                        except Exception:
                            pass
                
                await process.wait()
                
                if process.returncode == 0:
                    if progress_callback:
                        if is_single:
                            await progress_callback("✅ Download complete")
                        else:
                            await progress_callback(f"✅ Completed {idx+1}/{total_urls}")
                    
                    for file in os.listdir(dest_dir):
                        if file.endswith('.aria2'):
                            continue
                        file_path = os.path.join(dest_dir, file)
                        if os.path.isfile(file_path) and file_path not in downloaded_files:
                            downloaded_files.add(file_path)
                else:
                    if progress_callback:
                        await progress_callback(f"❌ Failed {idx+1}/{total_urls}")
                    
            except Exception as e:
                logger.error(f"Download error: {e}")
                if progress_callback:
                    await progress_callback(f"❌ Error {idx+1}/{total_urls}")
        
        return list(downloaded_files)


class DirectDownloader:
    """Download files using aiohttp directly with progress tracking."""
    
    @staticmethod
    async def download(
        urls: List[str],
        dest_dir: str,
        progress_callback: Optional[Callable] = None
    ) -> List[str]:
        """Download files using direct HTTP requests with progress."""
        downloaded: List[str] = []
        timeout = aiohttp.ClientTimeout(total=600)
        total_urls = len(urls)
        is_single = total_urls == 1
        
        async with aiohttp.ClientSession(timeout=timeout) as session:
            for idx, url in enumerate(urls):
                try:
                    if progress_callback:
                        if is_single:
                            await progress_callback("📥 Starting download...")
                        else:
                            await progress_callback(f"📥 Downloading {idx+1}/{total_urls}...")
                    
                    headers = {"User-Agent": "Mozilla/5.0"}
                    async with session.get(url, headers=headers) as resp:
                        resp.raise_for_status()
                        
                        cd = resp.headers.get("Content-Disposition")
                        fname = None
                        if cd and "filename=" in cd:
                            fname_match = re.findall(
                                r'filename[^;=\n]*=((["\']).*?\2|[^;\n]*)',
                                cd
                            )
                            if fname_match:
                                fname = fname_match[0][0].strip('"\'')
                        
                        if not fname:
                            path = resp.url.path.rstrip("/")
                            fname = os.path.basename(path) or f"downloaded_{idx}"
                        
                        fname = sanitize_filename(fname)
                        filepath = os.path.join(dest_dir, fname)
                        
                        total_size = int(resp.headers.get('Content-Length', 0))
                        # Show detail only for single files
                        tracker = ProgressTracker(total_size, callback=progress_callback, show_detail=is_single)
                        
                        with open(filepath, "wb") as f:
                            async for chunk in resp.content.iter_chunked(8192):
                                f.write(chunk)
                                tracker.update(len(chunk))
                        
                        downloaded.append(filepath)
                        
                        if progress_callback:
                            if is_single:
                                file_size = os.path.getsize(filepath)
                                await progress_callback(f"✅ Download complete\n📏 {format_file_size(file_size)}")
                            else:
                                await progress_callback(f"✅ Completed {idx+1}/{total_urls}")
                        
                except Exception as e:
                    logger.error(f"Download failed: {e}")
                    if progress_callback:
                        await progress_callback(f"❌ Failed {idx+1}/{total_urls}")
        
        return downloaded


class DownloadManager:
    """Unified download interface with progress support."""
    
    def __init__(self, method: str = "aria2"):
        self.method = method
        self.downloader = Aria2Downloader() if method == "aria2" else DirectDownloader()
    
    async def download(
        self,
        urls: List[str],
        dest_dir: str,
        progress_callback: Optional[Callable] = None
    ) -> List[str]:
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