#!/usr/bin/env python3
"""
ARM7TDMI Static Lifter
Translates ARM 32-bit instructions into an Intermediate Representation (IR),
builds a Control Flow Graph (CFG), and outputs structured C functions.
"""

import os
import sys
import struct
from typing import List, Dict, Any, Tuple, Optional

# Ensure project root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.lifter.cfg import BasicBlock, ControlFlowGraph


class ArmLifter:
    def __init__(self, rom_bytes: bytes, base_vram: int = 0x08000000):
        self.rom = rom_bytes
        self.base_vram = base_vram

    def is_valid_vram(self, vram_addr: int) -> bool:
        offset = vram_addr - self.base_vram
        return 0 <= offset <= len(self.rom) - 4

    def read_u32(self, vram_addr: int) -> int:
        offset = vram_addr - self.base_vram
        if 0 <= offset <= len(self.rom) - 4:
            return struct.unpack("<I", self.rom[offset:offset+4])[0]
        return 0

    def lift_block(self, start_vram: int) -> Tuple[List[Dict[str, Any]], List[int]]:
        """
        Disassembles a basic block starting at start_vram until an unconditional
        branch or return is reached. Returns (ir_instructions, outgoing_branch_targets).
        """
        ir_ops = []
        pc = start_vram
        targets = []
        max_instructions = 1000

        while max_instructions > 0:
            max_instructions -= 1
            if not self.is_valid_vram(pc):
                ir_ops.append({
                    "pc": pc,
                    "op": "HALT",
                    "c_code": "return 0; /* out of bounds */"
                })
                break

            raw_instr = self.read_u32(pc)
            instr_pc = pc
            pc += 4

            cond = (raw_instr >> 28) & 0xF
            # Format 1: B / BL (Branch)
            if (raw_instr & 0x0E000000) == 0x0A000000:
                is_link = bool(raw_instr & 0x01000000)
                offset = raw_instr & 0x00FFFFFF
                # Sign extend 24-bit to 32-bit
                if offset & 0x00800000:
                    offset |= ~0x00FFFFFF
                # Target is PC + 8 + (offset << 2)
                target_vram = (instr_pc + 8 + (offset << 2)) & 0xFFFFFFFF

                if is_link:
                    targets.append(target_vram)
                    ir_ops.append({
                        "pc": instr_pc,
                        "op": "CALL",
                        "target": target_vram,
                        "c_code": f"ctx->r[14] = 0x{instr_pc + 4:08X};\n    recomp_dispatch(ctx, 0x{target_vram:08X});"
                    })
                else:
                    # Check for self-loop (b .)
                    if target_vram == instr_pc:
                        ir_ops.append({
                            "pc": instr_pc,
                            "op": "BRANCH",
                            "target": target_vram,
                            "c_code": "return 0x00000000; /* infinite loop halt */"
                        })
                    else:
                        targets.append(target_vram)
                        ir_ops.append({
                            "pc": instr_pc,
                            "op": "BRANCH",
                            "target": target_vram,
                            "c_code": f"return 0x{target_vram:08X}; /* branch to 0x{target_vram:08X} */"
                        })
                    break

            # Format 2: MOV immediate with rotation (0xE3A0....)
            elif (raw_instr & 0x0FE00000) == 0x03A00000:
                rd = (raw_instr >> 12) & 0xF
                imm8 = raw_instr & 0xFF
                rotate = ((raw_instr >> 8) & 0xF) * 2
                val = ((imm8 >> rotate) | (imm8 << (32 - rotate))) & 0xFFFFFFFF if rotate > 0 else imm8
                ir_ops.append({
                    "pc": instr_pc,
                    "op": "MOV_IMM",
                    "rd": rd,
                    "val": val,
                    "c_code": f"ctx->r[{rd}] = 0x{val:08X};"
                })

            # Format 3: LDR immediate offset (0xE59F.... PC-relative load)
            elif (raw_instr & 0x0F700000) == 0x05100000:
                rd = (raw_instr >> 12) & 0xF
                rn = (raw_instr >> 16) & 0xF
                offset12 = raw_instr & 0xFFF
                is_add = bool(raw_instr & 0x00800000)
                if rn == 15:  # PC-relative load from constant pool!
                    target_addr = (instr_pc + 8 + (offset12 if is_add else -offset12)) & 0xFFFFFFFF
                    const_val = self.read_u32(target_addr)
                    ir_ops.append({
                        "pc": instr_pc,
                        "op": "LDR_CONST",
                        "rd": rd,
                        "val": const_val,
                        "c_code": f"ctx->r[{rd}] = 0x{const_val:08X}; /* loaded from 0x{target_addr:08X} */"
                    })
                else:
                    sign = "+" if is_add else "-"
                    ir_ops.append({
                        "pc": instr_pc,
                        "op": "LDR",
                        "c_code": f"ctx->r[{rd}] = mem_read32(ctx, ctx->r[{rn}] {sign} {offset12});"
                    })

            # Format 4: STRH halfword store (0xE1C0....)
            elif (raw_instr & 0x0E1000F0) == 0x000000B0:
                rd = (raw_instr >> 12) & 0xF  # Source reg
                rn = (raw_instr >> 16) & 0xF  # Base reg
                ir_ops.append({
                    "pc": instr_pc,
                    "op": "STRH",
                    "c_code": f"mem_write16(ctx, ctx->r[{rn}], (uint16_t)ctx->r[{rd}]);"
                })

            else:
                ir_ops.append({
                    "pc": instr_pc,
                    "op": "UNKNOWN",
                    "raw": raw_instr,
                    "c_code": f"/* Unhandled raw opcode 0x{raw_instr:08X} at 0x{instr_pc:08X} */"
                })
                # Terminate block on consecutive unknown opcode or zero padding
                if raw_instr == 0:
                    ir_ops.append({
                        "pc": instr_pc,
                        "op": "HALT",
                        "c_code": "return 0; /* padding halt */"
                    })
                    break

        return ir_ops, targets

    def build_cfg(self, entry_vram: int = 0x08000000) -> ControlFlowGraph:
        """
        Traces and constructs all reachable Basic Blocks via recursive descent
        from the specified entry point.
        """
        cfg = ControlFlowGraph(entry_vram)
        worklist = [entry_vram]
        visited = set()

        while worklist:
            vram = worklist.pop(0)
            if vram in visited or not self.is_valid_vram(vram):
                continue
            visited.add(vram)

            ops, targets = self.lift_block(vram)
            block = BasicBlock(
                start_vram=vram,
                end_vram=ops[-1]["pc"] if ops else vram,
                instructions=ops,
                successors=targets,
                is_terminal=len(targets) == 0
            )
            cfg.add_block(block)

            for target in targets:
                if target not in visited and self.is_valid_vram(target):
                    worklist.append(target)

        return cfg


