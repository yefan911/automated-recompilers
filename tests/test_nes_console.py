#!/usr/bin/env python3
"""
Test Suite: Nintendo Entertainment System (NES) Console Target
Validates iNES ROM creation, header detection, PRG/CHR ROM chunk parsing,
mapper decoding, and 6502 reset vector and instruction inspection.
"""

import os
import sys
import struct
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.core.rom_detector import detect_nes, inspect_file
from src.core.create_test_rom import create_nes_test_rom


def test_nes_rom_generation_and_detection(tmp_path):
    rom_file = str(tmp_path / "hello_nes.nes")
    out = create_nes_test_rom(rom_file)
    assert os.path.isfile(out)
    assert os.path.getsize(out) == 40976 # 16 header + 32768 PRG + 8192 CHR

    info = inspect_file(out)
    assert info is not None
    assert "Nintendo Entertainment System" in info["console"]
    assert "MOS 6502" in info["architecture"]
    assert info["endianness"] == "little"
    assert info["entry_point"] == "0x8000"
    assert info["prg_rom_size_kb"] == 32
    assert info["chr_rom_size_kb"] == 8
    assert info["mapper_number"] == 0
    assert info["mirroring"] == "Vertical"


def test_nes_ines_header_mapper_parsing():
    # Test Mapper 1 (MMC1) and Horizontal Mirroring
    header = bytearray(16)
    header[0:4] = b"NES\x1a"
    header[4] = 8   # 128KB PRG
    header[5] = 16  # 128KB CHR
    header[6] = 0x10 # Mapper low nibble = 1, Horizontal mirroring (bit 0 = 0)
    header[7] = 0x00 # Mapper high nibble = 0

    dummy_rom = bytes(header) + bytes(128 * 1024 + 128 * 1024)
    info = detect_nes(dummy_rom)
    assert info is not None
    assert info["mapper_number"] == 1
    assert info["mirroring"] == "Horizontal"
    assert info["prg_rom_size_kb"] == 128
    assert info["chr_rom_size_kb"] == 128


def test_nes_reset_vector_and_code_layout(tmp_path):
    rom_file = str(tmp_path / "hello_nes.nes")
    create_nes_test_rom(rom_file)

    with open(rom_file, "rb") as f:
        data = f.read()

    # 1. 16-byte header
    assert data[:4] == b"NES\x1a"

    # 2. Reset vector at offset 16 + 32768 - 4 = 32780
    reset_vector = struct.unpack("<H", data[32780:32782])[0]
    assert reset_vector == 0x8000

    # 3. First instruction at offset 16 (PRG start $8000) is SEI (0x78)
    assert data[16] == 0x78
    assert data[17] == 0xD8 # CLD
