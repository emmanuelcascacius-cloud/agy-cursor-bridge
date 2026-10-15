import asyncio
import logging
import os
import re
import shutil
import tempfile
import urllib.request
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger("tunnel")

class TunnelManager:
    def __init__(self, local_port: int):
        self.local_port = local_port
        self.process: Optional[asyncio.subprocess.Process] = None
        self.public_url: Optional[str] = None

    @staticmethod
    def _find_or_download_cloudflared() -> Optional[str]:
        # 1. Check PATH
        path_bin = shutil.which("cloudflared")
        if path_bin:
            return path_bin

        # 2. Check cached binary in ~/.gemini/antigravity-cli/bin/cloudflared or ~/.local/bin/cloudflared
        user_bins = [
            Path.home() / ".local/bin/cloudflared",
            Path.home() / ".gemini/antigravity-cli/bin/cloudflared",
            Path("/tmp/cloudflared"),
        ]
        for candidate in user_bins:
            if candidate.exists() and os.access(candidate, os.X_OK):
                return str(candidate)

        # 3. Attempt download if on Linux x86_64
        import platform
        machine = platform.machine().lower()
        system = platform.system().lower()
        if system == "linux" and ("x86_64" in machine or "amd64" in machine):
            target_path = Path.home() / ".local/bin/cloudflared"
            target_path.parent.mkdir(parents=True, exist_ok=True)
            url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64"
            try:
                logger.info(f"Downloading cloudflared for Linux x86_64 to {target_path}...")
                urllib.request.urlretrieve(url, str(target_path))
                target_path.chmod(0o755)
                return str(target_path)
            except Exception as e:
                logger.warning(f"Could not download cloudflared: {e}")

        return None

    async def start(self) -> Tuple[bool, Optional[str]]:
        cloudflared_bin = self._find_or_download_cloudflared()
        if not cloudflared_bin:
            return False, "cloudflared binary not found and automatic download failed."

        cmd = [
            cloudflared_bin,
            "tunnel",
            "--url",
            f"http://127.0.0.1:{self.local_port}",
            "--no-autoupdate",
        ]

        logger.info(f"Starting cloudflared tunnel to port {self.local_port}...")
        self.process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        # cloudflared logs the tunnel URL to stderr
        pattern = re.compile(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com")
        start_time = asyncio.get_event_loop().time()

        while asyncio.get_event_loop().time() - start_time < 15.0:
            if self.process.stderr is None:
                break
            line_bytes = await self.process.stderr.readline()
            if not line_bytes:
                break
            line = line_bytes.decode("utf-8", errors="replace")
            match = pattern.search(line)
            if match:
                self.public_url = match.group(0)
                logger.info(f"Cloudflare tunnel established: {self.public_url}")
                return True, self.public_url

        return False, "Timed out waiting for trycloudflare.com URL"

    async def stop(self):
        if self.process:
            logger.info("Stopping Cloudflare tunnel...")
            try:
                self.process.terminate()
                await asyncio.wait_for(self.process.wait(), timeout=3.0)
            except Exception:
                self.process.kill()
            self.process = None
            self.public_url = None