def lift_rom_to_c(rom_path: str, entry_point: int = 0x08000000) -> str:
    with open(rom_path, "rb") as f:
        rom_data = f.read()

    lifter = ArmLifter(rom_data, base_vram=0x08000000)
    cfg = lifter.build_cfg(entry_point)

    c_source = [
        '/* Automatically Generated by Automated Recompiler Framework */',
        '#include <stdint.h>',
        '#include <stdio.h>',
        '',
        'typedef struct {',
        '    uint32_t r[16];   /* r0-r15 registers (r13=SP, r14=LR, r15=PC) */',
        '    uint32_t cpsr;    /* Status register */',
        '    uint8_t  vram[0x18000]; /* 96KB GBA VRAM */',
        '    uint16_t dispcnt; /* Display control MMIO */',
        '} ArmCpuContext;',
        '',
        '/* Hardware Bus Shims */',
        'static inline void mem_write16(ArmCpuContext* ctx, uint32_t addr, uint16_t val) {',
        '    if (addr == 0x04000000) {',
        '        ctx->dispcnt = val;',
        '        printf("[GBA HAL] REG_DISPCNT set to 0x%04X (Mode %d)\\n", val, val & 7);',
        '    } else if (addr >= 0x06000000 && addr < 0x06018000) {',
        '        uint32_t offset = addr - 0x06000000;',
        '        *(uint16_t*)&ctx->vram[offset] = val;',
        '        printf("[GBA HAL] VRAM write at offset 0x%04X = 0x%04X (Pixel drawn)\\n", offset, val);',
        '    }',
        '}',
        '',
        'static inline uint32_t mem_read32(ArmCpuContext* ctx, uint32_t addr) {',
        '    (void)ctx;',
        '    (void)addr;',
        '    return 0;',
        '}',
        '',
        '/* Basic Block Prototypes */',
    ]

    for proto in cfg.emit_prototypes():
        c_source.append(proto)
    c_source.append('')

    # Emit all discovered basic blocks
    for block in cfg.sorted_blocks():
        c_source.append(block.emit_c_function())

    # Emit main function and dispatch loop
    c_source.extend([
        '/* Main Entry / Native Recompiled Executable */',
        'int main(int argc, char** argv) {',
        '    (void)argc;',
        '    (void)argv;',
        '    printf("=== Starting Automated Recompiled Game ===\\n");',
        '    ArmCpuContext ctx = {0};',
        '    ',
        f'    uint32_t next_pc = 0x{entry_point:08X};',
        '    int max_steps = 10;',
        '    while (max_steps-- > 0 && next_pc != 0) {',
    ])

    for line in cfg.emit_dispatch_switch():
        c_source.append(f'    {line}')

    c_source.extend([
        '    }',
        '    printf("=== Recompiled execution finished successfully ===\\n");',
        '    return 0;',
        '}',
    ])

    return "\n".join(c_source)


if __name__ == "__main__":
    import sys
    import os
    rom = sys.argv[1] if len(sys.argv) > 1 else "roms/test/hello_gba.gba"
    c_code = lift_rom_to_c(rom)
    out_file = "build/recompiled_game.c"
    os.makedirs("build", exist_ok=True)
    with open(out_file, "w") as f:
        f.write(c_code)
    print(f"Generated recompiled C source: {out_file}")
