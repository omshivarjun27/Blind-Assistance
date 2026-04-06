"""
Ally Vision v2 — Model-based framing judge.

Uses the vision model to assess image quality.
More accurate than pixel-only capture_coach check
but more expensive. Use capture_coach first.
Not wired into realtime.py in Plan 06.
"""

from __future__ import annotations

import logging

from apps.backend.services.dashscope.multimodal_client import (
    MultimodalClient,
    VisionRequest,
)

logger = logging.getLogger("ally-framing-judge")

_PROMPT = (
    "Is this image clear and readable? "
    "Reply with YES or NO followed by one sentence "
    "of guidance if NO. "
    "Example: NO - The image is too blurry."
)


async def get_framing_guidance(
    image_jpeg_b64: str,
    client: MultimodalClient,
) -> tuple[bool, str]:
    """
    Ask the vision model if the image is usable.
    Returns (is_usable, guidance_message).
    Defaults to (True, '') on any error.
    """
    result = await client.analyze(
        VisionRequest(image_jpeg_b64=image_jpeg_b64, prompt=_PROMPT)
    )
    if not result.success:
        logger.warning("Framing judge failed: %s", result.error)
        return True, ""  # allow turn to proceed on error

    text = result.text.strip()
    upper = text.upper()

    if upper.startswith("YES"):
        return True, ""

    if upper.startswith("NO"):
        parts = text.split("-", 1)
        guidance = parts[1].strip() if len(parts) > 1 else text
        return False, guidance

    logger.debug("Unexpected framing judge response: %r", text)
    return True, ""
