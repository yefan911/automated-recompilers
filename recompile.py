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

# Ensure root directory is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.core.rom_detector import inspect_file, scan_roms_directory
from src.lifter.arm_lifter import lift_rom_to_c
from src.lifter.mips_lifter import lift_mips_rom_to_c
from src.core.block_analyzer import BlockDataAnalyzer
from src.core.native_compiler import compile_c_to_exe

def main():
    if len(sys.argv) < 2:
        print("\n========================================================")
        print("    AUTOMATED GAME ROM RECOMPILER FRAMEWORK")
        print("========================================================\n")
        print("No ROM specified. Scanning roms/ directory for available games:\n")
        scan_roms_directory("roms")
        print("\nCommands:")
        print("    python recompile.py <rom_path>           # Auto-recompile & build native .exe")
        print("    python recompile.py --blocks <rom_path>  # Inspect CFG basic blocks & entropy map\n")
        return

    # Check for --blocks flag
    if sys.argv[1] in ("--blocks", "-b", "--inspect"):
        if len(sys.argv) < 3:
            print("Error: Please provide a ROM path after --blocks, e.g.:")
            print("    python recompile.py --blocks roms/n64/Yoshi.z64")
            return
        target = sys.argv[2]
        analyzer = BlockDataAnalyzer(target)
        analyzer.print_structural_blocks()
        analyzer.inspect_hex_block(0x1000, 64)
        analyzer.disassemble_basic_blocks(0x1000, 0x80200400, max_blocks=3)
        analyzer.scan_entropy_map(chunk_size=65536, max_chunks=16)
        return

    no_build = False
    args = sys.argv[1:]
    if "--no-build" in args:
        no_build = True
        args.remove("--no-build")

    rom_path = args[0]
    info = inspect_file(rom_path)
    if not info:
        print(f"Error: Could not analyze '{rom_path}'")
        return

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
        print(f"Traversing execution paths from entry vector {info.get('entry_point')}...")
        c_code = lift_rom_to_c(rom_path, entry_point=0x08000000)

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
    elif "Nintendo 64" in console or "PlayStation 1" in console:
        print("\n========================================================")
        print("  [2/4] Recursive Control Flow Graph (CFG) Disassembly (MIPS)")
        print("========================================================")
        raw_ep = info.get("entry_point")
        ep = int(raw_ep, 16) if isinstance(raw_ep, str) and raw_ep.startswith("0x") else None
        print(f"Traversing execution paths from entry vector {raw_ep}...")
        c_code = lift_mips_rom_to_c(rom_path, entry_point=ep)

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
    else:
        print(f"\n[Note] Console '{console}' pipeline:")
        print(f"  * Detected entry point: {info.get('entry_point')}")
        print(f"  * Run 'python recompile.py --blocks {rom_path}' to inspect CFG basic blocks.")

if __name__ == "__main__":
    main()
