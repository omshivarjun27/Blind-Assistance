import os

_ = os.environ.setdefault("PROFILE", "dev")
_ = os.environ.setdefault("DASHSCOPE_API_KEY", "test-key-for-unit-tests")
_ = os.environ.setdefault(
    "DASHSCOPE_COMPAT_BASE", "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
)
_ = os.environ.setdefault(
    "DASHSCOPE_REALTIME_URL", "wss://dashscope-intl.aliyuncs.com/api-ws/v1/realtime"
)
_ = os.environ.setdefault("QWEN_REALTIME_DEV", "qwen3.5-omni-plus-realtime")
_ = os.environ.setdefault("QWEN_REALTIME_EXAM", "qwen3.5-omni-plus-realtime")
_ = os.environ.setdefault("QWEN_HEAVY_VISION_MODEL", "qwen3.6-plus")
_ = os.environ.setdefault("QWEN_OMNI_VOICE", "Tina")
_ = os.environ.setdefault("QWEN_VISION_DEV", "qwen3.6-plus")
_ = os.environ.setdefault("QWEN_TRANSCRIPTION_MODEL", "gummy-realtime-v1")
_ = os.environ.setdefault("EMBEDDING_MODEL", "text-embedding-v4")
_ = os.environ.setdefault("APP_HOST", "127.0.0.1")
_ = os.environ.setdefault("APP_PORT", "8000")
_ = os.environ.setdefault("DEBUG", "true")
