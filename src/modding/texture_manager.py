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
from enum import Enum
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple, Any


class TextureFormat(str, Enum):
    RGBA8888 = "RGBA8888"
    RGB565 = "RGB565"
    RGBA5551 = "RGBA5551"
    RGBA4444 = "RGBA4444"
    INDEXED8 = "INDEXED8"
    INDEXED4 = "INDEXED4"


def compute_texture_crc32(data: bytes, width: int, height: int, fmt: TextureFormat = TextureFormat.RGBA8888) -> int:
    """
    Computes a deterministic, collision-resistant CRC32 hash for a texture
    based on its pixel payload, dimensions, and color format.
    """
    # Header salt incorporates dimensions and format to prevent collision between identical sub-blocks
    header_salt = f"TEX:{width}x{height}:{fmt.value}:".encode("ascii")
    combined = header_salt + data
    # Unsigned 32-bit CRC32
    return zlib.crc32(combined) & 0xFFFFFFFF


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

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["format"] = self.format.value
        d["crc32_hex"] = f"0x{self.crc32:08X}"
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TextureMetadata":
        crc32_val = data.get("crc32")
        if isinstance(crc32_val, str) and crc32_val.startswith("0x"):
            crc32_val = int(crc32_val, 16)
        fmt = TextureFormat(data.get("format", TextureFormat.RGBA8888.value))
        return cls(
            crc32=int(crc32_val or 0),
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
        scale_x = width / max(1, orig_width)
        scale_y = height / max(1, orig_height)
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
        if not os.path.exists(pack_dir):
            return 0

        loaded_count = 0
        manifest_path = os.path.join(pack_dir, "texture_pack.json")

        if os.path.isfile(manifest_path):
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    manifest = json.load(f)
                textures = manifest.get("textures", [])
                for item in textures:
                    crc_str = item.get("crc32")
                    if isinstance(crc_str, str):
                        crc = int(crc_str, 16) if crc_str.startswith("0x") else int(crc_str)
                    else:
                        crc = int(crc_str or 0)
                    rel_path = item.get("file", f"tex_{crc:08X}.png")
                    full_path = os.path.join(pack_dir, rel_path)
                    meta = TextureMetadata(
                        crc32=crc,
                        width=int(item.get("width", 0)),
                        height=int(item.get("height", 0)),
                        format=TextureFormat(item.get("format", TextureFormat.RGBA8888.value)),
                        data_size=int(item.get("size", 0)),
                        scale_factor=float(item.get("scale", 1.0)),
                        file_path=full_path,
                        name=item.get("name", os.path.basename(rel_path))
                    )
                    self.replacements[crc] = meta
                    loaded_count += 1
            except Exception:
                pass

        # Also discover loose files matching tex_<CRC32>.(png|bin|dds)
        for fname in os.listdir(pack_dir):
            if fname.startswith("tex_") and ("." in fname):
                parts = fname.split(".")
                crc_part = parts[0].replace("tex_", "")
                try:
                    crc = int(crc_part, 16)
                    if crc not in self.replacements:
                        full_path = os.path.join(pack_dir, fname)
                        self.replacements[crc] = TextureMetadata(
                            crc32=crc,
                            width=0,
                            height=0,
                            format=TextureFormat.RGBA8888,
                            data_size=os.path.getsize(full_path),
                            scale_factor=1.0,
                            file_path=full_path,
                            name=fname
                        )
                        loaded_count += 1
                except ValueError:
                    continue

        return loaded_count

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

        for crc, meta in self.replacements.items():
            path_str = meta.file_path.replace("\\", "/") if meta.file_path else ""
            lines.append(
                f'    {{ 0x{crc:08X}, {meta.width}, {meta.height}, {meta.scale_factor:.2f}f, "{path_str}" }},'
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
