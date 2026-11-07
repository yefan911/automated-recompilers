#!/usr/bin/env python3
"""
Native C Function Hook & Interception API
Part of the Automated Game ROM Recompiler Modding SDK.

Allows C/C++ mods and extensions to hook, augment, or completely override
game subroutines and basic blocks at native execution speed with zero runtime overhead.
"""

from enum import Enum
from dataclasses import dataclass
import re
from typing import Dict, List, Optional


_C_RESERVED_NAMES = set("auto break case char const continue default do double else enum extern float for goto if inline int long register restrict return short signed sizeof static struct switch typedef union unsigned void volatile while _Alignas _Alignof _Atomic _Bool _Complex _Generic _Imaginary _Noreturn _Static_assert _Thread_local alignas alignof and and_eq asm bitand bitor bool catch class compl constexpr const_cast decltype delete dynamic_cast explicit export false friend mutable namespace new noexcept not not_eq nullptr operator or or_eq private protected public reinterpret_cast requires static_assert static_cast template this thread_local throw true try typeid typename using virtual wchar_t xor xor_eq NULL uint32_t uint16_t uint8_t int32_t size_t RecompPreHookFn RecompReplaceHookFn RecompPostHookFn".split())


def _validate_identifier(name: str):
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", name) or name in _C_RESERVED_NAMES:
        raise ValueError(f"Invalid or reserved C function name: {name!r}")


def _validate_address(address: int):
    if isinstance(address, bool) or not isinstance(address, int) or not 0 <= address <= 0xFFFFFFFF:
        raise ValueError("Hook target must be an unsigned 32-bit address")


def _comment_text(text: str) -> str:
    return text.replace("/*", "/ *").replace("*/", "* /").replace("\r", " ").replace("\n", " ").replace("\0", " ")


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

    def __post_init__(self):
        self.validate()

    def validate(self):
        _validate_address(self.target_vram)
        _validate_identifier(self.hook_function_name)
        self.hook_type = HookType(self.hook_type)
        if isinstance(self.priority, bool) or not isinstance(self.priority, int):
            raise ValueError("Hook priority must be an integer")
        if not isinstance(self.enabled, bool) or not isinstance(self.description, str):
            raise ValueError("Hook enabled flag and description must be a bool and string")
        if self.target_symbol is not None:
            _validate_identifier(self.target_symbol)


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
        for existing_list in self.hooks.values():
            for existing in existing_list:
                if existing.hook_function_name == hook_function_name and existing.hook_type != hook.hook_type:
                    raise ValueError(f"Hook {hook_function_name!r} is already registered with a different signature")
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
        return sorted(self.hooks.get(target_vram, []), key=lambda hook: hook.priority)

    def _validate_hooks(self):
        signatures = {}
        for address, hook_list in self.hooks.items():
            _validate_address(address)
            for hook in hook_list:
                hook.validate()
                if hook.target_vram != address:
                    raise ValueError("Hook target address no longer matches its registration")
                name = hook.hook_function_name
                if name in signatures and signatures[name] != hook.hook_type:
                    raise ValueError(f"Hook {name!r} has conflicting C signatures")
                signatures[name] = hook.hook_type

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
        _validate_identifier(block_func_name)
        _validate_address(target_vram)
        self._validate_hooks()
        hooks = self.get_hooks(target_vram)
        if not hooks:
            return f"return {block_func_name}(ctx);"

        lines = []
        replace_hook = self.has_replace_hook(target_vram)

        # Pre-hooks
        for h in hooks:
            if h.enabled and h.hook_type == HookType.HOOK_PRE:
                lines.append(f"    /* PRE HOOK: {_comment_text(h.description or h.hook_function_name)} */")
                lines.append(f"    {h.hook_function_name}(ctx, 0x{target_vram:08X});")

        # Execution or Replace Hook
        if replace_hook:
            lines.append(f"    /* REPLACE HOOK: {_comment_text(replace_hook.description or replace_hook.hook_function_name)} */")
            lines.append(f"    uint32_t ret_val = {replace_hook.hook_function_name}(ctx, 0x{target_vram:08X});")
        else:
            lines.append(f"    uint32_t ret_val = {block_func_name}(ctx);")

        # Post-hooks
        for h in hooks:
            if h.enabled and h.hook_type == HookType.HOOK_POST:
                lines.append(f"    /* POST HOOK: {_comment_text(h.description or h.hook_function_name)} */")
                lines.append(f"    ret_val = {h.hook_function_name}(ctx, 0x{target_vram:08X}, ret_val);")

        lines.append("    return ret_val;")
        return "\n".join(lines)

    def emit_c_header(self) -> str:
        """
        Emits `recomp_hooks.h` defining the native modding hook interfaces.
        """
        self._validate_hooks()
        lines = [
            "/* Automated Recompiler Framework — Native Modding & C Function Hook API */",
            "#ifndef RECOMP_HOOKS_H",
            "#define RECOMP_HOOKS_H",
            "",
            "#include <stdint.h>",
            "#include <stdbool.h>",
            "",
            "#ifdef __cplusplus",
            "extern \"C\" {",
            "#endif",
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
            "#ifdef __cplusplus",
            "}",
            "#endif",
            "",
            "#endif /* RECOMP_HOOKS_H */",
        ])
        return "\n".join(lines)
