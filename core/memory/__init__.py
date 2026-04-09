"""Ally Vision v2 — memory layer."""

from importlib import import_module

from .embedding_client import EmbeddingClient, EmbeddingError
from .mem0_extractor import Mem0Extractor
from .memory_context_composer import compose_memory_context
from .session_memory import SessionMemory

__all__ = [
    "EmbeddingClient",
    "EmbeddingError",
    "MemoryStore",
    "MemoryManager",
    "SessionMemory",
    "Mem0Extractor",
    "compose_memory_context",
]


def __getattr__(name: str):
    if name == "MemoryStore":
        return import_module("core.memory.memory_store").MemoryStore
    if name == "MemoryManager":
        return import_module("core.memory.memory_manager").MemoryManager
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
