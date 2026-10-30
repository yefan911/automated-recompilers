#!/usr/bin/env python3
"""
ARM Thumb-16 (ARMv4T) Static Instruction Lifter
Translates 16-bit Thumb instructions into native C code and extracts
control flow edges for the CFG engine.
"""

import struct
from typing import List, Dict, Any, Tuple


class ThumbLifter:
    def __init__(self, rom_bytes: bytes, base_vram: int = 0x08000000):
        self.rom = rom_bytes
        self.base_vram = base_vram

    def is_valid_vram(self, vram_addr: int) -> bool:
        offset = vram_addr - self.base_vram
        return 0 <= offset <= len(self.rom) - 2

    def read_u16(self, vram_addr: int) -> int:
        offset = vram_addr - self.base_vram
        if 0 <= offset <= len(self.rom) - 2:
            return struct.unpack("<H", self.rom[offset:offset+2])[0]
        return 0

    def read_u32(self, vram_addr: int) -> int:
        offset = vram_addr - self.base_vram
        if 0 <= offset <= len(self.rom) - 4:
            return struct.unpack("<I", self.rom[offset:offset+4])[0]
        return 0

    def lift_block(self, start_vram: int) -> Tuple[List[Dict[str, Any]], List[int]]:
        """
        Disassembles a 16-bit Thumb basic block starting at start_vram.
        Returns (ir_operations, target_successors).
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

            raw = self.read_u16(pc)
            instr_pc = pc
            pc += 2

            # 1. Push / Pop registers (Format 14)
            # 0xB400 (push) / 0xBC00 (pop)
            if (raw & 0xF600) == 0xB400:
                is_pop = bool(raw & 0x0800)
                has_lr_pc = bool(raw & 0x0100)
                rlist = [i for i in range(8) if (raw & (1 << i))]

                if is_pop:
                    pop_lines = []
                    for r in rlist:
                        pop_lines.append(f"ctx->r[{r}] = mem_read32(ctx, ctx->r[13]); ctx->r[13] += 4;")
                    if has_lr_pc:
                        # Pop PC = return from function!
                        pop_lines.append("ctx->r[15] = mem_read32(ctx, ctx->r[13]); ctx->r[13] += 4;")
                        pop_lines.append("return ctx->r[15]; /* pop {..., pc} return */")
                        ir_ops.append({
                            "pc": instr_pc,
                            "op": "POP_PC",
                            "c_code": "\n    ".join(pop_lines)
                        })
                        break
                    else:
                        ir_ops.append({
                            "pc": instr_pc,
                            "op": "POP",
                            "c_code": "\n    ".join(pop_lines)
                        })
                else: # Push
                    push_lines = []
                    if has_lr_pc:
                        push_lines.append("ctx->r[13] -= 4; mem_write32(ctx, ctx->r[13], ctx->r[14]);")
                    for r in reversed(rlist):
                        push_lines.append(f"ctx->r[13] -= 4; mem_write32(ctx, ctx->r[13], ctx->r[{r}]);")
                    ir_ops.append({
                        "pc": instr_pc,
                        "op": "PUSH",
                        "c_code": "\n    ".join(push_lines)
                    })

            # 2. Add / Subtract offset to Stack Pointer (Format 13: 0xB000)
            elif (raw & 0xFF00) == 0xB000:
                is_neg = bool(raw & 0x0080)
                imm7 = (raw & 0x7F) << 2
                sign = "-" if is_neg else "+"
                ir_ops.append({
                    "pc": instr_pc,
                    "op": "ADD_SP",
                    "c_code": f"ctx->r[13] {sign}= {imm7};"
                })

            # 3. High Register Operations / BX (Format 5: 0x4400 - 0x47FF)
            elif (raw & 0xFC00) == 0x4400:
                sub_op = (raw >> 8) & 0x3
                h1 = bool(raw & 0x0080)
                h2 = bool(raw & 0x0040)
                rd = (raw & 0x7) | (8 if h1 else 0)
                rs = ((raw >> 3) & 0x7) | (8 if h2 else 0)

                if sub_op == 3: # BX (Branch Exchange)
                    ir_ops.append({
                        "pc": instr_pc,
                        "op": "BX",
                        "c_code": f"return ctx->r[{rs}]; /* bx r{rs} */"
                    })
                    break
                elif sub_op == 2: # MOV high
                    ir_ops.append({
                        "pc": instr_pc,
                        "op": "MOV_HI",
                        "c_code": f"ctx->r[{rd}] = ctx->r[{rs}];"
                    })
                elif sub_op == 0: # ADD high
                    ir_ops.append({
                        "pc": instr_pc,
                        "op": "ADD_HI",
                        "c_code": f"ctx->r[{rd}] += ctx->r[{rs}];"
                    })
                elif sub_op == 1: # CMP high
                    ir_ops.append({
                        "pc": instr_pc,
                        "op": "CMP_HI",
                        "c_code": f"ctx->flag_z = (ctx->r[{rd}] == ctx->r[{rs}]);"
                    })

            # 4. Long Branch with Link (BL): 0xF000 prefix + 0xF800 suffix
            elif (raw & 0xF800) == 0xF000:
                # First half of BL instruction
                offset_hi = raw & 0x07FF
                if offset_hi & 0x0400:
                    offset_hi |= ~0x07FF
                if self.is_valid_vram(pc):
                    raw2 = self.read_u16(pc)
                    if (raw2 & 0xF800) == 0xF800:
                        pc += 2 # Consume second half
                        offset_lo = raw2 & 0x07FF
                        total_offset = (offset_hi << 12) + (offset_lo << 1)
                        # Thumb BL target is relative to (instr_pc + 4)
                        target_vram = (instr_pc + 4 + total_offset) & 0xFFFFFFFF
                        targets.append(target_vram)
                        ir_ops.append({
                            "pc": instr_pc,
                            "op": "BL_THUMB",
                            "target": target_vram,
                            "c_code": f"ctx->r[14] = 0x{instr_pc + 4:08X} | 1; /* Thumb LR */\n    recomp_call(ctx, 0x{target_vram:08X});"
                        })

            # 5. Unconditional Branch (Format 18: 0xE000)
            elif (raw & 0xF800) == 0xE000:
                imm11 = raw & 0x07FF
                if imm11 & 0x0400:
                    imm11 |= ~0x07FF
                target_vram = (instr_pc + 4 + (imm11 << 1)) & 0xFFFFFFFF
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

            # 6. Conditional Branch (Format 16: 0xD000)
            elif (raw & 0xF000) == 0xD000:
                cond = (raw >> 8) & 0xF
                if cond < 0xE: # 0xE is undefined in Thumb
                    imm8 = raw & 0xFF
                    if imm8 & 0x80:
                        imm8 |= ~0xFF
                    target_vram = (instr_pc + 4 + (imm8 << 1)) & 0xFFFFFFFF
                    fallthrough = instr_pc + 2
                    targets.append(target_vram)
                    targets.append(fallthrough)

                    cond_expr = "!ctx->flag_z" if cond == 0x1 else ("ctx->flag_z" if cond == 0x0 else "ctx->flag_z")
                    ir_ops.append({
                        "pc": instr_pc,
                        "op": "B_COND",
                        "target": target_vram,
                        "fallthrough": fallthrough,
                        "c_code": f"if ({cond_expr}) return 0x{target_vram:08X};\n    else return 0x{fallthrough:08X};"
                    })
                    break

            # 7. PC-relative load: LDR Rd, [PC, #imm8] (Format 6: 0x4800)
            elif (raw & 0xF800) == 0x4800:
                rd = (raw >> 8) & 0x7
                imm8 = (raw & 0xFF) << 2
                # Target word aligned: ((PC + 4) & ~2) + imm8
                load_addr = ((instr_pc + 4) & ~2) + imm8
                val = self.read_u32(load_addr)
                ir_ops.append({
                    "pc": instr_pc,
                    "op": "LDR_PC",
                    "c_code": f"ctx->r[{rd}] = 0x{val:08X}; /* loaded from 0x{load_addr:08X} */"
                })

            # 8. Move / Compare / Add / Subtract Immediate (Format 3: 0x2000 - 0x3FFF)
            elif (raw & 0xE000) == 0x2000:
                sub_op = (raw >> 11) & 0x3
                rd = (raw >> 8) & 0x7
                imm8 = raw & 0xFF
                if sub_op == 0: # MOV Rd, #imm8
                    ir_ops.append({
                        "pc": instr_pc,
                        "op": "MOV_IMM",
                        "c_code": f"ctx->r[{rd}] = 0x{imm8:08X}; ctx->flag_z = ({imm8} == 0);"
                    })
                elif sub_op == 1: # CMP Rd, #imm8
                    ir_ops.append({
                        "pc": instr_pc,
                        "op": "CMP_IMM",
                        "c_code": f"ctx->flag_z = (ctx->r[{rd}] == 0x{imm8:08X});"
                    })
                elif sub_op == 2: # ADD Rd, #imm8
                    ir_ops.append({
                        "pc": instr_pc,
                        "op": "ADD_IMM",
                        "c_code": f"ctx->r[{rd}] += 0x{imm8:08X}; ctx->flag_z = (ctx->r[{rd}] == 0);"
                    })
                elif sub_op == 3: # SUB Rd, #imm8
                    ir_ops.append({
                        "pc": instr_pc,
                        "op": "SUB_IMM",
                        "c_code": f"ctx->r[{rd}] -= 0x{imm8:08X}; ctx->flag_z = (ctx->r[{rd}] == 0);"
                    })

            # 9. Load / Store with immediate offset: LDR / STR / LDRB / STRB (Format 9: 0x6000 - 0x7FFF)
            elif (raw & 0xE000) == 0x6000:
                is_byte = bool(raw & 0x1000)
                is_load = bool(raw & 0x0800)
                imm5 = ((raw >> 6) & 0x1F) << (0 if is_byte else 2)
                rn = (raw >> 3) & 0x7
                rd = raw & 0x7

                if is_load:
                    fn = "mem_read8" if is_byte else "mem_read32"
                    ir_ops.append({
                        "pc": instr_pc,
                        "op": "LDR",
                        "c_code": f"ctx->r[{rd}] = {fn}(ctx, ctx->r[{rn}] + {imm5});"
                    })
                else:
                    fn = "mem_write8" if is_byte else "mem_write32"
                    val_expr = f"(uint8_t)ctx->r[{rd}]" if is_byte else f"ctx->r[{rd}]"
                    ir_ops.append({
                        "pc": instr_pc,
                        "op": "STR",
                        "c_code": f"{fn}(ctx, ctx->r[{rn}] + {imm5}, {val_expr});"
                    })

            # 10. Load / Store Halfword: LDRH / STRH (Format 10: 0x8000 - 0x8FFF)
            elif (raw & 0xF000) == 0x8000:
                is_load = bool(raw & 0x0800)
                imm5 = ((raw >> 6) & 0x1F) << 1
                rn = (raw >> 3) & 0x7
                rd = raw & 0x7

                if is_load:
                    ir_ops.append({
                        "pc": instr_pc,
                        "op": "LDRH",
                        "c_code": f"ctx->r[{rd}] = mem_read16(ctx, ctx->r[{rn}] + {imm5});"
                    })
                else:
                    ir_ops.append({
                        "pc": instr_pc,
                        "op": "STRH",
                        "c_code": f"mem_write16(ctx, ctx->r[{rn}] + {imm5}, (uint16_t)ctx->r[{rd}]);"
                    })

            # 11. Add / Subtract register or 3-bit immediate (Format 2: 0x1800 - 0x1FFF)
            elif (raw & 0xF800) == 0x1800:
                is_imm = bool(raw & 0x0400)
                is_sub = bool(raw & 0x0200)
                rn = (raw >> 3) & 0x7
                rd = raw & 0x7
                op2 = ((raw >> 6) & 0x7) if is_imm else f"ctx->r[{(raw >> 6) & 0x7}]"
                sign = "-" if is_sub else "+"
                ir_ops.append({
                    "pc": instr_pc,
                    "op": "SUB_REG" if is_sub else "ADD_REG",
                    "c_code": f"ctx->r[{rd}] = ctx->r[{rn}] {sign} {op2}; ctx->flag_z = (ctx->r[{rd}] == 0);"
                })

            else:
                ir_ops.append({
                    "pc": instr_pc,
                    "op": "THUMB_RAW",
                    "raw": raw,
                    "c_code": f"/* Unhandled Thumb opcode 0x{raw:04X} at 0x{instr_pc:08X} */"
                })
                if raw == 0:
                    ir_ops.append({
                        "pc": instr_pc,
                        "op": "HALT",
                        "c_code": "return 0; /* padding halt */"
                    })
                    break

        return ir_ops, targets
