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
from typing import List, Dict, Any, Tuple

# Ensure stdout handles UTF-8 on Windows
if sys.platform == "win32":
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
        with open(filepath, "rb") as f:
            self.data = f.read()
        self.size = len(self.data)

    def print_structural_blocks(self):
        """Displays the major architectural blocks in an N64 ROM."""
        print(f"\n========================================================")
        print(f"  STRUCTURAL ROM BLOCK BREAKDOWN: {os.path.basename(self.filepath)}")
        print(f"  Total ROM Size: {self.size:,} bytes ({self.size / (1024*1024):.1f} MB)")
        print(f"========================================================")

        # Block 1: Header (0x0000 - 0x0040)
        magic = self.data[:4]
        title = self.data[0x20:0x34].decode('latin-1', errors='ignore').strip('\x00').strip()
        entry_point = struct.unpack(">I", self.data[0x08:0x0C])[0]
        crc1 = struct.unpack(">I", self.data[0x10:0x14])[0]
        crc2 = struct.unpack(">I", self.data[0x14:0x18])[0]

        print(f"\n[BLOCK 0] ROM Header (0x000000 - 0x00003F, 64 bytes)")
        print(f"  * Magic Endianness : {magic.hex(' ')} (Big-Endian N64 .z64)")
        print(f"  * Internal Title   : \"{title}\"")
        print(f"  * Entry Vector VRAM: 0x{entry_point:08X}")
        print(f"  * Checksums (CRC)  : CRC1=0x{crc1:08X}, CRC2=0x{crc2:08X}")

        # Block 2: IPL3 Bootloader (0x0040 - 0x0FFF, 4,032 bytes)
        ipl3_data = self.data[0x40:0x1000]
        ipl3_entropy = shannon_entropy(ipl3_data)
        print(f"\n[BLOCK 1] IPL3 Bootloader (0x000040 - 0x000FFF, 4,032 bytes)")
        print(f"  * Function         : Hardware initialization, CIC security check, memory DMA")
        print(f"  * Shannon Entropy  : {ipl3_entropy:.3f} bits/byte (High-density MIPS code)")

        # Block 3: Main Program Entry Block (0x1000+)
        entry_code = self.data[0x1000:0x2000]
        entry_entropy = shannon_entropy(entry_code)
        print(f"\n[BLOCK 2] Main Code Entry Segment (0x001000+, loads at 0x{entry_point:08X})")
        print(f"  * Function         : BSS clear loop, OS initialization, main thread bootstrap")
        print(f"  * Shannon Entropy  : {entry_entropy:.3f} bits/byte (Executable MIPS Instructions)")

    def inspect_hex_block(self, offset: int, length: int = 64):
        """Prints a detailed hex and ASCII view of a block of bytes."""
        print(f"\n--- HEX BLOCK INSPECTION: Offset 0x{offset:06X} ({length} bytes) ---")
        end = min(offset + length, self.size)
        chunk = self.data[offset:end]
        for row in range(0, len(chunk), 16):
            row_bytes = chunk[row:row+16]
            hex_str = " ".join(f"{b:02X}" for b in row_bytes)
            ascii_str = "".join(chr(b) if 32 <= b <= 126 else "." for b in row_bytes)
            print(f"0x{offset + row:06X}  {hex_str:<48}  |{ascii_str}|")

    def disassemble_basic_blocks(self, rom_offset: int = 0x1000, base_vram: int = 0x80200400, max_blocks: int = 4):
        """
        Traces and disassembles basic blocks starting from the entry point.
        A basic block ends after a branch instruction and its delay slot.
        """
        print(f"\n========================================================")
        print(f"  CONTROL FLOW GRAPH (CFG): DISASSEMBLED BASIC BLOCKS")
        print(f"  Starting at ROM Offset 0x{rom_offset:06X} (VRAM 0x{base_vram:08X})")
        print(f"========================================================")

        curr_offset = rom_offset
        curr_vram = base_vram
        block_idx = 0

        while block_idx < max_blocks and curr_offset < self.size - 8:
            block_idx += 1
            print(f"\n+-- [Basic Block #{block_idx}] Entry: VRAM 0x{curr_vram:08X} (ROM 0x{curr_offset:06X})")

            in_delay_slot = False
            while curr_offset < self.size - 4:
                raw = struct.unpack(">I", self.data[curr_offset:curr_offset+4])[0]
                instr = decode_mips_instruction(raw, curr_vram)

                # Format instruction output
                marker = "  \\-->" if in_delay_slot else "  |   "
                tag = " [DELAY SLOT]" if in_delay_slot else ""
                print(f"{marker} 0x{curr_vram:08X}:  {raw:08X}    {instr['asm']:<32}{tag}")

                curr_offset += 4
                curr_vram += 4

                if in_delay_slot:
                    # Delay slot finished, this basic block is complete!
                    print(f"+-- End of Basic Block #{block_idx}")
                    break

                if instr["is_branch"]:
                    # Next instruction is the branch delay slot
                    in_delay_slot = True

    def scan_entropy_map(self, chunk_size: int = 65536, max_chunks: int = 20):
        """Scans the ROM in chunks to classify code vs data vs compressed assets."""
        print(f"\n========================================================")
        print(f"  ROM ENTROPY MAP & DATA CLASSIFICATION (First {max_chunks} x {chunk_size//1024}KB Blocks)")
        print(f"========================================================")
        print(f"{'Block':<8} {'ROM Offset Range':<24} {'Entropy':<10} {'Classification'}")
        print("-" * 65)

        for i in range(min(max_chunks, self.size // chunk_size)):
            start = i * chunk_size
            end = start + chunk_size
            chunk = self.data[start:end]
            ent = shannon_entropy(chunk)

            # Classification heuristics
            if ent < 0.1:
                classif = "[EMPTY / PADDING] All zeros / repeated bytes"
            elif ent < 5.5:
                classif = "[CODE / TEXT] Uncompressed MIPS code & string tables"
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

    # 2. Hex block inspection at 0x1000
    analyzer.inspect_hex_block(0x1000, 64)

    # 3. Disassemble basic blocks starting at entry point
    analyzer.disassemble_basic_blocks(0x1000, 0x80200400, max_blocks=3)

    # 4. Entropy analysis
    analyzer.scan_entropy_map(chunk_size=65536, max_chunks=16)
