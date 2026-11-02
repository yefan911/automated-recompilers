#!/usr/bin/env python3
"""
Multi-Console Test ROM Generator
Generates clean, synthetic, legal homebrew test ROMs for all supported consoles:
- Game Boy Advance (GBA): ARM7TDMI + Thumb-16 Mode 3 display test
- Nintendo 64 (N64): Big-endian .z64 MIPS III with header, CRC, entry code
- Super Nintendo (SNES): 16-bit 65816 LoROM with header, reset vector, native mode
- Nintendo Entertainment System (NES): iNES format with PRG/CHR ROM and 6502 code
"""

import os
import sys
import struct
import argparse

NINTENDO_GBA_LOGO = bytes([
    0x24, 0xFF, 0xAE, 0x51, 0x69, 0x9A, 0xA2, 0x21, 0x3D, 0x84, 0x82, 0x0A, 0x84, 0xE4, 0x09, 0xAD,
    0x11, 0x24, 0x8B, 0x98, 0xC0, 0x81, 0x7F, 0x21, 0xA3, 0x52, 0xBE, 0x19, 0x93, 0x09, 0xCE, 0x22,
    0x41, 0xE2, 0xF8, 0x14, 0x85, 0xB1, 0xFE, 0x45, 0x8E, 0x7E, 0x5F, 0x0D, 0xFE, 0xDF, 0xCA, 0x53,
    0x41, 0x8F, 0xE8, 0x5C, 0x9B, 0xC4, 0x65, 0x40, 0x00, 0x84, 0x4F, 0x99, 0xB0, 0x18, 0x9B, 0x6C,
    0x87, 0xFA, 0x00, 0x54, 0x8F, 0x06, 0xEB, 0x4C, 0x64, 0xA1, 0xE0, 0xA2, 0x8F, 0xCA, 0x83, 0x4D,
    0x4C, 0x60, 0x72, 0xB4, 0x22, 0x3E, 0xD4, 0x08, 0xCE, 0x4A, 0xC9, 0xC6, 0xDB, 0x65, 0x8D, 0x21,
    0x94, 0x04, 0xB4, 0x09, 0x40, 0x85, 0x1D, 0x82, 0x45, 0x14, 0x50, 0x01, 0x45, 0x6E, 0x13, 0xAC,
    0x2D, 0xA5, 0x1A, 0xC6, 0xCA, 0x4E, 0xA9, 0xB6, 0x47, 0x0E, 0xB4, 0x54, 0xB7, 0x4A, 0x7C, 0x25,
    0xD7, 0x43, 0x5C, 0x13, 0x79, 0x47, 0x35, 0xD3, 0x16, 0xA4, 0x8A, 0x42, 0x73, 0x2C, 0xA3, 0x25,
    0xB0, 0x42, 0x70, 0xA7, 0x26, 0x43, 0x5F, 0x12
])


def create_enhanced_gba_rom(output_path: str = "roms/test/hello_gba.gba") -> str:
    """Generates a standalone, valid GBA ROM with ARM/Thumb execution and Mode 3 rendering."""
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    rom = bytearray(0x400) # 1024 bytes ROM

    # 1. Branch to 0x080000C0
    rom[0x00:0x04] = struct.pack("<I", 0xEA00002E)

    # 2. Header
    rom[0x04:0x04 + len(NINTENDO_GBA_LOGO)] = NINTENDO_GBA_LOGO
    rom[0xA0:0xAC] = b"TEST RECOMP\x00"
    rom[0xAC:0xB0] = b"TREC"
    rom[0xB0:0xB2] = b"01"
    rom[0xB2] = 0x96
    rom[0xB3] = 0x00
    rom[0xB4] = 0x00
    rom[0xBC] = 0x00

    chk = 0
    for b in rom[0xA0:0xBD]:
        chk = (chk - b) & 0xFF
    chk = (chk - 0x19) & 0xFF
    rom[0xBD] = chk

    # 3. Main Routine starting at 0x080000C0
    main_code = [
        0xE3A00404,  # mov r0, #0x04000000 (REG_DISPCNT address)
        0xE59F1020,  # ldr r1, [pc, #32] -> from 0xC4 to 0xEC
        0xE1C010B0,  # strh r1, [r0]
        0xEB00000B,  # bl 0x08000100 (draw_pattern)
        0xEAFFFFFE,  # spin: b spin
    ]

    for i, instr in enumerate(main_code):
        rom[0xC0 + i*4 : 0xC4 + i*4] = struct.pack("<I", instr)

    rom[0xEC:0xF0] = struct.pack("<I", 0x00000403) # Mode 3 | BG2 Enable

    # 4. Subroutine draw_pattern at 0x08000100
    sub_code = [
        0xE3A00406,  # 0x100: mov r0, #0x06000000 (VRAM pointer)
        0xE59F101C,  # 0x104: ldr r1, [pc, #28] -> from 0x104 to 0x128
        0xE3A0201F,  # 0x108: mov r2, #0x001F (Color: Red)
        0xE1C020B0,  # 0x10C: strh r2, [r0]
        0xE2800002,  # 0x110: add r0, r0, #2
        0xE2822001,  # 0x114: add r2, r2, #1
        0xE2511001,  # 0x118: subs r1, r1, #1
        0x1AFFFFFA,  # 0x11C: bne 0x0800010C
        0xE12FFF1E,  # 0x120: bx lr (return)
    ]

    for i, instr in enumerate(sub_code):
        rom[0x100 + i*4 : 0x104 + i*4] = struct.pack("<I", instr)

    rom[0x128:0x12C] = struct.pack("<I", 2400) # 2400 pixels

    with open(output_path, "wb") as f:
        f.write(rom)
    print(f"Generated GBA test ROM at {output_path} ({len(rom)} bytes)")
    return output_path


