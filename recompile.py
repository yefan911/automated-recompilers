#!/usr/bin/env python3
"""
Automated Game ROM Recompiler (Unified CLI)

Usage:
    python recompile.py                         # Scan roms/ and list detected games
    python recompile.py <rom_path>              # Recompile ROM and build native .exe
    python recompile.py --blocks <rom_path>     # Inspect structural blocks & entropy
    python recompile.py --no-build <rom_path>   # Only emit C source without building
"""

import os
import sys
import argparse

# Ensure root directory is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.core.rom_detector import inspect_file, scan_roms_directory
from src.lifter.arm_lifter import lift_rom_to_c
from src.lifter.mips_lifter import lift_mips_rom_to_c
from src.lifter.snes_lifter import lift_snes_rom_to_c
from src.core.block_analyzer import BlockDataAnalyzer
from src.core.native_compiler import compile_c_to_exe
from src.modding.widescreen import WidescreenPatcher, AspectRatio, WidescreenMode
from src.modding.texture_manager import TextureManager
from src.modding.hook_manager import HookManager

def apply_modding_enhancements(c_code: str, console: str, widescreen_ratio=None, texture_pack_dir=None, enable_hooks=False) -> str:
    headers = []
    if widescreen_ratio:
        try:
            native_ratio = AspectRatio.RATIO_3_2 if "Game Boy Advance" in console else AspectRatio.RATIO_4_3
            target_ratio = AspectRatio.from_string(widescreen_ratio)
            patcher = WidescreenPatcher(native_ratio=native_ratio, target_ratio=target_ratio)
            print(f"  [Modding] Injected Hor+ Widescreen ({target_ratio.desc}, FOV {patcher.fov_multiplier:.2f}x, X-Scale {patcher.projection_x_scale:.2f}x)")
            headers.append(patcher.emit_c_widescreen_shim())
        except Exception as e:
            print(f"  [Modding Warning] Could not apply widescreen patch: {e}")

    if texture_pack_dir:
        tm = TextureManager()
        loaded = tm.load_texture_pack(texture_pack_dir)
        print(f"  [Modding] Loaded {loaded} HD replacement textures from '{texture_pack_dir}'")
        headers.append(tm.emit_c_texture_interceptor())

    if enable_hooks:
        hm = HookManager()
        print("  [Modding] Injected native C Hook & Interception API (recomp_hooks.h)")
        headers.append(hm.emit_c_header())

    if headers:
        return "\n\n".join(headers) + "\n\n" + c_code
    return c_code

