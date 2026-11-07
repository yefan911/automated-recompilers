#!/usr/bin/env python3
"""
Block Data Analyzer & Basic Block Disassembler
Part of the Automated Recompiler Framework.

Analyzes ROM files into structural blocks, computes entropy distribution
(Code vs Data detection), and disassembles Control Flow Graph (CFG) Basic Blocks.
"""

import os
import sys
import math
import struct
from typing import List, Dict, Any, Tuple, Optional
from collections import deque

from src.core.rom_detector import inspect_file
from src.core.data_block_reader import create_block_reader

# Ensure stdout handles UTF-8 on Windows
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# MIPS GPR Register Names
MIPS_REGS = [
    "$zero", "$at", "$v0", "$v1", "$a0", "$a1", "$a2", "$a3",
    "$t0", "$t1", "$t2", "$t3", "$t4", "$t5", "$t6", "$t7",
    "$s0", "$s1", "$s2", "$s3", "$s4", "$s5", "$s6", "$s7",
    "$t8", "$t9", "$k0", "$k1", "$gp", "$sp", "$fp", "$ra"
]

def shannon_entropy(data: bytes) -> float:
    """Calculates Shannon entropy (0.0 = uniform/empty, 8.0 = maximum randomness/compression)."""
    if not data:
        return 0.0
    freq = {}
    for b in data:
        freq[b] = freq.get(b, 0) + 1
    total = len(data)
    entropy = 0.0
    for count in freq.values():
        p = count / total
        entropy -= p * math.log2(p)
    return entropy

