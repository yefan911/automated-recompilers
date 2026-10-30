#!/usr/bin/env python3
"""
MIPS I / III Static Instruction Lifter Prototype (PS1 / N64)
Demonstrates translating MIPS machine code into C basic blocks.
"""

import struct
from typing import List, Dict, Any, Tuple

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

        # SPECIAL (R-Type)
        if op == 0x00:
            if funct == 0x08: # JR (Jump Register)
                return {
                    "vram": vram_addr,
                    "asm": f"jr ${MIPS_REG_NAMES[rs]}",
                    "c": f"return ctx->r[{rs}]; /* indirect jump / return */",
                    "is_branch": True,
                    "is_indirect": True,
                }
            elif funct == 0x20 or funct == 0x21: # ADD / ADDU
                c_code = f"ctx->r[{rd}] = ctx->r[{rs}] + ctx->r[{rt}];" if rd != 0 else "/* nop: r0 */"
                return {"vram": vram_addr, "asm": f"addu ${MIPS_REG_NAMES[rd]}, ${MIPS_REG_NAMES[rs]}, ${MIPS_REG_NAMES[rt]}", "c": c_code}
            elif funct == 0x00 and raw == 0:
                return {"vram": vram_addr, "asm": "nop", "c": "/* nop */"}

        # ADDIU
        elif op == 0x09:
            c_code = f"ctx->r[{rt}] = (uint32_t)((int32_t)ctx->r[{rs}] + {simm});" if rt != 0 else "/* nop */"
            return {"vram": vram_addr, "asm": f"addiu ${MIPS_REG_NAMES[rt]}, ${MIPS_REG_NAMES[rs]}, {simm}", "c": c_code}

        # LUI (Load Upper Immediate)
        elif op == 0x0F:
            c_code = f"ctx->r[{rt}] = 0x{imm << 16:08X};" if rt != 0 else "/* nop */"
            return {"vram": vram_addr, "asm": f"lui ${MIPS_REG_NAMES[rt]}, 0x{imm:04X}", "c": c_code}

        # ORI (OR Immediate)
        elif op == 0x0D:
            c_code = f"ctx->r[{rt}] = ctx->r[{rs}] | 0x{imm:04X};" if rt != 0 else "/* nop */"
            return {"vram": vram_addr, "asm": f"ori ${MIPS_REG_NAMES[rt]}, ${MIPS_REG_NAMES[rs]}, 0x{imm:04X}", "c": c_code}

        # LW (Load Word)
        elif op == 0x23:
            return {"vram": vram_addr, "asm": f"lw ${MIPS_REG_NAMES[rt]}, {simm}(${MIPS_REG_NAMES[rs]})", "c": f"ctx->r[{rt}] = mem_read32(ctx, ctx->r[{rs}] + ({simm}));"}

        # SW (Store Word)
        elif op == 0x2B:
            return {"vram": vram_addr, "asm": f"sw ${MIPS_REG_NAMES[rt]}, {simm}(${MIPS_REG_NAMES[rs]})", "c": f"mem_write32(ctx, ctx->r[{rs}] + ({simm}), ctx->r[{rt}]);"}

        # JAL (Jump and Link / Function Call)
        elif op == 0x03:
            jump_vram = ((vram_addr + 4) & 0xF0000000) | (target26 << 2)
            return {
                "vram": vram_addr,
                "asm": f"jal 0x{jump_vram:08X}",
                "c": f"ctx->r[31] = 0x{vram_addr + 8:08X};\n    recomp_dispatch(ctx, 0x{jump_vram:08X});",
                "is_call": True,
                "target": jump_vram
            }

        return {
            "vram": vram_addr,
            "asm": f"unknown_op_0x{op:02X} (0x{raw:08X})",
            "c": f"/* Unknown MIPS op 0x{op:02X} */"
        }

if __name__ == "__main__":
    # Test sample: MIPS function prologue and epilogue
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
