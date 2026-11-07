#!/usr/bin/env python3
"""
HD Texture Replacement Pipeline
Part of the Automated Game ROM Recompiler Modding SDK.

Provides deterministic CRC32 texture identification, VRAM texture dumping,
high-resolution texture pack parsing, and native C runtime interception shims.
"""

import os
import json
import zlib
import math
import re
from pathlib import Path
from enum import Enum
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple, Any


def _uint32(value: int, label: str):
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 0xFFFFFFFF:
        raise ValueError(f"{label} must be an unsigned 32-bit integer")


def _dimensions(width: int, height: int, *, allow_zero: bool = False):
    for value, label in ((width, "Texture width"), (height, "Texture height")):
        _uint32(value, label)
        if not allow_zero and value == 0:
            raise ValueError(f"{label} must be positive")


def _crc32_value(value) -> int:
    if isinstance(value, str):
        value = int(value, 16 if value.lower().startswith("0x") or re.search(r"[a-fA-F]", value) else 10)
    _uint32(value, "Texture CRC32")
    return value


def _c_string(value: str) -> str:
    # Fixed-width octal escapes preserve UTF-8 bytes and cannot swallow a
    # following digit, quote, backslash, or line break in the C source.
    escaped = "".join(chr(b) if 32 <= b < 127 and b not in (34, 92) else f"\\{b:03o}" for b in value.encode("utf-8"))
    return '"' + escaped + '"'


class TextureFormat(str, Enum):
    RGBA8888 = "RGBA8888"
    RGB565 = "RGB565"
    RGBA5551 = "RGBA5551"
    RGBA4444 = "RGBA4444"
    INDEXED8 = "INDEXED8"
    INDEXED4 = "INDEXED4"


def compute_texture_crc32(data: bytes, width: int, height: int, fmt: TextureFormat = TextureFormat.RGBA8888) -> int:
    """
    Computes a deterministic CRC32 fingerprint for a texture
    based on its pixel payload, dimensions, and color format.
    """
    # Header salt incorporates dimensions and format to prevent collision between identical sub-blocks
    _dimensions(width, height)
    fmt = TextureFormat(fmt)
    header_salt = f"TEX:{width}x{height}:{fmt.value}:".encode("ascii")
    # Unsigned 32-bit CRC32
    return zlib.crc32(data, zlib.crc32(header_salt)) & 0xFFFFFFFF


@dataclass
class TextureMetadata:
    crc32: int
    width: int
    height: int
    format: TextureFormat
    data_size: int
    scale_factor: float = 1.0
    file_path: Optional[str] = None
    name: Optional[str] = None

    def __post_init__(self):
        self.validate()

    def validate(self):
        _uint32(self.crc32, "Texture CRC32")
        _dimensions(self.width, self.height, allow_zero=True)
        self.format = TextureFormat(self.format)
        if isinstance(self.data_size, bool) or not isinstance(self.data_size, int) or self.data_size < 0:
            raise ValueError("Texture data size must be a nonnegative integer")
        if isinstance(self.scale_factor, bool) or not isinstance(self.scale_factor, (int, float)) or not 1.4012985e-45 <= self.scale_factor <= 3.4028234e38 or not math.isfinite(self.scale_factor):
            raise ValueError("Texture scale must be positive, finite, and representable as a C float")
        if self.file_path is not None:
            if not isinstance(self.file_path, (str, os.PathLike)):
                raise ValueError("Texture file path must be a string or path")
            self.file_path = os.fspath(self.file_path)
            if not isinstance(self.file_path, str) or "\0" in self.file_path:
                raise ValueError("Texture file path must be a string without NUL bytes")

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["format"] = self.format.value
        d["crc32_hex"] = f"0x{self.crc32:08X}"
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TextureMetadata":
        crc32_val = _crc32_value(data.get("crc32", 0))
        fmt = TextureFormat(data.get("format", TextureFormat.RGBA8888.value))
        return cls(
            crc32=crc32_val,
            width=int(data.get("width", 0)),
            height=int(data.get("height", 0)),
            format=fmt,
            data_size=int(data.get("data_size", 0)),
            scale_factor=float(data.get("scale_factor", 1.0)),
            file_path=data.get("file_path"),
            name=data.get("name"),
        )


