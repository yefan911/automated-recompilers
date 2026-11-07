#!/usr/bin/env python3
"""
ARM7TDMI Static Lifter
Translates ARM 32-bit instructions (ALU, Branch, Memory, BX) into IR,
builds a Control Flow Graph (CFG), and outputs structured C functions.
"""

import os
import sys
import struct
from collections import deque
from typing import List, Dict, Any, Tuple, Optional

# Ensure project root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.lifter.cfg import BasicBlock, ControlFlowGraph, JumpTableRecovery
from src.lifter.thumb_lifter import ThumbLifter
from src.lifter.arm_codegen import ARM_FLAG_HELPERS, condition_expr


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
            op_start = len(ir_ops)

            # 1. Branch and Exchange (BX): 0x012FFF10..
            if (raw_instr & 0x0FFFFFF0) == 0x012FFF10:
                rm = raw_instr & 0xF
                # Check if register value is known statically from previous instruction
                for prev in reversed(ir_ops):
                    if prev.get("rd") == rm and "val" in prev:
                        targets.append(prev["val"])
                        break
                ir_ops.append({
                    "pc": instr_pc,
                    "op": "BX",
                    "rm": rm,
                    "c_code": f"if ({condition_expr(cond)}) return ctx->r[{rm}]; /* bx r{rm} */" if cond != 0xE else f"return ctx->r[{rm}]; /* bx r{rm} */"
                })
                if cond != 0xE:
                    targets.append(pc)
                    ir_ops[-1]["c_code"] += f"\n    return 0x{pc:08X};"
                break

            # 2. Branch / Branch with Link (B / BL): 0x0A000000 / 0x0B000000
            elif (raw_instr & 0x0E000000) == 0x0A000000:
                is_link = bool(raw_instr & 0x01000000)
                offset = raw_instr & 0x00FFFFFF
                # Sign extend 24-bit to 32-bit
                if offset & 0x00800000:
                    offset |= ~0x00FFFFFF
                # Target is PC + 8 + (offset << 2)
                target_vram = (instr_pc + 8 + (offset << 2)) & 0xFFFFFFFF

                if is_link:
                    targets.append(target_vram)
                    targets.append(pc)
                    ir_ops.append({
                        "pc": instr_pc,
                        "op": "CALL",
                        "target": target_vram,
                        "c_code": f"if ({condition_expr(cond)}) {{ ctx->r[14] = 0x{pc:08X}; return 0x{target_vram:08X}; }}\n    return 0x{pc:08X};"
                    })
                    break
                else:
                    # Check for self-loop (b .)
                    if target_vram == instr_pc and cond == 0xE:
                        ir_ops.append({
                            "pc": instr_pc,
                            "op": "BRANCH",
                            "target": target_vram,
                            "c_code": "return 0x00000000; /* infinite loop halt */"
                        })
                    elif cond == 0xE: # Unconditional branch
                        targets.append(target_vram)
                        ir_ops.append({
                            "pc": instr_pc,
                            "op": "BRANCH",
                            "target": target_vram,
                            "c_code": f"return 0x{target_vram:08X}; /* branch to 0x{target_vram:08X} */"
                        })
                    else: # Conditional branch (e.g. BNE, BEQ)
                        fallthrough = instr_pc + 4
                        targets.append(target_vram)
                        targets.append(fallthrough)
                        cond_check = condition_expr(cond)
                        ir_ops.append({
                            "pc": instr_pc,
                            "op": "COND_BRANCH",
                            "target": target_vram,
                            "fallthrough": fallthrough,
                            "c_code": f"if ({cond_check}) return 0x{target_vram:08X};\n    else return 0x{fallthrough:08X};"
                        })
                    break

            # Multiply and multiply-accumulate precede halfword transfer decoding.
            elif (raw_instr & 0x0FC000F0) == 0x00000090:
                rd = (raw_instr >> 16) & 0xF
                rn = (raw_instr >> 12) & 0xF
                rs = (raw_instr >> 8) & 0xF
                rm = raw_instr & 0xF
                accumulate = bool(raw_instr & 0x00200000)
                code = f"ctx->r[{rd}] = ctx->r[{rm}] * ctx->r[{rs}]"
                code += f" + ctx->r[{rn}];" if accumulate else ";"
                if raw_instr & 0x00100000:
                    code += f" arm_set_nz(ctx, ctx->r[{rd}]);"
                ir_ops.append({"pc": instr_pc, "op": "MLA" if accumulate else "MUL", "rd": rd, "c_code": code})

            # Halfword and signed-byte data transfers.
            elif (raw_instr & 0x0E000090) == 0x00000090 and raw_instr & 0x60:
                is_load = bool(raw_instr & 0x00100000)
                is_imm_offset = bool(raw_instr & 0x00400000)
                rn = (raw_instr >> 16) & 0xF
                rd = (raw_instr >> 12) & 0xF
                is_add = bool(raw_instr & 0x00800000)
                sign = "+" if is_add else "-"
                pre_index = bool(raw_instr & 0x01000000)
                writeback = bool(raw_instr & 0x00200000) or not pre_index

                if is_imm_offset:
                    offset8 = ((raw_instr >> 4) & 0xF0) | (raw_instr & 0xF)
                    offset_expr = str(offset8)
                else:
                    rm = raw_instr & 0xF
                    offset_expr = f"ctx->r[{rm}]"

                transfer_type = (raw_instr >> 5) & 3
                if is_load:
                    read_expr = ("mem_read16(ctx, address)" if transfer_type == 1
                                 else "(uint32_t)(int32_t)(int8_t)mem_read8(ctx, address)" if transfer_type == 2
                                 else "(uint32_t)(int32_t)(int16_t)mem_read16(ctx, address)")
                    op_name = {1: "LDRH", 2: "LDRSB", 3: "LDRSH"}[transfer_type]
                    transfer = f"ctx->r[{rd}] = {read_expr};"
                else:
                    op_name = "STRH"
                    transfer = f"mem_write16(ctx, address, (uint16_t)ctx->r[{rd}]);"
                code = (f"{{ uint32_t base = ctx->r[{rn}]; uint32_t adjusted = base {sign} ({offset_expr}); "
                        f"uint32_t address = {'adjusted' if pre_index else 'base'}; {transfer}")
                if writeback:
                    code += f" ctx->r[{rn}] = adjusted;"
                code += " }"
                ir_ops.append({"pc": instr_pc, "op": op_name, "rd": rd, "c_code": code})

            # 4. Data Processing (ALU operations): ADD, SUB, AND, ORR, EOR, CMP, MOV, etc.
            elif (raw_instr & 0x0C000000) == 0x00000000 and (raw_instr & 0x00000090) != 0x00000090:
                is_imm = bool(raw_instr & 0x02000000)
                s_bit = bool(raw_instr & 0x00100000)
                alu_op = (raw_instr >> 21) & 0xF
                rn = (raw_instr >> 16) & 0xF
                rd = (raw_instr >> 12) & 0xF

                if is_imm:
                    imm8 = raw_instr & 0xFF
                    rotate = ((raw_instr >> 8) & 0xF) * 2
                    op2_val = ((imm8 >> rotate) | (imm8 << (32 - rotate))) & 0xFFFFFFFF if rotate > 0 else imm8
                    op2_str = f"0x{op2_val:08X}"
                else:
                    rm = raw_instr & 0xF
                    shift_type = (raw_instr >> 5) & 0x3
                    shift_amount = (raw_instr >> 7) & 0x1F
                    if raw_instr & 0x10:
                        shift_reg = (raw_instr >> 8) & 0xF
                        op2_str = f"arm_shift(ctx, ctx->r[{rm}], {shift_type}, ctx->r[{shift_reg}] & 0xFF, true, false)"
                    elif shift_amount == 0 and shift_type == 0:
                        op2_str = f"ctx->r[{rm}]"
                    elif shift_type == 0:  # LSL
                        op2_str = f"(ctx->r[{rm}] << {shift_amount})"
                    elif shift_type == 1:  # LSR
                        op2_str = f"(ctx->r[{rm}] >> {shift_amount})" if shift_amount else "0"
                    elif shift_type == 2:  # ASR
                        op2_str = f"((int32_t)ctx->r[{rm}] >> {shift_amount})" if shift_amount else f"(((int32_t)ctx->r[{rm}] < 0) ? 0xFFFFFFFF : 0)"
                    else:  # ROR (or RRX if shift_amount == 0)
                        if shift_amount == 0:
                            op2_str = f"((ctx->r[{rm}] >> 1) | (((ctx->cpsr >> 29) & 1) << 31))"
                        else:
                            op2_str = f"((ctx->r[{rm}] >> {shift_amount}) | (ctx->r[{rm}] << (32 - {shift_amount})))"

                alu_map = {
                    0x0: ("AND", f"ctx->r[{rd}] = ctx->r[{rn}] & {op2_str};"),
                    0x1: ("EOR", f"ctx->r[{rd}] = ctx->r[{rn}] ^ {op2_str};"),
                    0x2: ("SUB", f"ctx->r[{rd}] = ctx->r[{rn}] - {op2_str};"),
                    0x3: ("RSB", f"ctx->r[{rd}] = {op2_str} - ctx->r[{rn}];"),
                    0x4: ("ADD", f"ctx->r[{rd}] = ctx->r[{rn}] + {op2_str};"),
                    0x5: ("ADC", f"ctx->r[{rd}] = ctx->r[{rn}] + {op2_str} + ((ctx->cpsr >> 29) & 1);"),
                    0x6: ("SBC", f"ctx->r[{rd}] = ctx->r[{rn}] - {op2_str} + ((ctx->cpsr >> 29) & 1) - 1;"),
                    0x7: ("RSC", f"ctx->r[{rd}] = {op2_str} - ctx->r[{rn}] + ((ctx->cpsr >> 29) & 1) - 1;"),
                    0x8: ("TST", f"ctx->flag_z = ((ctx->r[{rn}] & ({op2_str})) == 0);"),
                    0x9: ("TEQ", f"ctx->flag_z = ((ctx->r[{rn}] ^ ({op2_str})) == 0);"),
                    0xA: ("CMP", f"ctx->flag_z = ((ctx->r[{rn}] - ({op2_str})) == 0);"),
                    0xB: ("CMN", f"ctx->flag_z = ((ctx->r[{rn}] + ({op2_str})) == 0);"),
                    0xC: ("ORR", f"ctx->r[{rd}] = ctx->r[{rn}] | {op2_str};"),
                    0xD: ("MOV_IMM" if is_imm else "MOV", f"ctx->r[{rd}] = {op2_str};"),
                    0xE: ("BIC", f"ctx->r[{rd}] = ctx->r[{rn}] & ~({op2_str});"),
                    0xF: ("MVN", f"ctx->r[{rd}] = ~({op2_str});"),
                }

                op_name, c_code = alu_map[alu_op]
                update_flags = s_bit or alu_op in (0x8, 0x9, 0xA, 0xB)
                if update_flags:
                    a = f"ctx->r[{rn}]"
                    b = op2_str
                    carry = "((ctx->cpsr >> 29) & 1)"
                    arithmetic = {
                        0x2: f"arm_sub(ctx, {a}, {b}, 1, true)",
                        0x3: f"arm_sub(ctx, {b}, {a}, 1, true)",
                        0x4: f"arm_add(ctx, {a}, {b}, 0, true)",
                        0x5: f"arm_add(ctx, {a}, {b}, {carry}, true)",
                        0x6: f"arm_sub(ctx, {a}, {b}, {carry}, true)",
                        0x7: f"arm_sub(ctx, {b}, {a}, {carry}, true)",
                        0xA: f"arm_sub(ctx, {a}, {b}, 1, true)",
                        0xB: f"arm_add(ctx, {a}, {b}, 0, true)",
                    }
                    if alu_op in arithmetic:
                        c_code = (f"(void){arithmetic[alu_op]};" if alu_op in (0xA, 0xB)
                                  else f"ctx->r[{rd}] = {arithmetic[alu_op]};")
                    else:
                        b = op2_str if is_imm else "arm_operand"
                        if alu_op in (0x8, 0x9):
                            operator = "&" if alu_op == 0x8 else "^"
                            c_code = f"arm_set_nz(ctx, {a} {operator} ({b}));"
                        else:
                            expression = {
                                0x0: f"{a} & ({b})", 0x1: f"{a} ^ ({b})",
                                0xC: f"{a} | ({b})", 0xD: b,
                                0xE: f"{a} & ~({b})", 0xF: f"~({b})",
                            }[alu_op]
                            c_code = f"ctx->r[{rd}] = {expression}; arm_set_nz(ctx, ctx->r[{rd}]);"
                        if is_imm and rotate:
                            c_code += f" ctx->cpsr = (ctx->cpsr & ~0x20000000u) | 0x{(op2_val >> 31) << 29:08X}u;"
                        elif not is_imm:
                            shift_count = f"(ctx->r[{(raw_instr >> 8) & 0xF}] & 0xFF)" if raw_instr & 0x10 else str(shift_amount)
                            c_code = f"{{ uint32_t arm_operand = arm_shift(ctx, ctx->r[{rm}], {shift_type}, {shift_count}, {'true' if raw_instr & 0x10 else 'false'}, true); (void)arm_operand; {c_code} }}"
                ir_op_entry = {
                    "pc": instr_pc,
                    "op": op_name,
                    "rd": rd,
                    "c_code": c_code
                }
                if is_imm and alu_op == 0xD:
                    ir_op_entry["val"] = op2_val
                if is_imm and alu_op == 0xA:
                    ir_op_entry["imm"] = op2_val
                ir_ops.append(ir_op_entry)
                if rd == 15 and alu_op not in (0x8, 0x9, 0xA, 0xB):
                    ir_ops[-1]["c_code"] += " return ctx->r[15] & ~3u;"
                    if cond != 0xE:
                        ir_ops[-1]["c_code"] = f"if ({condition_expr(cond)}) {{ {ir_ops[-1]['c_code']} }} return 0x{pc:08X};"
                        targets.append(pc)
                    break

            # 5. Single Data Transfer: LDR / STR / LDRB / STRB (0x04000000 - 0x07FFFFFF)
            elif (raw_instr & 0x0C000000) == 0x04000000:
                is_reg_offset = bool(raw_instr & 0x02000000)
                is_add = bool(raw_instr & 0x00800000)
                is_byte = bool(raw_instr & 0x00400000)
                is_load = bool(raw_instr & 0x00100000)
                rn = (raw_instr >> 16) & 0xF
                rd = (raw_instr >> 12) & 0xF
                pre_index = bool(raw_instr & 0x01000000)
                writeback = bool(raw_instr & 0x00200000) or not pre_index
                offset12 = raw_instr & 0xFFF
                sign = "+" if is_add else "-"

                if rn == 15 and is_load and not is_byte and not is_reg_offset and pre_index and not writeback:
                    target_addr = (instr_pc + 8 + (offset12 if is_add else -offset12)) & 0xFFFFFFFF
                    const_val = self.read_u32(target_addr)
                    entry = {
                        "pc": instr_pc, "op": "LDR_CONST", "rd": rd, "val": const_val,
                        "c_code": f"ctx->r[{rd}] = 0x{const_val:08X}; /* loaded from 0x{target_addr:08X} */"
                    }
                    if rd == 15 and self.is_valid_vram(const_val & ~3):
                        targets.append(const_val & ~3)
                else:
                    offset_expr = str(offset12)
                    if is_reg_offset:
                        rm = raw_instr & 0xF
                        shift_type = (raw_instr >> 5) & 3
                        shift_count = (raw_instr >> 7) & 0x1F
                        offset_expr = f"arm_shift(ctx, ctx->r[{rm}], {shift_type}, {shift_count}, false, false)"
                    code = (f"{{ uint32_t base = ctx->r[{rn}]; uint32_t adjusted = base {sign} ({offset_expr}); "
                            f"uint32_t address = {'adjusted' if pre_index else 'base'}; ")
                    if is_load:
                        op_name = "LDRB" if is_byte else "LDR"
                        func_call = "mem_read8" if is_byte else "mem_read32"
                        code += f"ctx->r[{rd}] = {func_call}(ctx, address);"
                    else:
                        op_name = "STRB" if is_byte else "STR"
                        func_call = "mem_write8" if is_byte else "mem_write32"
                        value = f"0x{(instr_pc + 12) & 0xFFFFFFFF:08X}u" if rd == 15 else f"ctx->r[{rd}]"
                        if is_byte:
                            value = f"(uint8_t)({value})"
                        code += f"{func_call}(ctx, address, {value});"
                    if writeback:
                        code += f" ctx->r[{rn}] = adjusted;"
                    code += " }"
                    entry = {"pc": instr_pc, "op": op_name, "rd": rd, "c_code": code}
                if is_load and rd == 15:
                    entry["c_code"] += " return ctx->r[15] & ~3u;"
                    if cond != 0xE:
                        entry["c_code"] = f"if ({condition_expr(cond)}) {{ {entry['c_code']} }} return 0x{pc:08X};"
                        targets.append(pc)
                    ir_ops.append(entry)
                    break
                ir_ops.append(entry)

            # 6. Software Interrupt (SWI): 0x0F000000
            elif (raw_instr & 0x0F000000) == 0x0F000000:
                swi_num = (raw_instr >> 16) & 0xFF
                if swi_num == 0:
                    swi_num = raw_instr & 0xFF
                ir_ops.append({
                    "pc": instr_pc,
                    "op": "SWI",
                    "swi": swi_num,
                    "c_code": f"gba_bios_swi(ctx, 0x{swi_num:02X}); /* swi 0x{swi_num:02X} */"
                })

            else:
                ir_ops.append({
                    "pc": instr_pc,
                    "op": "UNKNOWN",
                    "raw": raw_instr,
                    "c_code": f"/* Unhandled raw opcode 0x{raw_instr:08X} at 0x{instr_pc:08X} */"
                })
                # Terminate block on zero padding
                if raw_instr == 0:
                    ir_ops.append({
                        "pc": instr_pc,
                        "op": "HALT",
                        "c_code": "return 0; /* padding halt */"
                    })
                    break

            for entry in ir_ops[op_start:]:
                code = entry.get("c_code", "")
                if cond != 0xE:
                    entry["c_code"] = f"if ({condition_expr(cond)}) {{ {code} }}"
        else:
            targets.append(pc)
            ir_ops.append({"pc": pc, "op": "FALLTHROUGH", "c_code": f"return 0x{pc:08X}; /* instruction budget */"})

        for entry in ir_ops:
            if "ctx->r[15]" in entry["c_code"]:
                entry["c_code"] = f"ctx->r[15] = 0x{(entry['pc'] + 8) & 0xFFFFFFFF:08X}u; " + entry["c_code"]

        return ir_ops, targets

    def build_cfg(self, entry_vram: int = 0x08000000, max_blocks: int = 2500) -> ControlFlowGraph:
        """
        Traces and constructs all reachable Basic Blocks via recursive descent
        from the specified entry point, seamlessly handling both 32-bit ARM mode
        and 16-bit Thumb mode when targets have bit 0 set.
        """
        cfg = ControlFlowGraph(entry_vram)
        worklist = deque([entry_vram])
        visited = set()
        queued = {entry_vram & ~1}
        thumb_lifter = ThumbLifter(self.rom, self.base_vram)

        while worklist and len(cfg) < max_blocks:
            raw_vram = worklist.popleft()
            is_thumb = bool(raw_vram & 1)
            vram = raw_vram & ~1

            if vram in visited or not (thumb_lifter.is_valid_vram(vram) if is_thumb else self.is_valid_vram(vram)):
                continue
            visited.add(vram)

            if is_thumb:
                ops, targets = thumb_lifter.lift_block(vram)
                worklist_targets = [t if (t & 1) else (t | 1) for t in targets]
            else:
                ops, targets = self.lift_block(vram)
                worklist_targets = targets

            # Check for recoverable indirect jump tables
            jt = None
            if not targets and not is_thumb:
                jt = JumpTableRecovery.recover_arm_jump_table(ops, self.read_u32)
                if jt:
                    targets.extend(jt.targets)
                    worklist_targets.extend(jt.targets)

            block = BasicBlock(
                start_vram=vram,
                end_vram=ops[-1]["pc"] if ops else vram,
                instructions=ops,
                successors=targets,
                is_terminal=len(targets) == 0
            )

            if not is_thumb and 'jt' in locals() and jt:
                block.is_indirect = True
                block.terminator_type = "SWITCH"
                block.jump_table = jt
                cfg.add_jump_table(jt)

            cfg.add_block(block)

            for target in worklist_targets:
                clean_target = target & ~1
                valid_target = thumb_lifter.is_valid_vram(clean_target) if target & 1 else self.is_valid_vram(clean_target)
                if clean_target not in visited and clean_target not in queued and valid_target:
                    queued.add(clean_target)
                    worklist.append(target)

        return cfg


