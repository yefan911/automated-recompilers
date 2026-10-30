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
class BasicBlock:
    start_vram: int
    end_vram: int = 0
    instructions: List[Dict[str, Any]] = field(default_factory=list)
    successors: List[int] = field(default_factory=list)
    is_terminal: bool = False
    terminator_type: str = "BRANCH"

    @property
    def func_name(self) -> str:
        return f"bb_{self.start_vram:08X}"

    def emit_c_function(self) -> str:
        lines = [
            f"/* Basic Block 0x{self.start_vram:08X} - 0x{self.end_vram:08X} */",
            f"uint32_t {self.func_name}(ArmCpuContext* ctx) {{",
            "    (void)ctx;",
        ]
        for op in self.instructions:
            code = op.get("c_code", "")
            if code:
                lines.append(f"    {code}")
        lines.append("}\n")
        return "\n".join(lines)


class ControlFlowGraph:
    """
    Manages the graph of Basic Blocks discovered during static lifting.
    """

    def __init__(self, entry_vram: int):
        self.entry_vram = entry_vram
        self.blocks: Dict[int, BasicBlock] = {}
        self.edges: Set[tuple] = set()

    def add_block(self, block: BasicBlock):
        self.blocks[block.start_vram] = block
        for succ in block.successors:
            self.edges.add((block.start_vram, succ))

    def has_block(self, vram_addr: int) -> bool:
        return vram_addr in self.blocks

    def get_block(self, vram_addr: int) -> Optional[BasicBlock]:
        return self.blocks.get(vram_addr)

    def sorted_blocks(self) -> List[BasicBlock]:
        return sorted(self.blocks.values(), key=lambda b: b.start_vram)

    def emit_prototypes(self) -> List[str]:
        protos = ["uint32_t recomp_dispatch(ArmCpuContext* ctx, uint32_t target_vram);"]
        protos.extend([f"uint32_t {b.func_name}(ArmCpuContext* ctx);" for b in self.sorted_blocks()])
        return protos

    def emit_dispatch_function(self) -> List[str]:
        lines = [
            "/* Global Dispatch Trampoline */",
            "uint32_t recomp_dispatch(ArmCpuContext* ctx, uint32_t target_vram) {",
            "    switch (target_vram) {",
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
