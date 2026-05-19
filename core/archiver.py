import asyncio
import os
from pathlib import Path
from typing import List
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
    async def create_archive(files: List[str], output_path: str, password: str = "") -> str:
        """Create a single 7z archive."""
        cmd = ["7z", "a", "-t7z", "-mx=1", output_path]
        
        if password:
            cmd.extend([f"-p{password}", "-mhe=on"])
        
        cmd.extend(files)
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            raise RuntimeError(f"7z failed: {stderr.decode().strip()[:200]}")
        
        return output_path
    
    @staticmethod
    async def create_split_archive(
        files: List[str],
        output_base: str,
        password: str = "",
        max_volume_mb: int = 49
    ) -> List[Path]:
        """Create a split 7z archive."""
        cmd = ["7z", "a", "-t7z", "-mx=0", f"-v{max_volume_mb}m"]
        
        if password:
            cmd.extend([f"-p{password}", "-mhe=on"])
        
        cmd.append(output_base)
        cmd.extend(files)
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            raise RuntimeError(f"7z split failed: {stderr.decode().strip()[:200]}")
        
        output_dir = os.path.dirname(output_base)
        base_name = os.path.basename(output_base)
        
        volumes = sorted(
            [p for p in Path(output_dir).glob(base_name + "*") 
             if not p.name.endswith('.tmp')],
            key=lambda p: p.name
        )
        
        return volumes