def lift_rom_to_c(rom_path: str, entry_point: int = 0x08000000, max_blocks: int = 2500) -> str:
    if isinstance(max_blocks, bool) or not isinstance(max_blocks, int) or max_blocks < 1:
        raise ValueError("max_blocks must be a positive integer")
    if isinstance(entry_point, bool) or not isinstance(entry_point, int) or not 0 <= entry_point <= 0xFFFFFFFF:
        raise ValueError("GBA entry point must be an unsigned 32-bit address")
    with open(rom_path, "rb") as f:
        rom_data = f.read(0x02000000 + 1)
    if not rom_data or len(rom_data) > 0x02000000:
        raise ValueError("GBA ROM size must be between 1 byte and 32 MiB")
    lifter = ArmLifter(rom_data, base_vram=0x08000000)
    valid_entry = ThumbLifter(rom_data).is_valid_vram(entry_point & ~1) if entry_point & 1 else lifter.is_valid_vram(entry_point)
    if not valid_entry:
        raise ValueError("GBA entry point must lie in mapped cartridge ROM")
    cfg = lifter.build_cfg(entry_point, max_blocks=max_blocks)

    c_source = [
        '/* Automatically Generated by Automated Recompiler Framework */',
        '#define _CRT_SECURE_NO_WARNINGS',
        '#include <stdint.h>',
        '#include <stdio.h>',
        '#include <stdbool.h>',
        '#include <stdlib.h>',
        '#include <string.h>',
        '#include <math.h>',
        '',
        '#ifdef _WIN32',
        '#include <windows.h>',
        '#endif',
        '',
        'typedef struct {',
        '    uint32_t r[16];          /* r0-r15 registers (r13=SP, r14=LR, r15=PC) */',
        '    uint32_t cpsr;           /* Status register */',
        '    bool     flag_z;         /* Zero condition flag */',
        '    uint32_t pixels_written; /* VRAM pixel counter */',
        '    uint8_t  ewram[0x40000]; /* 256KB EWRAM */',
        '    uint8_t  iwram[0x8000];  /* 32KB IWRAM */',
        '    uint8_t  vram[0x18000];  /* 96KB VRAM */',
        '    uint16_t dispcnt;        /* Display control MMIO (0x04000000) */',
        '    uint16_t bg0cnt;         /* BG0 Control (0x04000008) */',
        '    uint16_t bg1cnt;         /* BG1 Control (0x0400000A) */',
        '    uint16_t bg2cnt;         /* BG2 Control (0x0400000C) */',
        '    uint16_t bg3cnt;         /* BG3 Control (0x0400000E) */',
        '    uint16_t bg_hofs[4];     /* BG Scroll X offsets */',
        '    uint16_t bg_vofs[4];     /* BG Scroll Y offsets */',
        '    int16_t  bg2_pa, bg2_pb, bg2_pc, bg2_pd; /* BG2 Affine Matrix */',
        '    int32_t  bg2_x, bg2_y;   /* BG2 Reference point */',
        '    int8_t   sound_fifo_a[32];/* DirectSound FIFO A */',
        '    uint8_t  fifo_a_count;   /* FIFO A write index */',
        '    uint16_t keyinput;       /* Keypad status (0x04000130, active-low) */',
        '    uint16_t vcount;         /* Scanline counter (0x04000006) */',
        '    uint8_t  pram[0x400];    /* 1KB Palette RAM (0x05000000) */',
        '} ArmCpuContext;',
        '',
        '/* Hardware Memory Bus Shims */',
        'static inline uint8_t mem_read8(ArmCpuContext* ctx, uint32_t addr) {',
        '    if (addr == 0x04000130 || addr == 0x04000131) return (uint8_t)(ctx->keyinput >> ((addr & 1) * 8));',
        '    if (addr == 0x04000000 || addr == 0x04000001) return (uint8_t)(ctx->dispcnt >> ((addr & 1) * 8));',
        '    if (addr >= 0x08000000 && addr < 0x0E000000) { uint32_t offset = (addr - 0x08000000) & 0x01FFFFFF; return offset < sizeof(gba_rom) ? gba_rom[offset] : 0; }',
        '    if (addr >= 0x02000000 && addr < 0x02040000) return ctx->ewram[addr - 0x02000000];',
        '    if (addr >= 0x03000000 && addr < 0x03008000) return ctx->iwram[addr - 0x03000000];',
        '    if (addr >= 0x05000000 && addr < 0x05000400) return ctx->pram[addr - 0x05000000];',
        '    if (addr >= 0x06000000 && addr < 0x06018000) return ctx->vram[addr - 0x06000000];',
        '    return 0;',
        '}',
        '',
        'static inline void mem_write8(ArmCpuContext* ctx, uint32_t addr, uint8_t val) {',
        '    if (addr >= 0x02000000 && addr < 0x02040000) ctx->ewram[addr - 0x02000000] = val;',
        '    else if (addr >= 0x03000000 && addr < 0x03008000) ctx->iwram[addr - 0x03000000] = val;',
        '    else if (addr >= 0x05000000 && addr < 0x05000400) ctx->pram[addr - 0x05000000] = val;',
        '    else if (addr >= 0x06000000 && addr < 0x06018000) ctx->vram[addr - 0x06000000] = val;',
        '}',
        '',
        'static inline uint16_t mem_read16(ArmCpuContext* ctx, uint32_t addr) {',
        '    if (addr == 0x04000000) return ctx->dispcnt;',
        '    if (addr == 0x04000004) return (ctx->vcount >= 160) ? 0x0001 : 0x0000; /* REG_DISPSTAT: VBlank bit */',
        '    if (addr == 0x04000006) return ctx->vcount;',
        '    if (addr == 0x04000008) return ctx->bg0cnt;',
        '    if (addr == 0x0400000A) return ctx->bg1cnt;',
        '    if (addr == 0x0400000C) return ctx->bg2cnt;',
        '    if (addr == 0x0400000E) return ctx->bg3cnt;',
        '    if (addr == 0x04000130) return ctx->keyinput;',
        '    if ((addr >= 0x02000000 && addr <= 0x02040000 - 2) || (addr >= 0x03000000 && addr <= 0x03008000 - 2) || (addr >= 0x05000000 && addr <= 0x05000400 - 2) || (addr >= 0x06000000 && addr <= 0x06018000 - 2) || (addr >= 0x08000000 && addr <= 0x0E000000 - 2)) return (uint16_t)(mem_read8(ctx, addr) | ((uint16_t)mem_read8(ctx, addr + 1) << 8));',
        '    return 0;',
        '}',
        '',
        'static inline void mem_write16(ArmCpuContext* ctx, uint32_t addr, uint16_t val) {',
        '    if (addr == 0x04000000) {',
        '        ctx->dispcnt = val;',
        '        printf("[GBA HAL] REG_DISPCNT set to 0x%04X (Mode %d)\\n", val, val & 7);',
        '    } else if (addr == 0x04000008) {',
        '        ctx->bg0cnt = val;',
        '    } else if (addr == 0x0400000A) {',
        '        ctx->bg1cnt = val;',
        '    } else if (addr == 0x0400000C) {',
        '        ctx->bg2cnt = val;',
        '    } else if (addr == 0x0400000E) {',
        '        ctx->bg3cnt = val;',
        '    } else if (addr >= 0x04000010 && addr <= 0x04000016) {',
        '        int bg = (addr - 0x04000010) / 4;',
        '        if ((addr & 2) == 0) ctx->bg_hofs[bg] = val;',
        '        else ctx->bg_vofs[bg] = val;',
        '    } else if (addr == 0x04000020) {',
        '        ctx->bg2_pa = (int16_t)val;',
        '    } else if (addr == 0x04000022) {',
        '        ctx->bg2_pb = (int16_t)val;',
        '    } else if (addr == 0x04000024) {',
        '        ctx->bg2_pc = (int16_t)val;',
        '    } else if (addr == 0x04000026) {',
        '        ctx->bg2_pd = (int16_t)val;',
        '    } else if (addr >= 0x02000000 && addr <= 0x02040000 - 2) {',
        '        mem_write8(ctx, addr, (uint8_t)val); mem_write8(ctx, addr + 1, (uint8_t)(val >> 8));',
        '    } else if (addr >= 0x03000000 && addr <= 0x03008000 - 2) {',
        '        mem_write8(ctx, addr, (uint8_t)val); mem_write8(ctx, addr + 1, (uint8_t)(val >> 8));',
        '    } else if (addr >= 0x05000000 && addr <= 0x05000400 - 2) {',
        '        mem_write8(ctx, addr, (uint8_t)val); mem_write8(ctx, addr + 1, (uint8_t)(val >> 8));',
        '    } else if (addr >= 0x06000000 && addr <= 0x06018000 - 2) {',
        '        mem_write8(ctx, addr, (uint8_t)val); mem_write8(ctx, addr + 1, (uint8_t)(val >> 8));',
        '        ctx->pixels_written++;',
        '    }',
        '}',
        '',
        'static inline uint32_t mem_read32(ArmCpuContext* ctx, uint32_t addr) {',
        '    if ((addr >= 0x02000000 && addr <= 0x02040000 - 4) || (addr >= 0x03000000 && addr <= 0x03008000 - 4) || (addr >= 0x05000000 && addr <= 0x05000400 - 4) || (addr >= 0x06000000 && addr <= 0x06018000 - 4) || (addr >= 0x08000000 && addr <= 0x0E000000 - 4)) return mem_read8(ctx, addr) | ((uint32_t)mem_read8(ctx, addr + 1) << 8) | ((uint32_t)mem_read8(ctx, addr + 2) << 16) | ((uint32_t)mem_read8(ctx, addr + 3) << 24);',
        '    return 0;',
        '}',
        '',
        'static inline void mem_write32(ArmCpuContext* ctx, uint32_t addr, uint32_t val) {',
        '    if (addr == 0x04000028) {',
        '        ctx->bg2_x = (int32_t)val;',
        '    } else if (addr == 0x0400002C) {',
        '        ctx->bg2_y = (int32_t)val;',
        '    } else if (addr == 0x040000A0) {',
        '        ctx->sound_fifo_a[ctx->fifo_a_count & 0x1F] = (int8_t)(val & 0xFF);',
        '        ctx->sound_fifo_a[(ctx->fifo_a_count + 1) & 0x1F] = (int8_t)((val >> 8) & 0xFF);',
        '        ctx->sound_fifo_a[(ctx->fifo_a_count + 2) & 0x1F] = (int8_t)((val >> 16) & 0xFF);',
        '        ctx->sound_fifo_a[(ctx->fifo_a_count + 3) & 0x1F] = (int8_t)((val >> 24) & 0xFF);',
        '        ctx->fifo_a_count += 4;',
        '    } else if ((addr >= 0x02000000 && addr <= 0x02040000 - 4) || (addr >= 0x03000000 && addr <= 0x03008000 - 4) || (addr >= 0x05000000 && addr <= 0x05000400 - 4) || (addr >= 0x06000000 && addr <= 0x06018000 - 4)) {',
        '        mem_write8(ctx, addr, (uint8_t)val); mem_write8(ctx, addr + 1, (uint8_t)(val >> 8)); mem_write8(ctx, addr + 2, (uint8_t)(val >> 16)); mem_write8(ctx, addr + 3, (uint8_t)(val >> 24));',
        '    }',
        '}',
        '',
        '/* GBA BIOS SWI Emulation Shims */',
        'static inline void gba_bios_swi(ArmCpuContext* ctx, uint32_t swi_num) {',
        '    switch (swi_num) {',
        '        case 0x00: /* SoftReset */',
        '            ctx->r[13] = 0x03007F00;',
        '            break;',
        '        case 0x01: /* RegisterRamReset */',
        '            break;',
        '        case 0x02: /* Halt */',
        '        case 0x03: /* Stop */',
        '        case 0x04: /* IntrWait */',
        '        case 0x05: /* VBlankIntrWait */',
        '            break;',
        '        case 0x06: /* Div: r0 / r1 */',
        '            if (ctx->r[1] != 0) {',
        '                int64_t num = (int32_t)ctx->r[0];',
        '                int64_t den = (int32_t)ctx->r[1];',
        '                ctx->r[0] = (uint32_t)(num / den);',
        '                ctx->r[1] = (uint32_t)(num % den);',
        '                int64_t quotient = num / den; ctx->r[3] = (uint32_t)(quotient < 0 ? -quotient : quotient);',
        '            }',
        '            break;',
        '        case 0x07: /* DivARM: r1 / r0 */',
        '            if (ctx->r[0] != 0) {',
        '                int64_t num = (int32_t)ctx->r[1];',
        '                int64_t den = (int32_t)ctx->r[0];',
        '                ctx->r[0] = (uint32_t)(num / den);',
        '                ctx->r[1] = (uint32_t)(num % den);',
        '                int64_t quotient = num / den; ctx->r[3] = (uint32_t)(quotient < 0 ? -quotient : quotient);',
        '            }',
        '            break;',
        '        case 0x08: /* Sqrt */',
        '            {',
        '                uint32_t val = ctx->r[0];',
        '                uint32_t root = 0;',
        '                uint32_t bit = 1u << 30;',
        '                while (bit > val) bit >>= 2;',
        '                while (bit) { if (val >= root + bit) { val -= root + bit; root = (root >> 1) + bit; } else root >>= 1; bit >>= 2; }',
        '                ctx->r[0] = root;',
        '            }',
        '            break;',
        '        case 0x0A: /* ArcTan2: r0 = x, r1 = y */',
        '            {',
        '                int32_t x = (int32_t)ctx->r[0];',
        '                int32_t y = (int32_t)ctx->r[1];',
        '                double angle = atan2((double)y, (double)x);',
        '                if (angle < 0) angle += 2.0 * 3.141592653589793;',
        '                ctx->r[0] = (uint32_t)(angle * 65536.0 / (2.0 * 3.141592653589793));',
        '            }',
        '            break;',
        '        case 0x0B: /* CpuSet */',
        '            {',
        '                uint32_t src = ctx->r[0];',
        '                uint32_t dst = ctx->r[1];',
        '                uint32_t control = ctx->r[2];',
        '                uint32_t count = control & 0x1FFFFF;',
        '                bool is_32bit = (control & (1 << 26)) != 0;',
        '                bool is_fill = (control & (1 << 24)) != 0;',
        '                for (uint32_t i = 0; i < count; i++) {',
        '                    if (is_32bit) {',
        '                        uint32_t val = mem_read32(ctx, is_fill ? src : (src + i * 4));',
        '                        mem_write32(ctx, dst + i * 4, val);',
        '                    } else {',
        '                        uint16_t val = mem_read16(ctx, is_fill ? src : (src + i * 2));',
        '                        mem_write16(ctx, dst + i * 2, val);',
        '                    }',
        '                }',
        '            }',
        '            break;',
        '        case 0x0C: /* CpuFastSet */',
        '            {',
        '                uint32_t src = ctx->r[0];',
        '                uint32_t dst = ctx->r[1];',
        '                uint32_t control = ctx->r[2];',
        '                uint32_t count = control & 0x1FFFFF;',
        '                bool is_fill = (control & (1 << 24)) != 0;',
        '                for (uint32_t i = 0; i < count; i++) {',
        '                    uint32_t val = mem_read32(ctx, is_fill ? src : (src + i * 4));',
        '                    mem_write32(ctx, dst + i * 4, val);',
        '                }',
        '            }',
        '            break;',
        '        case 0x10: /* BitUnPack: r0 = src, r1 = dst, r2 = param_ptr */',
        '            {',
        '                uint32_t src = ctx->r[0];',
        '                uint32_t dst = ctx->r[1];',
        '                uint32_t param = ctx->r[2];',
        '                uint16_t len = mem_read16(ctx, param);',
        '                uint8_t src_width = mem_read8(ctx, param + 2);',
        '                uint8_t dst_width = mem_read8(ctx, param + 3);',
        '                uint32_t base_offset = mem_read32(ctx, param + 4);',
        '                if ((src_width == 1 || src_width == 2 || src_width == 4 || src_width == 8) && (dst_width == 1 || dst_width == 2 || dst_width == 4 || dst_width == 8 || dst_width == 16 || dst_width == 32) && dst_width >= src_width) {',
        '                    uint32_t packed = 0, bits = 0, out = dst;',
        '                    uint32_t count = (uint32_t)len * 8 / src_width;',
        '                    for (uint32_t i = 0; i < count; i++) {',
        '                        uint8_t b = mem_read8(ctx, src + (i * src_width / 8));',
        '                        uint8_t val = (b >> ((i * src_width) % 8)) & ((1 << src_width) - 1);',
        '                        uint32_t value = val; if (val != 0 || (base_offset & 0x80000000u)) value += base_offset & 0x7FFFFFFFu;',
        '                        uint32_t mask = dst_width == 32 ? ~0u : ((1u << dst_width) - 1);',
        '                        packed |= (value & mask) << bits; bits += dst_width;',
        '                        if (bits == 32) { mem_write32(ctx, out, packed); out += 4; packed = 0; bits = 0; }',
        '                    }',
        '                    if (bits) mem_write32(ctx, out, packed);',
        '                }',
        '            }',
        '            break;',
        '        default:',
        '            break;',
        '    }',
        '}',
        '',
        '/* Basic Block Prototypes */',
    ]

    image = "static const uint8_t gba_rom[] = {\n" + ",\n".join(",".join(f"0x{b:02X}" for b in rom_data[i:i + 32]) for i in range(0, len(rom_data), 32)) + "\n};"
    c_source.insert(c_source.index('/* Hardware Memory Bus Shims */'), image)
    c_source.append(ARM_FLAG_HELPERS)

    for proto in cfg.emit_prototypes():
        c_source.append(proto)
    c_source.append('')

    # Emit all discovered basic blocks
    for block in cfg.sorted_blocks():
        c_source.append(block.emit_c_function())

    # Emit global dispatch trampoline
    for line in cfg.emit_dispatch_function():
        c_source.append(line)

    # Emit Win32 Window Presentation & Main Entry
    c_source.extend([
        '/* Framebuffer conversion shared by snapshots and window presentation. */',
        'static uint32_t screen_buffer[240 * 160];',
        '',
        'void update_screen_from_vram(ArmCpuContext* ctx) {',
        '    uint8_t mode = ctx->dispcnt & 0x7;',
        '    if (mode == 3) {',
        '        /* Mode 3: 240x160 16-bit direct color */',
        '        uint16_t* vram16 = (uint16_t*)ctx->vram;',
        '        for (int i = 0; i < 240 * 160; i++) {',
        '            uint16_t c = vram16[i];',
        '            uint8_t r = ((c >>  0) & 0x1F) << 3;',
        '            uint8_t g = ((c >>  5) & 0x1F) << 3;',
        '            uint8_t b = ((c >> 10) & 0x1F) << 3;',
        '            screen_buffer[i] = (r << 16) | (g << 8) | b;',
        '        }',
        '    } else if (mode == 4) {',
        '        /* Mode 4: 240x160 8-bit paletted with page flip */',
        '        uint32_t page = (ctx->dispcnt & (1 << 4)) ? 0xA000 : 0x0000;',
        '        uint16_t* pal = (uint16_t*)ctx->pram;',
        '        for (int i = 0; i < 240 * 160; i++) {',
        '            uint8_t idx = ctx->vram[page + i];',
        '            uint16_t c = pal[idx];',
        '            uint8_t r = ((c >>  0) & 0x1F) << 3;',
        '            uint8_t g = ((c >>  5) & 0x1F) << 3;',
        '            uint8_t b = ((c >> 10) & 0x1F) << 3;',
        '            screen_buffer[i] = (r << 16) | (g << 8) | b;',
        '        }',
        '    } else {',
        '        /* Mode 0/1/2: Tilemap PPU & Affine Renderer */',
        '        uint16_t* pal = (uint16_t*)ctx->pram;',
        '        uint16_t backdrop = pal[0];',
        '        uint32_t bg_color = (((backdrop & 0x1F) << 3) << 16) | ((((backdrop >> 5) & 0x1F) << 3) << 8) | (((backdrop >> 10) & 0x1F) << 3);',
        '        for (int i = 0; i < 240 * 160; i++) screen_buffer[i] = bg_color;',
        '        ',
        '        /* Render Backgrounds 3 down to 0 */',
        '        for (int bg = 3; bg >= 0; bg--) {',
        '            if (!(ctx->dispcnt & (1 << (8 + bg)))) continue;',
        '            uint16_t bgcnt = (bg == 0) ? ctx->bg0cnt : (bg == 1) ? ctx->bg1cnt : (bg == 2) ? ctx->bg2cnt : ctx->bg3cnt;',
        '            uint32_t cbb = ((bgcnt >> 2) & 0x3) * 0x4000;',
        '            uint32_t sbb = ((bgcnt >> 8) & 0x1F) * 0x800;',
        '            bool is_8bpp = (bgcnt & (1 << 7)) != 0;',
        '            uint16_t hofs = ctx->bg_hofs[bg];',
        '            uint16_t vofs = ctx->bg_vofs[bg];',
        '            ',
        '            for (int y = 0; y < 160; y++) {',
        '                int py = (y + vofs) & 0xFF;',
        '                int ty = py / 8;',
        '                int fine_y = py % 8;',
        '                for (int x = 0; x < 240; x++) {',
        '                    int px = (x + hofs) & 0xFF;',
        '                    int tx = px / 8;',
        '                    int fine_x = px % 8;',
        '                    uint32_t map_addr = (sbb + (ty * 32 + tx) * 2) % (sizeof(ctx->vram) - 1);',
        '                    uint16_t tile_entry = *(uint16_t*)&ctx->vram[map_addr];',
        '                    uint16_t tile_id = tile_entry & 0x3FF;',
        '                    uint8_t pal_idx = (tile_entry >> 12) & 0xF;',
        '                    ',
        '                    if (is_8bpp) {',
        '                        uint32_t tile_off = (cbb + tile_id * 64 + fine_y * 8 + fine_x) % sizeof(ctx->vram);',
        '                        uint8_t color_idx = ctx->vram[tile_off];',
        '                        if (color_idx != 0) {',
        '                            uint16_t c = pal[color_idx];',
        '                            screen_buffer[y * 240 + x] = (((c & 0x1F) << 3) << 16) | ((((c >> 5) & 0x1F) << 3) << 8) | (((c >> 10) & 0x1F) << 3);',
        '                        }',
        '                    } else {',
        '                        uint32_t tile_off = (cbb + tile_id * 32 + fine_y * 4 + (fine_x / 2)) % sizeof(ctx->vram);',
        '                        uint8_t byte_val = ctx->vram[tile_off];',
        '                        uint8_t color_idx = (fine_x % 2 == 0) ? (byte_val & 0xF) : ((byte_val >> 4) & 0xF);',
        '                        if (color_idx != 0) {',
        '                            uint16_t c = pal[(pal_idx * 16 + color_idx) & 0xFF];',
        '                            screen_buffer[y * 240 + x] = (((c & 0x1F) << 3) << 16) | ((((c >> 5) & 0x1F) << 3) << 8) | (((c >> 10) & 0x1F) << 3);',
        '                        }',
        '                    }',
        '                }',
        '            }',
        '        }',
        '    }',
        '}',
        '',
        'static int dump_framebuffer(ArmCpuContext* ctx, const char* path) {',
        '    update_screen_from_vram(ctx);',
        '    FILE* output = fopen(path, "wb");',
        '    if (!output) { perror("Framebuffer output"); return 1; }',
        '    bool ok = fprintf(output, "P6\\n240 160\\n255\\n") > 0;',
        '    for (int i = 0; ok && i < 240 * 160; i++) {',
        '        uint32_t pixel = screen_buffer[i];',
        '        uint8_t rgb[3] = {(uint8_t)(pixel >> 16), (uint8_t)(pixel >> 8), (uint8_t)pixel};',
        '        ok = fwrite(rgb, 1, 3, output) == 3;',
        '    }',
        '    if (fclose(output) != 0) ok = false;',
        '    if (!ok) { fprintf(stderr, "Could not write framebuffer\\n"); return 1; }',
        '    return 0;',
        '}',
        '',
        '#ifdef _WIN32',
        'static volatile bool g_running = true;',
        '',
        'LRESULT CALLBACK WindowProc(HWND hwnd, UINT uMsg, WPARAM wParam, LPARAM lParam) {',
        '    if (uMsg == WM_DESTROY || (uMsg == WM_KEYDOWN && wParam == VK_ESCAPE)) {',
        '        g_running = false;',
        '        PostQuitMessage(0);',
        '        return 0;',
        '    }',
        '    return DefWindowProc(hwnd, uMsg, wParam, lParam);',
        '}',
        '',
        'static inline void poll_gba_input(ArmCpuContext* ctx) {',
        '    /* GBA keys: active-low (0 = pressed, 1 = released). Default = 0x03FF */',
        '    uint16_t keys = 0x03FF;',
        '    if (GetAsyncKeyState(\'X\') & 0x8000) keys &= ~(1 << 0);       /* Button A */',
        '    if (GetAsyncKeyState(\'Z\') & 0x8000) keys &= ~(1 << 1);       /* Button B */',
        '    if (GetAsyncKeyState(VK_BACK) & 0x8000) keys &= ~(1 << 2);    /* Select */',
        '    if (GetAsyncKeyState(VK_RETURN) & 0x8000) keys &= ~(1 << 3);  /* Start */',
        '    if (GetAsyncKeyState(VK_RIGHT) & 0x8000) keys &= ~(1 << 4);   /* Right */',
        '    if (GetAsyncKeyState(VK_LEFT) & 0x8000) keys &= ~(1 << 5);    /* Left */',
        '    if (GetAsyncKeyState(VK_UP) & 0x8000) keys &= ~(1 << 6);      /* Up */',
        '    if (GetAsyncKeyState(VK_DOWN) & 0x8000) keys &= ~(1 << 7);    /* Down */',
        '    if (GetAsyncKeyState(\'S\') & 0x8000) keys &= ~(1 << 8);       /* Button R */',
        '    if (GetAsyncKeyState(\'A\') & 0x8000) keys &= ~(1 << 9);       /* Button L */',
        '    ctx->keyinput = keys;',
        '}',
        '',
        'void run_presentation_window(ArmCpuContext* ctx, uint32_t start_pc) {',
        '    HINSTANCE hInstance = GetModuleHandle(NULL);',
        '    WNDCLASS wc = {0};',
        '    wc.lpfnWndProc = WindowProc;',
        '    wc.hInstance = hInstance;',
        '    wc.lpszClassName = "RecompGBAWindow";',
        '    wc.hCursor = LoadCursor(NULL, IDC_ARROW);',
        '    RegisterClass(&wc);',
        '    ',
        '    int scale = 3;',
        '    int win_w = 240 * scale;',
        '    int win_h = 160 * scale;',
        '    RECT rect = {0, 0, win_w, win_h};',
        '    AdjustWindowRect(&rect, WS_OVERLAPPEDWINDOW, FALSE);',
        '    ',
        '    HWND hwnd = CreateWindow("RecompGBAWindow", "Automated Recompiled Game - Native Display (60 FPS)",',
        '        WS_OVERLAPPED | WS_CAPTION | WS_SYSMENU | WS_MINIMIZEBOX | WS_VISIBLE,',
        '        CW_USEDEFAULT, CW_USEDEFAULT, rect.right - rect.left, rect.bottom - rect.top,',
        '        NULL, NULL, hInstance, NULL);',
        '    ',
        '    BITMAPINFO bmi = {0};',
        '    bmi.bmiHeader.biSize = sizeof(BITMAPINFOHEADER);',
        '    bmi.bmiHeader.biWidth = 240;',
        '    bmi.bmiHeader.biHeight = -160; /* Top-down DIB */',
        '    bmi.bmiHeader.biPlanes = 1;',
        '    bmi.bmiHeader.biBitCount = 32;',
        '    bmi.bmiHeader.biCompression = BI_RGB;',
        '    ',
        '    HDC hdc = GetDC(hwnd);',
        '    MSG msg = {0};',
        '    printf("[HAL Window] Desktop Window Launched (720x480, 60 FPS). Press ESC to close.\\n");',
        '    printf("[HAL Input] Controls: Arrows=D-Pad, X=A, Z=B, Enter=Start, Backspace=Select, A=L, S=R\\n");',
        '    ',
        '    uint32_t pc = start_pc;',
        '    g_running = true;',
        '    ',
        '    while (g_running) {',
        '        while (PeekMessage(&msg, NULL, 0, 0, PM_REMOVE)) {',
        '            if (msg.message == WM_QUIT) {',
        '                g_running = false;',
        '                break;',
        '            }',
        '            TranslateMessage(&msg);',
        '            DispatchMessage(&msg);',
        '        }',
        '        if (!g_running) break;',
        '        ',
        '        poll_gba_input(ctx);',
        '        ',
        '        /* Step 228 GBA scanlines per frame (160 visible + 68 VBlank, 1,232 cycles/line) */',
        '        for (ctx->vcount = 0; ctx->vcount < 228 && pc != 0; ctx->vcount++) {',
        '            int scanline_cycles = 1232;',
        '            while (scanline_cycles-- > 0 && pc != 0) {',
        '                pc = recomp_dispatch(ctx, pc);',
        '            }',
        '        }',
        '        ',
        '        update_screen_from_vram(ctx);',
        '        StretchDIBits(hdc, 0, 0, win_w, win_h, 0, 0, 240, 160, screen_buffer, &bmi, DIB_RGB_COLORS, SRCCOPY);',
        '        Sleep(16);',
        '    }',
        '    ReleaseDC(hwnd, hdc);',
        '}',
        '#endif',
        '',
        '/* Main Entry / Native Recompiled Executable */',
        'static ArmCpuContext s_ctx;',
        'int main(int argc, char** argv) {',
        '    const char* framebuffer_path = NULL;',
        '    bool window = false;',
        '    for (int i = 1; i < argc; i++) {',
        '        if (strcmp(argv[i], "--framebuffer") == 0 && i + 1 < argc) framebuffer_path = argv[++i];',
        '        else if (strcmp(argv[i], "--window") == 0) window = true;',
        '        else if (strcmp(argv[i], "--headless") == 0) window = false;',
        '        else if (strcmp(argv[i], "--no-hold") == 0) { /* bounded mode */ }',
        '        else { fprintf(stderr, "Unknown or incomplete option: %s\\n", argv[i]); return 2; }',
        '    }',
        '    printf("=== Starting Automated Recompiled Game ===\\n");',
        '    ArmCpuContext* ctx = &s_ctx;',
        '    ctx->keyinput = 0x03FF;',
        '    ctx->r[13] = 0x03007F00;',
        '    ',
        f'    uint32_t next_pc = 0x{entry_point:08X};',
        '    int max_cycles = 100000;',
        '#if defined(_MSC_VER) && defined(_WIN32)',
        '    __try {',
        '#endif',
        '#ifdef _WIN32',
        '        if (window) {',
        '            run_presentation_window(ctx, next_pc);',
        '        } else',
        '#else',
        '        (void)window;',
        '#endif',
        '        while (max_cycles-- > 0 && next_pc != 0) {',
        '            next_pc = recomp_dispatch(ctx, next_pc);',
        '        }',
        '#if defined(_MSC_VER) && defined(_WIN32)',
        '    } __except(1) {',
        '        printf("[Crash Guard] Caught hardware exception during GBA execution (code: 0x%08lX)\\n", GetExceptionCode());',
        '        return 1;',
        '    }',
        '#endif',
        '    ',
        '    printf("=== Recompiled execution finished successfully ===\\n");',
        '    printf("  * REG_DISPCNT  : 0x%04X (Mode %d)\\n", ctx->dispcnt, ctx->dispcnt & 7);',
        '    printf("  * Pixels Drawn : %u pixels written to VRAM\\n", ctx->pixels_written);',
        '    if (framebuffer_path && dump_framebuffer(ctx, framebuffer_path) != 0) return 1;',
        '    ',
        '    return 0;',
        '}',
    ])

    return "\n".join(c_source)


if __name__ == "__main__":
    rom = sys.argv[1] if len(sys.argv) > 1 else "roms/test/hello_gba.gba"
    c_code = lift_rom_to_c(rom)
    out_file = "build/recompiled_game.c"
    os.makedirs("build", exist_ok=True)
    with open(out_file, "w") as f:
        f.write(c_code)
    print(f"Generated recompiled C source: {out_file}")
