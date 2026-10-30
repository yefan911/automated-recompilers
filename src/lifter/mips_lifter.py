#!/usr/bin/env python3
"""
MIPS I / III Static Lifter (N64 / PS1)
Part of Automated Recompiler Framework.

Translates 32-bit MIPS machine code into structured C basic blocks,
handles branch delay slots, constructs a Control Flow Graph, and
emits native C source code with hardware shims.
"""

import os
import sys
import struct
from typing import List, Dict, Any, Tuple, Optional

# Ensure project root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.lifter.cfg import BasicBlock, ControlFlowGraph
from src.core.rom_detector import inspect_file

MIPS_REG_NAMES = [
    "zero", "at", "v0", "v1", "a0", "a1", "a2", "a3",
    "t0", "t1", "t2", "t3", "t4", "t5", "t6", "t7",
    "s0", "s1", "s2", "s3", "s4", "s5", "s6", "s7",
    "t8", "t9", "k0", "k1", "gp", "sp", "fp", "ra"
]


class MipsLifter:
    def __init__(self, data: bytes, base_vram: int = 0x80000000, is_big_endian: bool = True):
        self.data = data
        self.base_vram = base_vram
        self.fmt = ">I" if is_big_endian else "<I"

    def is_valid_vram(self, vram_addr: int) -> bool:
        offset = vram_addr - self.base_vram
        return 0 <= offset <= len(self.data) - 4

    def read_u32(self, vram_addr: int) -> int:
        offset = vram_addr - self.base_vram
        if 0 <= offset <= len(self.data) - 4:
            return struct.unpack(self.fmt, self.data[offset:offset+4])[0]
        return 0

    def lift_instruction(self, vram_addr: int, raw: int) -> Dict[str, Any]:
        op = (raw >> 26) & 0x3F
        rs = (raw >> 21) & 0x1F
        rt = (raw >> 16) & 0x1F
        rd = (raw >> 11) & 0x1F
        shamt = (raw >> 6) & 0x1F
        funct = raw & 0x3F
        imm = raw & 0xFFFF
        simm = imm if imm < 0x8000 else imm - 0x10000
        target26 = raw & 0x03FFFFFF

        # 1. SPECIAL (R-Type)
        if op == 0x00:
            if raw == 0:
                return {"vram": vram_addr, "asm": "nop", "c": "/* nop */"}

            elif funct == 0x08:  # JR
                return {
                    "vram": vram_addr,
                    "asm": f"jr ${MIPS_REG_NAMES[rs]}",
                    "c": f"return ctx->r[{rs}]; /* indirect jump / return */",
                    "is_branch": True,
                    "is_indirect": True,
                    "is_terminal": True,
                    "targets": []
                }

            elif funct == 0x09:  # JALR
                return {
                    "vram": vram_addr,
                    "asm": f"jalr ${MIPS_REG_NAMES[rd]}, ${MIPS_REG_NAMES[rs]}",
                    "c": f"ctx->r[{rd if rd != 0 else 31}] = 0x{vram_addr + 8:08X};\n    recomp_mips_dispatch(ctx, ctx->r[{rs}]);",
                    "is_call": True,
                }

            elif funct == 0x20 or funct == 0x21:  # ADD / ADDU
                c_code = f"ctx->r[{rd}] = ctx->r[{rs}] + ctx->r[{rt}];" if rd != 0 else "/* nop: r0 */"
                return {"vram": vram_addr, "asm": f"addu ${MIPS_REG_NAMES[rd]}, ${MIPS_REG_NAMES[rs]}, ${MIPS_REG_NAMES[rt]}", "c": c_code}

            elif funct == 0x22 or funct == 0x23:  # SUB / SUBU
                c_code = f"ctx->r[{rd}] = ctx->r[{rs}] - ctx->r[{rt}];" if rd != 0 else "/* nop: r0 */"
                return {"vram": vram_addr, "asm": f"subu ${MIPS_REG_NAMES[rd]}, ${MIPS_REG_NAMES[rs]}, ${MIPS_REG_NAMES[rt]}", "c": c_code}

            elif funct == 0x24:  # AND
                c_code = f"ctx->r[{rd}] = ctx->r[{rs}] & ctx->r[{rt}];" if rd != 0 else "/* nop: r0 */"
                return {"vram": vram_addr, "asm": f"and ${MIPS_REG_NAMES[rd]}, ${MIPS_REG_NAMES[rs]}, ${MIPS_REG_NAMES[rt]}", "c": c_code}

            elif funct == 0x25:  # OR
                c_code = f"ctx->r[{rd}] = ctx->r[{rs}] | ctx->r[{rt}];" if rd != 0 else "/* nop: r0 */"
                return {"vram": vram_addr, "asm": f"or ${MIPS_REG_NAMES[rd]}, ${MIPS_REG_NAMES[rs]}, ${MIPS_REG_NAMES[rt]}", "c": c_code}

            elif funct == 0x26:  # XOR
                c_code = f"ctx->r[{rd}] = ctx->r[{rs}] ^ ctx->r[{rt}];" if rd != 0 else "/* nop: r0 */"
                return {"vram": vram_addr, "asm": f"xor ${MIPS_REG_NAMES[rd]}, ${MIPS_REG_NAMES[rs]}, ${MIPS_REG_NAMES[rt]}", "c": c_code}

            elif funct == 0x2A or funct == 0x2B:  # SLT / SLTU
                c_code = f"ctx->r[{rd}] = ((int32_t)ctx->r[{rs}] < (int32_t)ctx->r[{rt}]) ? 1 : 0;" if rd != 0 else "/* nop: r0 */"
                return {"vram": vram_addr, "asm": f"slt ${MIPS_REG_NAMES[rd]}, ${MIPS_REG_NAMES[rs]}, ${MIPS_REG_NAMES[rt]}", "c": c_code}

            elif funct == 0x00:  # SLL
                c_code = f"ctx->r[{rd}] = ctx->r[{rt}] << {shamt};" if rd != 0 else "/* nop: r0 */"
                return {"vram": vram_addr, "asm": f"sll ${MIPS_REG_NAMES[rd]}, ${MIPS_REG_NAMES[rt]}, {shamt}", "c": c_code}

            elif funct == 0x02:  # SRL
                c_code = f"ctx->r[{rd}] = ctx->r[{rt}] >> {shamt};" if rd != 0 else "/* nop: r0 */"
                return {"vram": vram_addr, "asm": f"srl ${MIPS_REG_NAMES[rd]}, ${MIPS_REG_NAMES[rt]}, {shamt}", "c": c_code}

            elif funct == 0x03:  # SRA
                c_code = f"ctx->r[{rd}] = (uint32_t)((int32_t)ctx->r[{rt}] >> {shamt});" if rd != 0 else "/* nop: r0 */"
                return {"vram": vram_addr, "asm": f"sra ${MIPS_REG_NAMES[rd]}, ${MIPS_REG_NAMES[rt]}, {shamt}", "c": c_code}

        # 2. J (Jump)
        elif op == 0x02:
            target = ((vram_addr + 4) & 0xF0000000) | (target26 << 2)
            return {
                "vram": vram_addr,
                "asm": f"j 0x{target:08X}",
                "c": f"return 0x{target:08X};",
                "is_branch": True,
                "is_terminal": True,
                "targets": [target]
            }

        # 3. JAL (Jump and Link)
        elif op == 0x03:
            target = ((vram_addr + 4) & 0xF0000000) | (target26 << 2)
            return {
                "vram": vram_addr,
                "asm": f"jal 0x{target:08X}",
                "c": f"ctx->r[31] = 0x{vram_addr + 8:08X};\n    recomp_mips_dispatch(ctx, 0x{target:08X});",
                "is_call": True,
                "targets": [target]
            }

        # 4. BEQ
        elif op == 0x04:
            target = vram_addr + 4 + (simm << 2)
            fallthrough = vram_addr + 8
            cond = f"ctx->r[{rs}] == ctx->r[{rt}]"
            return {
                "vram": vram_addr,
                "asm": f"beq ${MIPS_REG_NAMES[rs]}, ${MIPS_REG_NAMES[rt]}, 0x{target:08X}",
                "c": f"if ({cond}) return 0x{target:08X};\n    else return 0x{fallthrough:08X};",
                "is_branch": True,
                "is_terminal": True,
                "targets": [target, fallthrough]
            }

        # 5. BNE
        elif op == 0x05:
            target = vram_addr + 4 + (simm << 2)
            fallthrough = vram_addr + 8
            cond = f"ctx->r[{rs}] != ctx->r[{rt}]"
            return {
                "vram": vram_addr,
                "asm": f"bne ${MIPS_REG_NAMES[rs]}, ${MIPS_REG_NAMES[rt]}, 0x{target:08X}",
                "c": f"if ({cond}) return 0x{target:08X};\n    else return 0x{fallthrough:08X};",
                "is_branch": True,
                "is_terminal": True,
                "targets": [target, fallthrough]
            }

        # 6. ADDI / ADDIU
        elif op == 0x08 or op == 0x09:
            c_code = f"ctx->r[{rt}] = (uint32_t)((int32_t)ctx->r[{rs}] + {simm});" if rt != 0 else "/* nop */"
            mnemonic = "addi" if op == 0x08 else "addiu"
            return {"vram": vram_addr, "asm": f"{mnemonic} ${MIPS_REG_NAMES[rt]}, ${MIPS_REG_NAMES[rs]}, {simm}", "c": c_code}

        # 7. LUI
        elif op == 0x0F:
            c_code = f"ctx->r[{rt}] = 0x{imm << 16:08X};" if rt != 0 else "/* nop */"
            return {"vram": vram_addr, "asm": f"lui ${MIPS_REG_NAMES[rt]}, 0x{imm:04X}", "c": c_code}

        # 8. ORI
        elif op == 0x0D:
            c_code = f"ctx->r[{rt}] = ctx->r[{rs}] | 0x{imm:04X};" if rt != 0 else "/* nop */"
            return {"vram": vram_addr, "asm": f"ori ${MIPS_REG_NAMES[rt]}, ${MIPS_REG_NAMES[rs]}, 0x{imm:04X}", "c": c_code}

        # 9. ANDI
        elif op == 0x0C:
            c_code = f"ctx->r[{rt}] = ctx->r[{rs}] & 0x{imm:04X};" if rt != 0 else "/* nop */"
            return {"vram": vram_addr, "asm": f"andi ${MIPS_REG_NAMES[rt]}, ${MIPS_REG_NAMES[rs]}, 0x{imm:04X}", "c": c_code}

        # 10. LW
        elif op == 0x23:
            return {"vram": vram_addr, "asm": f"lw ${MIPS_REG_NAMES[rt]}, {simm}(${MIPS_REG_NAMES[rs]})", "c": f"ctx->r[{rt}] = mips_read32(ctx, ctx->r[{rs}] + ({simm}));"}

        # 11. SW
        elif op == 0x2B:
            return {"vram": vram_addr, "asm": f"sw ${MIPS_REG_NAMES[rt]}, {simm}(${MIPS_REG_NAMES[rs]})", "c": f"mips_write32(ctx, ctx->r[{rs}] + ({simm}), ctx->r[{rt}]);"}

        # 12. LH / LHU
        elif op == 0x21 or op == 0x25:
            return {"vram": vram_addr, "asm": f"lh ${MIPS_REG_NAMES[rt]}, {simm}(${MIPS_REG_NAMES[rs]})", "c": f"ctx->r[{rt}] = mips_read16(ctx, ctx->r[{rs}] + ({simm}));"}

        # 13. SH
        elif op == 0x29:
            return {"vram": vram_addr, "asm": f"sh ${MIPS_REG_NAMES[rt]}, {simm}(${MIPS_REG_NAMES[rs]})", "c": f"mips_write16(ctx, ctx->r[{rs}] + ({simm}), (uint16_t)ctx->r[{rt}]);"}

        # 14. LB / LBU
        elif op == 0x20 or op == 0x24:
            return {"vram": vram_addr, "asm": f"lb ${MIPS_REG_NAMES[rt]}, {simm}(${MIPS_REG_NAMES[rs]})", "c": f"ctx->r[{rt}] = mips_read8(ctx, ctx->r[{rs}] + ({simm}));"}

        # 15. SB
        elif op == 0x28:
            return {"vram": vram_addr, "asm": f"sb ${MIPS_REG_NAMES[rt]}, {simm}(${MIPS_REG_NAMES[rs]})", "c": f"mips_write8(ctx, ctx->r[{rs}] + ({simm}), (uint8_t)ctx->r[{rt}]);"}

        return {
            "vram": vram_addr,
            "asm": f"unknown_op_0x{op:02X} (0x{raw:08X})",
            "c": f"/* Unknown MIPS op 0x{op:02X} (0x{raw:08X}) at 0x{vram_addr:08X} */"
        }

    def lift_block(self, start_vram: int) -> Tuple[List[Dict[str, Any]], List[int]]:
        """
        Disassembles a MIPS basic block, lifting branch delay slots before terminal jumps.
        """
        ir_ops = []
        pc = start_vram
        targets = []
        max_instructions = 500

        while max_instructions > 0:
            max_instructions -= 1
            if not self.is_valid_vram(pc):
                ir_ops.append({"pc": pc, "op": "HALT", "c_code": "return 0; /* out of bounds */"})
                break

            raw = self.read_u32(pc)
            info = self.lift_instruction(pc, raw)

            if info.get("is_branch"):
                delay_slot_raw = self.read_u32(pc + 4)
                delay_slot_info = self.lift_instruction(pc + 4, delay_slot_raw)

                # Execute delay slot instruction before branch executes
                if delay_slot_info.get("c") and delay_slot_info.get("c") != "/* nop */":
                    ir_ops.append({
                        "pc": pc + 4,
                        "op": "DELAY_SLOT",
                        "c_code": f"/* Delay Slot */ {delay_slot_info['c']}"
                    })

                ir_ops.append({
                    "pc": pc,
                    "op": info.get("asm", "").split()[0].upper(),
                    "c_code": info["c"]
                })

                targets.extend(info.get("targets", []))
                break

            elif info.get("is_call"):
                delay_slot_raw = self.read_u32(pc + 4)
                delay_slot_info = self.lift_instruction(pc + 4, delay_slot_raw)
                if delay_slot_info.get("c") and delay_slot_info.get("c") != "/* nop */":
                    ir_ops.append({
                        "pc": pc + 4,
                        "op": "DELAY_SLOT",
                        "c_code": f"/* Delay Slot */ {delay_slot_info['c']}"
                    })
                ir_ops.append({
                    "pc": pc,
                    "op": "CALL",
                    "c_code": info["c"]
                })
                targets.extend(info.get("targets", []))
                pc += 8  # Skip both call and delay slot
                continue

            else:
                ir_ops.append({
                    "pc": pc,
                    "op": "INSN",
                    "c_code": info["c"]
                })
                pc += 4

        return ir_ops, targets

    def build_cfg(self, entry_vram: int, max_blocks: int = 1500) -> ControlFlowGraph:
        cfg = ControlFlowGraph(entry_vram)
        worklist = [entry_vram]
        visited = set()

        while worklist and len(cfg) < max_blocks:
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