def _main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Recompile supported console ROMs to native C and executables.")
    parser.add_argument("rom", nargs="?", help="ROM file to inspect or recompile")
    parser.add_argument("--gui", "--ui", "-g", action="store_true")
    parser.add_argument("--blocks", "-b", "--inspect", action="store_true")
    parser.add_argument("--no-build", action="store_true")
    parser.add_argument("--max-blocks", type=int, default=2500)
    parser.add_argument("--widescreen", nargs="?", const="16:9")
    parser.add_argument("--load-textures")
    parser.add_argument("--enable-hooks", action="store_true")
    options = parser.parse_args(argv)
    if options.max_blocks < 1:
        parser.error("--max-blocks must be a positive integer")
    if options.widescreen:
        try:
            AspectRatio.from_string(options.widescreen)
        except ValueError as error:
            parser.error(str(error))
    if options.gui:
        from gui import main as launch_gui
        launch_gui()
        return 0

    if options.rom is None and not (sys.argv[1:] if argv is None else argv):
        print("\n========================================================")
        print("    AUTOMATED GAME ROM RECOMPILER FRAMEWORK")
        print("========================================================\n")
        print("No ROM specified. Scanning roms/ directory for available games:\n")
        scan_roms_directory("roms")
        print("\nCommands:")
        print("    python recompile.py <rom_path>           # Auto-recompile & build native .exe")
        print("    python recompile.py --ui                 # Launch Graphical Desktop Interface")
        print("    python recompile.py --blocks <rom_path>  # Inspect CFG basic blocks & entropy map")
        print("    python recompile.py <rom_path> --widescreen 16:9    # Apply Hor+ widescreen geometry patch")
        print("    python recompile.py <rom_path> --load-textures <dir> # Inject HD replacement texture pack\n")
        return 0

    # Check for --blocks flag
    if options.rom is None:
        print("Error: Please provide a ROM path.")
        return 2

    if options.blocks:
        if not os.path.isfile(options.rom):
            print(f"Error: file not found '{options.rom}'")
            return 1
        target = options.rom
        try:
            analyzer = BlockDataAnalyzer(target)
            analyzer.print_structural_blocks()
            analyzer.inspect_hex_block(analyzer.entry_rom_offset or 0, 64)
            analyzer.disassemble_basic_blocks(max_blocks=3)
            analyzer.scan_entropy_map(chunk_size=65536, max_chunks=16)
        except (OSError, ValueError) as error:
            print(f"Error: {error}")
            return 1
        return 0

    no_build = options.no_build
    max_blocks = options.max_blocks
    widescreen_ratio = options.widescreen
    texture_pack_dir = options.load_textures
    enable_hooks = options.enable_hooks
    if texture_pack_dir and not os.path.isdir(texture_pack_dir):
        print(f"Error: texture pack directory not found '{texture_pack_dir}'")
        return 1
    rom_path = options.rom
    info = inspect_file(rom_path)
    if not info:
        print(f"Error: Could not analyze '{rom_path}'")
        return 1

    print("\n========================================================")
    print("  [1/4] ROM Identification & Header Analysis")
    print("========================================================")
    for k, v in info.items():
        if k not in ("path",):
            print(f"  * {k.replace('_', ' ').title()}: {v}")

    console = info.get("console", "")
    os.makedirs("build", exist_ok=True)
    base_name = os.path.splitext(info["filename"])[0]
    out_c_path = os.path.join("build", f"{base_name}_recompiled.c")
    out_exe_path = os.path.join("build", f"{base_name}.exe")

    if "Game Boy Advance" in console:
        print("\n========================================================")
        print("  [2/4] Recursive Control Flow Graph (CFG) Disassembly")
        print("========================================================")
        print(f"Traversing execution paths from entry vector {info.get('entry_point')} (max {max_blocks} blocks)...")
        c_code = lift_rom_to_c(rom_path, entry_point=0x08000000, max_blocks=max_blocks)
        c_code = apply_modding_enhancements(c_code, console, widescreen_ratio, texture_pack_dir, enable_hooks)

        print("\n========================================================")
        print("  [3/4] Native C Code Generation")
        print("========================================================")
        with open(out_c_path, "w") as f:
            f.write(c_code)
        print(f"Emitted recompiled source: {out_c_path}")

        if not no_build:
            print("\n========================================================")
            print("  [4/4] Native Executable Build & Link")
            print("========================================================")
            success = compile_c_to_exe(out_c_path, out_exe_path)
            if success:
                print("\n========================================================")
                print(f"  RECOMPILATION COMPLETE: {os.path.basename(out_exe_path)}")
                print("========================================================")
                print("Your game ROM has been compiled into a standalone native Windows binary!")
                print(f"\nRun the recompiled game (headless test):")
                print(f"    .{os.sep}{out_exe_path}")
                print(f"\nRun with live desktop display window (720x480):")
                print(f"    .{os.sep}{out_exe_path} --window\n")
            else:
                print("Compilation failed. See compiler output above.")
                return 1
    elif "Nintendo 64" in console or "PlayStation 1" in console:
        print("\n========================================================")
        print("  [2/4] Recursive Control Flow Graph (CFG) Disassembly (MIPS)")
        print("========================================================")
        raw_ep = info.get("entry_point")
        ep = int(raw_ep, 16) if isinstance(raw_ep, str) and raw_ep.startswith("0x") else None
        print(f"Traversing execution paths from entry vector {raw_ep} (max {max_blocks} blocks)...")
        c_code = lift_mips_rom_to_c(rom_path, entry_point=ep, max_blocks=max_blocks)
        c_code = apply_modding_enhancements(c_code, console, widescreen_ratio, texture_pack_dir, enable_hooks)

        print("\n========================================================")
        print("  [3/4] Native C Code Generation")
        print("========================================================")
        with open(out_c_path, "w") as f:
            f.write(c_code)
        print(f"Emitted recompiled source: {out_c_path}")

        if not no_build:
            print("\n========================================================")
            print("  [4/4] Native Executable Build & Link")
            print("========================================================")
            success = compile_c_to_exe(out_c_path, out_exe_path)
            if success:
                print("\n========================================================")
                print(f"  RECOMPILATION COMPLETE: {os.path.basename(out_exe_path)}")
                print("========================================================")
                print("Your game ROM has been compiled into a standalone native binary!")
                print(f"\nRun the recompiled game:")
                print(f"    .{os.sep}{out_exe_path}\n")
            else:
                print("Compilation failed. See compiler output above.")
                return 1
    elif "Super Nintendo" in console:
        print("\n========================================================")
        print("  [2/4] Recursive Control Flow Graph (CFG) Disassembly (SNES)")
        print("========================================================")
        raw_ep = info.get("entry_point")
        ep = int(raw_ep, 16) if isinstance(raw_ep, str) and raw_ep.startswith("0x") else 0x8000
        print(f"Traversing execution paths from entry vector {raw_ep} (max {max_blocks} blocks)...")
        c_code = lift_snes_rom_to_c(rom_path, entry_point=ep, max_blocks=max_blocks)
        c_code = apply_modding_enhancements(c_code, console, widescreen_ratio, texture_pack_dir, enable_hooks)

        print("\n========================================================")
        print("  [3/4] Native C Code Generation")
        print("========================================================")
        with open(out_c_path, "w") as f:
            f.write(c_code)
        print(f"Emitted recompiled source: {out_c_path}")

        if not no_build:
            print("\n========================================================")
            print("  [4/4] Native Executable Build & Link")
            print("========================================================")
            success = compile_c_to_exe(out_c_path, out_exe_path)
            if success:
                print("\n========================================================")
                print(f"  RECOMPILATION COMPLETE: {os.path.basename(out_exe_path)}")
                print("========================================================")
                print("Your game ROM has been compiled into a standalone native binary!")
                print(f"\nRun the recompiled game:")
                print(f"    .{os.sep}{out_exe_path}\n")
            else:
                print("Compilation failed. See compiler output above.")
                return 1
    else:
        print(f"\n[Note] Console '{console}' pipeline:")
        print(f"  * Detected entry point: {info.get('entry_point')}")
        print(f"  * Run 'python recompile.py --blocks {rom_path}' to inspect CFG basic blocks.")
        return 1

    return 0


def main(argv=None) -> int:
    try:
        return _main(argv)
    except (OSError, ValueError, RuntimeError) as error:
        print(f"Error: {error}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
