import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from agy_cursor_bridge import __version__
from agy_cursor_bridge.routes.models import router as models_router
from agy_cursor_bridge.routes.completions import router as completions_router
from agy_cursor_bridge.routes.health import router as health_router
from agy_cursor_bridge.core.session_store import session_store

logger = logging.getLogger("server")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Run periodic session cleaner in background
    async def session_cleaner():
        while True:
            await asyncio.sleep(600)  # Every 10 minutes
            session_store.prune_expired()

    cleaner_task = asyncio.create_task(session_cleaner())
    yield
    # Shutdown
    cleaner_task.cancel()
    try:
        await cleaner_task
    except asyncio.CancelledError:
        pass

def create_app() -> FastAPI:
    app = FastAPI(
        title="agy-cursor-bridge",
        description="OpenAI-compatible routing layer connecting Cursor IDE to Google Antigravity (agy CLI)",
        version=__version__,
        lifespan=lifespan,
    )

    # Permissive CORS for Cursor and external clients
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount routes
    app.include_router(health_router)
    app.include_router(models_router)
    app.include_router(completions_router)

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error(f"Global unhandled exception on {request.url.path}: {exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "message": str(exc),
                    "type": "internal_server_error",
                    "code": 500,
                }
            }
        )

    return app

app = create_app()
