import asyncio
import re
import time
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from agy_cursor_bridge.config import settings
from agy_cursor_bridge.core.auth import AuthManager
from agy_cursor_bridge.models.schemas import ModelCard, ModelListResponse

router = APIRouter(tags=["models"])
security = HTTPBearer(auto_error=False)

# Cache model list for 5 minutes
_cached_models: List[str] = []
_last_fetch_time: float = 0.0

DEFAULT_FALLBACK_MODELS = [
    "gemini-3.8-flash",
    "gemini-3.8-pro",
    "gemini-3.8-flash-lite",
    "claude-3-7-sonnet",
    "deepseek-r1",
    "deepseek-v3",
    "gpt-5.4",
    "o3-mini",
    # Non-colliding custom names for Cursor
    "agy-flash",
    "agy-gemini",
    "agy-gemini-3.8-flash",
    "agy-pro",
    "agy-sonnet",
    "agy-deepseek",
    # Standard OpenAI models
    "gpt-4o",
    "gpt-4",
    "gpt-4o-mini",
    "auto",
    "cursor-agent",
]

async def fetch_available_models() -> List[str]:
    global _cached_models, _last_fetch_time
    now = time.time()
    if _cached_models and (now - _last_fetch_time < 300.0):
        return _cached_models

    try:
        agy_bin = AuthManager.find_agy_binary()
        proc = await asyncio.create_subprocess_exec(
            agy_bin,
            "models",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5.0)
        output = stdout.decode("utf-8", errors="replace")

        discovered: List[str] = []
        for line in output.splitlines():
            line = line.strip()
            if not line or line.startswith("=") or line.startswith("Current") or line.startswith("Default") or line.startswith("Available") or line.startswith("Use") or line.startswith("Selected"):
                continue
            # First token is the model id
            parts = line.split()
            if parts:
                model_id = parts[0].replace("(default)", "").strip()
                if model_id and re.match(r"^[a-zA-Z0-9_\-\.]+$", model_id):
                    discovered.append(model_id)

        if discovered:
            # Add virtual aliases and non-colliding names
            extra_aliases = [
                "agy-flash",
                "agy-gemini",
                "agy-gemini-3.8-flash",
                "agy-pro",
                "agy-sonnet",
                "agy-deepseek",
                "gpt-4o",
                "gpt-4",
                "gpt-4o-mini",
                "auto",
                "cursor-agent",
            ]
            for alias in extra_aliases:
                if alias not in discovered:
                    discovered.append(alias)
            _cached_models = discovered
            _last_fetch_time = now
            return _cached_models

    except Exception:
        pass

    _cached_models = DEFAULT_FALLBACK_MODELS
    _last_fetch_time = now
    return _cached_models

def verify_token(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)):
    if credentials:
        if not AuthManager.validate_api_key(credentials.credentials):
            raise HTTPException(status_code=401, detail="Invalid API Key")
    elif settings.api_key and settings.api_key != "agy-live":
        raise HTTPException(status_code=401, detail="Authentication required")
    return True

@router.get("/v1/models", response_model=ModelListResponse)
@router.get("/cursor/models", response_model=ModelListResponse)
@router.get("/cursor/v1/models", response_model=ModelListResponse)
@router.get("/models", response_model=ModelListResponse)
async def list_models(authorized: bool = Depends(verify_token)):
    models = await fetch_available_models()
    cards = [ModelCard(id=m) for m in models]
    return ModelListResponse(object="list", data=cards)

@router.get("/v1/models/{model_id}", response_model=ModelCard)
@router.get("/cursor/models/{model_id}", response_model=ModelCard)
@router.get("/models/{model_id}", response_model=ModelCard)
async def get_model(model_id: str, authorized: bool = Depends(verify_token)):
    models = await fetch_available_models()
    if model_id in models or any(model_id.lower() in m.lower() for m in models):
        return ModelCard(id=model_id)
    # Allow unknown model query to not break Cursor
    return ModelCard(id=model_id)