def create_n64_test_rom(output_path: str = "roms/test/hello_n64.z64") -> str:
    """Generates a standalone, valid Big-Endian N64 (.z64) ROM with header and MIPS code."""
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    rom = bytearray(65536) # 64 KB ROM

    # 1. Header (0x00 - 0x40)
    rom[0x00:0x04] = b'\x80\x37\x12\x40' # Magic Big-Endian .z64
    struct.pack_into(">I", rom, 0x08, 0x80000400) # Entry point VRAM
    struct.pack_into(">I", rom, 0x10, 0x12345678) # CRC1
    struct.pack_into(">I", rom, 0x14, 0x87654321) # CRC2
    rom[0x20:0x2E] = b"HELLO N64 TEST"
    rom[0x3B] = ord('N') # Media format
    rom[0x3C:0x3E] = b"HN" # Cart ID
    rom[0x3E] = ord('E') # Country code

    # 2. Main Entry Code at offset 0x1000 (loads at 0x80000400)
    instructions = [
        0x3C080400, # 0x80000400: lui $t0, 0x0400
        0x35080000, # 0x80000404: ori $t0, $t0, 0x0000
        0x2404002A, # 0x80000408: addiu $a0, $zero, 42
        0xAD040000, # 0x8000040C: sw $a0, 0($t0)
        0x0C000108, # 0x80000410: jal 0x80000420 (call subroutine)
        0x00000000, # 0x80000414: nop (delay slot)
        0x1000FFFF, # 0x80000418: b 0x80000418 (spin halt)
        0x00000000, # 0x8000041C: nop (delay slot)
        # Subroutine at 0x80000420:
        0x24020001, # 0x80000420: addiu $v0, $zero, 1
        0x03E00008, # 0x80000424: jr $ra
        0x00000000, # 0x80000428: nop (delay slot)
    ]

    for i, ins in enumerate(instructions):
        struct.pack_into(">I", rom, 0x1000 + i*4, ins)

    with open(output_path, "wb") as f:
        f.write(rom)
    print(f"Generated N64 test ROM at {output_path} ({len(rom)} bytes)")
    return output_path


def create_snes_test_rom(output_path: str = "roms/test/hello_snes.sfc") -> str:
    """Generates a standalone, valid 65816 LoROM SNES (.sfc) ROM with internal header and vectors."""
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    rom = bytearray(65536) # 64 KB ROM

    # 1. Internal LoROM Header at 0x7FC0
    rom[0x7FC0:0x7FD5] = b"HELLO SNES TEST      " # 21-char Title
    rom[0x7FD5] = 0x20 # LoROM 2.68MHz
    rom[0x7FD6] = 0x00 # ROM only
    rom[0x7FD7] = 0x08 # Size (256 KB indicator)
    rom[0x7FD8] = 0x00 # SRAM size
    rom[0x7FD9] = 0x01 # North America
    rom[0x7FDA] = 0x01 # Developer ID
    rom[0x7FDB] = 0x00 # Version
    struct.pack_into("<H", rom, 0x7FDC, 0x55AA) # Checksum complement
    struct.pack_into("<H", rom, 0x7FDE, 0xAA55) # Checksum

    # Emulation mode Reset vector at 0x7FFC (Points to 0x8000 in Bank 00 -> offset 0x0000)
    struct.pack_into("<H", rom, 0x7FFC, 0x8000)

    # 2. Executable 65816 Code at offset 0x0000 (VRAM 0x008000)
    code = bytes([
        0x78,             # 0x8000: SEI (Disable interrupts)
        0x18,             # 0x8001: CLC (Clear carry)
        0xFB,             # 0x8002: XCE (Exchange carry with emulation flag -> 16-bit native mode)
        0xC2, 0x30,       # 0x8003: REP #$30 (16-bit Accumulator & Index registers)
        0xA9, 0x34, 0x12, # 0x8005: LDA #$1234
        0x8D, 0x00, 0x20, # 0x8008: STA $2000
        0xA2, 0x78, 0x56, # 0x800B: LDX #$5678
        0x8E, 0x02, 0x20, # 0x800E: STX $2002
        0x20, 0x17, 0x80, # 0x8011: JSR $8017 (Call subroutine)
        0x80, 0xFE,       # 0x8014: BRA $8014 (Spin halt)
        0xEA,             # 0x8016: NOP
        # Subroutine at 0x8017 (offset 0x0017):
        0xE8,             # 0x8017: INX
        0x60,             # 0x8018: RTS
    ])
    rom[0:len(code)] = code

    with open(output_path, "wb") as f:
        f.write(rom)
    print(f"Generated SNES test ROM at {output_path} ({len(rom)} bytes)")
    return output_path


