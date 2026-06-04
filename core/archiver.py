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
        cmd = ["7z", "a", "-t7z", "-mx=1", "-bsp1", output_path]
        
        if password:
            cmd.extend([f"-p{password}", "-mhe=on"])
        
        cmd.extend(files)
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT  # Merge stderr to stdout
        )
        
        # Read output line by line - single reader
        last_progress = 0
        while True:
            line = await process.stdout.readline()
            if not line:
                break
            
            line_text = line.decode().strip()
            
            if progress_callback and line_text:
                # Parse 7z progress (look for percentage)
                if '%' in line_text:
                    try:
                        # Extract percentage
                        percent_str = line_text.split('%')[0].strip()
                        percent = int(percent_str) if percent_str.isdigit() else 0
                        
                        # Only update on significant changes
                        if percent >= last_progress + 5:
                            last_progress = percent
                            await progress_callback(f"📦 Compressing: {percent}%")
                    except ValueError:
                        pass
        
        await process.wait()
        
        if process.returncode != 0:
            raise RuntimeError("7z compression failed")
        
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
        cmd = ["7z", "a", "-t7z", "-mx=0", f"-v{max_volume_mb}m", "-bsp1", output_base]
        
        if password:
            cmd.extend([f"-p{password}", "-mhe=on"])
        
        cmd.extend(files)
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT  # Merge to single stream
        )
        
        # Single reader - no race condition
        last_progress = 0
        while True:
            line = await process.stdout.readline()
            if not line:
                break
            
            line_text = line.decode().strip()
            
            if progress_callback and line_text and '%' in line_text:
                try:
                    percent_str = line_text.split('%')[0].strip()
                    percent = int(percent_str) if percent_str.isdigit() else 0
                    
                    if percent >= last_progress + 5:
                        last_progress = percent
                        await progress_callback(f"📦 Splitting: {percent}%")
                except ValueError:
                    pass
        
        await process.wait()
        
        if process.returncode != 0:
            raise RuntimeError("7z split failed")
        
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