def decode_mips_instruction(raw: int, pc: int) -> Dict[str, Any]:
    """Decodes a single 32-bit MIPS R4300i instruction."""
    op = (raw >> 26) & 0x3F
    rs = (raw >> 21) & 0x1F
    rt = (raw >> 16) & 0x1F
    rd = (raw >> 11) & 0x1F
    shamt = (raw >> 6) & 0x1F
    funct = raw & 0x3F
    imm = raw & 0xFFFF
    simm = imm if imm < 0x8000 else imm - 0x10000
    target26 = raw & 0x03FFFFFF

    asm_text = f"unknown_0x{op:02X}"
    branch_target = None
    is_branch = False
    is_indirect = False
    is_call = False

    if op == 0x00:  # SPECIAL R-type
        if raw == 0:
            asm_text = "nop"
        elif funct == 0x08:  # JR
            asm_text = f"jr {MIPS_REGS[rs]}"
            is_branch = True
            is_indirect = True
        elif funct == 0x09:  # JALR
            asm_text = f"jalr {MIPS_REGS[rd]}, {MIPS_REGS[rs]}"
            is_branch = True
            is_indirect = True
            is_call = True
        elif funct == 0x20:
            asm_text = f"add {MIPS_REGS[rd]}, {MIPS_REGS[rs]}, {MIPS_REGS[rt]}"
        elif funct == 0x21:
            asm_text = f"addu {MIPS_REGS[rd]}, {MIPS_REGS[rs]}, {MIPS_REGS[rt]}"
        elif funct == 0x24:
            asm_text = f"and {MIPS_REGS[rd]}, {MIPS_REGS[rs]}, {MIPS_REGS[rt]}"
        elif funct == 0x25:
            asm_text = f"or {MIPS_REGS[rd]}, {MIPS_REGS[rs]}, {MIPS_REGS[rt]}"
        elif funct == 0x00:
            asm_text = f"sll {MIPS_REGS[rd]}, {MIPS_REGS[rt]}, {shamt}"
        elif funct == 0x02:
            asm_text = f"srl {MIPS_REGS[rd]}, {MIPS_REGS[rt]}, {shamt}"
        elif funct == 0x03:
            asm_text = f"sra {MIPS_REGS[rd]}, {MIPS_REGS[rt]}, {shamt}"
        else:
            asm_text = f"special_funct_0x{funct:02X} {MIPS_REGS[rd]}, {MIPS_REGS[rs]}, {MIPS_REGS[rt]}"

    elif op == 0x02:  # J
        branch_target = ((pc + 4) & 0xF0000000) | (target26 << 2)
        asm_text = f"j 0x{branch_target:08X}"
        is_branch = True

    elif op == 0x03:  # JAL
        branch_target = ((pc + 4) & 0xF0000000) | (target26 << 2)
        asm_text = f"jal 0x{branch_target:08X}"
        is_branch = True
        is_call = True

    elif op == 0x04:  # BEQ
        branch_target = pc + 4 + (simm << 2)
        asm_text = f"beq {MIPS_REGS[rs]}, {MIPS_REGS[rt]}, 0x{branch_target:08X}"
        is_branch = True

    elif op == 0x05:  # BNE
        branch_target = pc + 4 + (simm << 2)
        asm_text = f"bne {MIPS_REGS[rs]}, {MIPS_REGS[rt]}, 0x{branch_target:08X}"
        is_branch = True

    elif op == 0x08:  # ADDI
        asm_text = f"addi {MIPS_REGS[rt]}, {MIPS_REGS[rs]}, {simm}"
    elif op == 0x09:  # ADDIU
        asm_text = f"addiu {MIPS_REGS[rt]}, {MIPS_REGS[rs]}, {simm}"
    elif op == 0x0F:  # LUI
        asm_text = f"lui {MIPS_REGS[rt]}, 0x{imm:04X}"
    elif op == 0x0C:  # ANDI
        asm_text = f"andi {MIPS_REGS[rt]}, {MIPS_REGS[rs]}, 0x{imm:04X}"
    elif op == 0x0D:  # ORI
        asm_text = f"ori {MIPS_REGS[rt]}, {MIPS_REGS[rs]}, 0x{imm:04X}"
    elif op == 0x20:  # LB
        asm_text = f"lb {MIPS_REGS[rt]}, {simm}({MIPS_REGS[rs]})"
    elif op == 0x23:  # LW
        asm_text = f"lw {MIPS_REGS[rt]}, {simm}({MIPS_REGS[rs]})"
    elif op == 0x28:  # SB
        asm_text = f"sb {MIPS_REGS[rt]}, {simm}({MIPS_REGS[rs]})"
    elif op == 0x29:  # SH
        asm_text = f"sh {MIPS_REGS[rt]}, {simm}({MIPS_REGS[rs]})"
    elif op == 0x2B:  # SW
        asm_text = f"sw {MIPS_REGS[rt]}, {simm}({MIPS_REGS[rs]})"
    else:
        asm_text = f"op_0x{op:02X} {MIPS_REGS[rt]}, {simm}({MIPS_REGS[rs]})"

    return {
        "pc": pc,
        "raw": raw,
        "asm": asm_text,
        "is_branch": is_branch,
        "is_call": is_call,
        "is_indirect": is_indirect,
        "target": branch_target
    }

