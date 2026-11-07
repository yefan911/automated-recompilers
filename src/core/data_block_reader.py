#!/usr/bin/env python3
"""
Unified Data Block Reader
Translates virtual console addresses to ROM file offsets.
"""

import os
import struct
from abc import ABC, abstractmethod
from typing import Optional

from src.core.rom_detector import detect_n64, inspect_file


def snes_vram_to_offset(vram: int, file_size: int, mapping: str = "LoROM", copier_header_size: int = 0) -> Optional[int]:
    """Map SNES cartridge ROM addresses, excluding WRAM, IO, and SRAM windows."""
    if not 0 <= vram <= 0xFFFFFF or copier_header_size < 0:
        return None
    bank, addr = divmod(vram, 0x10000)
    if bank in (0x7E, 0x7F):
        return None
    if mapping == "LoROM":
        if addr < 0x8000 and not 0x40 <= (bank & 0x7F) <= 0x6F:
            return None
        offset = ((bank & 0x7F) << 15) | (addr & 0x7FFF)
    elif mapping in ("HiROM", "ExHiROM"):
        if (bank & 0x7F) < 0x40 and addr < 0x8000:
            return None
        offset = ((bank & 0x3F) << 16) | addr
        if mapping == "ExHiROM" and bank < 0x80:
            offset += 0x400000
    else:
        raise ValueError(f"Unsupported SNES ROM mapping: {mapping}")
    offset += copier_header_size
    return offset if copier_header_size <= offset < file_size else None


class DataBlockReader(ABC):
    def __init__(self, rom_path: str):
        self.rom_path = rom_path
        self._file = None
        self.file_size = os.path.getsize(rom_path)
        # For smaller ROMs (<= 16MB), cache in memory; for large CD images, read on demand
        if self.file_size <= 16 * 1024 * 1024:
            with open(rom_path, 'rb') as f:
                self.data = f.read()
            self._file = None
        else:
            with open(rom_path, 'rb') as f:
                self.data = f.read(131072)
            self._file = open(rom_path, 'rb')

    def close(self):
        if getattr(self, '_file', None) is not None:
            self._file.close()
            self._file = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass

    @abstractmethod
    def vram_to_offset(self, vram_addr: int) -> Optional[int]:
        pass

    def _read_at(self, off: int, size: int) -> bytes:
        if off < 0 or size < 0 or off + size > self.file_size:
            return b""
        if self._file is not None:
            self._file.seek(off)
            return self._file.read(size)
        return self.data[off:off+size]

    def read_bytes(self, vram_addr: int, size: int) -> bytes:
        if not isinstance(size, int) or size <= 0 or not isinstance(vram_addr, int) or vram_addr < 0:
            return b""
        off = self.vram_to_offset(vram_addr)
        last = self.vram_to_offset(vram_addr + size - 1)
        if off is None or last != off + size - 1:
            return b""
        return self._read_at(off, size)

    def read_u8(self, vram_addr: int) -> int:
        b = self.read_bytes(vram_addr, 1)
        return b[0] if b else 0

    def read_u16(self, vram_addr: int) -> int:
        b = self.read_bytes(vram_addr, 2)
        return struct.unpack("<H", b)[0] if len(b)==2 else 0

    def read_u32(self, vram_addr: int) -> int:
        b = self.read_bytes(vram_addr, 4)
        return struct.unpack("<I", b)[0] if len(b)==4 else 0

class GbaReader(DataBlockReader):
    def vram_to_offset(self, vram: int) -> Optional[int]:
        # GBA Game Pak ROM is mapped at 0x08000000..0x09FFFFFF,
        # with waitstate mirrors at 0x0A000000..0x0BFFFFFF and 0x0C000000..0x0DFFFFFF
        if 0x08000000 <= vram < 0x0E000000:
            off = vram & 0x01FFFFFF
            return off if off < self.file_size else None
        return None

class SnesLoRomReader(DataBlockReader):
    def __init__(self, rom_path: str, copier_header_size: int = None):
        super().__init__(rom_path)
        self.copier_header_size = (
            512 if self.file_size % 0x8000 == 512 else 0
        ) if copier_header_size is None else copier_header_size
        self.mapping = "LoROM"

    def vram_to_offset(self, vram: int) -> Optional[int]:
        return snes_vram_to_offset(vram, self.file_size, self.mapping, self.copier_header_size)

class SnesHiRomReader(SnesLoRomReader):
    def __init__(self, rom_path: str, copier_header_size: int = None, is_extended: bool = False):
        super().__init__(rom_path, copier_header_size)
        self.is_extended = is_extended
        self.mapping = "ExHiROM" if is_extended else "HiROM"

