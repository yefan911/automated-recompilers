#!/usr/bin/env python3
"""
W65C816 (SNES) Static Lifter
Translates 65816 machine code (LoROM/HiROM banked 24-bit addresses, M/X register width flags)
into structured basic blocks and emits C code for the Automated Recompiler Framework.
"""

import os
import sys
import struct
from typing import List, Dict, Any, Tuple, Optional

# Ensure project root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.lifter.cfg import BasicBlock, ControlFlowGraph, JumpTableRecovery


class SnesLifter:
    def __init__(self, rom_bytes: bytes, is_lorom: bool = True):
        self.rom = rom_bytes
        self.is_lorom = is_lorom

    def map_address_to_rom_offset(self, addr_24bit: int) -> int:
        """
        Maps a 24-bit SNES CPU address (Bank:Offset) to a physical ROM offset.
        LoROM Mapping: Bank $00-$7F, Offset $8000-$FFFF -> (Bank & 0x7F) << 15 | (Offset - 0x8000)
        Also handles banks $80-$FF (mirror of $00-$7F in LoROM).
        HiROM Mapping: Bank $40-$7D / $C0-$FF, Offset $0000-$FFFF -> (Bank & 0x3F) << 16 | Offset (or similar).
        """
        bank = (addr_24bit >> 16) & 0xFF
        offset = addr_24bit & 0xFFFF

        if self.is_lorom:
            # LoROM: CPU addresses Bank $00-$7F / $80-$FF, Offset $8000-$FFFF
            # Physical ROM offset = ((bank & 0x7F) << 15) | (offset & 0x7FFF)
            # Note: Offset must be >= 0x8000 for standard LoROM mapping, but some games use Bank $00-$3F Offset $0000-$7FFF for WRAM/SRAM.
            # For ROM mapping:
            normalized_bank = bank & 0x7F
            if offset >= 0x8000:
                rom_off = (normalized_bank << 15) | (offset - 0x8000)
            else:
                # Lower half of bank in LoROM typically points to RAM/registers, but if accessed as ROM or unmapped:
                rom_off = (normalized_bank << 15) | offset  # Fallback
            return rom_off
        else:
            # HiROM Mapping
            normalized_bank = bank & 0x3F
            if bank >= 0x40 and bank <= 0x7D:
                rom_off = ((bank - 0x40) << 16) | offset
            elif bank >= 0xC0:
                rom_off = ((bank - 0xC0) << 16) | offset
            else:
                rom_off = (normalized_bank << 16) | offset
            return rom_off

    def is_valid_address(self, addr_24bit: int) -> bool:
        rom_off = self.map_address_to_rom_offset(addr_24bit)
        return 0 <= rom_off < len(self.rom)

    def read_u8(self, addr_24bit: int) -> int:
        rom_off = self.map_address_to_rom_offset(addr_24bit)
        if 0 <= rom_off < len(self.rom):
            return self.rom[rom_off]
        return 0

    def read_u16(self, addr_24bit: int) -> int:
        b0 = self.read_u8(addr_24bit)
        b1 = self.read_u8(addr_24bit + 1)
        return b0 | (b1 << 8)

    def read_u24(self, addr_24bit: int) -> int:
        b0 = self.read_u8(addr_24bit)
        b1 = self.read_u8(addr_24bit + 1)
        b2 = self.read_u8(addr_24bit + 2)
        return b0 | (b1 << 8) | (b2 << 16)

    def lift_instruction(self, pc: int, p_flags: int) -> Tuple[Dict[str, Any], int]:
        """
        Decodes and lifts a single W65C816 instruction at 24-bit PC with status flags P.
        Returns (instruction_dict, next_pc).
        """
        m_flag = bool(p_flags & 0x20)  # Bit 5: Accumulator width (1 = 8-bit, 0 = 16-bit)
        x_flag = bool(p_flags & 0x10)  # Bit 4: Index register width (1 = 8-bit, 0 = 16-bit)

        opcode = self.read_u8(pc)
        instr_pc = pc
        next_pc = pc + 1

        # Helper for immediate values based on M/X flags
        def get_imm8() -> int:
            nonlocal next_pc
            val = self.read_u8(next_pc)
            next_pc += 1
            return val

        def get_imm16() -> int:
            nonlocal next_pc
            val = self.read_u16(next_pc)
            next_pc += 2
            return val

        def get_imm_m() -> Tuple[int, int]:
            """Returns (value, width_in_bytes) for Accumulator immediate (LDA #imm, CMP #imm, ADC #imm, etc.)"""
            if m_flag:
                return get_imm8(), 1
            else:
                return get_imm16(), 2

        def get_imm_x() -> Tuple[int, int]:
            """Returns (value, width_in_bytes) for Index immediate (LDX #imm, LDY #imm, CPX #imm, etc.)"""
            if x_flag:
                return get_imm8(), 1
            else:
                return get_imm16(), 2

        def get_abs16() -> int:
            nonlocal next_pc
            val = self.read_u16(next_pc)
            next_pc += 2
            return val

        def get_abs24() -> int:
            nonlocal next_pc
            val = self.read_u24(next_pc)
            next_pc += 3
            return val

        def get_zp8() -> int:
            nonlocal next_pc
            val = self.read_u8(next_pc)
            next_pc += 1
            return val

        # Opcodes
        # 1. REP ($C2) / SEP ($E2) - Immediate 8-bit mask modifying P status flags
        if opcode == 0xC2:
            mask = get_imm8()
            new_p = p_flags & ~mask
            return {
                "pc": instr_pc,
                "op": "REP",
                "mask": mask,
                "new_p": new_p,
                "c_code": f"ctx->p &= ~0x{mask:02X}; /* rep #{mask:#04x} */"
            }, next_pc

        elif opcode == 0xE2:
            mask = get_imm8()
            new_p = p_flags | mask
            return {
                "pc": instr_pc,
                "op": "SEP",
                "mask": mask,
                "new_p": new_p,
                "c_code": f"ctx->p |= 0x{mask:02X}; /* sep #{mask:#04x} */"
            }, next_pc

        # 2. LDA (Load Accumulator)
        # $A9: Immediate, $AD: Absolute, $A5: Zero Page, $BD: Absolute,X, $B9: Absolute,Y, $B5: Zero Page,X, $AF: Absolute Long
        elif opcode == 0xA9:
            val, width = get_imm_m()
            c = f"ctx->a = 0x{val:04X};" if width == 2 else f"ctx->a = (ctx->a & 0xFF00) | 0x{val:02X};"
            return {"pc": instr_pc, "op": "LDA_IMM", "c_code": c}, next_pc

        elif opcode == 0xAD:
            addr = get_abs16()
            if m_flag:
                c = f"ctx->a = (ctx->a & 0xFF00) | snes_read8(ctx, (ctx->db << 16) | 0x{addr:04X});"
            else:
                c = f"ctx->a = snes_read16(ctx, (ctx->db << 16) | 0x{addr:04X});"
            return {"pc": instr_pc, "op": "LDA_ABS", "addr": addr, "c_code": c}, next_pc

        elif opcode == 0xA5:
            zp = get_zp8()
            if m_flag:
                c = f"ctx->a = (ctx->a & 0xFF00) | snes_read8(ctx, (ctx->dp + 0x{zp:02X}) & 0xFFFF);"
            else:
                c = f"ctx->a = snes_read16(ctx, (ctx->dp + 0x{zp:02X}) & 0xFFFF);"
            return {"pc": instr_pc, "op": "LDA_ZP", "zp": zp, "c_code": c}, next_pc

        elif opcode == 0xAF:
            addr24 = get_abs24()
            if m_flag:
                c = f"ctx->a = (ctx->a & 0xFF00) | snes_read8(ctx, 0x{addr24:06X});"
            else:
                c = f"ctx->a = snes_read16(ctx, 0x{addr24:06X});"
            return {"pc": instr_pc, "op": "LDA_LONG", "addr24": addr24, "c_code": c}, next_pc

        # 3. STA (Store Accumulator)
        # $8D: Absolute, $85: Zero Page, $8F: Absolute Long
        elif opcode == 0x8D:
            addr = get_abs16()
            if m_flag:
                c = f"snes_write8(ctx, (ctx->db << 16) | 0x{addr:04X}, (uint8_t)ctx->a);"
            else:
                c = f"snes_write16(ctx, (ctx->db << 16) | 0x{addr:04X}, ctx->a);"
            return {"pc": instr_pc, "op": "STA_ABS", "addr": addr, "c_code": c}, next_pc

        elif opcode == 0x85:
            zp = get_zp8()
            if m_flag:
                c = f"snes_write8(ctx, (ctx->dp + 0x{zp:02X}) & 0xFFFF, (uint8_t)ctx->a);"
            else:
                c = f"snes_write16(ctx, (ctx->dp + 0x{zp:02X}) & 0xFFFF, ctx->a);"
            return {"pc": instr_pc, "op": "STA_ZP", "zp": zp, "c_code": c}, next_pc

        elif opcode == 0x8F:
            addr24 = get_abs24()
            if m_flag:
                c = f"snes_write8(ctx, 0x{addr24:06X}, (uint8_t)ctx->a);"
            else:
                c = f"snes_write16(ctx, 0x{addr24:06X}, ctx->a);"
            return {"pc": instr_pc, "op": "STA_LONG", "addr24": addr24, "c_code": c}, next_pc

        # 4. LDX / LDY (Load Index Registers)
        elif opcode == 0xA2:  # LDX Immediate
            val, width = get_imm_x()
            c = f"ctx->x = 0x{val:04X};" if width == 2 else f"ctx->x = (ctx->x & 0xFF00) | 0x{val:02X};"
            return {"pc": instr_pc, "op": "LDX_IMM", "c_code": c}, next_pc

        elif opcode == 0xA0:  # LDY Immediate
            val, width = get_imm_x()
            c = f"ctx->y = 0x{val:04X};" if width == 2 else f"ctx->y = (ctx->y & 0xFF00) | 0x{val:02X};"
            return {"pc": instr_pc, "op": "LDY_IMM", "c_code": c}, next_pc

        # 5. STX / STY
        elif opcode == 0x8E:  # STX Absolute
            addr = get_abs16()
            if x_flag:
                c = f"snes_write8(ctx, (ctx->db << 16) | 0x{addr:04X}, (uint8_t)ctx->x);"
            else:
                c = f"snes_write16(ctx, (ctx->db << 16) | 0x{addr:04X}, ctx->x);"
            return {"pc": instr_pc, "op": "STX_ABS", "c_code": c}, next_pc

        elif opcode == 0x8C:  # STY Absolute
            addr = get_abs16()
            if x_flag:
                c = f"snes_write8(ctx, (ctx->db << 16) | 0x{addr:04X}, (uint8_t)ctx->y);"
            else:
                c = f"snes_write16(ctx, (ctx->db << 16) | 0x{addr:04X}, ctx->y);"
            return {"pc": instr_pc, "op": "STY_ABS", "c_code": c}, next_pc

        # 6. Arithmetic & Logic: ADC, SBC, CMP
        elif opcode == 0x69:  # ADC Immediate
            val, width = get_imm_m()
            c = f"ctx->a += 0x{val:04X};" if width == 2 else f"ctx->a = (ctx->a & 0xFF00) | (((ctx->a & 0xFF) + 0x{val:02X}) & 0xFF);"
            return {"pc": instr_pc, "op": "ADC_IMM", "c_code": c}, next_pc

        elif opcode == 0x6D:  # ADC Absolute
            addr = get_abs16()
            if m_flag:
                c = f"ctx->a = (ctx->a & 0xFF00) | (((ctx->a & 0xFF) + snes_read8(ctx, (ctx->db << 16) | 0x{addr:04X})) & 0xFF);"
            else:
                c = f"ctx->a += snes_read16(ctx, (ctx->db << 16) | 0x{addr:04X});"
            return {"pc": instr_pc, "op": "ADC_ABS", "c_code": c}, next_pc

        elif opcode == 0xE9:  # SBC Immediate
            val, width = get_imm_m()
            c = f"ctx->a -= 0x{val:04X};" if width == 2 else f"ctx->a = (ctx->a & 0xFF00) | (((ctx->a & 0xFF) - 0x{val:02X}) & 0xFF);"
            return {"pc": instr_pc, "op": "SBC_IMM", "c_code": c}, next_pc

        elif opcode == 0xED:  # SBC Absolute
            addr = get_abs16()
            if m_flag:
                c = f"ctx->a = (ctx->a & 0xFF00) | (((ctx->a & 0xFF) - snes_read8(ctx, (ctx->db << 16) | 0x{addr:04X})) & 0xFF);"
            else:
                c = f"ctx->a -= snes_read16(ctx, (ctx->db << 16) | 0x{addr:04X});"
            return {"pc": instr_pc, "op": "SBC_ABS", "c_code": c}, next_pc

        elif opcode == 0xC9:  # CMP Immediate
            val, width = get_imm_m()
            c = f"ctx->p = ((ctx->a == 0x{val:04X}) ? (ctx->p | 0x02) : (ctx->p & ~0x02));" if width == 2 else f"ctx->p = (((ctx->a & 0xFF) == 0x{val:02X}) ? (ctx->p | 0x02) : (ctx->p & ~0x02));"
            return {"pc": instr_pc, "op": "CMP_IMM", "c_code": c}, next_pc

        elif opcode == 0xCD:  # CMP Absolute
            addr = get_abs16()
            if m_flag:
                c = f"ctx->p = (((ctx->a & 0xFF) == snes_read8(ctx, (ctx->db << 16) | 0x{addr:04X})) ? (ctx->p | 0x02) : (ctx->p & ~0x02));"
            else:
                c = f"ctx->p = ((ctx->a == snes_read16(ctx, (ctx->db << 16) | 0x{addr:04X})) ? (ctx->p | 0x02) : (ctx->p & ~0x02));"
            return {"pc": instr_pc, "op": "CMP_ABS", "c_code": c}, next_pc

        # 7. Control Flow: JMP ($4C Abs, $6C Abs Ind, $5C Long), JSR ($20), JSL ($22)
        elif opcode == 0x4C:  # JMP Absolute
            addr = get_abs16()
            target = ((pc & 0xFF0000) | addr) & 0xFFFFFF
            return {
                "pc": instr_pc,
                "op": "JMP",
                "target": target,
                "c_code": f"return 0x{target:06X}; /* jmp 0x{target:06X} */"
            }, next_pc

        elif opcode == 0x5C:  # JMP Long (24-bit)
            addr24 = get_abs24()
            return {
                "pc": instr_pc,
                "op": "JML",
                "target": addr24,
                "c_code": f"return 0x{addr24:06X}; /* jml 0x{addr24:06X} */"
            }, next_pc

        elif opcode == 0x6C:  # JMP Absolute Indirect
            addr = get_abs16()
            return {
                "pc": instr_pc,
                "op": "JMP_IND",
                "indirect_addr": addr,
                "c_code": f"return snes_read16(ctx, (ctx->pb << 16) | 0x{addr:04X}); /* jmp (0x{addr:04X}) */"
            }, next_pc

        elif opcode == 0x7C:  # JMP Absolute Indexed Indirect ($xxxx,X) - Switch/Jump Table
            addr = get_abs16()
            return {
                "pc": instr_pc,
                "op": "JMP_IND_X",
                "indirect_addr": addr,
                "c_code": f"return snes_read16(ctx, (ctx->pb << 16) | ((0x{addr:04X} + ctx->x) & 0xFFFF)); /* jmp (0x{addr:04X},x) */"
            }, next_pc

        elif opcode == 0x20:  # JSR Absolute
            addr = get_abs16()
            target = ((pc & 0xFF0000) | addr) & 0xFFFFFF
            ret_addr = next_pc
            return {
                "pc": instr_pc,
                "op": "JSR",
                "target": target,
                "ret_addr": ret_addr,
                "c_code": f"ctx->sp -= 2; snes_write16(ctx, 0x000000 | ctx->sp, 0x{ret_addr & 0xFFFF:04X});\n    recomp_snes_call(ctx, 0x{target:06X});"
            }, next_pc

        elif opcode == 0x22:  # JSL Long (Subroutine)
            addr24 = get_abs24()
            ret_addr = next_pc
            # Pushing Program Bank (8-bit) and 16-bit return address
            return {
                "pc": instr_pc,
                "op": "JSL",
                "target": addr24,
                "ret_addr": ret_addr,
                "c_code": f"ctx->sp -= 3;\n    snes_write8(ctx, 0x000000 | ctx->sp, ctx->pb);\n    snes_write16(ctx, 0x000000 | ctx->sp + 1, 0x{ret_addr & 0xFFFF:04X});\n    recomp_snes_call(ctx, 0x{addr24:06X});"
            }, next_pc

        # 8. Returns: RTS ($60), RTL ($6B)
        elif opcode == 0x60:  # RTS
            return {
                "pc": instr_pc,
                "op": "RTS",
                "c_code": f"{{ uint16_t ret = snes_read16(ctx, 0x000000 | ctx->sp); ctx->sp += 2; return ((ctx->pb << 16) | ret) + 1; }} /* rts */"
            }, next_pc

        elif opcode == 0x6B:  # RTL
            return {
                "pc": instr_pc,
                "op": "RTL",
                "c_code": f"{{ uint16_t ret_off = snes_read16(ctx, 0x000000 | ctx->sp + 1); uint8_t ret_bank = snes_read8(ctx, 0x000000 | ctx->sp); ctx->sp += 3; return ((ret_bank << 16) | ret_off) + 1; }} /* rtl */"
            }, next_pc

        # 9. Branch Instructions: BRA ($80), BEQ ($F0), BNE ($D0), BBMI ($30), BBPL ($10), BVC ($50), BVS ($70), BCS ($B0), BCC ($90), BRL ($82)
        elif opcode == 0x82:  # BRL (Branch Long Relative 16-bit)
            rel16 = get_abs16()
            simv = rel16 if rel16 < 0x8000 else rel16 - 0x10000
            target = (next_pc + simv) & 0xFFFFFF
            return {
                "pc": instr_pc,
                "op": "BRL",
                "target": target,
                "c_code": f"return 0x{target:06X}; /* brl 0x{target:06X} */"
            }, next_pc

        elif opcode in (0x80, 0xF0, 0xD0, 0x30, 0x10, 0x50, 0x70, 0xB0, 0x90):
            rel8 = get_imm8()
            # Sign extend 8-bit relative offset
            simv = rel8 if rel8 < 0x80 else rel8 - 0x100
            target = (next_pc + simv) & 0xFFFFFF
            fallthrough = next_pc

            branch_names = {
                0x80: ("BRA", f"return 0x{target:06X};"),
                0xF0: ("BEQ", f"if (ctx->p & 0x02) return 0x{target:06X};\n    else return 0x{fallthrough:06X};"),
                0xD0: ("BNE", f"if (!(ctx->p & 0x02)) return 0x{target:06X};\n    else return 0x{fallthrough:06X};"),
                0x30: ("BMI", f"if (ctx->p & 0x80) return 0x{target:06X};\n    else return 0x{fallthrough:06X};"),
                0x10: ("BPL", f"if (!(ctx->p & 0x80)) return 0x{target:06X};\n    else return 0x{fallthrough:06X};"),
                0xB0: ("BCS", f"if (ctx->p & 0x01) return 0x{target:06X};\n    else return 0x{fallthrough:06X};"),
                0x90: ("BCC", f"if (!(ctx->p & 0x01)) return 0x{target:06X};\n    else return 0x{fallthrough:06X};"),
            }
            op_name, cond_c = branch_names.get(opcode, ("BRANCH", f"return 0x{target:06X};"))
            return {
                "pc": instr_pc,
                "op": op_name,
                "target": target,
                "fallthrough": fallthrough,
                "c_code": cond_c
            }, next_pc

        # 10. Register Transfers: TAX, TAY, TXA, TYA, TSX, TXS, TCD, TDC, TCS, TSC
        elif opcode == 0xAA:  # TAX
            c = "ctx->x = (ctx->p & 0x10) ? (ctx->a & 0xFF) : ctx->a;"
            return {"pc": instr_pc, "op": "TAX", "c_code": c}, next_pc

        elif opcode == 0xA8:  # TAY
            c = "ctx->y = (ctx->p & 0x10) ? (ctx->a & 0xFF) : ctx->a;"
            return {"pc": instr_pc, "op": "TAY", "c_code": c}, next_pc

        elif opcode == 0x8A:  # TXA
            c = "ctx->a = (ctx->p & 0x20) ? ((ctx->a & 0xFF00) | (ctx->x & 0xFF)) : ctx->x;"
            return {"pc": instr_pc, "op": "TXA", "c_code": c}, next_pc

        elif opcode == 0x98:  # TYA
            c = "ctx->a = (ctx->p & 0x20) ? ((ctx->a & 0xFF00) | (ctx->y & 0xFF)) : ctx->y;"
            return {"pc": instr_pc, "op": "TYA", "c_code": c}, next_pc

        elif opcode == 0xBA:  # TSX
            c = "ctx->x = (ctx->p & 0x10) ? (ctx->sp & 0xFF) : ctx->sp;"
            return {"pc": instr_pc, "op": "TSX", "c_code": c}, next_pc

        elif opcode == 0x9A:  # TXS
            c = "ctx->sp = ctx->x;"
            return {"pc": instr_pc, "op": "TXS", "c_code": c}, next_pc

        elif opcode == 0x5B:  # TCD (16-bit A to DP)
            return {"pc": instr_pc, "op": "TCD", "c_code": "ctx->dp = (uint8_t)(ctx->a & 0xFF);"}, next_pc

        elif opcode == 0x7B:  # TDC (DP to 16-bit A)
            return {"pc": instr_pc, "op": "TDC", "c_code": "ctx->a = (uint16_t)ctx->dp;"}, next_pc

        elif opcode == 0x1B:  # TCS (16-bit A to SP)
            return {"pc": instr_pc, "op": "TCS", "c_code": "ctx->sp = ctx->a;"}, next_pc

        elif opcode == 0x3B:  # TSC (SP to 16-bit A)
            return {"pc": instr_pc, "op": "TSC", "c_code": "ctx->a = ctx->sp;"}, next_pc

        elif opcode == 0xFB:  # XCE (Exchange Carry with Emulation)
            return {"pc": instr_pc, "op": "XCE", "c_code": "/* xce: exchange carry with emulation flag */"}, next_pc

        # 11. Status Flag Modifiers: CLC, SEC, CLI, SEI, CLD, SED, CLV
        elif opcode == 0x18:  # CLC
            return {"pc": instr_pc, "op": "CLC", "c_code": "ctx->p &= ~0x01;"}, next_pc

        elif opcode == 0x38:  # SEC
            return {"pc": instr_pc, "op": "SEC", "c_code": "ctx->p |= 0x01;"}, next_pc

        elif opcode == 0x58:  # CLI
            return {"pc": instr_pc, "op": "CLI", "c_code": "ctx->p &= ~0x04;"}, next_pc

        elif opcode == 0x78:  # SEI
            return {"pc": instr_pc, "op": "SEI", "c_code": "ctx->p |= 0x04;"}, next_pc

        elif opcode == 0xD8:  # CLD
            return {"pc": instr_pc, "op": "CLD", "c_code": "ctx->p &= ~0x08;"}, next_pc

        elif opcode == 0xF8:  # SED
            return {"pc": instr_pc, "op": "SED", "c_code": "ctx->p |= 0x08;"}, next_pc

        elif opcode == 0xB8:  # CLV
            return {"pc": instr_pc, "op": "CLV", "c_code": "ctx->p &= ~0x40;"}, next_pc

        # 12. Register Increments & Decrements: INX, DEX, INY, DEY, INC, DEC
        elif opcode == 0xE8:  # INX
            c = "ctx->x = (ctx->p & 0x10) ? (((ctx->x & 0xFF) + 1) & 0xFF) : ((ctx->x + 1) & 0xFFFF);"
            return {"pc": instr_pc, "op": "INX", "c_code": c}, next_pc

        elif opcode == 0xCA:  # DEX
            c = "ctx->x = (ctx->p & 0x10) ? (((ctx->x & 0xFF) - 1) & 0xFF) : ((ctx->x - 1) & 0xFFFF);"
            return {"pc": instr_pc, "op": "DEX", "c_code": c}, next_pc

        elif opcode == 0xC8:  # INY
            c = "ctx->y = (ctx->p & 0x10) ? (((ctx->y & 0xFF) + 1) & 0xFF) : ((ctx->y + 1) & 0xFFFF);"
            return {"pc": instr_pc, "op": "INY", "c_code": c}, next_pc

        elif opcode == 0x88:  # DEY
            c = "ctx->y = (ctx->p & 0x10) ? (((ctx->y & 0xFF) - 1) & 0xFF) : ((ctx->y - 1) & 0xFFFF);"
            return {"pc": instr_pc, "op": "DEY", "c_code": c}, next_pc

        elif opcode == 0x1A:  # INC Accumulator
            c = "ctx->a = (ctx->p & 0x20) ? ((ctx->a & 0xFF00) | (((ctx->a & 0xFF) + 1) & 0xFF)) : ((ctx->a + 1) & 0xFFFF);"
            return {"pc": instr_pc, "op": "INC", "c_code": c}, next_pc

        elif opcode == 0x3A:  # DEC Accumulator
            c = "ctx->a = (ctx->p & 0x20) ? ((ctx->a & 0xFF00) | (((ctx->a & 0xFF) - 1) & 0xFF)) : ((ctx->a - 1) & 0xFFFF);"
            return {"pc": instr_pc, "op": "DEC", "c_code": c}, next_pc

        elif opcode == 0xEE:  # INC Absolute
            addr = get_abs16()
            if m_flag:
                c = f"snes_write8(ctx, (ctx->db << 16) | 0x{addr:04X}, (snes_read8(ctx, (ctx->db << 16) | 0x{addr:04X}) + 1) & 0xFF);"
            else:
                c = f"snes_write16(ctx, (ctx->db << 16) | 0x{addr:04X}, snes_read16(ctx, (ctx->db << 16) | 0x{addr:04X}) + 1);"
            return {"pc": instr_pc, "op": "INC", "addr": addr, "c_code": c}, next_pc

        elif opcode == 0xCE:  # DEC Absolute
            addr = get_abs16()
            if m_flag:
                c = f"snes_write8(ctx, (ctx->db << 16) | 0x{addr:04X}, (snes_read8(ctx, (ctx->db << 16) | 0x{addr:04X}) - 1) & 0xFF);"
            else:
                c = f"snes_write16(ctx, (ctx->db << 16) | 0x{addr:04X}, snes_read16(ctx, (ctx->db << 16) | 0x{addr:04X}) - 1);"
            return {"pc": instr_pc, "op": "DEC", "addr": addr, "c_code": c}, next_pc

        # 13. Bitwise Shifts & Rotates: ASL, LSR, ROL, ROR
        elif opcode == 0x0A:  # ASL Accumulator
            c = "ctx->a = (ctx->p & 0x20) ? ((ctx->a & 0xFF00) | (((ctx->a & 0xFF) << 1) & 0xFF)) : ((ctx->a << 1) & 0xFFFF);"
            return {"pc": instr_pc, "op": "ASL", "c_code": c}, next_pc

        elif opcode == 0x4A:  # LSR Accumulator
            c = "ctx->a = (ctx->p & 0x20) ? ((ctx->a & 0xFF00) | ((ctx->a & 0xFF) >> 1)) : ((ctx->a >> 1) & 0xFFFF);"
            return {"pc": instr_pc, "op": "LSR", "c_code": c}, next_pc

        elif opcode == 0x2A:  # ROL Accumulator
            c = "ctx->a = (ctx->p & 0x20) ? ((ctx->a & 0xFF00) | ((((ctx->a & 0xFF) << 1) | (ctx->p & 1)) & 0xFF)) : ((((ctx->a << 1) | (ctx->p & 1)) & 0xFFFF));"
            return {"pc": instr_pc, "op": "ROL", "c_code": c}, next_pc

        elif opcode == 0x6A:  # ROR Accumulator
            c = "ctx->a = (ctx->p & 0x20) ? ((ctx->a & 0xFF00) | (((ctx->a & 0xFF) >> 1) | ((ctx->p & 1) << 7))) : (((ctx->a >> 1) | ((ctx->p & 1) << 15)) & 0xFFFF);"
            return {"pc": instr_pc, "op": "ROR", "c_code": c}, next_pc

        # 14. Logical Operations: AND, ORA, EOR, BIT
        elif opcode == 0x29:  # AND Immediate
            val, width = get_imm_m()
            c = f"ctx->a &= 0x{val:04X};" if width == 2 else f"ctx->a = (ctx->a & 0xFF00) | ((ctx->a & 0x{val:02X}) & 0xFF);"
            return {"pc": instr_pc, "op": "AND", "c_code": c}, next_pc

        elif opcode == 0x2D:  # AND Absolute
            addr = get_abs16()
            if m_flag:
                c = f"ctx->a = (ctx->a & 0xFF00) | ((ctx->a & snes_read8(ctx, (ctx->db << 16) | 0x{addr:04X})) & 0xFF);"
            else:
                c = f"ctx->a &= snes_read16(ctx, (ctx->db << 16) | 0x{addr:04X});"
            return {"pc": instr_pc, "op": "AND", "c_code": c}, next_pc

        elif opcode == 0x09:  # ORA Immediate
            val, width = get_imm_m()
            c = f"ctx->a |= 0x{val:04X};" if width == 2 else f"ctx->a = (ctx->a & 0xFF00) | (((ctx->a & 0xFF) | 0x{val:02X}) & 0xFF);"
            return {"pc": instr_pc, "op": "ORA", "c_code": c}, next_pc

        elif opcode == 0x0D:  # ORA Absolute
            addr = get_abs16()
            if m_flag:
                c = f"ctx->a = (ctx->a & 0xFF00) | (((ctx->a & 0xFF) | snes_read8(ctx, (ctx->db << 16) | 0x{addr:04X})) & 0xFF);"
            else:
                c = f"ctx->a |= snes_read16(ctx, (ctx->db << 16) | 0x{addr:04X});"
            return {"pc": instr_pc, "op": "ORA", "c_code": c}, next_pc

        elif opcode == 0x49:  # EOR Immediate
            val, width = get_imm_m()
            c = f"ctx->a ^= 0x{val:04X};" if width == 2 else f"ctx->a = (ctx->a & 0xFF00) | (((ctx->a & 0xFF) ^ 0x{val:02X}) & 0xFF);"
            return {"pc": instr_pc, "op": "EOR", "c_code": c}, next_pc

        elif opcode == 0x4D:  # EOR Absolute
            addr = get_abs16()
            if m_flag:
                c = f"ctx->a = (ctx->a & 0xFF00) | (((ctx->a & 0xFF) ^ snes_read8(ctx, (ctx->db << 16) | 0x{addr:04X})) & 0xFF);"
            else:
                c = f"ctx->a ^= snes_read16(ctx, (ctx->db << 16) | 0x{addr:04X});"
            return {"pc": instr_pc, "op": "EOR", "c_code": c}, next_pc

        elif opcode == 0x89:  # BIT Immediate
            val, width = get_imm_m()
            c = f"ctx->p = ((ctx->a & 0x{val:04X}) == 0) ? (ctx->p | 0x02) : (ctx->p & ~0x02);" if width == 2 else f"ctx->p = (((ctx->a & 0xFF) & 0x{val:02X}) == 0) ? (ctx->p | 0x02) : (ctx->p & ~0x02);"
            return {"pc": instr_pc, "op": "BIT", "c_code": c}, next_pc

        elif opcode == 0x2C:  # BIT Absolute
            addr = get_abs16()
            c = f"{{ uint16_t v = snes_read16(ctx, (ctx->db << 16) | 0x{addr:04X}); ctx->p = (ctx->p & ~0xC2) | (v & 0xC0) | ((ctx->a & v) == 0 ? 0x02 : 0); }}"
            return {"pc": instr_pc, "op": "BIT", "c_code": c}, next_pc

        # 15. Index Comparisons: CPX, CPY
        elif opcode == 0xE0:  # CPX Immediate
            val, width = get_imm_x()
            c = f"ctx->p = ((ctx->x == 0x{val:04X}) ? (ctx->p | 0x02) : (ctx->p & ~0x02));" if width == 2 else f"ctx->p = (((ctx->x & 0xFF) == 0x{val:02X}) ? (ctx->p | 0x02) : (ctx->p & ~0x02));"
            return {"pc": instr_pc, "op": "CPX", "c_code": c}, next_pc

        elif opcode == 0xEC:  # CPX Absolute
            addr = get_abs16()
            c = f"ctx->p = ((ctx->x == snes_read16(ctx, (ctx->db << 16) | 0x{addr:04X})) ? (ctx->p | 0x02) : (ctx->p & ~0x02));"
            return {"pc": instr_pc, "op": "CPX", "c_code": c}, next_pc

        elif opcode == 0xC0:  # CPY Immediate
            val, width = get_imm_x()
            c = f"ctx->p = ((ctx->y == 0x{val:04X}) ? (ctx->p | 0x02) : (ctx->p & ~0x02));" if width == 2 else f"ctx->p = (((ctx->y & 0xFF) == 0x{val:02X}) ? (ctx->p | 0x02) : (ctx->p & ~0x02));"
            return {"pc": instr_pc, "op": "CPY", "c_code": c}, next_pc

        elif opcode == 0xCC:  # CPY Absolute
            addr = get_abs16()
            c = f"ctx->p = ((ctx->y == snes_read16(ctx, (ctx->db << 16) | 0x{addr:04X})) ? (ctx->p | 0x02) : (ctx->p & ~0x02));"
            return {"pc": instr_pc, "op": "CPY", "c_code": c}, next_pc

        # 16. Stack Operations: PHA ($48), PLA ($68), PHB ($8B), PLB ($AB), PHX ($DA), PLX ($FA), PHY ($5A), PLY ($7A), PHP ($08), PLP ($28), PEA ($F4)
        elif opcode == 0xEA:
            return {"pc": instr_pc, "op": "NOP", "c_code": "/* nop */"}, next_pc

        elif opcode == 0x48:  # PHA
            if m_flag:
                c = "ctx->sp -= 1; snes_write8(ctx, 0x000000 | ctx->sp, (uint8_t)ctx->a);"
            else:
                c = "ctx->sp -= 2; snes_write16(ctx, 0x000000 | ctx->sp, ctx->a);"
            return {"pc": instr_pc, "op": "PHA", "c_code": c}, next_pc

        elif opcode == 0x68:  # PLA
            if m_flag:
                c = "ctx->a = (ctx->a & 0xFF00) | snes_read8(ctx, 0x000000 | ctx->sp); ctx->sp += 1;"
            else:
                c = "ctx->a = snes_read16(ctx, 0x000000 | ctx->sp); ctx->sp += 2;"
            return {"pc": instr_pc, "op": "PLA", "c_code": c}, next_pc

        elif opcode == 0x8B:  # PHB
            return {"pc": instr_pc, "op": "PHB", "c_code": "ctx->sp -= 1; snes_write8(ctx, 0x000000 | ctx->sp, ctx->db);"}, next_pc

        elif opcode == 0xAB:  # PLB
            return {"pc": instr_pc, "op": "PLB", "c_code": "ctx->db = snes_read8(ctx, 0x000000 | ctx->sp); ctx->sp += 1;"}, next_pc

        elif opcode == 0xDA:  # PHX
            c = "ctx->sp -= (ctx->p & 0x10) ? 1 : 2; if (ctx->p & 0x10) snes_write8(ctx, 0x000000 | ctx->sp, (uint8_t)ctx->x); else snes_write16(ctx, 0x000000 | ctx->sp, ctx->x);"
            return {"pc": instr_pc, "op": "PHX", "c_code": c}, next_pc

        elif opcode == 0xFA:  # PLX
            c = "if (ctx->p & 0x10) { ctx->x = (ctx->x & 0xFF00) | snes_read8(ctx, 0x000000 | ctx->sp); ctx->sp += 1; } else { ctx->x = snes_read16(ctx, 0x000000 | ctx->sp); ctx->sp += 2; }"
            return {"pc": instr_pc, "op": "PLX", "c_code": c}, next_pc

        elif opcode == 0x5A:  # PHY
            c = "ctx->sp -= (ctx->p & 0x10) ? 1 : 2; if (ctx->p & 0x10) snes_write8(ctx, 0x000000 | ctx->sp, (uint8_t)ctx->y); else snes_write16(ctx, 0x000000 | ctx->sp, ctx->y);"
            return {"pc": instr_pc, "op": "PHY", "c_code": c}, next_pc

        elif opcode == 0x7A:  # PLY
            c = "if (ctx->p & 0x10) { ctx->y = (ctx->y & 0xFF00) | snes_read8(ctx, 0x000000 | ctx->sp); ctx->sp += 1; } else { ctx->y = snes_read16(ctx, 0x000000 | ctx->sp); ctx->sp += 2; }"
            return {"pc": instr_pc, "op": "PLY", "c_code": c}, next_pc

        elif opcode == 0x08:  # PHP
            return {"pc": instr_pc, "op": "PHP", "c_code": "ctx->sp -= 1; snes_write8(ctx, 0x000000 | ctx->sp, ctx->p);"}, next_pc

        elif opcode == 0x28:  # PLP
            return {"pc": instr_pc, "op": "PLP", "c_code": "ctx->p = snes_read8(ctx, 0x000000 | ctx->sp); ctx->sp += 1;"}, next_pc

        elif opcode == 0xF4:  # PEA (Push Effective Absolute)
            val = get_abs16()
            c = f"ctx->sp -= 2; snes_write16(ctx, 0x000000 | ctx->sp, 0x{val:04X});"
            return {"pc": instr_pc, "op": "PEA", "c_code": c}, next_pc

        # Fallback for unrecognized opcodes
        return {
            "pc": instr_pc,
            "op": f"UNKNOWN_{opcode:02X}",
            "c_code": f"/* unknown snes opcode 0x{opcode:02X} at 0x{instr_pc:06X} */"
        }, next_pc

    def lift_block(self, start_bank: int, start_pc: int, start_p: int = 0x30) -> Tuple[List[Dict[str, Any]], List[int], int]:
        """
        Lifts a basic block starting at Bank:PC with initial flags P.
        Returns (ir_ops, targets, final_p).
        """
        ir_ops = []
        pc = (start_bank << 16) | start_pc
        p_flags = start_p
        targets = []
        max_instructions = 500

        while max_instructions > 0:
            max_instructions -= 1
            if not self.is_valid_address(pc):
                ir_ops.append({"pc": pc, "op": "HALT", "c_code": "return 0; /* out of bounds */"})
                break

            instr, next_pc = self.lift_instruction(pc, p_flags)
            ir_ops.append(instr)

            # Update live P flags if instruction modified REP/SEP
            if instr["op"] == "REP":
                p_flags = instr["new_p"]
            elif instr["op"] == "SEP":
                p_flags = instr["new_p"]

            op = instr["op"]
            if op in ("JMP", "JML", "RTS", "RTL", "BRL"):
                if "target" in instr:
                    targets.append(instr["target"])
                break
            elif op in ("BEQ", "BNE", "BMI", "BPL", "BCS", "BCC", "BRA", "BRANCH"):
                if "target" in instr:
                    targets.append(instr["target"])
                if "fallthrough" in instr and op != "BRA":
                    targets.append(instr["fallthrough"])
                break
            elif op in ("JSR", "JSL"):
                if "target" in instr:
                    targets.append(instr["target"])
                if "fallthrough" in instr:
                    targets.append(instr["fallthrough"])
                # Continue block or break? Subroutines call and return, but in static recompilation we treat JSR fallthrough or block end as target
                targets.append(next_pc)
                break
            else:
                pc = next_pc

        return ir_ops, targets, p_flags

    def build_cfg(self, entry_bank: int, entry_pc: int, max_blocks: int = 500) -> ControlFlowGraph:
        entry_vram = (entry_bank << 16) | entry_pc
        cfg = ControlFlowGraph(entry_vram)
        worklist = [(entry_bank, entry_pc, 0x30)]  # Default p_flags: M=1, X=1 (8-bit mode)
        visited = set()
        queued = {entry_vram}

        while worklist and len(cfg) < max_blocks:
            bank, pc, p = worklist.pop(0)
            addr = (bank << 16) | pc
            if addr in visited or not self.is_valid_address(addr):
                continue
            visited.add(addr)

            ops, targets, final_p = self.lift_block(bank, pc, p)

            # Check for recoverable indirect switch/jump tables
            if not targets:
                jt = JumpTableRecovery.recover_snes_jump_table(
                    ops,
                    read_u16_func=lambda b, off: self.read_u16((b << 16) | off),
                    bank=bank
                )
                if jt:
                    targets.extend(jt.targets)

            block = BasicBlock(
                start_vram=addr,
                end_vram=ops[-1]["pc"] if ops else addr,
                instructions=ops,
                successors=targets,
                is_terminal=len(targets) == 0
            )

            if "jt" in locals() and jt:
                block.is_indirect = True
                block.terminator_type = "SWITCH"
                block.jump_table = jt
                cfg.add_jump_table(jt)

            cfg.add_block(block)

            for target in targets:
                t_bank = (target >> 16) & 0xFF
                t_pc = target & 0xFFFF
                if target not in queued and self.is_valid_address(target):
                    queued.add(target)
                    worklist.append((t_bank, t_pc, final_p))

        return cfg


