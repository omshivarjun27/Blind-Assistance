"""Minimal live DashScope realtime access diagnostic."""

from __future__ import annotations

import sys
import threading
import time
from importlib.metadata import PackageNotFoundError, version
from typing import Any

from dashscope.audio.qwen_omni.omni_realtime import (
    MultiModality,
    OmniRealtimeCallback,
    OmniRealtimeConversation,
)

from apps.backend.services.dashscope.realtime_client import default_voice_for_model
from shared.config.settings import (
    DASHSCOPE_REALTIME_URL,
    QWEN_REALTIME_MODEL,
    get_api_key,
)


def endpoint_region(endpoint: str) -> str:
    if "dashscope-intl" in endpoint:
        return "intl"
    if "dashscope.aliyuncs.com" in endpoint:
        return "beijing"
    return "unknown"


class DiagnosticCallback(OmniRealtimeCallback):
    def __init__(self) -> None:
        self.updated = threading.Event()
        self.closed = threading.Event()
        self.last_event: dict[str, Any] | None = None
        self.last_close_status_code: int | None = None
        self.last_close_msg: str | None = None

    def on_open(self) -> None:
        print("EVENT open")

    def on_event(self, message: Any) -> None:
        if isinstance(message, dict):
            self.last_event = message
            print(f"EVENT {message.get('type', '')}")
        else:
            print(f"EVENT {message!r}")
            self.last_event = None
        if isinstance(message, dict) and message.get("type") == "session.updated":
            self.updated.set()
        if isinstance(message, dict) and message.get("type") == "error":
            self.closed.set()

    def on_close(self, close_status_code, close_msg) -> None:
        self.last_close_status_code = close_status_code
        self.last_close_msg = close_msg
        print(f"CLOSE code={close_status_code!r} msg={close_msg!r}")
        self.closed.set()


def main() -> int:
    model = QWEN_REALTIME_MODEL
    endpoint = DASHSCOPE_REALTIME_URL
    voice = default_voice_for_model(model)
    region = endpoint_region(endpoint)

    try:
        dashscope_version = version("dashscope")
    except PackageNotFoundError:
        dashscope_version = "unknown"

    print(f"MODEL: {model}")
    print(f"ENDPOINT: {endpoint}")
    print(f"ENDPOINT_REGION: {region}")
    print(f"VOICE: {voice}")
    print(f"DASHSCOPE_VERSION: {dashscope_version}")

    callback = DiagnosticCallback()
    conversation = OmniRealtimeConversation(
        model=model,
        callback=callback,
        api_key=get_api_key(),
        url=endpoint,
    )

    reached_updated = False
    try:
        conversation.connect()
        conversation.update_session(
            output_modalities=[MultiModality.TEXT, MultiModality.AUDIO],
            voice=voice,
        )
        deadline = time.monotonic() + 10.0
        while time.monotonic() < deadline:
            if callback.updated.is_set():
                reached_updated = True
                break
            if callback.closed.is_set():
                break
            time.sleep(0.1)

        if reached_updated:
            print("RESULT: SESSION_UPDATED_REACHED")
            return 0

        print("DIAGNOSIS:")
        print("ACCESS_DENIED")
        print("REGION_MISMATCH_POSSIBLE")
        print("WORKSPACE_OR_MODEL_ENTITLEMENT_POSSIBLE")
        if callback.last_event is not None:
            print(f"LAST_EVENT: {callback.last_event}")
        if (
            callback.last_close_status_code is not None
            or callback.last_close_msg is not None
        ):
            print(
                "LAST_CLOSE: "
                f"code={callback.last_close_status_code!r} msg={callback.last_close_msg!r}"
            )
        print("RESULT: SESSION_UPDATED_NOT_REACHED")
        return 1
    except Exception as exc:
        print(f"EXCEPTION: {type(exc).__name__}: {exc}")
        print("DIAGNOSIS:")
        print("ACCESS_DENIED")
        print("REGION_MISMATCH_POSSIBLE")
        print("WORKSPACE_OR_MODEL_ENTITLEMENT_POSSIBLE")
        return 1
    finally:
        try:
            conversation.close()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
