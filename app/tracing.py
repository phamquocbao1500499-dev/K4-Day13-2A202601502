from __future__ import annotations

import os
from typing import Any

# Load env vars BEFORE langfuse import - SDK needs keys at initialization
from dotenv import load_dotenv
load_dotenv(override=True)

try:
    from langfuse import get_client, observe

    LANGFUSE_SDK_AVAILABLE = True
except ImportError:  # pragma: no cover - chỉ dùng khi chưa cài requirements
    LANGFUSE_SDK_AVAILABLE = False

    def observe(*args: Any, **kwargs: Any):
        def decorator(func):
            return func

        return decorator

    class _DummyClient:
        def update_current_trace(self, **kwargs: Any) -> None:
            return None

        def update_current_generation(self, **kwargs: Any) -> None:
            return None

        def flush(self) -> None:
            return None

    def get_client():
        return _DummyClient()


def get_langfuse_client():
    return get_client()


def flush_traces() -> None:
    """Flush pending traces synchronously. Call on app shutdown."""
    if LANGFUSE_SDK_AVAILABLE:
        get_client().flush()


async def flush_traces_async() -> None:
    """Flush pending traces asynchronously. Call on app shutdown in async context."""
    if LANGFUSE_SDK_AVAILABLE:
        flush_traces()  # SDK uses sync flush internally


def tracing_enabled() -> bool:
    return LANGFUSE_SDK_AVAILABLE and bool(
        os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY")
    )