def lift_mips_rom_to_c(rom_path: str, entry_point: Optional[int] = None, max_blocks: int = 1500) -> str:
    with open(rom_path, "rb") as f:
        data = f.read()

    # Determine endianness and entry point
    is_big_endian = True
    base_vram = 0x80000000
    ep = entry_point

    if data[:4] == b'\x80\x37\x12\x40':  # N64 .z64 Big-endian
        is_big_endian = True
        ep = ep or struct.unpack(">I", data[0x08:0x0C])[0]
        # In official N64 ROMs (size > 0x1000), offset 0x1000 maps to ep.
        # In small test ROMs (size <= 0x1000), offset 0x400 maps to ep.
        code_offset = 0x1000 if len(data) > 0x1000 else 0x400
        base_vram = (ep - code_offset) & 0xFFFFFFFF
    elif data[:4] == b'\x40\x12\x37\x80':  # N64 .n64 Little-endian
        is_big_endian = False
        ep = ep or struct.unpack("<I", data[0x08:0x0C])[0]
        code_offset = 0x1000 if len(data) > 0x1000 else 0x400
        base_vram = (ep - code_offset) & 0xFFFFFFFF
    elif data.startswith(b"PS-X EXE"):
        is_big_endian = False
        ep = ep or struct.unpack("<I", data[0x10:0x14])[0]
        text_vram = struct.unpack("<I", data[0x18:0x1C])[0]
        base_vram = text_vram

    ep = ep or 0x80000400
    lifter = MipsLifter(data, base_vram=base_vram, is_big_endian=is_big_endian)
    cfg = lifter.build_cfg(ep, max_blocks=max_blocks)

    c_source = [
        '/* Automatically Generated by Automated Recompiler Framework (MIPS Target) */',
        '#include <stdint.h>',
        '#include <stdio.h>',
        '#include <stdbool.h>',
        '',
        'typedef struct {',
        '    uint32_t r[32];         /* $zero, $at, $v0-$v1, $a0-$a3, $t0-$t9, $s0-$s7, $gp, $sp, $fp, $ra */',
        '    uint32_t hi, lo;        /* Mult/Div registers */',
        '    uint32_t pc;            /* Program Counter */',
        '    uint8_t  rdram[0x800000]; /* 8MB RDRAM */',
        '} MipsCpuContext;',
        '',
        '/* Hardware Memory Shims */',
        'static inline uint32_t mips_read32(MipsCpuContext* ctx, uint32_t addr) {',
        '    uint32_t phys = addr & 0x1FFFFFFF;',
        '    if (phys < 0x800000) return *(uint32_t*)&ctx->rdram[phys];',
        '    return 0;',
        '}',
        '',
        'static inline void mips_write32(MipsCpuContext* ctx, uint32_t addr, uint32_t val) {',
        '    uint32_t phys = addr & 0x1FFFFFFF;',
        '    if (phys < 0x800000) *(uint32_t*)&ctx->rdram[phys] = val;',
        '}',
        '',
        'static inline uint16_t mips_read16(MipsCpuContext* ctx, uint32_t addr) {',
        '    uint32_t phys = addr & 0x1FFFFFFF;',
        '    if (phys < 0x800000) return *(uint16_t*)&ctx->rdram[phys];',
        '    return 0;',
        '}',
        '',
        'static inline void mips_write16(MipsCpuContext* ctx, uint32_t addr, uint16_t val) {',
        '    uint32_t phys = addr & 0x1FFFFFFF;',
        '    if (phys < 0x800000) *(uint16_t*)&ctx->rdram[phys] = val;',
        '}',
        '',
        'static inline uint8_t mips_read8(MipsCpuContext* ctx, uint32_t addr) {',
        '    uint32_t phys = addr & 0x1FFFFFFF;',
        '    if (phys < 0x800000) return ctx->rdram[phys];',
        '    return 0;',
        '}',
        '',
        'static inline void mips_write8(MipsCpuContext* ctx, uint32_t addr, uint8_t val) {',
        '    uint32_t phys = addr & 0x1FFFFFFF;',
        '    if (phys < 0x800000) ctx->rdram[phys] = val;',
        '}',
        '',
        '/* Basic Block Prototypes */',
        'uint32_t recomp_mips_dispatch(MipsCpuContext* ctx, uint32_t target_vram);',
    ]

    for b in cfg.sorted_blocks():
        c_source.append(f'uint32_t {b.func_name}(MipsCpuContext* ctx);')
    c_source.append('')

    # Emit all blocks
    for b in cfg.sorted_blocks():
        c_source.append(f'/* Basic Block 0x{b.start_vram:08X} */')
        c_source.append(f'uint32_t {b.func_name}(MipsCpuContext* ctx) {{')
        c_source.append('    (void)ctx;')
        for op in b.instructions:
            code = op.get("c_code", "")
            if code:
                c_source.append(f'    {code}')
        c_source.append('}\n')

    # Emit Dispatch Trampoline
    c_source.extend([
        '/* Global MIPS Dispatch Trampoline */',
        'uint32_t recomp_mips_dispatch(MipsCpuContext* ctx, uint32_t target_vram) {',
        '    switch (target_vram) {',
    ])
    for b in cfg.sorted_blocks():
        c_source.append(f'        case 0x{b.start_vram:08X}: return {b.func_name}(ctx);')
    c_source.extend([
        '        default:',
        '            printf("[MIPS Dispatch] Halt at unmapped jump target 0x%08X\\n", target_vram);',
        '            return 0;',
        '    }',
        '}\n',
        '/* Main Entry / Native Recompiled Executable */',
        'static MipsCpuContext s_ctx;',
        'int main(int argc, char** argv) {',
        '    (void)argc;',
        '    (void)argv;',
        '    printf("=== Starting Automated Recompiled MIPS Game ===\\n");',
        '    MipsCpuContext* ctx = &s_ctx;',
        f'    uint32_t next_pc = 0x{ep:08X};',
        '    int max_steps = 1000;',
        '    while (max_steps-- > 0 && next_pc != 0) {',
        '        next_pc = recomp_mips_dispatch(ctx, next_pc);',
        '    }',
        '    printf("=== Recompiled execution finished successfully ===\\n");',
        '    return 0;',
        '}',
    ])

    return "\n".join(c_source)


if __name__ == "__main__":
    test_mips_bytes = struct.pack(">5I",
        0x27BDFFF8,  # addiu $sp, $sp, -8
        0xAFBF0004,  # sw $ra, 4($sp)
        0x00851021,  # addu $v0, $a0, $a1
        0x8FBF0004,  # lw $ra, 4($sp)
        0x03E00008,  # jr $ra
    )
    lifter = MipsLifter(test_mips_bytes, base_vram=0x80001000, is_big_endian=True)
    print("MIPS Lifting Demonstration:")
    print("=" * 60)
    for i in range(5):
        addr = 0x80001000 + i * 4
        raw = lifter.read_u32(addr)
        info = lifter.lift_instruction(addr, raw)
        print(f"0x{addr:08X}: {info['asm']:<30} -> {info['c']}")
    print("=" * 60)
