#!/usr/bin/env python3
"""
Universal Console ROM Detector & Header Analyzer
Part of Automated Recompiler Framework.

Detects console target, endianness, entry point, internal memory layout,
and header metadata across GBA, N64, PS1, NES, and SNES.
"""

import os
import sys
import struct
from typing import Dict, Any, Optional

GBA_LOGO_START = bytes([
    0x24, 0xFF, 0xAE, 0x51, 0x69, 0x9A, 0xA2, 0x21,
    0x3D, 0x84, 0x82, 0x0A, 0x84, 0xE4, 0x09, 0xAD
])


def detect_gba(data: bytes) -> Optional[Dict[str, Any]]:
    if len(data) < 0xC0:
        return None
    # GBA ROMs contain the Nintendo logo at 0x04..0x9F
    if data[0x04:0x14] == GBA_LOGO_START:
        title = data[0xA0:0xAC].decode('ascii', errors='ignore').strip('\x00').strip()
        game_code = data[0xAC:0xB0].decode('ascii', errors='ignore').strip('\x00').strip()
        maker_code = data[0xB0:0xB2].decode('ascii', errors='ignore').strip('\x00').strip()
        version = data[0xBC]
        checksum = data[0xBD]
        return {
            "console": "Game Boy Advance (GBA)",
            "architecture": "ARM7TDMI (32-bit ARM + 16-bit Thumb)",
            "endianness": "little",
            "entry_point": "0x08000000",
            "title": title,
            "game_code": game_code,
            "maker_code": maker_code,
            "version": version,
            "checksum": hex(checksum),
            "size_bytes": len(data),
            "rom_mapped_vram": "0x08000000",
        }
    return None


def detect_n64(data: bytes) -> Optional[Dict[str, Any]]:
    if len(data) < 0x40:
        return None
    magic = data[0:4]
    endian = None
    normalized_data = data

    if magic == b'\x80\x37\x12\x40':
        endian = "Big-Endian (.z64)"
    elif magic == b'\x40\x12\x37\x80':
        endian = "Little-Endian (.n64)"
        # Convert to big endian for parsing
        b = bytearray(data[:0x40])
        for i in range(0, len(b), 4):
            b[i:i+4] = b[i:i+4][::-1]
        normalized_data = bytes(b)
    elif magic == b'\x37\x80\x40\x12':
        endian = "Byte-Swapped (.v64)"
        b = bytearray(data[:0x40])
        for i in range(0, len(b), 2):
            b[i], b[i+1] = b[i+1], b[i]
        normalized_data = bytes(b)
    else:
        return None

    entry_point = struct.unpack(">I", normalized_data[0x08:0x0C])[0]
    crc1 = struct.unpack(">I", normalized_data[0x10:0x14])[0]
    crc2 = struct.unpack(">I", normalized_data[0x14:0x18])[0]
    title = normalized_data[0x20:0x34].decode('latin-1', errors='ignore').strip('\x00').strip()
    media_format = chr(normalized_data[0x3B]) if 32 <= normalized_data[0x3B] <= 126 else '?'
    cart_id = normalized_data[0x3C:0x3E].decode('latin-1', errors='ignore').strip()
    country_code = chr(normalized_data[0x3E]) if 32 <= normalized_data[0x3E] <= 126 else '?'

    return {
        "console": "Nintendo 64 (N64)",
        "architecture": "MIPS III (VR4300i 64-bit / 32-bit mode) + RSP",
        "endianness": endian,
        "entry_point": hex(entry_point),
        "crc1": hex(crc1),
        "crc2": hex(crc2),
        "title": title,
        "cart_id": cart_id,
        "country_code": country_code,
        "size_bytes": len(data),
    }


def detect_ps1(data: bytes) -> Optional[Dict[str, Any]]:
    # PS-X EXE direct format
    if data.startswith(b"PS-X EXE"):
        initial_pc = struct.unpack("<I", data[0x10:0x14])[0]
        text_vram = struct.unpack("<I", data[0x18:0x1C])[0]
        text_size = struct.unpack("<I", data[0x1C:0x20])[0]
        initial_sp = struct.unpack("<I", data[0x30:0x34])[0]
        marker = data[0x4C:0x60].decode('ascii', errors='ignore').strip('\x00').strip()
        return {
            "console": "Sony PlayStation 1 (PS-X EXE)",
            "architecture": "MIPS I (R3000A 32-bit + GTE Coprocessor 2)",
            "endianness": "little",
            "entry_point": hex(initial_pc),
            "text_vram": hex(text_vram),
            "text_size": text_size,
            "initial_sp": hex(initial_sp),
            "marker": marker,
            "size_bytes": len(data),
        }
    return None


def detect_nes(data: bytes) -> Optional[Dict[str, Any]]:
    if data.startswith(b"NES\x1a"):
        prg_rom_chunks = data[4]  # in 16KB units
        chr_rom_chunks = data[5]  # in 8KB units
        flags6 = data[6]
        flags7 = data[7]
        mapper = ((flags7 & 0xF0) | (flags6 >> 4))
        has_battery = bool(flags6 & 0x02)
        has_trainer = bool(flags6 & 0x04)
        mirroring = "Vertical" if (flags6 & 0x01) else "Horizontal"
        return {
            "console": "Nintendo Entertainment System (NES)",
            "architecture": "MOS 6502 (Ricoh 2A03/2A07)",
            "endianness": "little",
            "prg_rom_size_kb": prg_rom_chunks * 16,
            "chr_rom_size_kb": chr_rom_chunks * 8,
            "mapper_number": mapper,
            "has_battery": has_battery,
            "has_trainer": has_trainer,
            "mirroring": mirroring,
            "size_bytes": len(data),
        }
    return None


def inspect_file(filepath: str) -> Optional[Dict[str, Any]]:
    if not os.path.isfile(filepath):
        print(f"Error: file not found '{filepath}'")
        return None

    with open(filepath, "rb") as f:
        # Read up to first 2MB or entire file if smaller
        data = f.read()

    detectors = [detect_gba, detect_n64, detect_ps1, detect_nes]
    for detector in detectors:
        info = detector(data)
        if info:
            info["filename"] = os.path.basename(filepath)
            info["path"] = os.path.abspath(filepath)
            return info

    return {
        "filename": os.path.basename(filepath),
        "console": "Unknown or Raw Image",
        "size_bytes": len(data),
        "magic_hex": data[:16].hex(' '),
    }


def scan_roms_directory(rom_dir: str = "roms"):
    if not os.path.exists(rom_dir):
        print(f"Directory '{rom_dir}' does not exist.")
        return

    found = 0
    print(f"Scanning '{rom_dir}' for game ROMs...\n" + "=" * 60)
    for root, _, files in os.walk(rom_dir):
        for file in files:
            if file == ".gitkeep":
                continue
            full_path = os.path.join(root, file)
            info = inspect_file(full_path)
            if info:
                found += 1
                print(f"\n[FILE] {info.get('filename')}")
                for k, v in info.items():
                    if k not in ("filename", "path"):
                        print(f"  * {k.replace('_', ' ').title()}: {v}")
    print("=" * 60)
    if found == 0:
        print(f"No ROMs found in '{rom_dir}'. Place ROM files into 'roms/gba', 'roms/n64', etc.")
    else:
        print(f"Total ROMs detected: {found}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        result = inspect_file(sys.argv[1])
        if result:
            for k, v in result.items():
                print(f"{k}: {v}")
    else:
        scan_roms_directory()