def create_nes_test_rom(output_path: str = "roms/test/hello_nes.nes") -> str:
    """Generates a standalone, valid iNES 1.0 (.nes) ROM with 32KB PRG, 8KB CHR, and 6502 code."""
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    # 1. 16-byte iNES Header
    header = bytearray(16)
    header[0:4] = b"NES\x1a"
    header[4] = 2    # 2 x 16KB PRG ROM = 32KB
    header[5] = 1    # 1 x 8KB CHR ROM = 8KB
    header[6] = 0x01 # Vertical mirroring, Mapper 0 (NROM)
    header[7] = 0x00 # Mapper 0 higher nibble

    # 2. 32KB PRG ROM ($8000 - $FFFF)
    prg = bytearray(32768)
    code = bytes([
        0x78,             # 0x8000: SEI (Disable interrupts)
        0xD8,             # 0x8001: CLD (Clear decimal mode)
        0xA2, 0xFF,       # 0x8002: LDX #$FF (Init stack)
        0x9A,             # 0x8004: TXS
        0xA9, 0x00,       # 0x8005: LDA #$00
        0x8D, 0x00, 0x20, # 0x8007: STA $2000 (PPU Control)
        0x8D, 0x01, 0x20, # 0x800A: STA $2001 (PPU Mask)
        0x4C, 0x0D, 0x80, # 0x800D: JMP $800D (Spin halt)
    ])
    prg[0:len(code)] = code

    # Reset vector at offset 0x7FFC in 32KB PRG (maps to $FFFC in CPU address space)
    struct.pack_into("<H", prg, 0x7FFC, 0x8000)

    # 3. 8KB CHR ROM
    chr_rom = bytearray(8192)

    rom = header + prg + chr_rom
    with open(output_path, "wb") as f:
        f.write(rom)
    print(f"Generated NES test ROM at {output_path} ({len(rom)} bytes)")
    return output_path


def create_all_test_roms(test_dir: str = "roms/test"):
    """Generates test ROMs for all supported consoles except PS1."""
    os.makedirs(test_dir, exist_ok=True)
    paths = {
        "gba": create_enhanced_gba_rom(os.path.join(test_dir, "hello_gba.gba")),
        "n64": create_n64_test_rom(os.path.join(test_dir, "hello_n64.z64")),
        "snes": create_snes_test_rom(os.path.join(test_dir, "hello_snes.sfc")),
        "nes": create_nes_test_rom(os.path.join(test_dir, "hello_nes.nes")),
    }
    return paths


# Aliases for backwards compatibility
create_gba_test_rom = create_enhanced_gba_rom

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Multi-Console Test ROM Generator")
    parser.add_argument("--console", choices=["gba", "n64", "snes", "nes", "all"], default="all")
    parser.add_argument("--outdir", default="roms/test")
    args = parser.parse_args()

    if args.console == "all":
        create_all_test_roms(args.outdir)
    elif args.console == "gba":
        create_enhanced_gba_rom(os.path.join(args.outdir, "hello_gba.gba"))
    elif args.console == "n64":
        create_n64_test_rom(os.path.join(args.outdir, "hello_n64.z64"))
    elif args.console == "snes":
        create_snes_test_rom(os.path.join(args.outdir, "hello_snes.sfc"))
    elif args.console == "nes":
        create_nes_test_rom(os.path.join(args.outdir, "hello_nes.nes"))
