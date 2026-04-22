"""
Ally Vision v2 — Settings
All config comes from environment variables.
Never hardcode secrets here.
"""

from __future__ import annotations
import os
import pathlib
from dotenv import load_dotenv

_ = load_dotenv()


def _require(key: str) -> str:
    val = os.environ.get(key, "")
    if not val or val.startswith("your_") or val == "FILL_IN_YOUR_KEY_HERE":
        raise ValueError(f"Required env var {key!r} is not set. Check your .env file.")
    return val


def _get(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


# Profile
PROFILE: str = _get("PROFILE", "dev")
_is_exam = PROFILE == "exam"

# DashScope
DASHSCOPE_API_KEY: str = ""  # loaded lazily to allow tests
DASHSCOPE_REGION: str = _get("DASHSCOPE_REGION", "singapore")
DASHSCOPE_HTTP_BASE: str = _get(
    "DASHSCOPE_HTTP_BASE",
    "https://dashscope-intl.aliyuncs.com/api/v1",
)
DASHSCOPE_REALTIME_URL: str = _get(
    "DASHSCOPE_REALTIME_URL",
    "wss://dashscope-intl.aliyuncs.com/api-ws/v1/realtime",
)
DASHSCOPE_COMPAT_BASE: str = _get(
    "DASHSCOPE_COMPAT_BASE",
    "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
)

# Model selection by profile
QWEN_REALTIME_MODEL: str = _get(
    "QWEN_REALTIME_EXAM" if _is_exam else "QWEN_REALTIME_DEV",
    "qwen3.5-omni-plus-realtime",
)
QWEN_OMNI_VOICE: str = _get("QWEN_OMNI_VOICE", "Tina")
QWEN_HEAVY_VISION_MODEL: str = _get("QWEN_HEAVY_VISION_MODEL", "qwen3.6-plus")
QWEN_VISION_MODEL: str = _get(
    "QWEN_HEAVY_VISION_MODEL",
    _get(
        "QWEN_VISION_EXAM" if _is_exam else "QWEN_VISION_DEV",
        "qwen3.6-plus",
    ),
)
QWEN_TRANSCRIPTION_MODEL: str = _get("QWEN_TRANSCRIPTION_MODEL", "gummy-realtime-v1")
QWEN_TURBO_MODEL: str = _get("QWEN_TURBO_MODEL", "qwen-turbo")

# Embedding
EMBEDDING_MODEL: str = _get("EMBEDDING_MODEL", "text-embedding-v4")
EMBEDDING_DIMENSIONS: int = int(_get("EMBEDDING_DIMENSIONS", "1024"))
EMBEDDING_OUTPUT_TYPE: str = _get("EMBEDDING_OUTPUT_TYPE", "dense")
_DEFAULT_MEMORY_DB_PATH = pathlib.Path(__file__).resolve().parents[2] / "data" / "sqlite" / "memory.db"
MEMORY_DB_PATH: str = os.getenv("MEMORY_DB_PATH", str(_DEFAULT_MEMORY_DB_PATH))

# Ensure parent directory exists at settings load time
pathlib.Path(MEMORY_DB_PATH).parent.mkdir(parents=True, exist_ok=True)

# App
APP_HOST: str = _get("APP_HOST", "127.0.0.1")
APP_PORT: int = int(_get("APP_PORT", "8000"))
DEBUG: bool = _get("DEBUG", "true").lower() == "true"


def get_api_key() -> str:
    """Get DashScope API key. Raises if not set."""
    return _require("DASHSCOPE_API_KEY")


def get_config() -> dict[str, object]:
    """Return full config as dict for health checks."""
    return {
        "profile": PROFILE,
        "realtime_model": QWEN_REALTIME_MODEL,
        "vision_model": QWEN_VISION_MODEL,
        "embedding_model": EMBEDDING_MODEL,
        "embedding_dimensions": EMBEDDING_DIMENSIONS,
        "dashscope_region": DASHSCOPE_REGION,
        "app_host": APP_HOST,
        "app_port": APP_PORT,
        "debug": DEBUG,
    }


# Learning layer knobs (Plan 10)
LEARNING_DECAY_FACTOR: float = 0.3
LEARNING_FAILURE_THRESHOLD: float = 1.0
LEARNING_PATCH_MONITOR_TURNS: int = 10
LEARNING_PRIORITY_PROMOTION_MIN_RECALLS: int = 3
