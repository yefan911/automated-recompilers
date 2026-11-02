#!/usr/bin/env python3
"""
Test Suite: Game Boy Advance (GBA) Console Target
Validates GBA ROM creation, header detection, ARM7TDMI/Thumb-16 lifting,
memory bus shims, BIOS SWI shims, and C code generation.
"""

import os
import sys
import struct
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.core.rom_detector import detect_gba, inspect_file
from src.core.create_test_rom import create_enhanced_gba_rom
from src.lifter.arm_lifter import ArmLifter, lift_rom_to_c
from src.lifter.thumb_lifter import ThumbLifter


def test_gba_rom_generation_and_detection(tmp_path):
    rom_file = str(tmp_path / "test_hello_gba.gba")
    out = create_enhanced_gba_rom(rom_file)
    assert os.path.isfile(out)
    assert os.path.getsize(out) == 1024

    info = inspect_file(out)
    assert info is not None
    assert "Game Boy Advance" in info["console"]
    assert info["architecture"] == "ARM7TDMI (32-bit ARM + 16-bit Thumb)"
    assert info["endianness"] == "little"
    assert info["entry_point"] == "0x08000000"
    assert info["title"] == "TEST RECOMP"
    assert info["game_code"] == "TREC"


def test_gba_arm_mode3_pattern_lifting(tmp_path):
    rom_file = str(tmp_path / "test_pattern.gba")
    create_enhanced_gba_rom(rom_file)
    with open(rom_file, "rb") as f:
        rom_data = f.read()

    lifter = ArmLifter(rom_data, base_vram=0x08000000)
    cfg = lifter.build_cfg(0x08000000)

    # Entry branch at 0x08000000 branches to 0x080000C0
    assert cfg.has_block(0x08000000)
    assert cfg.has_block(0x080000C0)
    assert cfg.has_block(0x08000100)

    # Subroutine 0x08000100 writes 2400 pixels
    b100 = cfg.get_block(0x08000100)
    ops = [op["op"] for op in b100.instructions]
    assert "MOV" in ops or "MOV_IMM" in ops
    assert "STRH" in ops
    assert "SUBS" in ops or "SUB" in ops


def test_gba_thumb_mode_interworking():
    # ARM block jumping to Thumb code via BX
    arm_bytes = bytearray(0x40)
    struct.pack_into("<I", arm_bytes, 0x00, 0xE59F1000) # ldr r1, [pc, #0] -> loads 0x08000011
    struct.pack_into("<I", arm_bytes, 0x04, 0xE12FFF11) # bx r1
    struct.pack_into("<I", arm_bytes, 0x08, 0x08000011) # Target address with bit 0 set
    struct.pack_into("<H", arm_bytes, 0x10, 0x202A)     # mov r0, #42
    struct.pack_into("<H", arm_bytes, 0x12, 0x4770)     # bx lr

    lifter = ArmLifter(bytes(arm_bytes), base_vram=0x08000000)
    cfg = lifter.build_cfg(0x08000000)

    assert cfg.has_block(0x08000000)
    assert cfg.has_block(0x08000010)


def test_gba_c_source_code_emission(tmp_path):
    rom_file = str(tmp_path / "hello.gba")
    create_enhanced_gba_rom(rom_file)

    c_source = lift_rom_to_c(rom_file)
    assert "typedef struct" in c_source
    assert "ArmCpuContext" in c_source
    assert "mem_read8" in c_source
    assert "mem_write8" in c_source
    assert "mem_read16" in c_source
    assert "mem_write16" in c_source
    assert "mem_read32" in c_source
    assert "mem_write32" in c_source
    assert "gba_bios_swi" in c_source
    assert "recomp_dispatch" in c_source
    assert "uint32_t bb_08000000(ArmCpuContext* ctx)" in c_source
