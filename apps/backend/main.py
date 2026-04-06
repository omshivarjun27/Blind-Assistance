"""
Ally Vision v2 — FastAPI entry point.
"""

from __future__ import annotations
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from shared.config.settings import get_config, APP_HOST, APP_PORT, DEBUG

logging.basicConfig(
    level=logging.DEBUG if DEBUG else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("ally-vision")

app = FastAPI(
    title="Ally Vision v2",
    description="Blind-first voice+vision assistant",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
