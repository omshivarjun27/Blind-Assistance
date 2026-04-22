from __future__ import annotations

import httpx

_vision_http_client: httpx.AsyncClient | None = None
_compat_http_client: httpx.AsyncClient | None = None


def configure_shared_http_clients(
    *,
    vision_client: httpx.AsyncClient | None,
    compat_client: httpx.AsyncClient | None,
) -> None:
    global _vision_http_client, _compat_http_client
    _vision_http_client = vision_client
    _compat_http_client = compat_client


async def close_shared_http_clients() -> None:
    global _vision_http_client, _compat_http_client

    if _vision_http_client is not None:
        await _vision_http_client.aclose()
    if _compat_http_client is not None and _compat_http_client is not _vision_http_client:
        await _compat_http_client.aclose()

    _vision_http_client = None
    _compat_http_client = None


def get_vision_http_client() -> httpx.AsyncClient | None:
    return _vision_http_client


def get_compat_http_client() -> httpx.AsyncClient | None:
    return _compat_http_client
