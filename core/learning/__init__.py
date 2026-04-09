from importlib import import_module

__all__ = [
    "CorrectionStore",
    "OnlineReflection",
    "PatchStore",
    "Rollback",
    "OfflineReplay",
]


def __getattr__(name: str):
    if name == "CorrectionStore":
        return import_module("core.learning.correction_store").CorrectionStore
    if name == "OnlineReflection":
        return import_module("core.learning.online_reflection").OnlineReflection
    if name == "PatchStore":
        return import_module("core.learning.patch_store").PatchStore
    if name == "Rollback":
        return import_module("core.learning.rollback").Rollback
    if name == "OfflineReplay":
        return import_module("core.learning.offline_replay").OfflineReplay
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
