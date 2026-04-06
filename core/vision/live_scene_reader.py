"""
Ally Vision v2 — Live scene reader.
Sends camera frame to heavy vision model for scene description.
"""

from __future__ import annotations

import logging

from apps.backend.services.dashscope.multimodal_client import (
    MultimodalClient,
    VisionRequest,
)

logger = logging.getLogger("ally-scene-reader")

_PROMPTS = {
    "standard": (
        "Describe what you see. Be specific about objects, "
        "their positions, and distances. "
        "Keep it brief for a blind user."
    ),
    "detailed": (
        "Describe everything visible in detail. Include objects, "
        "text, people, colors, spatial relationships, and distances."
    ),
}


async def read_scene(
    image_jpeg_b64: str,
    client: MultimodalClient,
    detail_level: str = "standard",
) -> str:
    """
    Describe the scene visible in the camera frame.
    Returns description text or error fallback string.
    """
    prompt = _PROMPTS.get(detail_level, _PROMPTS["standard"])
    result = await client.analyze(
        VisionRequest(image_jpeg_b64=image_jpeg_b64, prompt=prompt)
    )
    if result.success:
        return result.text
    logger.warning("Scene read failed: %s", result.error)
    return "I could not analyze the scene. Please try again."
