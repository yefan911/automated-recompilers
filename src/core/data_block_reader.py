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
        with open(rom_path, 'rb') as f:
            self.data = f.read()

    @abstractmethod
    def vram_to_offset(self, vram_addr: int) -> Optional[int]:
        pass

    def read_bytes(self, vram_addr: int, size: int) -> bytes:
        off = self.vram_to_offset(vram_addr)
        if off is None or off + size > len(self.data):
            return b""
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
            return off if off < len(self.data) else None
        return None

class SnesLoRomReader(DataBlockReader):
    def vram_to_offset(self, vram: int) -> Optional[int]:
        bank = (vram >> 16) & 0xFF
        addr = vram & 0xFFFF
        if addr < 0x8000: return None
        off = (bank * 0x8000) + (addr - 0x8000)
        return off if off < len(self.data) else None

def create_block_reader(rom_path: str) -> DataBlockReader:
    ext = os.path.splitext(rom_path)[1].lower()
    if ext == '.gba': return GbaReader(rom_path)
    if ext == '.sfc': return SnesLoRomReader(rom_path)
    # Default to linear for now
    return GbaReader(rom_path)
