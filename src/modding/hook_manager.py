#!/usr/bin/env python3
"""
Native C Function Hook & Interception API
Part of the Automated Game ROM Recompiler Modding SDK.

Allows C/C++ mods and extensions to hook, augment, or completely override
game subroutines and basic blocks at native execution speed with zero runtime overhead.
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


class HookType(str, Enum):
    HOOK_PRE = "HOOK_PRE"         # Executes immediately before the target basic block
    HOOK_POST = "HOOK_POST"       # Executes after the target basic block completes
    HOOK_REPLACE = "HOOK_REPLACE" # Bypasses the target basic block entirely


@dataclass
class FunctionHook:
    target_vram: int
    hook_function_name: str
    hook_type: HookType
    priority: int = 100           # Lower priority numbers execute earlier
    enabled: bool = True
    description: str = ""
    target_symbol: Optional[str] = None


class HookManager:
    """
    Manages registration, prioritization, and C code generation for native mod hooks.
    """

    def __init__(self):
        # Maps target_vram -> list of FunctionHook
        self.hooks: Dict[int, List[FunctionHook]] = {}

    def register_hook(
        self,
        target_vram: int,
        hook_function_name: str,
        hook_type: HookType = HookType.HOOK_PRE,
        priority: int = 100,
        description: str = "",
        target_symbol: Optional[str] = None
    ) -> FunctionHook:
        """
        Registers a hook on a target VRAM function address.
        """
        hook = FunctionHook(
            target_vram=target_vram,
            hook_function_name=hook_function_name,
            hook_type=hook_type,
            priority=priority,
            description=description,
            target_symbol=target_symbol
        )
        if target_vram not in self.hooks:
            self.hooks[target_vram] = []

        self.hooks[target_vram].append(hook)
        self.hooks[target_vram].sort(key=lambda h: h.priority)
        return hook

    def unregister_hook(self, target_vram: int, hook_function_name: str) -> bool:
        if target_vram in self.hooks:
            before_len = len(self.hooks[target_vram])
            self.hooks[target_vram] = [
                h for h in self.hooks[target_vram] if h.hook_function_name != hook_function_name
            ]
            if not self.hooks[target_vram]:
                del self.hooks[target_vram]
            return len(self.hooks.get(target_vram, [])) < before_len
        return False

    def get_hooks(self, target_vram: int) -> List[FunctionHook]:
        return self.hooks.get(target_vram, [])

    def has_replace_hook(self, target_vram: int) -> Optional[FunctionHook]:
        for h in self.get_hooks(target_vram):
            if h.enabled and h.hook_type == HookType.HOOK_REPLACE:
                return h
        return None

    def emit_c_hook_trampoline(self, block_func_name: str, target_vram: int, context_type: str = "void") -> str:
        """
        Generates a C wrapper trampoline for a basic block or subroutine that executes
        registered PRE hooks, optional REPLACE hook, original function, and POST hooks.
        """
        hooks = self.get_hooks(target_vram)
        if not hooks:
            return f"return {block_func_name}(ctx);"

        lines = []
        replace_hook = self.has_replace_hook(target_vram)

        # Pre-hooks
        for h in hooks:
            if h.enabled and h.hook_type == HookType.HOOK_PRE:
                lines.append(f"    /* PRE HOOK: {h.description or h.hook_function_name} */")
                lines.append(f"    {h.hook_function_name}(ctx, 0x{target_vram:08X});")

        # Execution or Replace Hook
        if replace_hook:
            lines.append(f"    /* REPLACE HOOK: {replace_hook.description or replace_hook.hook_function_name} */")
            lines.append(f"    uint32_t ret_val = {replace_hook.hook_function_name}(ctx, 0x{target_vram:08X});")
        else:
            lines.append(f"    uint32_t ret_val = {block_func_name}(ctx);")

        # Post-hooks
        for h in hooks:
            if h.enabled and h.hook_type == HookType.HOOK_POST:
                lines.append(f"    /* POST HOOK: {h.description or h.hook_function_name} */")
                lines.append(f"    ret_val = {h.hook_function_name}(ctx, 0x{target_vram:08X}, ret_val);")

        lines.append("    return ret_val;")
        return "\n".join(lines)

    def emit_c_header(self) -> str:
        """
        Emits `recomp_hooks.h` defining the native modding hook interfaces.
        """
        lines = [
            "/* Automated Recompiler Framework — Native Modding & C Function Hook API */",
            "#ifndef RECOMP_HOOKS_H",
            "#define RECOMP_HOOKS_H",
            "",
            "#include <stdint.h>",
            "#include <stdbool.h>",
            "",
            "/* Hook Function Signature Typedefs */",
            "typedef void (*RecompPreHookFn)(void* ctx, uint32_t vram);",
            "typedef uint32_t (*RecompReplaceHookFn)(void* ctx, uint32_t vram);",
            "typedef uint32_t (*RecompPostHookFn)(void* ctx, uint32_t vram, uint32_t result);",
            "",
            "/* Macro allowing external C/C++ mods to declare hooks with automatic export */",
            "#ifdef _WIN32",
            "#define RECOMP_MOD_EXPORT __declspec(dllexport)",
            "#else",
            "#define RECOMP_MOD_EXPORT __attribute__((visibility(\"default\")))",
            "#endif",
            "",
            "/* Registered Hook Function Declarations */",
        ]

        # Declare all unique hook function prototypes
        declared = set()
        for vram, hook_list in self.hooks.items():
            for h in hook_list:
                if h.hook_function_name in declared:
                    continue
                declared.add(h.hook_function_name)
                if h.hook_type == HookType.HOOK_PRE:
                    lines.append(f"extern void {h.hook_function_name}(void* ctx, uint32_t vram);")
                elif h.hook_type == HookType.HOOK_REPLACE:
                    lines.append(f"extern uint32_t {h.hook_function_name}(void* ctx, uint32_t vram);")
                elif h.hook_type == HookType.HOOK_POST:
                    lines.append(f"extern uint32_t {h.hook_function_name}(void* ctx, uint32_t vram, uint32_t result);")

        lines.extend([
            "",
            "#endif /* RECOMP_HOOKS_H */",
        ])
        return "\n".join(lines)
