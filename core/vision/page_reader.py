"""
Ally Vision v2 — Page reader.
OCR-style text extraction and page summarization.
"""

from __future__ import annotations

import logging

from apps.backend.services.dashscope.multimodal_client import (
    MultimodalClient,
    VisionRequest,
)

logger = logging.getLogger("ally-page-reader")


async def read_text_from_image(
    image_jpeg_b64: str,
    client: MultimodalClient,
) -> str:
    """
    Extract all visible text from an image.
    Returns the text or 'No text found'.
    """
    prompt = (
        "Read all text visible in this image. "
        "Return the exact text, nothing else. "
        "If no text is visible, say 'No text found'."
    )
    result = await client.analyze(
        VisionRequest(image_jpeg_b64=image_jpeg_b64, prompt=prompt)
    )
    if result.success:
        return result.text
    logger.warning("Text read failed: %s", result.error)
    return "I could not read the text. Please try again."


async def summarize_page(
    image_jpeg_b64: str,
    client: MultimodalClient,
    page_number: int = 1,
) -> str:
    """
    Summarize a document page.
    Returns page summary string.
    """
    prompt = (
        f"This is page {page_number} of a document. "
        "Describe its content: main topic, key points, "
        "any important numbers, dates, or names."
    )
    result = await client.analyze(
        VisionRequest(image_jpeg_b64=image_jpeg_b64, prompt=prompt)
    )
    if result.success:
        return result.text
    logger.warning("Page summarize failed: %s", result.error)
    return f"I could not summarize page {page_number}. Please try again."