class BlockDataAnalyzer:
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.filename = os.path.basename(filepath)
        self.size = os.path.getsize(filepath)
        with open(filepath, "rb") as f:
            self.data = f.read(min(self.size, 16 * 1024 * 1024))
        self.total_bytes = self.size
        self.info = inspect_file(filepath) or {}
        console = self.info.get("console", "")
        self.is_n64 = "Nintendo 64" in console
        self.is_gba = "Game Boy Advance" in console
        self.is_ps1 = "PlayStation 1" in console
        self.is_snes = "Super Nintendo" in console
        self.entry_vram = int(self.info.get("entry_point") or "0", 16)
        self.reader = create_block_reader(filepath) if any((self.is_n64, self.is_gba, self.is_ps1, self.is_snes)) else None
        self.entry_rom_offset = self.reader.vram_to_offset(self.entry_vram) if self.reader else 0

    def close(self):
        if getattr(self, "reader", None) is not None:
            self.reader.close()

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass

    def _read_file_bytes(self, offset: int, length: int) -> bytes:
        if offset < 0 or length < 0 or offset > self.size:
            raise ValueError("ROM offset and length must describe a nonnegative file range")
        length = min(length, self.size - offset)
        if offset + length <= len(self.data):
            return self.data[offset:offset + length]
        with open(self.filepath, "rb") as stream:
            stream.seek(offset)
            return stream.read(length)

    def print_structural_blocks(self):
        """Displays the major architectural blocks in the ROM."""
        print(f"\n========================================================")
        print(f"  STRUCTURAL ROM BLOCK BREAKDOWN: {os.path.basename(self.filepath)}")
        print(f"  Total ROM Size: {self.size:,} bytes ({self.size / (1024*1024):.1f} MB)")
        print(f"========================================================")

        if self.is_n64 and len(self.data) >= 0x40:
            magic = self.data[:4]
            title = self.info["title"]
            entry_point = self.entry_vram
            crc1 = int(self.info["crc1"], 16)
            crc2 = int(self.info["crc2"], 16)

            print(f"\n[BLOCK 0] ROM Header (0x000000 - 0x00003F, 64 bytes)")
            print(f"  * Magic Endianness : {magic.hex(' ')} ({self.info['endianness']})")
            print(f"  * Internal Title   : \"{title}\"")
            print(f"  * Entry Vector VRAM: 0x{entry_point:08X}")
            print(f"  * Checksums (CRC)  : CRC1=0x{crc1:08X}, CRC2=0x{crc2:08X}")

            if len(self.data) >= 0x1000:
                ipl3_data = self.data[0x40:0x1000]
                ipl3_entropy = shannon_entropy(ipl3_data)
                print(f"\n[BLOCK 1] IPL3 Bootloader (0x000040 - 0x000FFF, 4,032 bytes)")
                print(f"  * Function         : Hardware initialization, CIC security check, memory DMA")
                print(f"  * Shannon Entropy  : {ipl3_entropy:.3f} bits/byte (High-density MIPS code)")

            if len(self.data) >= 0x2000:
                entry_code = self.data[0x1000:0x2000]
                entry_entropy = shannon_entropy(entry_code)
                print(f"\n[BLOCK 2] Main Code Entry Segment (0x001000+, loads at 0x{entry_point:08X})")
                print(f"  * Function         : BSS clear loop, OS initialization, main thread bootstrap")
                print(f"  * Shannon Entropy  : {entry_entropy:.3f} bits/byte (Executable MIPS Instructions)")

        elif self.is_gba and len(self.data) >= 0xC0:
            title = self.data[0xA0:0xAC].decode('ascii', errors='ignore').strip('\x00').strip()
            game_code = self.data[0xAC:0xB0].decode('ascii', errors='ignore').strip('\x00').strip()
            print(f"\n[BLOCK 0] GBA ROM Header (0x000000 - 0x0000BF, 192 bytes)")
            print(f"  * Architecture     : ARM7TDMI (32-bit ARM + 16-bit Thumb)")
            print(f"  * Internal Title   : \"{title}\"")
            print(f"  * Game Serial Code : \"{game_code}\"")
            print(f"  * Entry Vector VRAM: 0x08000000")
            header_entropy = shannon_entropy(self.data[:0xC0])
            print(f"  * Header Entropy   : {header_entropy:.3f} bits/byte")
        elif self.is_ps1 or self.is_snes:
            header_offset = self.info.get("exe_offset", self.info.get("header_offset", 0))
            print(f"\n[BLOCK 0] {self.info['console']} Header (ROM 0x{header_offset:06X})")
            print(f"  * Architecture     : {self.info['architecture']}")
            print(f"  * Internal Title   : \"{self.info.get('title', '')}\"")
            print(f"  * Entry Vector VRAM: 0x{self.entry_vram:08X}")
            if self.is_snes:
                print(f"  * ROM Mapping      : {self.info['mapping']}")
                print(f"  * Copier Header    : {self.info['copier_header_size']} bytes")
            else:
                print(f"  * Text Load Address: {self.info['text_vram']}")
                print(f"  * Text Length      : {self.info['text_size']} bytes")
        else:
            header_bytes = self.data[:min(64, self.size)]
            print(f"\n[BLOCK 0] Raw Image Header (First {len(header_bytes)} bytes)")
            print(f"  * Magic Hex        : {header_bytes[:16].hex(' ')}")
            print(f"  * Shannon Entropy  : {shannon_entropy(header_bytes):.3f} bits/byte")

    def inspect_hex_block(self, offset: int, length: int = 64):
        """Prints a detailed hex and ASCII view of a block of bytes."""
        chunk = self._read_file_bytes(offset, length)
        print(f"\n--- HEX BLOCK INSPECTION: Offset 0x{offset:06X} ({length} bytes) ---")
        for row in range(0, len(chunk), 16):
            row_bytes = chunk[row:row+16]
            hex_str = " ".join(f"{b:02X}" for b in row_bytes)
            ascii_str = "".join(chr(b) if 32 <= b <= 126 else "." for b in row_bytes)
            print(f"0x{offset + row:06X}  {hex_str:<48}  |{ascii_str}|")

    def disassemble_basic_blocks(self, rom_offset: Optional[int] = None, base_vram: Optional[int] = None, max_blocks: int = 4):
        """Inspect bounded basic blocks using the detected console and entry point."""
        if max_blocks <= 0 or rom_offset is not None and not 0 <= rom_offset < self.size:
            raise ValueError("A valid ROM offset and positive block count are required")
        rom_offset = self.entry_rom_offset if rom_offset is None else rom_offset
        base_vram = self.entry_vram if base_vram is None else base_vram
        print(f"\n========================================================")
        print(f"  CONTROL FLOW GRAPH (CFG): DISASSEMBLED BASIC BLOCKS")
        if rom_offset is None or self.reader is None:
            print("  No supported executable mapping was detected for this image.")
            return
        if self.reader.vram_to_offset(base_vram) != rom_offset:
            raise ValueError("ROM offset and CPU address refer to different locations")
        print(f"  {self.info['architecture']}")
        print(f"  Starting at ROM Offset 0x{rom_offset:06X} (VRAM 0x{base_vram:08X})")
        print(f"========================================================")
        if self.is_n64 or self.is_ps1:
            self._disassemble_mips(base_vram, max_blocks)
        else:
            self._disassemble_lifted(base_vram, max_blocks)

    def _disassemble_mips(self, entry: int, max_blocks: int):
        from src.lifter.mips_lifter import MipsLifter
        lifter = MipsLifter(b"")
        pending, seen = deque([entry]), set()
        while pending and len(seen) < max_blocks:
            pc = pending.popleft()
            if pc in seen or len(self.reader.read_bytes(pc, 4)) != 4:
                continue
            seen.add(pc)
            print(f"\n+-- [Basic Block #{len(seen)}] Entry: VRAM 0x{pc:08X} (ROM 0x{self.reader.vram_to_offset(pc):06X})")
            for _ in range(64):
                encoded = self.reader.read_bytes(pc, 4)
                if len(encoded) != 4:
                    break
                raw = int.from_bytes(encoded, "big" if self.is_n64 else "little")
                instr = lifter.lift_instruction(pc, raw)
                print(f"  |    0x{pc:08X}:  {raw:08X}    {instr['asm']}")
                if instr.get("is_branch") or instr.get("is_call"):
                    encoded = self.reader.read_bytes(pc + 4, 4)
                    if len(encoded) == 4:
                        delay_raw = int.from_bytes(encoded, "big" if self.is_n64 else "little")
                        delay = lifter.lift_instruction(pc + 4, delay_raw)
                        print(f"  \\--> 0x{pc + 4:08X}:  {delay_raw:08X}    {delay['asm']} [DELAY SLOT]")
                    pending.extend(instr.get("targets", []))
                    opcode = raw >> 26
                    if instr.get("is_call") or opcode in (1, 4, 5, 6, 7, 0x14, 0x15, 0x16, 0x17):
                        pending.append(pc + 8)
                    break
                pc += 4
            print(f"+-- End of Basic Block #{len(seen)}")

    def _disassemble_lifted(self, entry: int, max_blocks: int):
        if self.is_gba:
            from src.lifter.arm_lifter import ArmLifter
            from src.lifter.thumb_lifter import ThumbLifter
            arm, thumb = ArmLifter(self.data), ThumbLifter(self.data)
            arm.read_u32 = self.reader.read_u32
            arm.is_valid_vram = lambda pc: len(self.reader.read_bytes(pc, 4)) == 4
            thumb.read_u16, thumb.read_u32 = self.reader.read_u16, self.reader.read_u32
            thumb.is_valid_vram = lambda pc: len(self.reader.read_bytes(pc, 2)) == 2
        else:
            from src.lifter.snes_lifter import SnesLifter
            snes = SnesLifter(self.data, is_lorom=self.info["mapping"] == "LoROM")
            snes.read_u8 = self.reader.read_u8
            snes.is_valid_address = lambda pc: self.reader.vram_to_offset(pc) is not None
            snes.map_address_to_rom_offset = lambda pc: self.reader.vram_to_offset(pc) if self.reader.vram_to_offset(pc) is not None else -1
        pending, seen = deque([(entry, 0x30)]), set()
        while pending and len(seen) < max_blocks:
            encoded_pc, flags = pending.popleft()
            pc = encoded_pc & ~1 if self.is_gba else encoded_pc
            key = (encoded_pc, flags) if self.is_snes else encoded_pc
            off = self.reader.vram_to_offset(pc)
            if key in seen or off is None:
                continue
            seen.add(key)
            print(f"\n+-- [Basic Block #{len(seen)}] Entry: VRAM 0x{pc:08X} (ROM 0x{off:06X})")
            if self.is_gba:
                instructions, targets = (thumb if encoded_pc & 1 else arm).lift_block(pc)
            else:
                instructions, targets, flags = snes.lift_block(pc >> 16, pc & 0xFFFF, flags)
            for instr in instructions[:64]:
                code = " ".join(instr.get("c_code", "").split())
                print(f"  |    0x{instr.get('pc', pc):08X}:  {instr.get('op', '?'):<16} {code[:100]}")
            if len(instructions) > 64:
                print(f"  |    ... {len(instructions) - 64} further instructions omitted")
            pending.extend((target, flags) for target in targets)
            print(f"+-- End of Basic Block #{len(seen)}")

    def scan_entropy_map(self, chunk_size: int = 65536, max_chunks: int = 20):
        """Scans the ROM in chunks to classify code vs data vs compressed assets."""
        if chunk_size <= 0 or max_chunks < 0:
            raise ValueError("Chunk size must be positive and chunk count nonnegative")
        print(f"\n========================================================")
        print(f"  ROM ENTROPY MAP & DATA CLASSIFICATION (First {max_chunks} x {chunk_size//1024}KB Blocks)")
        print(f"========================================================")
        print(f"{'Block':<8} {'ROM Offset Range':<24} {'Entropy':<10} {'Classification'}")
        print("-" * 65)

        for i in range(min(max_chunks, (self.size + chunk_size - 1) // chunk_size)):
            start = i * chunk_size
            end = min(start + chunk_size, self.size)
            chunk = self._read_file_bytes(start, end - start)
            ent = shannon_entropy(chunk)

            # Classification heuristics
            if ent < 0.1:
                classif = "[EMPTY / PADDING] All zeros / repeated bytes"
            elif ent < 5.5:
                classif = "[CODE / TEXT] Uncompressed code & string tables"
            elif ent < 6.8:
                classif = "[STRUCTURED DATA] Matrices, palettes, audio samples"
            else:
                classif = "[COMPRESSED / ASSETS] High entropy textures & audio"

            bar = "#" * int(ent * 3)
            print(f"#{i:<7} 0x{start:06X} - 0x{end-1:06X}   {ent:5.2f}/8.0  {bar:<24} {classif}")


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "roms/n64/Yoshi.z64"
    if not os.path.exists(target):
        print(f"File not found: {target}")
        sys.exit(1)

    analyzer = BlockDataAnalyzer(target)
    # 1. Structural breakdown
    analyzer.print_structural_blocks()

    # 2. Hex block inspection at the detected entry point
    analyzer.inspect_hex_block(analyzer.entry_rom_offset or 0, 64)

    # 3. Disassemble basic blocks starting at entry point
    analyzer.disassemble_basic_blocks(max_blocks=3)

    # 4. Entropy analysis
    analyzer.scan_entropy_map(chunk_size=65536, max_chunks=16)
