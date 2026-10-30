#!/usr/bin/env python3
"""
Automated Game ROM Recompiler (CLI Entry Point)

Usage:
    python recompile.py                   # Scans roms/ and lists detected ROMs
    python recompile.py <path_to_rom>     # Lifts ROM and emits native C source into build/
"""

import os
import sys

# Ensure root directory is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.core.rom_detector import inspect_file, scan_roms_directory
from src.lifter.arm_lifter import lift_rom_to_c

def main():
    if len(sys.argv) < 2:
        print("\n========================================================")
        print("    AUTOMATED GAME ROM RECOMPILER FRAMEWORK")
        print("========================================================\n")
        print("No ROM specified. Scanning roms/ directory for available games:\n")
        scan_roms_directory("roms")
        print("\nTo recompile a ROM, run:")
        print("    python recompile.py roms/test/hello_gba.gba")
        print("    python recompile.py roms/gba/your_game.gba")
        print("    python recompile.py roms/n64/your_game.z64\n")
        return

    rom_path = sys.argv[1]
    info = inspect_file(rom_path)
    if not info:
        print(f"Error: Could not analyze '{rom_path}'")
        return

    print("\n[1/3] ROM Identification & Header Analysis:")
    print("-" * 50)
    for k, v in info.items():
        if k not in ("path",):
            print(f"  * {k.replace('_', ' ').title()}: {v}")
    print("-" * 50)

    console = info.get("console", "")
    os.makedirs("build", exist_ok=True)
    out_c_path = os.path.join("build", f"{os.path.splitext(info['filename'])[0]}_recompiled.c")

    if "Game Boy Advance" in console:
        print("\n[2/3] Lifting ARM7TDMI Machine Code to Intermediate Representation (IR)...")
        c_code = lift_rom_to_c(rom_path)
        with open(out_c_path, "w") as f:
            f.write(c_code)
        print(f"[3/3] Emitted native C source code -> {out_c_path}")
        print("\nRecompilation succeeded!")
        print(f"To compile to a native executable on your machine:")
        print(f"    gcc -O2 {out_c_path} -o build/{os.path.splitext(info['filename'])[0]}.exe")
        print(f"    clang -O2 {out_c_path} -o build/{os.path.splitext(info['filename'])[0]}.exe\n")
    else:
        print(f"\n[Note] Console '{console}' lifter integration is staged.")
        print(f"Detected entry point: {info.get('entry_point')}. Ready for CFG pipeline.")

if __name__ == "__main__":
    main()