class TextureManager:
    """
    Manages dumping of raw game textures to disk, cataloging them by CRC32 hash,
    and loading HD replacement textures to inject at runtime.
    """

    def __init__(self, dump_dir: str = "dumps/textures", mods_dir: str = "mods/textures"):
        self.dump_dir = dump_dir
        self.mods_dir = mods_dir
        self.replacements: Dict[int, TextureMetadata] = {}
        self.dumped_textures: Dict[int, TextureMetadata] = {}

    def dump_texture(
        self,
        data: bytes,
        width: int,
        height: int,
        fmt: TextureFormat = TextureFormat.RGBA8888,
        name: Optional[str] = None
    ) -> TextureMetadata:
        """
        Dumps a texture buffer to disk with deterministic CRC32 naming.
        Saves raw binary data and a accompanying JSON descriptor.
        """
        crc = compute_texture_crc32(data, width, height, fmt)
        os.makedirs(self.dump_dir, exist_ok=True)

        crc_hex = f"{crc:08X}"
        bin_path = os.path.join(self.dump_dir, f"tex_{crc_hex}.bin")
        meta_path = os.path.join(self.dump_dir, f"tex_{crc_hex}.json")

        meta = TextureMetadata(
            crc32=crc,
            width=width,
            height=height,
            format=fmt,
            data_size=len(data),
            scale_factor=1.0,
            file_path=bin_path,
            name=name or f"Texture_{crc_hex}"
        )

        with open(bin_path, "wb") as f:
            f.write(data)

        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta.to_dict(), f, indent=2)

        self.dumped_textures[crc] = meta
        return meta

    def register_replacement(
        self,
        crc32: int,
        file_path: str,
        width: int,
        height: int,
        orig_width: int,
        orig_height: int,
        fmt: TextureFormat = TextureFormat.RGBA8888,
        name: Optional[str] = None
    ) -> TextureMetadata:
        """
        Registers an HD replacement texture for an existing original texture CRC32.
        Calculates scale factor relative to the original dimensions.
        """
        _uint32(crc32, "Texture CRC32")
        _dimensions(width, height)
        _dimensions(orig_width, orig_height)
        if not os.path.isfile(file_path):
            raise ValueError(f"Replacement texture file not found: {file_path}")
        scale_x = width / orig_width
        scale_y = height / orig_height
        scale = max(scale_x, scale_y)

        meta = TextureMetadata(
            crc32=crc32,
            width=width,
            height=height,
            format=fmt,
            data_size=os.path.getsize(file_path) if os.path.exists(file_path) else 0,
            scale_factor=scale,
            file_path=file_path,
            name=name or os.path.basename(file_path)
        )
        self.replacements[crc32] = meta
        return meta

    def load_texture_pack(self, pack_dir: str) -> int:
        """
        Loads a community HD texture pack directory.
        Scans for manifest `texture_pack.json` or standalone `<CRC32>.png` files.
        Returns the number of replacement textures loaded.
        """
        root = Path(pack_dir).resolve()
        if not root.exists():
            return 0
        if not root.is_dir():
            raise ValueError("Texture pack must be a directory")
        entries = {}
        manifest_path = root / "texture_pack.json"

        def texture_path(relative_path):
            if not isinstance(relative_path, str) or Path(relative_path).is_absolute():
                raise ValueError("Texture manifest paths must be relative to the pack directory")
            path = (root / relative_path).resolve()
            if not path.is_relative_to(root):
                raise ValueError("Texture path leaves the pack directory")
            if not path.is_file():
                raise ValueError(f"Texture file not found: {relative_path}")
            return str(path)

        if manifest_path.is_file():
            try:
                with manifest_path.open("r", encoding="utf-8") as f:
                    manifest = json.load(f)
            except (OSError, ValueError) as error:
                raise ValueError(f"Invalid texture pack manifest: {error}") from error
            if not isinstance(manifest, dict) or not isinstance(manifest.get("textures", []), list):
                raise ValueError("Texture manifest must contain a textures list")
            for item in manifest.get("textures", []):
                if not isinstance(item, dict) or "crc32" not in item:
                    raise ValueError("Each texture entry must contain a CRC32")
                crc = _crc32_value(item["crc32"])
                full_path = texture_path(item.get("file", f"tex_{crc:08X}.png"))
                meta = TextureMetadata(
                    crc32=crc,
                    width=item.get("width", 0),
                    height=item.get("height", 0),
                    format=TextureFormat(item.get("format", TextureFormat.RGBA8888.value)),
                    data_size=os.path.getsize(full_path),
                    scale_factor=item.get("scale", 1.0),
                    file_path=full_path,
                    name=item.get("name", os.path.basename(full_path))
                )
                entries[crc] = meta

        # Also discover loose files matching tex_<CRC32>.(png|bin|dds)
        for file in sorted(root.iterdir(), key=lambda path: (path.suffix.lower() != ".png", path.name.lower())):
            match = re.fullmatch(r"tex_([0-9a-fA-F]{8})(?:_hd)?\.(png|bin|dds)", file.name, re.IGNORECASE)
            if match and file.is_file():
                crc = int(match[1], 16)
                if crc not in entries:
                    full_path = texture_path(file.name)
                    entries[crc] = TextureMetadata(
                        crc32=crc, width=0, height=0, format=TextureFormat.RGBA8888,
                        data_size=os.path.getsize(full_path), file_path=full_path, name=file.name
                    )
        self.replacements.update(entries)
        return len(entries)

    def get_replacement(self, crc32: int) -> Optional[TextureMetadata]:
        return self.replacements.get(crc32)

    def emit_c_texture_interceptor(self) -> str:
        """
        Emits standard C99 runtime shims for deterministic texture lookup and HD injection.
        """
        lines = [
            "/* Automated Recompiler Framework — HD Texture Replacement Runtime Interceptor */",
            "#ifndef RECOMP_TEXTURE_MODDING_H",
            "#define RECOMP_TEXTURE_MODDING_H",
            "",
            "#include <stdint.h>",
            "#include <stdbool.h>",
            "#include <stdlib.h>",
            "#include <string.h>",
            "",
            "typedef struct {",
            "    uint32_t orig_crc32;",
            "    uint32_t width;",
            "    uint32_t height;",
            "    float    scale_factor;",
            "    const char* file_path;",
            "} RecompHdTextureEntry;",
            "",
            f"/* Registered HD Texture Replacements: {len(self.replacements)} entries */",
            "static const RecompHdTextureEntry g_recomp_hd_textures[] = {",
        ]

        for crc, meta in sorted(self.replacements.items()):
            meta.validate()
            if crc != meta.crc32:
                raise ValueError("Texture CRC32 no longer matches its registration")
            path_str = meta.file_path.replace("\\", "/") if meta.file_path else ""
            lines.append(
                f'    {{ 0x{crc:08X}, {meta.width}, {meta.height}, {meta.scale_factor:.9e}f, {_c_string(path_str)} }},'
            )

        lines.extend([
            "    { 0, 0, 0, 0.0f, NULL } /* Sentinel */",
            "};",
            "",
            "static inline const RecompHdTextureEntry* recomp_lookup_hd_texture(uint32_t orig_crc32) {",
            "    for (int i = 0; g_recomp_hd_textures[i].file_path != NULL; i++) {",
            "        if (g_recomp_hd_textures[i].orig_crc32 == orig_crc32) {",
            "            return &g_recomp_hd_textures[i];",
            "        }",
            "    }",
            "    return NULL;",
            "}",
            "",
            "#endif /* RECOMP_TEXTURE_MODDING_H */",
        ])

        return "\n".join(lines)
