#!/usr/bin/env python3
"""
Test Suite: Nintendo 64 (N64) Console Target
Validates N64 ROM creation, header detection (.z64, .n64, .v64),
MIPS III instruction lifting, delay slot scheduling, and C code generation.
"""

import os
import sys
import struct
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.core.rom_detector import detect_n64, inspect_file
from src.core.create_test_rom import create_n64_test_rom
from src.lifter.mips_lifter import MipsLifter, lift_mips_rom_to_c
from src.core.native_compiler import compile_c_to_exe


def test_n64_rom_generation_and_detection(tmp_path):
    rom_file = str(tmp_path / "hello_n64.z64")
    out = create_n64_test_rom(rom_file)
    assert os.path.isfile(out)
    assert os.path.getsize(out) == 65536

    info = inspect_file(out)
    assert info is not None
    assert "Nintendo 64" in info["console"]
    assert "MIPS III" in info["architecture"]
    assert info["endianness"] == "Big-Endian (.z64)"
    assert info["entry_point"] == "0x80000400"
    assert info["crc1"] == "0x12345678"
    assert info["crc2"] == "0x87654321"
    assert info["title"] == "HELLO N64 TEST"


def test_n64_endian_variants_detection():
    # 1. Big-Endian (.z64)
    z64_hdr = bytearray(0x40)
    z64_hdr[0:4] = b'\x80\x37\x12\x40'
    struct.pack_into(">I", z64_hdr, 0x08, 0x80000400)
    res_z64 = detect_n64(bytes(z64_hdr))
    assert res_z64["endianness"] == "Big-Endian (.z64)"

    # 2. Byte-Swapped (.v64)
    v64_hdr = bytearray(0x40)
    v64_hdr[0:4] = b'\x37\x80\x40\x12'
    struct.pack_into(">I", v64_hdr, 0x08, 0x80000400)
    # Swap pairs for entry point
    v64_hdr[0x08], v64_hdr[0x09] = v64_hdr[0x09], v64_hdr[0x08]
    v64_hdr[0x0A], v64_hdr[0x0B] = v64_hdr[0x0B], v64_hdr[0x0A]
    res_v64 = detect_n64(bytes(v64_hdr))
    assert res_v64["endianness"] == "Byte-Swapped (.v64)"

    # 3. Little-Endian (.n64)
    n64_hdr = bytearray(0x40)
    n64_hdr[0:4] = b'\x40\x12\x37\x80'
    struct.pack_into("<I", n64_hdr, 0x08, 0x80000400)
    res_n64 = detect_n64(bytes(n64_hdr))
    assert res_n64["endianness"] == "Little-Endian (.n64)"


def test_n64_mips_instruction_and_delay_slot_lifting(tmp_path):
    rom_file = str(tmp_path / "hello_n64.z64")
    create_n64_test_rom(rom_file)

    with open(rom_file, "rb") as f:
        data = f.read()

    # Code loads at 0x80000400 with offset 0x1000
    base_vram = (0x80000400 - 0x1000) & 0xFFFFFFFF
    lifter = MipsLifter(data, base_vram=base_vram, is_big_endian=True)
    cfg = lifter.build_cfg(0x80000400)

    assert cfg.has_block(0x80000400)
    entry_block = cfg.get_block(0x80000400)
    assert len(entry_block.instructions) >= 4

    ops = [op.get("op") for op in entry_block.instructions]
    assert "INSN" in ops or "LUI" in ops or "ADDIU" in ops


def test_n64_c_code_emission_and_build(tmp_path):
    rom_file = str(tmp_path / "hello_n64.z64")
    create_n64_test_rom(rom_file)

    c_source = lift_mips_rom_to_c(rom_file)
    assert "MipsCpuContext" in c_source
    assert "mips_read32" in c_source
    assert "mips_write32" in c_source
    assert "recomp_mips_dispatch" in c_source

    out_c = str(tmp_path / "hello_n64_recompiled.c")
    with open(out_c, "w") as f:
        f.write(c_source)

    out_exe = str(tmp_path / "hello_n64.exe")
    compiled = compile_c_to_exe(out_c, out_exe)
    assert compiled is True
    assert os.path.isfile(out_exe)
