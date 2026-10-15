import os
import shutil
from pathlib import Path
from pydantic import BaseModel, Field

class Settings(BaseModel):
    # Server configuration
    host: str = Field(default="0.0.0.0", description="Host address to bind the HTTP server to")
    port: int = Field(default=8000, description="Port number to bind the HTTP server to")
    api_key: str = Field(default=os.getenv("AGY_API_KEY", "agy-live"), description="Virtual OpenAI API key required by Cursor")
    
    # Antigravity CLI configuration
    agy_binary: str = Field(
        default=os.getenv("AGY_BIN_PATH", shutil.which("agy") or str(Path.home() / ".local/bin/agy")),
        description="Path to the agy CLI executable"
    )
    default_model: str = Field(default="gemini-3.8-flash", description="Default model when unspecified")
    default_mode: str = Field(default="auto", description="Execution mode: auto, accept-edits, or plan")
    default_effort: str = Field(default="high", description="Default reasoning effort (low, medium, high, xhigh, max)")
    auto_approve_permissions: bool = Field(default=True, description="Enable --dangerously-skip-permissions for agent tools")
    
    # Path to local credentials
    token_path: Path = Field(
        default=Path.home() / ".gemini/antigravity-cli/antigravity-oauth-token",
        description="Path to local OAuth token"
    )
    
    # Session handling
    session_ttl_seconds: int = Field(default=7200, description="In-memory cache TTL for conversation IDs (2 hours)")
    max_cached_sessions: int = Field(default=500, description="Maximum number of mapped sessions in LRU memory")
    
    # Thinking & Reasoning style
    emit_reasoning_content: bool = Field(default=True, description="Emit reasoning_content delta for compatible UIs")
    emit_thought_tags: bool = Field(default=False, description="Wrap thoughts in <thought>...</thought> tags in text delta")

settings = Settings()
