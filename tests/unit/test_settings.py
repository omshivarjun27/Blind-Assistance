"""Tests for shared/config/settings.py"""

import pytest


def test_profile_defaults_to_dev():
    from shared.config import settings

    assert settings.PROFILE in ("dev", "exam")


def test_realtime_model_set():
    from shared.config import settings

    assert settings.QWEN_REALTIME_MODEL != ""
    assert "realtime" in settings.QWEN_REALTIME_MODEL


def test_vision_model_set():
    from shared.config import settings

    assert settings.QWEN_VISION_MODEL != ""


def test_embedding_model_set():
    from shared.config import settings

    assert settings.EMBEDDING_MODEL == "text-embedding-v3"
    assert settings.EMBEDDING_DIMENSIONS == 1024
    assert settings.EMBEDDING_OUTPUT_TYPE == "dense"


def test_dashscope_endpoints_set():
    from shared.config import settings

    assert "dashscope-intl" in settings.DASHSCOPE_REALTIME_URL
    assert "dashscope-intl" in settings.DASHSCOPE_COMPAT_BASE


def test_get_config_returns_dict():
    from shared.config.settings import get_config

    cfg = get_config()
    required_keys = [
        "profile",
        "realtime_model",
        "vision_model",
        "embedding_model",
        "embedding_dimensions",
    ]
    for k in required_keys:
        assert k in cfg, f"Missing key: {k}"


def test_get_api_key_raises_when_not_set():
    import os

    original = os.environ.pop("DASHSCOPE_API_KEY", None)
    try:
        # Force module reload with missing key
        from shared.config import settings as s

        with pytest.raises(ValueError, match="DASHSCOPE_API_KEY"):
            _ = s.get_api_key()
    finally:
        if original:
            os.environ["DASHSCOPE_API_KEY"] = original
