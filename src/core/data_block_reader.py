#!/usr/bin/env python3
"""
Unified Data Block Reader
Translates virtual console addresses to ROM file offsets.
"""

import os
import struct
from abc import ABC, abstractmethod
from typing import Optional, Union

class DataBlockReader(ABC):
    def __init__(self, rom_path: str):
        self.rom_path = rom_path
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

    def __del__(self):
        if getattr(self, '_file', None) is not None:
            try:
                self._file.close()
            except Exception:
                pass

    @abstractmethod
    def vram_to_offset(self, vram_addr: int) -> Optional[int]:
        pass

    def read_bytes(self, vram_addr: int, size: int) -> bytes:
        off = self.vram_to_offset(vram_addr)
        if off is None or off + size > self.file_size:
            return b""
        if self._file is not None:
            self._file.seek(off)
            return self._file.read(size)
        return self.data[off:off+size]

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
        if 0x08000000 <= vram < 0x0A000000:
            off = vram & 0x01FFFFFF
            return off if off < self.file_size else None
        return None

class SnesLoRomReader(DataBlockReader):
    def vram_to_offset(self, vram: int) -> Optional[int]:
        bank = (vram >> 16) & 0xFF
        addr = vram & 0xFFFF
        if addr < 0x8000: return None
        off = (bank * 0x8000) + (addr - 0x8000)
        return off if off < self.file_size else None

class Ps1Reader(DataBlockReader):
    def __init__(self, rom_path: str):
        super().__init__(rom_path)
        psx_idx = self.data.find(b"PS-X EXE")
        if psx_idx != -1 and len(self.data) >= psx_idx + 0x40:
            hdr = self.data[psx_idx:psx_idx+2048]
            self.text_vram = struct.unpack("<I", hdr[0x18:0x1C])[0]
            self.text_size = struct.unpack("<I", hdr[0x1C:0x20])[0]
            self.is_raw_cd = (psx_idx >= 24 and (psx_idx - 24) % 2352 == 0)
            self.sector_size = 2352 if self.is_raw_cd else 2048
            self.text_sector_start = (psx_idx // self.sector_size) + 1
        else:
            self.text_vram = 0x80010000
            self.text_size = self.file_size
            self.is_raw_cd = False
            self.sector_size = 2048
            self.text_sector_start = 0

    def vram_to_offset(self, vram: int) -> Optional[int]:
        if self.text_vram <= vram < self.text_vram + self.text_size:
            rel = vram - self.text_vram
            sec_idx = rel // 2048
            sec_off = rel % 2048
            user_offset = 24 if self.is_raw_cd else 0
            file_off = (self.text_sector_start + sec_idx) * self.sector_size + user_offset + sec_off
            return file_off if file_off < self.file_size else None
        return None

def create_block_reader(rom_path: str) -> DataBlockReader:
    ext = os.path.splitext(rom_path)[1].lower()
    if ext == '.gba': return GbaReader(rom_path)
    if ext == '.sfc': return SnesLoRomReader(rom_path)
    if ext in ('.bin', '.iso', '.exe'): return Ps1Reader(rom_path)
    # Default to linear
    return GbaReader(rom_path)
