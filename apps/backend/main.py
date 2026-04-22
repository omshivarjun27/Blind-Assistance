"""
Ally Vision v2 — FastAPI entry point.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.backend.api.routes import realtime as realtime_route
from apps.backend.services.shared_http import (
    close_shared_http_clients,
    configure_shared_http_clients,
)
from shared.config.settings import APP_HOST, APP_PORT, DEBUG, MEMORY_DB_PATH, get_config

logging.basicConfig(
    level=logging.DEBUG if DEBUG else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("ally-vision")

@asynccontextmanager
async def lifespan(_: FastAPI):
    vision_client = httpx.AsyncClient(
        timeout=httpx.Timeout(60.0),
        limits=httpx.Limits(max_keepalive_connections=3, max_connections=6),
    )
    compat_client = httpx.AsyncClient(
        timeout=httpx.Timeout(10.0),
        limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
    )
    configure_shared_http_clients(
        vision_client=vision_client,
        compat_client=compat_client,
    )
    logger.info("Memory DB absolute path: %s", Path(MEMORY_DB_PATH).resolve())
    try:
        yield
    finally:
        await close_shared_http_clients()


app = FastAPI(
    title="Ally Vision v2",
    description="Blind-first voice+vision assistant",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(realtime_route.router)


@app.get("/health")
async def health() -> dict[str, object]:
    cfg = get_config()
    return {
        "status": "ok",
        "profile": cfg["profile"],
        "realtime_model": cfg["realtime_model"],
        "vision_model": cfg["vision_model"],
        "embedding_model": cfg["embedding_model"],
    }


@app.get("/config")
async def config() -> dict[str, object]:
    return get_config()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "apps.backend.main:app",
        host=APP_HOST,
        port=APP_PORT,
        reload=DEBUG,
    )
