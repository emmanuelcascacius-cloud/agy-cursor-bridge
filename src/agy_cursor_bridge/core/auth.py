import asyncio
import os
import shutil
from pathlib import Path
from typing import Dict, Any, Tuple
from agy_cursor_bridge.config import settings

class AuthManager:
    @staticmethod
    def get_token_path() -> Path:
        return settings.token_path

    @staticmethod
    def is_token_present() -> bool:
        token_file = AuthManager.get_token_path()
        return token_file.exists() and token_file.stat().st_size > 0

    @staticmethod
    def find_agy_binary() -> str:
        # Check explicit setting
        if settings.agy_binary and os.path.exists(settings.agy_binary) and os.access(settings.agy_binary, os.X_OK):
            return settings.agy_binary
        
        # Check PATH
        path_binary = shutil.which("agy")
        if path_binary:
            return path_binary
            
        # Common locations
        candidates = [
            Path.home() / ".local/bin/agy",
            Path("/usr/local/bin/agy"),
            Path("/usr/bin/agy"),
        ]
        for c in candidates:
            if c.exists() and os.access(c, os.X_OK):
                return str(c)
                
        raise FileNotFoundError("Could not find 'agy' binary. Please ensure agy CLI is installed in PATH or ~/.local/bin/agy")

    @staticmethod
    async def verify_auth() -> Tuple[bool, str]:
        """Runs a quick check against agy to verify authentication status."""
        try:
            agy_bin = AuthManager.find_agy_binary()
        except FileNotFoundError as e:
            return False, str(e)

        if not AuthManager.is_token_present():
            return False, f"Antigravity OAuth token not found at {AuthManager.get_token_path()}. Run 'agy' once to sign in."

        try:
            proc = await asyncio.create_subprocess_exec(
                agy_bin,
                "models",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=8.0)
            if proc.returncode == 0:
                return True, "Authenticated"
            err_msg = stderr.decode().strip() or stdout.decode().strip()
            return False, f"agy models returned error (code {proc.returncode}): {err_msg}"
        except asyncio.TimeoutError:
            # If models check timed out, token is still present so we allow proceeding
            return True, "Auth token present (models check timed out)"
        except Exception as e:
            return False, f"Failed to check agy auth: {e}"

    @staticmethod
    def validate_api_key(client_key: str) -> bool:
        """
        Validates the incoming API key from Cursor.
        If AGY_API_KEY is configured, enforces exact match.
        Otherwise allows any non-empty bearer token (e.g. 'agy-live').
        """
        if not client_key:
            return False
        if settings.api_key and settings.api_key != "agy-live":
            # strict check
            clean_key = client_key.replace("Bearer ", "").strip()
            return clean_key == settings.api_key
        return True
