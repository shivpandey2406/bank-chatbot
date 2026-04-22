"""
Main Application Entry Point
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.logging import setup_logging, get_logger
from app.core.security import create_default_user
from app.db.session import init_db

from app.api.health import router as health_router
from app.api.chat import router as chat_router
from app.api.files import router as files_router
from app.api.oauth import router as oauth_router

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Banking Chatbot application...")
    try:
        await init_db()
        logger.info("Database initialized")
        # Embedding model + vector store load lazily on first query
        # so the server starts instantly instead of blocking for 30-60s
        logger.info("Embedding model and vector store will load on first use")
        await create_default_user()
        logger.info("Application startup completed — server is ready")
    except Exception as e:
        logger.exception("Error during startup", error=str(e))
        raise
    yield
    logger.info("Shutting down Banking Chatbot application...")


def create_app() -> FastAPI:
    setup_logging()

    app = FastAPI(
        title=settings.app_name,
        description=settings.description,
        version=settings.app_version,
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        openapi_url="/openapi.json" if settings.debug else None,
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    # Routes
    app.include_router(health_router)
    app.include_router(chat_router)
    app.include_router(files_router)
    app.include_router(oauth_router)

    # Upload directory
    os.makedirs(os.path.join(settings.upload_dir, "raw"), exist_ok=True)
    os.makedirs(os.path.join(settings.upload_dir, "processed"), exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=settings.upload_dir), name="uploads")

    # Exception handlers
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request, exc):
        return JSONResponse(
            status_code=exc.status_code,
            content={"success": False, "error": exc.detail},
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request, exc):
        logger.exception(f"Unhandled exception: {exc}")
        if settings.debug:
            detail = str(exc)
        else:
            detail = "An internal server error occurred"
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": detail},
        )

    return app


app = create_app()


@app.get("/", response_class=HTMLResponse)
async def root():
    return f"""<!DOCTYPE html>
<html><head><title>{settings.app_name}</title>
<style>body{{font-family:Arial,sans-serif;margin:40px}}.ok{{color:#155724;background:#d4edda;
display:inline-block;padding:4px 12px;border-radius:4px}}a{{color:#007bff;display:block;margin:4px 0}}</style>
</head><body>
<h1>{settings.app_name}</h1><span class="ok">Running</span>
<p>{settings.description}</p>
<a href="/health">Health Check</a>
<a href="/api/chat/agents">Agents</a>
{'<a href="/docs">API Docs</a>' if settings.debug else ''}
</body></html>"""


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.host, port=settings.port,
                reload=settings.debug, log_level="info")
