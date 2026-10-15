import time
from fastapi import APIRouter
from agy_cursor_bridge import __version__
from agy_cursor_bridge.config import settings
from agy_cursor_bridge.core.auth import AuthManager
from agy_cursor_bridge.core.session_store import session_store

router = APIRouter(tags=["health"])
_start_time = time.time()

@router.get("/health")
@router.get("/v1/health")
async def health_check():
    is_auth, auth_status = await AuthManager.verify_auth()
    return {
        "status": "ok",
        "version": __version__,
        "uptime_seconds": int(time.time() - _start_time),
        "antigravity": {
            "authenticated": is_auth,
            "status": auth_status,
            "token_present": AuthManager.is_token_present(),
            "default_model": settings.default_model,
        },
        "sessions": {
            "active_count": session_store.active_sessions_count,
        }
    }