class Ps1Reader(DataBlockReader):
    def __init__(self, rom_path: str, info: dict = None):
        super().__init__(rom_path)
        info = inspect_file(rom_path) if info is None else info
        if not info or "PlayStation 1" not in info["console"]:
            self.close()
            raise ValueError("No valid PS-X EXE header found")
        self.text_vram = int(info["text_vram"], 16)
        self._text_physical = self.text_vram & 0x1FFFFFFF
        self.text_size = info["text_size"]
        self.entry_vram = int(info["entry_point"], 16)
        self.sector_size = info["sector_size"]
        self.user_offset = info["sector_user_offset"]
        self.is_raw_cd = self.sector_size == 2352
        self.text_sector_start = info["exe_offset"] // self.sector_size + 1
        if self.text_size:
            final_sector, final_within = divmod(self.text_size - 1, 2048)
            end = (self.text_sector_start + final_sector) * self.sector_size + self.user_offset + final_within + 1
            if end > self.file_size:
                self.close()
                raise ValueError("PS-X EXE payload is truncated")

    def vram_to_offset(self, vram: int) -> Optional[int]:
        if not 0 <= vram <= 0xFFFFFFFF or vram >> 29 not in (0, 4, 5):
            return None
        physical = vram & 0x1FFFFFFF
        if self._text_physical <= physical < self._text_physical + self.text_size:
            rel = physical - self._text_physical
            sec_idx = rel // 2048
            sec_off = rel % 2048
            file_off = (self.text_sector_start + sec_idx) * self.sector_size + self.user_offset + sec_off
            return file_off if file_off < self.file_size else None
        return None

    def read_bytes(self, vram_addr: int, size: int) -> bytes:
        if not isinstance(size, int) or size <= 0 or not isinstance(vram_addr, int):
            return b""
        if self.vram_to_offset(vram_addr) is None:
            return b""
        physical = vram_addr & 0x1FFFFFFF
        if physical + size > self._text_physical + self.text_size:
            return b""
        parts = []
        while size:
            within = ((vram_addr & 0x1FFFFFFF) - self._text_physical) % 2048
            amount = min(size, 2048 - within)
            off = self.vram_to_offset(vram_addr)
            part = self._read_at(off, amount)
            if len(part) != amount:
                return b""
            parts.append(part)
            vram_addr += amount
            size -= amount
        return b"".join(parts)

class N64Reader(DataBlockReader):
    def __init__(self, rom_path: str):
        super().__init__(rom_path)
        info = detect_n64(self.data)
        magic = self.data[:4]
        self.swap_unit = 4 if magic == b"\x40\x12\x37\x80" else 2 if magic == b"\x37\x80\x40\x12" else 1
        if info:
            ep = int(info["entry_point"], 16)
            code_offset = 0x1000 if self.file_size > 0x1000 else 0x400
            self.base_vram = (ep - code_offset) & 0xFFFFFFFF
        else:
            self.base_vram = 0x80000000

    def vram_to_offset(self, vram: int) -> Optional[int]:
        if not 0 <= vram <= 0xFFFFFFFF:
            return None
        if self.base_vram <= vram < self.base_vram + self.file_size:
            off = vram - self.base_vram
            return off if off < self.file_size else None
        # Cartridge domain: 0x10000000
        if 0x10000000 <= vram < 0x10000000 + self.file_size:
            off = vram - 0x10000000
            return off if off < self.file_size else None
        return None

    def read_bytes(self, vram_addr: int, size: int) -> bytes:
        if not isinstance(size, int) or size <= 0 or not isinstance(vram_addr, int):
            return b""
        off = self.vram_to_offset(vram_addr)
        if off is None or self.vram_to_offset(vram_addr + size - 1) != off + size - 1:
            return b""
        if self.swap_unit == 1:
            return self._read_at(off, size)
        start = off - off % self.swap_unit
        end = ((off + size + self.swap_unit - 1) // self.swap_unit) * self.swap_unit
        raw = self._read_at(start, end - start)
        if not raw:
            return b""
        normalized = b"".join(raw[pos:pos + self.swap_unit][::-1] for pos in range(0, len(raw), self.swap_unit))
        return normalized[off - start:off - start + size]

    def read_u16(self, vram_addr: int) -> int:
        data = self.read_bytes(vram_addr, 2)
        return struct.unpack(">H", data)[0] if len(data) == 2 else 0

    def read_u32(self, vram_addr: int) -> int:
        data = self.read_bytes(vram_addr, 4)
        return struct.unpack(">I", data)[0] if len(data) == 4 else 0

def create_block_reader(rom_path: str) -> DataBlockReader:
    ext = os.path.splitext(rom_path)[1].lower()
    info = inspect_file(rom_path) or {}
    console = info.get("console", "")
    if "Game Boy Advance" in console:
        return GbaReader(rom_path)
    if "Super Nintendo" in console or ext in ('.sfc', '.smc'):
        mapping = info.get("mapping", "LoROM")
        if mapping in ("HiROM", "ExHiROM"):
            return SnesHiRomReader(rom_path, info.get("copier_header_size"), mapping == "ExHiROM")
        return SnesLoRomReader(rom_path, info.get("copier_header_size"))
    if "Nintendo 64" in console or ext in ('.z64', '.n64', '.v64'):
        return N64Reader(rom_path)
    if "PlayStation 1" in console or ext in ('.bin', '.iso', '.exe'):
        return Ps1Reader(rom_path, info)
    # Default to linear
    return GbaReader(rom_path)
