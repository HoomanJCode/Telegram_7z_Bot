import asyncio
import os
from pathlib import Path
from typing import List, Optional, Callable
from utils.logger import setup_logger

logger = setup_logger(__name__)


class SevenZipArchiver:
    """Handle 7z archive operations."""
    
    @staticmethod
    async def check_availability() -> bool:
        """Check if 7z is available."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "7z",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await proc.communicate()
            return True
        except FileNotFoundError:
            return False
    
    @staticmethod
    async def create_archive(
        files: List[str],
        output_path: str,
        password: str = "",
        progress_callback: Optional[Callable] = None
    ) -> str:
        """Create a single 7z archive with progress."""
        cmd = ["7z", "a", "-t7z", "-mx=1", output_path]
        
        if password:
            cmd.extend([f"-p{password}", "-mhe=on"])
        
        cmd.extend(files)
        
        # Calculate total input size for progress
        total_size = sum(os.path.getsize(f) for f in files if os.path.exists(f))
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        # Monitor progress from stdout
        async def monitor_progress():
            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                line_text = line.decode().strip()
                
                if progress_callback and line_text:
                    # Parse 7z progress (shows percentage)
                    if '%' in line_text:
                        # Clean up 7z output
                        clean_msg = line_text.strip()
                        if clean_msg and not clean_msg.startswith('7z'):
                            await progress_callback(f"📦 Compressing: {clean_msg[:80]}")
        
        monitor_task = asyncio.create_task(monitor_progress())
        stdout, stderr = await process.communicate()
        monitor_task.cancel()
        
        try:
            await monitor_task
        except asyncio.CancelledError:
            pass
        
        if process.returncode != 0:
            error_msg = stderr.decode().strip() if stderr else "Unknown error"
            raise RuntimeError(f"7z failed: {error_msg[:200]}")
        
        if progress_callback:
            output_size = os.path.getsize(output_path)
            await progress_callback(f"📦 Compressed: {_format_size(output_size)}")
        
        return output_path
    
    @staticmethod
    async def create_split_archive(
        files: List[str],
        output_base: str,
        password: str = "",
        max_volume_mb: int = 49,
        progress_callback: Optional[Callable] = None
    ) -> List[Path]:
        """Create a split 7z archive with progress."""
        cmd = ["7z", "a", "-t7z", "-mx=0", f"-v{max_volume_mb}m"]
        
        if password:
            cmd.extend([f"-p{password}", "-mhe=on"])
        
        cmd.append(output_base)
        cmd.extend(files)
        
        # Calculate total input size
        total_size = sum(os.path.getsize(f) for f in files if os.path.exists(f))
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        # Monitor progress
        async def monitor_progress():
            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                line_text = line.decode().strip()
                
                if progress_callback and line_text and '%' in line_text:
                    clean_msg = line_text.strip()
                    if clean_msg and not clean_msg.startswith('7z'):
                        await progress_callback(f"📦 Splitting: {clean_msg[:80]}")
        
        monitor_task = asyncio.create_task(monitor_progress())
        stdout, stderr = await process.communicate()
        monitor_task.cancel()
        
        try:
            await monitor_task
        except asyncio.CancelledError:
            pass
        
        if process.returncode != 0:
            error_msg = stderr.decode().strip() if stderr else "Unknown error"
            raise RuntimeError(f"7z split failed: {error_msg[:200]}")
        
        # Find all volumes
        output_dir = os.path.dirname(output_base)
        base_name = os.path.basename(output_base)
        volumes = sorted(
            [p for p in Path(output_dir).glob(base_name + "*") 
             if not p.name.endswith('.tmp')],
            key=lambda p: p.name
        )
        
        if progress_callback:
            total_output = sum(os.path.getsize(v) for v in volumes)
            await progress_callback(f"📦 Split into {len(volumes)} parts ({_format_size(total_output)})")
        
        return volumes


def _format_size(size_bytes: int) -> str:
    """Format file size for display."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"