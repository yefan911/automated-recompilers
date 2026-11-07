#!/usr/bin/env python3
"""
Control Flow Graph (CFG) Engine
Part of Automated Recompiler Framework.

Constructs basic blocks and builds an inter-procedural Control Flow Graph
via recursive descent disassembly from known entry points and branch targets.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Set, Optional


@dataclass
class JumpTableInfo:
    table_vram: int
    entry_count: int
    targets: List[int] = field(default_factory=list)
    source_pc: int = 0
    architecture: str = "generic"
    default_target: Optional[int] = None

    def emit_c_table_comment(self) -> str:
        targets_hex = ", ".join(f"0x{t:08X}" for t in self.targets)
        return f"/* Jump Table at 0x{self.table_vram:08X} ({self.entry_count} entries): [{targets_hex}] */"


@dataclass
class BasicBlock:
    start_vram: int
    end_vram: int = 0
    instructions: List[Dict[str, Any]] = field(default_factory=list)
    successors: List[int] = field(default_factory=list)
    is_terminal: bool = False
    terminator_type: str = "BRANCH"
    is_indirect: bool = False
    jump_table: Optional[JumpTableInfo] = None

    @property
    def func_name(self) -> str:
        return f"bb_{self.start_vram:08X}"

    def emit_c_function(self) -> str:
        lines = [
            f"/* Basic Block 0x{self.start_vram:08X} - 0x{self.end_vram:08X} */",
            f"uint32_t {self.func_name}(ArmCpuContext* ctx) {{",
            "    (void)ctx;",
        ]
        if self.jump_table:
            lines.append(f"    {self.jump_table.emit_c_table_comment()}")
        for op in self.instructions:
            code = op.get("c_code", "")
            if code:
                lines.append(f"    {code}")
        lines.append("    return 0; /* bounded block fallback */")
        lines.append("}\n")
        return "\n".join(lines)


class JumpTableRecovery:
    """
    Static analysis heuristics for recovering indirect jump tables
    (C switch statements, computed gotos, dispatch tables) across MIPS, ARM, and 65816.
    """

    @staticmethod
    def recover_mips_jump_table(
        instructions: List[Dict[str, Any]],
        read_u32_func,
        valid_range: tuple = (0x80000000, 0x80800000),
        max_entries: int = 128
    ) -> Optional[JumpTableInfo]:
        """
        Backward-slicing heuristic for MIPS compiled switch statements:
        Matches patterns like:
          - SLTIU $at, $reg, <bound> / BNEZ / BEQZ
          - LUI $reg, %hi(table)
          - ADDIU / ORI $reg, $reg, %lo(table)
          - SLL $reg, $reg, 2
          - ADDU $reg, $reg, $base
          - LW $reg, 0($reg)
          - JR $reg (where $reg != 31)
        """
        if not instructions:
            return None

        # 1. Identify terminating JR instruction
        last_insn = instructions[-1]
        jr_pc = last_insn.get("pc", 0)
        asm = last_insn.get("asm", "")
        # Check if block ends in JR $reg (and not JR $ra)
        if "jr" not in asm.lower() or "$ra" in asm.lower():
            if len(instructions) >= 2 and "jr" in instructions[-2].get("asm", "").lower() and "$ra" not in instructions[-2].get("asm", "").lower():
                last_insn = instructions[-2]
                jr_pc = last_insn.get("pc", 0)
                asm = last_insn.get("asm", "")
            else:
                return None

        # 2. Backward slice to find table base address and optional bound
        table_base = None
        bound = None
        hi_val = None
        lo_val = None

        for op in reversed(instructions):
            insn_asm = op.get("asm", "").lower()
            tokens = insn_asm.replace(",", " ").split()
            if not tokens:
                continue

            op_name = tokens[0]

            # Look for LUI $rx, 0xYYYY
            if op_name == "lui" and len(tokens) >= 3:
                try:
                    val = int(tokens[2], 0)
                    hi_val = val << 16
                except ValueError:
                    pass

            # Look for ADDIU / ORI $rx, $ry, 0xZZZZ
            elif op_name in ("addiu", "ori") and len(tokens) >= 4:
                try:
                    val = int(tokens[3], 0)
                    lo_val = val
                except ValueError:
                    pass

            # Look for bounds check: SLTI / SLTIU $at, $reg, bound
            elif op_name in ("slti", "sltiu") and len(tokens) >= 4:
                try:
                    b_cand = int(tokens[3], 0)
                    if 1 < b_cand <= max_entries:
                        bound = b_cand
                except ValueError:
                    pass

            # If we found both hi and lo or can reconstruct table base
            if hi_val is not None and lo_val is not None and table_base is None:
                cand_addr = (hi_val + (lo_val if lo_val < 0x8000 or op_name == "ori" else lo_val - 0x10000)) & 0xFFFFFFFF
                if valid_range[0] <= cand_addr <= valid_range[1]:
                    table_base = cand_addr

        # 3. If a table base was detected, scan target entries
        if table_base is not None and read_u32_func is not None:
            entries_to_read = bound if bound is not None else max_entries
            targets = []
            curr_vram = table_base

            for _ in range(entries_to_read):
                target = read_u32_func(curr_vram)
                if valid_range[0] <= target <= valid_range[1] and (target & 3) == 0:
                    targets.append(target)
                    curr_vram += 4
                else:
                    break

            if len(targets) >= 2:
                return JumpTableInfo(
                    table_vram=table_base,
                    entry_count=len(targets),
                    targets=targets,
                    source_pc=jr_pc,
                    architecture="mips"
                )

        return None

    @staticmethod
    def recover_arm_jump_table(
        instructions: List[Dict[str, Any]],
        read_u32_func,
        valid_range: tuple = (0x08000000, 0x0A000000),
        max_entries: int = 128
    ) -> Optional[JumpTableInfo]:
        """
        Backward-slicing heuristic for ARM compiled switch statements:
        Matches patterns like:
          - CMP $rx, #bound
          - LDR_CONST with table address
          - LDR pc, [pc, rx, lsl #2] or LDR pc, [base, rx, lsl #2]
        """
        if not instructions:
            return None

        last_insn = instructions[-1]
        pc = last_insn.get("pc", 0)

        table_base = None
        bound = None

        for op in reversed(instructions):
            if op.get("op") == "LDR_CONST":
                val = op.get("val", 0)
                if valid_range[0] <= val <= valid_range[1]:
                    table_base = val
            elif op.get("op") == "CMP" or "cmp" in op.get("c_code", "").lower():
                imm = op.get("imm")
                if imm and 1 < imm <= max_entries:
                    bound = imm

        if table_base is not None and read_u32_func is not None:
            entries_to_read = bound if bound is not None else max_entries
            targets = []
            curr_vram = table_base

            for _ in range(entries_to_read):
                target = read_u32_func(curr_vram)
                clean_target = target & ~1
                if valid_range[0] <= clean_target <= valid_range[1]:
                    targets.append(target)
                    curr_vram += 4
                else:
                    break

            if len(targets) >= 2:
                return JumpTableInfo(
                    table_vram=table_base,
                    entry_count=len(targets),
                    targets=targets,
                    source_pc=pc,
                    architecture="arm"
                )

        return None

    @staticmethod
    def recover_snes_jump_table(
        instructions: List[Dict[str, Any]],
        read_u16_func,
        bank: int = 0x00,
        valid_range: tuple = (0x8000, 0xFFFF),
        max_entries: int = 64
    ) -> Optional[JumpTableInfo]:
        """
        Backward-slicing heuristic for SNES 65816 switch statements:
        Matches:
          - CPX #bound / CPY #bound / CMP #bound
          - JMP ($xxxx,X) [Opcode 0x7C] or JMP ($xxxx) [Opcode 0x6C]
        """
        if not instructions:
            return None

        last_insn = instructions[-1]
        table_base = last_insn.get("indirect_addr") or last_insn.get("target")
        bound = None

        for op in reversed(instructions):
            if op.get("op") in ("CPX", "CPY", "CMP") and "imm" in op:
                imm = op.get("imm")
                if imm and 1 < imm <= max_entries:
                    bound = imm

        if table_base is not None and read_u16_func is not None:
            entries_to_read = bound if bound is not None else max_entries
            targets = []
            curr_offset = table_base & 0xFFFF

            for _ in range(entries_to_read):
                target_offset = read_u16_func(bank, curr_offset)
                if valid_range[0] <= target_offset <= valid_range[1]:
                    full_target = (bank << 16) | target_offset
                    targets.append(full_target)
                    curr_offset += 2
                else:
                    break

            if len(targets) >= 2:
                return JumpTableInfo(
                    table_vram=(bank << 16) | table_base,
                    entry_count=len(targets),
                    targets=targets,
                    source_pc=last_insn.get("pc", 0),
                    architecture="snes"
                )

        return None


class ControlFlowGraph:
    """
    Manages the graph of Basic Blocks discovered during static lifting.
    """

    def __init__(self, entry_vram: int):
        self.entry_vram = entry_vram
        self.blocks: Dict[int, BasicBlock] = {}
        self.edges: Set[tuple] = set()
        self.jump_tables: Dict[int, JumpTableInfo] = {}

    def add_block(self, block: BasicBlock):
        self.blocks[block.start_vram] = block
        for succ in block.successors:
            self.edges.add((block.start_vram, succ))

    def add_jump_table(self, jt: JumpTableInfo):
        """Registers a recovered jump table, linking table targets to CFG edges."""
        self.jump_tables[jt.table_vram] = jt
        for target in jt.targets:
            self.edges.add((jt.source_pc, target))
            # If source block is in graph, update its successors
            if jt.source_pc in self.blocks:
                b = self.blocks[jt.source_pc]
                if target not in b.successors:
                    b.successors.append(target)
                b.is_terminal = False
                b.is_indirect = True
                b.terminator_type = "SWITCH"
                b.jump_table = jt

    def has_block(self, vram_addr: int) -> bool:
        return vram_addr in self.blocks

    def get_block(self, vram_addr: int) -> Optional[BasicBlock]:
        return self.blocks.get(vram_addr)

    def sorted_blocks(self) -> List[BasicBlock]:
        return sorted(self.blocks.values(), key=lambda b: b.start_vram)

    def emit_prototypes(self) -> List[str]:
        protos = [
            "uint32_t recomp_dispatch(ArmCpuContext* ctx, uint32_t target_vram);",
            "static inline void recomp_call(ArmCpuContext* ctx, uint32_t target_vram) {",
            "    uint32_t ret_addr = ctx->r[14];",
            "    uint32_t next = target_vram;",
            "    int budget = 500000;",
            "    while (next != 0 && next != ret_addr && budget-- > 0) {",
            "        next = recomp_dispatch(ctx, next);",
            "    }",
            "}",
        ]
        protos.extend([f"uint32_t {b.func_name}(ArmCpuContext* ctx);" for b in self.sorted_blocks()])
        return protos

    def emit_dispatch_function(self) -> List[str]:
        lines = [
            "/* Global Dispatch Trampoline */",
            "uint32_t recomp_dispatch(ArmCpuContext* ctx, uint32_t target_vram) {",
            "    uint32_t clean_target = target_vram & ~1; /* strip Thumb bit */",
            "    switch (clean_target) {",
        ]
        for b in self.sorted_blocks():
            lines.append(f"        case 0x{b.start_vram:08X}: return {b.func_name}(ctx);")
        lines.extend([
            "        default:",
            '            printf("[Recomp Dispatch] Halt at unmapped / halt jump target 0x%08X\\n", target_vram);',
            "            return 0;",
            "    }",
            "}\n",
        ])
        return lines

    def emit_dispatch_switch(self) -> List[str]:
        lines = ["    switch (next_pc) {"]
        for b in self.sorted_blocks():
            lines.append(f"        case 0x{b.start_vram:08X}: next_pc = {b.func_name}(&ctx); break;")
        lines.append("        default:")
        lines.append('            printf("Reached unmapped / halt jump target 0x%08X\\n", next_pc);')
        lines.append("            return 0;")
        lines.append("    }")
        return lines

    def __len__(self) -> int:
        return len(self.blocks)