def lift_snes_rom_to_c(rom_path: str, entry_point: Optional[int] = None, max_blocks: int = 500) -> str:
    with open(rom_path, "rb") as f:
        rom_bytes = f.read()

    # Detect LoROM vs HiROM from header location ($7FC0 for LoROM, $FFC0 for HiROM)
    # LoROM header check
    is_lorom = True
    if len(rom_bytes) >= 0x7FD5:
        # Check title or reset vector
        reset_vec_lorom = struct.unpack("<H", rom_bytes[0x7FFC:0x7FFE])[0] if len(rom_bytes) >= 0x7FFE else 0x8000
        reset_vec_hirom = struct.unpack("<H", rom_bytes[0xFFFC:0xFFFE])[0] if len(rom_bytes) >= 0xFFFE else 0x8000
        if reset_vec_hirom != 0 and reset_vec_lorom == 0:
            is_lorom = False

    lifter = SnesLifter(rom_bytes, is_lorom=is_lorom)

    if entry_point is not None:
        entry_bank = (entry_point >> 16) & 0xFF
        entry_pc = entry_point & 0xFFFF
    else:
        # Read reset vector from ROM header
        header_base = 0x7FC0 if is_lorom else 0xFFC0
        # Reset vector at offset 0x3C in header ($7FFC / $FFFC)
        reset_vector_offset = header_base + 0x3C
        if len(rom_bytes) >= reset_vector_offset + 2:
            entry_pc = struct.unpack("<H", rom_bytes[reset_vector_offset:reset_vector_offset+2])[0]
        else:
            entry_pc = 0x8000
        entry_bank = 0x00

    cfg = lifter.build_cfg(entry_bank, entry_pc, max_blocks=max_blocks)

    c_source = [
        '/* Automatically Generated by Automated Recompiler Framework (SNES W65C816 Target) */',
        '#include <stdint.h>',
        '#include <stdio.h>',
        '#include <stdbool.h>',
        '',
        'typedef struct {',
        '    uint16_t a, x, y, sp;      /* 16-bit registers (width controlled by flags) */',
        '    uint8_t  dp;               /* Direct Page register (base address) */',
        '    uint8_t  db;               /* Data Bank register */',
        '    uint8_t  pb;               /* Program Bank register */',
        '    uint8_t  p;                /* Status Register (N, V, M, X, D, I, Z, C) */',
        '    uint8_t  ram[0x20000];     /* 128KB WRAM */',
        '} SnesCpuContext;',
        '',
        '/* Hardware Memory Shims */',
        'static inline uint8_t snes_read8(SnesCpuContext* ctx, uint32_t addr24) {',
        '    uint32_t bank = (addr24 >> 16) & 0xFF;',
        '    uint32_t offset = addr24 & 0xFFFF;',
        '    if (bank == 0x7E || bank == 0x7F) {',
        '        return ctx->ram[((bank - 0x7E) << 16) + offset];',
        '    }',
        '    return 0;',
        '}',
        '',
        'static inline void snes_write8(SnesCpuContext* ctx, uint32_t addr24, uint8_t val) {',
        '    uint32_t bank = (addr24 >> 16) & 0xFF;',
        '    uint32_t offset = addr24 & 0xFFFF;',
        '    if (bank == 0x7E || bank == 0x7F) {',
        '        ctx->ram[((bank - 0x7E) << 16) + offset] = val;',
        '    }',
        '}',
        '',
        'static inline uint16_t snes_read16(SnesCpuContext* ctx, uint32_t addr24) {',
        '    uint8_t lo = snes_read8(ctx, addr24);',
        '    uint8_t hi = snes_read8(ctx, addr24 + 1);',
        '    return lo | (hi << 8);',
        '}',
        '',
        'static inline void snes_write16(SnesCpuContext* ctx, uint32_t addr24, uint16_t val) {',
        '    snes_write8(ctx, addr24, (uint8_t)(val & 0xFF));',
        '    snes_write8(ctx, addr24 + 1, (uint8_t)(val >> 8));',
        '}',
        '',
        '/* Basic Block Prototypes & Trampolines */',
        'uint32_t recomp_snes_dispatch(SnesCpuContext* ctx, uint32_t target_vram);',
        '',
        'static inline void recomp_snes_call(SnesCpuContext* ctx, uint32_t target_vram) {',
        '    uint32_t next = target_vram;',
        '    int budget = 500000;',
        '    while (next != 0 && budget-- > 0) {',
        '        next = recomp_snes_dispatch(ctx, next);',
        '    }',
        '}',
        '',
    ]

    for b in cfg.sorted_blocks():
        c_source.append(f'uint32_t bb_{b.start_vram:06X}(SnesCpuContext* ctx);')
    c_source.append('')

    # Emit basic blocks
    for b in cfg.sorted_blocks():
        c_source.append(f'/* SNES Basic Block 0x{b.start_vram:06X} - 0x{b.end_vram:06X} */')
        c_source.append(f'uint32_t bb_{b.start_vram:06X}(SnesCpuContext* ctx) {{')
        c_source.append('    (void)ctx;')
        for op in b.instructions:
            code = op.get("c_code", "")
            if code:
                c_source.append(f'    {code}')
        c_source.append('    return 0;\n}\n')

    # Emit dispatch trampoline
    c_source.extend([
        'uint32_t recomp_snes_dispatch(SnesCpuContext* ctx, uint32_t target_vram) {',
        '    switch (target_vram & 0xFFFFFF) {',
    ])

    for b in cfg.sorted_blocks():
        c_source.append(f'        case 0x{b.start_vram:06X}: return bb_{b.start_vram:06X}(ctx);')

    c_source.extend([
        '        default:',
        '            printf("[SNES Dispatch] Unhandled target 0x%06X\\n", target_vram);',
        '            return 0;',
        '    }',
        '}\n',
        '/* Main Entry / Native Recompiled Executable */',
        'static SnesCpuContext s_snes_ctx;',
        'int main(int argc, char** argv) {',
        '    (void)argc;',
        '    (void)argv;',
        '    printf("=== Starting Automated Recompiled SNES Game ===\\n");',
        '    SnesCpuContext* ctx = &s_snes_ctx;',
        '    ctx->sp = 0x01FF;  /* Initial SNES Stack Pointer */',
        '    ctx->p  = 0x34;    /* Initial Status Register: M=1, X=1, I=1 */',
        f'    uint32_t next_pc = 0x{(entry_bank << 16) | (entry_pc & 0xFFFF):06X};',
        '    int max_steps = 10000;',
        '    while (max_steps-- > 0 && next_pc != 0) {',
        '        next_pc = recomp_snes_dispatch(ctx, next_pc);',
        '    }',
        '    printf("=== Recompiled execution finished successfully ===\\n");',
        '    return 0;',
        '}',
    ])

    return '\n'.join(c_source)
