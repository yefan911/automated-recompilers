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


def test_snes_lifter_transfers_and_flags():
    # TAX ($AA), TAY ($A8), TXA ($8A), TYA ($98), TSX ($BA), TXS ($9A)
    # CLC ($18), SEC ($38), CLI ($58), SEI ($78), CLD ($D8), SED ($F8), CLV ($B8), RTS ($60)
    code = bytes([
        0xAA, 0xA8, 0x8A, 0x98, 0xBA, 0x9A,
        0x18, 0x38, 0x58, 0x78, 0xD8, 0xF8, 0xB8,
        0x60
    ])
    rom = create_dummy_lorom(code, entry_pc=0x8000)
    lifter = SnesLifter(rom, is_lorom=True)
    ir_ops, targets, _ = lifter.lift_block(start_bank=0x00, start_pc=0x8000, start_p=0x30)

    ops = [op["op"] for op in ir_ops]
    assert "TAX" in ops
    assert "TAY" in ops
    assert "TXA" in ops
    assert "TYA" in ops
    assert "TSX" in ops
    assert "TXS" in ops
    assert "CLC" in ops
    assert "SEC" in ops
    assert "CLI" in ops
    assert "SEI" in ops
    assert "CLD" in ops
    assert "SED" in ops
    assert "CLV" in ops
    assert "RTS" in ops


def test_snes_lifter_increments_shifts_bitwise():
    # INX ($E8), DEX ($CA), INY ($C8), DEY ($88), INC ($1A), DEC ($3A)
    # ASL ($0A), LSR ($4A), ROL ($2A), ROR ($6A)
    # AND #$0F ($29 $0F), ORA #$F0 ($09 $F0), EOR #$55 ($49 $55), BIT #$80 ($89 $80)
    # RTS ($60)
    code = bytes([
        0xE8, 0xCA, 0xC8, 0x88, 0x1A, 0x3A,
        0x0A, 0x4A, 0x2A, 0x6A,
        0x29, 0x0F,
        0x09, 0xF0,
        0x49, 0x55,
        0x89, 0x80,
        0x60
    ])
    rom = create_dummy_lorom(code, entry_pc=0x8000)
    lifter = SnesLifter(rom, is_lorom=True)
    ir_ops, _, _ = lifter.lift_block(start_bank=0x00, start_pc=0x8000, start_p=0x30)

    ops = [op["op"] for op in ir_ops]
    assert "INX" in ops
    assert "DEX" in ops
    assert "INY" in ops
    assert "DEY" in ops
    assert "INC" in ops
    assert "DEC" in ops
    assert "ASL" in ops
    assert "LSR" in ops
    assert "ROL" in ops
    assert "ROR" in ops
    assert "AND" in ops
    assert "ORA" in ops
    assert "EOR" in ops
    assert "BIT" in ops


def test_snes_lifter_stack_and_brl():
    # PHX ($DA), PLX ($FA), PHY ($5A), PLY ($7A), PHP ($08), PLP ($28), PEA $1234 ($F4 $34 $12)
    # BRL +$0004 ($82 $04 $00)
    code = bytes([
        0xDA, 0xFA, 0x5A, 0x7A, 0x08, 0x28,
        0xF4, 0x34, 0x12,
        0x82, 0x04, 0x00,
        0xEA, 0xEA, 0xEA, 0xEA,
        0x60
    ])
    rom = create_dummy_lorom(code, entry_pc=0x8000)
    lifter = SnesLifter(rom, is_lorom=True)
    ir_ops, targets, _ = lifter.lift_block(start_bank=0x00, start_pc=0x8000, start_p=0x30)

    ops = [op["op"] for op in ir_ops]
    assert "PHX" in ops
    assert "PLX" in ops
    assert "PHY" in ops
    assert "PLY" in ops
    assert "PHP" in ops
    assert "PLP" in ops
    assert "PEA" in ops
    assert "BRL" in ops
    assert len(targets) == 1
    # BRL target: next_pc (0x8000 + 12 = 0x800C) + 4 = 0x8010
    assert 0x008010 in targets


def test_snes_lifter_index_comparisons():
    # CPX #$10 ($E0 $10), CPY #$20 ($C0 $20), RTS ($60)
    code = bytes([
        0xE0, 0x10,
        0xC0, 0x20,
        0x60
    ])
    rom = create_dummy_lorom(code, entry_pc=0x8000)
    lifter = SnesLifter(rom, is_lorom=True)
    ir_ops, _, _ = lifter.lift_block(start_bank=0x00, start_pc=0x8000, start_p=0x30)

    ops = [op["op"] for op in ir_ops]
    assert "CPX" in ops
    assert "CPY" in ops

