"""
Ally Vision v2 — Capture coach.

Lightweight pixel-quality gate before expensive vision calls.
Checks for darkness, tiny dimensions, and uniform (blurry/blank) frames.
Imports PIL lazily — not at module level.
"""

from __future__ import annotations

import base64
import logging

logger = logging.getLogger("ally-capture-coach")


def assess_frame_quality(
    image_jpeg_b64: str | None,
) -> tuple[bool, str]:
    """
    Check whether a captured JPEG frame is usable for vision tasks.

    Returns (is_usable: bool, guidance_message: str).
    guidance_message is empty string when frame is usable.
    """
    if not image_jpeg_b64:
        return False, "Please point the camera at something."

    try:
        import io

        import numpy as np
        from PIL import Image

        data = base64.b64decode(image_jpeg_b64)
        img = Image.open(io.BytesIO(data)).convert("RGB")
        w, h = img.size

        if w < 100 or h < 100:
            return False, "Move closer."

        arr = np.asarray(img, dtype=np.float32)

        mean_brightness = float(arr.mean())
        if mean_brightness < 30.0:
            return False, "Move to better lighting."

        std_dev = float(arr.std())
        if std_dev < 5.0:
            return False, "Hold the camera still."

        return True, ""

    except Exception as exc:
        logger.warning("Frame quality check failed: %s", exc)
        return True, ""
