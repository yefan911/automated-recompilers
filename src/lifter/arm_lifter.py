#!/usr/bin/env python3
"""
ARM7TDMI Static Lifter
Translates ARM 32-bit instructions (ALU, Branch, Memory, BX) into IR,
builds a Control Flow Graph (CFG), and outputs structured C functions.
"""

import os
import sys
import struct
from typing import List, Dict, Any, Tuple, Optional

# Ensure project root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.lifter.cfg import BasicBlock, ControlFlowGraph
from src.lifter.thumb_lifter import ThumbLifter


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
                    "c_code": f"return ctx->r[{rm}]; /* bx r{rm} */"
                })
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
                    ir_ops.append({
                        "pc": instr_pc,
                        "op": "CALL",
                        "target": target_vram,
                        "c_code": f"ctx->r[14] = 0x{instr_pc + 4:08X};\n    recomp_call(ctx, 0x{target_vram:08X});"
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
                        cond_check = "!ctx->flag_z" if cond == 0x1 else "ctx->flag_z"
                        ir_ops.append({
                            "pc": instr_pc,
                            "op": "COND_BRANCH",
                            "target": target_vram,
                            "fallthrough": fallthrough,
                            "c_code": f"if ({cond_check}) return 0x{target_vram:08X};\n    else return 0x{fallthrough:08X};"
                        })
                    break

            # 3. Halfword Data Transfer: LDRH / STRH (0x00000090 with bits [7:4] == 0x9 or 0xB)
            elif (raw_instr & 0x0E000090) == 0x00000090:
                is_load = bool(raw_instr & 0x00100000)
                is_imm_offset = bool(raw_instr & 0x00400000)
                rn = (raw_instr >> 16) & 0xF
                rd = (raw_instr >> 12) & 0xF
                is_add = bool(raw_instr & 0x00800000)
                sign = "+" if is_add else "-"

                if is_imm_offset:
                    offset8 = ((raw_instr >> 4) & 0xF0) | (raw_instr & 0xF)
                    addr_expr = f"ctx->r[{rn}] {sign} {offset8}" if offset8 else f"ctx->r[{rn}]"
                else:
                    rm = raw_instr & 0xF
                    addr_expr = f"ctx->r[{rn}] {sign} ctx->r[{rm}]"

                if is_load:
                    ir_ops.append({
                        "pc": instr_pc,
                        "op": "LDRH",
                        "rd": rd,
                        "c_code": f"ctx->r[{rd}] = mem_read16(ctx, {addr_expr});"
                    })
                else:
                    ir_ops.append({
                        "pc": instr_pc,
                        "op": "STRH",
                        "rd": rd,
                        "c_code": f"mem_write16(ctx, {addr_expr}, (uint16_t)ctx->r[{rd}]);"
                    })

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
                    if shift_amount == 0 and shift_type == 0:
                        op2_str = f"ctx->r[{rm}]"
                    elif shift_type == 0:  # LSL
                        op2_str = f"(ctx->r[{rm}] << {shift_amount})"
                    elif shift_type == 1:  # LSR
                        op2_str = f"(ctx->r[{rm}] >> {shift_amount})"
                    elif shift_type == 2:  # ASR
                        op2_str = f"((int32_t)ctx->r[{rm}] >> {shift_amount})"
                    else:  # ROR
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
                if s_bit and alu_op not in (0x8, 0x9, 0xA, 0xB):
                    c_code += f" ctx->flag_z = (ctx->r[{rd}] == 0);"
                ir_op_entry = {
                    "pc": instr_pc,
                    "op": op_name,
                    "rd": rd,
                    "c_code": c_code
                }
                if is_imm and alu_op == 0xD:
                    ir_op_entry["val"] = op2_val
                ir_ops.append(ir_op_entry)

            # 5. Single Data Transfer: LDR / STR / LDRB / STRB (0x04000000 - 0x07FFFFFF)
            elif (raw_instr & 0x0C000000) == 0x04000000:
                is_reg_offset = bool(raw_instr & 0x02000000)
                is_add = bool(raw_instr & 0x00800000)
                is_byte = bool(raw_instr & 0x00400000)
                is_load = bool(raw_instr & 0x00100000)
                rn = (raw_instr >> 16) & 0xF
                rd = (raw_instr >> 12) & 0xF

                if not is_reg_offset:
                    offset12 = raw_instr & 0xFFF
                    if rn == 15 and is_load and not is_byte:  # PC-relative load from constant pool
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
                        addr_expr = f"ctx->r[{rn}] {sign} {offset12}" if offset12 else f"ctx->r[{rn}]"
                        if is_load:
                            op_name = "LDRB" if is_byte else "LDR"
                            func_call = "mem_read8" if is_byte else "mem_read32"
                            ir_ops.append({
                                "pc": instr_pc,
                                "op": op_name,
                                "rd": rd,
                                "c_code": f"ctx->r[{rd}] = {func_call}(ctx, {addr_expr});"
                            })
                        else:
                            op_name = "STRB" if is_byte else "STR"
                            func_call = "mem_write8" if is_byte else "mem_write32"
                            val_cast = "(uint8_t)ctx->r" if is_byte else "ctx->r"
                            ir_ops.append({
                                "pc": instr_pc,
                                "op": op_name,
                                "rd": rd,
                                "c_code": f"{func_call}(ctx, {addr_expr}, {val_cast}[{rd}]);"
                            })
                else:
                    rm = raw_instr & 0xF
                    sign = "+" if is_add else "-"
                    addr_expr = f"ctx->r[{rn}] {sign} ctx->r[{rm}]"
                    if is_load:
                        op_name = "LDRB" if is_byte else "LDR"
                        func_call = "mem_read8" if is_byte else "mem_read32"
                        ir_ops.append({
                            "pc": instr_pc,
                            "op": op_name,
                            "rd": rd,
                            "c_code": f"ctx->r[{rd}] = {func_call}(ctx, {addr_expr});"
                        })
                    else:
                        op_name = "STRB" if is_byte else "STR"
                        func_call = "mem_write8" if is_byte else "mem_write32"
                        val_cast = "(uint8_t)ctx->r" if is_byte else "ctx->r"
                        ir_ops.append({
                            "pc": instr_pc,
                            "op": op_name,
                            "rd": rd,
                            "c_code": f"{func_call}(ctx, {addr_expr}, {val_cast}[{rd}]);"
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

        return ir_ops, targets

    def build_cfg(self, entry_vram: int = 0x08000000) -> ControlFlowGraph:
        """
        Traces and constructs all reachable Basic Blocks via recursive descent
        from the specified entry point, seamlessly handling both 32-bit ARM mode
        and 16-bit Thumb mode when targets have bit 0 set.
        """
        cfg = ControlFlowGraph(entry_vram)
        worklist = [entry_vram]
        visited = set()
        thumb_lifter = ThumbLifter(self.rom, self.base_vram)

        while worklist:
            raw_vram = worklist.pop(0)
            is_thumb = bool(raw_vram & 1)
            vram = raw_vram & ~1

            if vram in visited or not self.is_valid_vram(vram):
                continue
            visited.add(vram)

            if is_thumb:
                ops, targets = thumb_lifter.lift_block(vram)
            else:
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
                clean_target = target & ~1
                if clean_target not in visited and self.is_valid_vram(clean_target):
                    worklist.append(target)

        return cfg


def lift_rom_to_c(rom_path: str, entry_point: int = 0x08000000) -> str:
    with open(rom_path, "rb") as f:
        rom_data = f.read()

    lifter = ArmLifter(rom_data, base_vram=0x08000000)
    cfg = lifter.build_cfg(entry_point)

    c_source = [
        '/* Automatically Generated by Automated Recompiler Framework */',
        '#define _CRT_SECURE_NO_WARNINGS',
        '#include <stdint.h>',
        '#include <stdio.h>',
        '#include <stdbool.h>',
        '#include <stdlib.h>',
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
        '    uint16_t dispcnt;        /* Display control MMIO */',
        '} ArmCpuContext;',
        '',
        '/* Hardware Memory Bus Shims */',
        'static inline uint8_t mem_read8(ArmCpuContext* ctx, uint32_t addr) {',
        '    if (addr >= 0x02000000 && addr < 0x02040000) return ctx->ewram[addr - 0x02000000];',
        '    if (addr >= 0x03000000 && addr < 0x03008000) return ctx->iwram[addr - 0x03000000];',
        '    if (addr >= 0x06000000 && addr < 0x06018000) return ctx->vram[addr - 0x06000000];',
        '    return 0;',
        '}',
        '',
        'static inline void mem_write8(ArmCpuContext* ctx, uint32_t addr, uint8_t val) {',
        '    if (addr >= 0x02000000 && addr < 0x02040000) ctx->ewram[addr - 0x02000000] = val;',
        '    else if (addr >= 0x03000000 && addr < 0x03008000) ctx->iwram[addr - 0x03000000] = val;',
        '    else if (addr >= 0x06000000 && addr < 0x06018000) ctx->vram[addr - 0x06000000] = val;',
        '}',
        '',
        'static inline uint16_t mem_read16(ArmCpuContext* ctx, uint32_t addr) {',
        '    if (addr >= 0x02000000 && addr < 0x02040000) return *(uint16_t*)&ctx->ewram[addr - 0x02000000];',
        '    if (addr >= 0x03000000 && addr < 0x03008000) return *(uint16_t*)&ctx->iwram[addr - 0x03000000];',
        '    if (addr >= 0x06000000 && addr < 0x06018000) return *(uint16_t*)&ctx->vram[addr - 0x06000000];',
        '    return 0;',
        '}',
        '',
        'static inline void mem_write16(ArmCpuContext* ctx, uint32_t addr, uint16_t val) {',
        '    if (addr == 0x04000000) {',
        '        ctx->dispcnt = val;',
        '        printf("[GBA HAL] REG_DISPCNT set to 0x%04X (Mode %d)\\n", val, val & 7);',
        '    } else if (addr >= 0x02000000 && addr < 0x02040000) {',
        '        *(uint16_t*)&ctx->ewram[addr - 0x02000000] = val;',
        '    } else if (addr >= 0x03000000 && addr < 0x03008000) {',
        '        *(uint16_t*)&ctx->iwram[addr - 0x03000000] = val;',
        '    } else if (addr >= 0x06000000 && addr < 0x06018000) {',
        '        uint32_t offset = addr - 0x06000000;',
        '        *(uint16_t*)&ctx->vram[offset] = val;',
        '        ctx->pixels_written++;',
        '    }',
        '}',
        '',
        'static inline uint32_t mem_read32(ArmCpuContext* ctx, uint32_t addr) {',
        '    if (addr >= 0x02000000 && addr < 0x02040000) return *(uint32_t*)&ctx->ewram[addr - 0x02000000];',
        '    if (addr >= 0x03000000 && addr < 0x03008000) return *(uint32_t*)&ctx->iwram[addr - 0x03000000];',
        '    if (addr >= 0x06000000 && addr < 0x06018000) return *(uint32_t*)&ctx->vram[addr - 0x06000000];',
        '    return 0;',
        '}',
        '',
        'static inline void mem_write32(ArmCpuContext* ctx, uint32_t addr, uint32_t val) {',
        '    if (addr >= 0x02000000 && addr < 0x02040000) *(uint32_t*)&ctx->ewram[addr - 0x02000000] = val;',
        '    else if (addr >= 0x03000000 && addr < 0x03008000) *(uint32_t*)&ctx->iwram[addr - 0x03000000] = val;',
        '    else if (addr >= 0x06000000 && addr < 0x06018000) *(uint32_t*)&ctx->vram[addr - 0x06000000] = val;',
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

    # Emit global dispatch trampoline
    for line in cfg.emit_dispatch_function():
        c_source.append(line)

    # Emit Win32 Window Presentation & Main Entry
    c_source.extend([
        '#ifdef _WIN32',
        '/* Win32 Presentation Window (Scales GBA 240x160 3x to 720x480) */',
        'static uint32_t screen_buffer[240 * 160];',
        '',
        'void update_screen_from_vram(ArmCpuContext* ctx) {',
        '    uint16_t* vram16 = (uint16_t*)ctx->vram;',
        '    for (int i = 0; i < 240 * 160; i++) {',
        '        uint16_t c = vram16[i];',
        '        uint8_t r = ((c >>  0) & 0x1F) << 3;',
        '        uint8_t g = ((c >>  5) & 0x1F) << 3;',
        '        uint8_t b = ((c >> 10) & 0x1F) << 3;',
        '        /* Win32 DIB format: 0x00RRGGBB */',
        '        screen_buffer[i] = (r << 16) | (g << 8) | b;',
        '    }',
        '}',
        '',
        'LRESULT CALLBACK WindowProc(HWND hwnd, UINT uMsg, WPARAM wParam, LPARAM lParam) {',
        '    if (uMsg == WM_DESTROY || (uMsg == WM_KEYDOWN && wParam == VK_ESCAPE)) {',
        '        PostQuitMessage(0);',
        '        return 0;',
        '    }',
        '    return DefWindowProc(hwnd, uMsg, wParam, lParam);',
        '}',
        '',
        'void run_presentation_window(ArmCpuContext* ctx) {',
        '    update_screen_from_vram(ctx);',
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
        '    HWND hwnd = CreateWindow("RecompGBAWindow", "Automated Recompiled Game - Native Display",',
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
        '    printf("[HAL Window] Desktop Window Launched (720x480). Press ESC to close.\\n");',
        '    ',
        '    while (GetMessage(&msg, NULL, 0, 0)) {',
        '        TranslateMessage(&msg);',
        '        DispatchMessage(&msg);',
        '        StretchDIBits(hdc, 0, 0, win_w, win_h, 0, 0, 240, 160, screen_buffer, &bmi, DIB_RGB_COLORS, SRCCOPY);',
        '    }',
        '    ReleaseDC(hwnd, hdc);',
        '}',
        '#endif',
        '',
        '/* Main Entry / Native Recompiled Executable */',
        'static ArmCpuContext s_ctx;',
        'int main(int argc, char** argv) {',
        '    (void)argc;',
        '    (void)argv;',
        '    printf("=== Starting Automated Recompiled Game ===\\n");',
        '    ArmCpuContext* ctx = &s_ctx;',
        '    ',
        f'    uint32_t next_pc = 0x{entry_point:08X};',
        '    int max_cycles = 100000;',
        '    while (max_cycles-- > 0 && next_pc != 0) {',
        '        next_pc = recomp_dispatch(ctx, next_pc);',
        '    }',
        '    ',
        '    printf("=== Recompiled execution finished successfully ===\\n");',
        '    printf("  * REG_DISPCNT  : 0x%04X (Mode %d)\\n", ctx->dispcnt, ctx->dispcnt & 7);',
        '    printf("  * Pixels Drawn : %u pixels written to VRAM\\n", ctx->pixels_written);',
        '    ',
        '#ifdef _WIN32',
        '    if (argc > 1 && strcmp(argv[1], "--window") == 0) {',
        '        run_presentation_window(ctx);',
        '    }',
        '#endif',
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
