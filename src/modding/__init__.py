"""
Automated Game ROM Recompiler — Modding SDK & Visual Enhancement Package
Provides HD texture replacement, widescreen camera geometry patching, and native C function hooking.
"""

from src.modding.texture_manager import (
    TextureFormat,
    TextureMetadata,
    TextureManager,
    compute_texture_crc32,
)
from src.modding.widescreen import (
    AspectRatio,
    WidescreenMode,
    WidescreenPatcher,
)
from src.modding.hook_manager import (
    HookType,
    FunctionHook,
    HookManager,
)

__all__ = [
    "TextureFormat",
    "TextureMetadata",
    "TextureManager",
    "compute_texture_crc32",
    "AspectRatio",
    "WidescreenMode",
    "WidescreenPatcher",
    "HookType",
    "FunctionHook",
    "HookManager",
]
