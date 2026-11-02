#!/usr/bin/env python3
"""
Test Suite: Super Nintendo Entertainment System (SNES) Console Target
Validates SNES LoROM creation, internal header parsing, 24-bit banked addressing,
65816 instruction lifting (native mode XCE, REP/SEP flags), and C code generation.
"""

import os
import sys
import struct
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.core.rom_detector import detect_snes, inspect_file
from src.core.create_test_rom import create_snes_test_rom
from src.lifter.snes_lifter import SnesLifter, lift_snes_rom_to_c
from src.core.native_compiler import compile_c_to_exe


def test_snes_rom_generation_and_detection(tmp_path):
    rom_file = str(tmp_path / "hello_snes.sfc")
    out = create_snes_test_rom(rom_file)
    assert os.path.isfile(out)
    assert os.path.getsize(out) == 65536

    info = inspect_file(out)
    assert info is not None
    assert "Super Nintendo" in info["console"]
    assert "65816" in info["architecture"]
    assert info["endianness"] == "little"
    assert info["entry_point"] == "0x8000"
    assert info["title"] == "HELLO SNES TEST"
    assert info["map_mode"] == "0x20"


def test_snes_lorom_address_translation():
    lifter = SnesLifter(b"\x00" * 65536, is_lorom=True)
    # Bank 00, Offset $8000 -> ROM offset 0
    assert lifter.map_address_to_rom_offset(0x008000) == 0
    # Bank 00, Offset $FFFF -> ROM offset $7FFF
    assert lifter.map_address_to_rom_offset(0x00FFFF) == 0x7FFF
    # Bank 01, Offset $8000 -> ROM offset $8000
    assert lifter.map_address_to_rom_offset(0x018000) == 0x8000


def test_snes_65816_instruction_lifting(tmp_path):
    rom_file = str(tmp_path / "hello_snes.sfc")
    create_snes_test_rom(rom_file)

    with open(rom_file, "rb") as f:
        rom_data = f.read()

    lifter = SnesLifter(rom_data, is_lorom=True)
    cfg = lifter.build_cfg(entry_bank=0x00, entry_pc=0x8000)

    # Basic block at 0x008000
    assert cfg.has_block(0x008000)
    b8000 = cfg.get_block(0x008000)
    ops = [op["op"] for op in b8000.instructions]

    assert "SEI" in ops
    assert "CLC" in ops
    assert "XCE" in ops
    assert "REP" in ops
    assert "LDA_IMM" in ops
    assert "STA_ABS" in ops


def test_snes_c_code_emission_and_build(tmp_path):
    rom_file = str(tmp_path / "hello_snes.sfc")
    create_snes_test_rom(rom_file)

    c_source = lift_snes_rom_to_c(rom_file)
    assert "SnesCpuContext" in c_source
    assert "snes_read8" in c_source
    assert "snes_write8" in c_source
    assert "snes_read16" in c_source
    assert "snes_write16" in c_source
    assert "recomp_snes_dispatch" in c_source
    assert "uint32_t bb_008000(SnesCpuContext* ctx)" in c_source

    out_c = str(tmp_path / "hello_snes_recompiled.c")
    with open(out_c, "w") as f:
        f.write(c_source)

    out_exe = str(tmp_path / "hello_snes.exe")
    compiled = compile_c_to_exe(out_c, out_exe)
    assert compiled is True
    assert os.path.isfile(out_exe)
