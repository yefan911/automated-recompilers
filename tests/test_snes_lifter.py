import os
import sys
import struct
import pytest

# Ensure project root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.lifter.snes_lifter import SnesLifter, lift_snes_rom_to_c


def create_dummy_lorom(code_bytes: bytes, entry_pc: int = 0x8000) -> bytes:
    """
    Creates a minimal 512KB LoROM buffer with code_bytes placed at entry_pc in Bank $00.
    Bank $00 Offset 0x8000 maps to physical ROM offset 0x0000.
    Header is at 0x7FC0. Reset vector at 0x7FFC.
    """
    rom = bytearray(0x80000)  # 512 KB
    # Place code at entry_pc offset (entry_pc - 0x8000 in physical ROM for Bank 0)
    start_offset = entry_pc - 0x8000
    rom[start_offset:start_offset + len(code_bytes)] = code_bytes

    # Set reset vector at 0x7FFC in physical ROM
    struct.pack_into("<H", rom, 0x7FFC, entry_pc)
    return bytes(rom)


def test_lorom_address_mapping():
    lifter = SnesLifter(b"\x00" * 0x80000, is_lorom=True)
    # Bank 00, Offset 8000 -> ROM offset 0
    assert lifter.map_address_to_rom_offset(0x008000) == 0
    # Bank 00, Offset FFFF -> ROM offset 0x7FFF
    assert lifter.map_address_to_rom_offset(0x00FFFF) == 0x7FFF
    # Bank 01, Offset 8000 -> ROM offset 0x8000
    assert lifter.map_address_to_rom_offset(0x018000) == 0x8000
    # Bank 80 (mirror), Offset 8000 -> ROM offset 0
    assert lifter.map_address_to_rom_offset(0x808000) == 0


def test_snes_lifter_lda_sta_rep_sep():
    # Instructions:
    # REP #0x30 (C2 30) -> set 16-bit M and X
    # LDA #0x1234 (A9 34 12)
    # STA $2000 (8D 00 20)
    # SEP #0x30 (E2 30) -> set 8-bit M and X
    # LDA #0x56 (A9 56)
    # RTS (60)
    code = bytes([
        0xC2, 0x30,        # REP #0x30
        0xA9, 0x34, 0x12,  # LDA #0x1234 (16-bit)
        0x8D, 0x00, 0x20,  # STA $2000 (16-bit)
        0xE2, 0x30,        # SEP #0x30
        0xA9, 0x56,        # LDA #0x56 (8-bit)
        0x60               # RTS
    ])
    rom = create_dummy_lorom(code, entry_pc=0x8000)
    lifter = SnesLifter(rom, is_lorom=True)
    ir_ops, targets, final_p = lifter.lift_block(start_bank=0x00, start_pc=0x8000, start_p=0x30)

    assert len(ir_ops) == 6
    assert ir_ops[0]["op"] == "REP"
    assert ir_ops[1]["op"] == "LDA_IMM"
    assert "ctx->a = 0x1234;" in ir_ops[1]["c_code"]
    assert ir_ops[2]["op"] == "STA_ABS"
    assert "snes_write16" in ir_ops[2]["c_code"]
    assert ir_ops[3]["op"] == "SEP"
    assert ir_ops[4]["op"] == "LDA_IMM"
    assert "ctx->a = (ctx->a & 0xFF00) | 0x56;" in ir_ops[4]["c_code"]
    assert ir_ops[5]["op"] == "RTS"


def test_snes_lifter_branches():
    # Instructions:
    # BEQ +4 (F0 04) -> targets 0x8006, fallthrough 0x8002
    # NOP (EA)
    # NOP (EA)
    # RTS (60)
    code = bytes([
        0xF0, 0x04,  # BEQ +4 (target = 0x8002 + 4 = 0x8006)
        0xEA,        # NOP
        0xEA,        # NOP
        0xEA,        # NOP
        0xEA,        # NOP
        0x60         # RTS
    ])
    rom = create_dummy_lorom(code, entry_pc=0x8000)
    lifter = SnesLifter(rom, is_lorom=True)
    ir_ops, targets, _ = lifter.lift_block(start_bank=0x00, start_pc=0x8000, start_p=0x30)

    assert ir_ops[0]["op"] == "BEQ"
    assert 0x008006 in targets
    assert 0x008002 in targets


def test_snes_lifter_arithmetic():
    # ADC #0x10, SBC #0x05, CMP #0x20, RTS
    code = bytes([
        0x69, 0x10,  # ADC #0x10
        0xE9, 0x05,  # SBC #0x05
        0xC9, 0x20,  # CMP #0x20
        0x60         # RTS
    ])
    rom = create_dummy_lorom(code, entry_pc=0x8000)
    lifter = SnesLifter(rom, is_lorom=True)
    ir_ops, targets, _ = lifter.lift_block(start_bank=0x00, start_pc=0x8000, start_p=0x30)

    assert ir_ops[0]["op"] == "ADC_IMM"
    assert ir_ops[1]["op"] == "SBC_IMM"
    assert ir_ops[2]["op"] == "CMP_IMM"


def test_lift_snes_rom_to_c(tmp_path):
    code = bytes([
        0xA9, 0x42,  # LDA #0x42
        0x85, 0x10,  # STA $10 (ZP)
        0x60         # RTS
    ])
    rom_bytes = create_dummy_lorom(code, entry_pc=0x8000)
    rom_path = str(tmp_path / "test.sfc")
    with open(rom_path, "wb") as f:
        f.write(rom_bytes)

    c_code = lift_snes_rom_to_c(rom_path, max_blocks=10)
    assert "SnesCpuContext" in c_code
    assert "bb_008000" in c_code
    assert "snes_write8" in c_code
    assert "recomp_snes_dispatch" in c_code
