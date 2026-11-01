import os
import sys
import subprocess
import tempfile
import struct

# Ensure project root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.lifter.snes_lifter import lift_snes_rom_to_c
from src.core.native_compiler import compile_c_to_exe

def create_dummy_lorom(code_bytes: bytes, entry_pc: int = 0x8000) -> bytes:
    rom = bytearray(0x80000)  # 512 KB
    start_offset = entry_pc - 0x8000
    rom[start_offset:start_offset + len(code_bytes)] = code_bytes
    # Reset vector at 0x7FFC
    struct.pack_into("<H", rom, 0x7FFC, entry_pc)
    # Put something at 0x7FD5 to pass LoROM check
    rom[0x7FD5] = 0x20
    return bytes(rom)

def verify_compilation() -> bool:
    code = bytes([
        0xC2, 0x30,
        0xA9, 0x34, 0x12,
        0x8D, 0x00, 0x20,
        0xAD, 0x00, 0x20,
        0xA5, 0x10,
        0xAF, 0x00, 0x00, 0x7E,
        0x8F, 0x00, 0x00, 0x7E,
        0xA2, 0x11, 0x22,
        0xA0, 0x33, 0x44,
        0x8E, 0x10, 0x21,
        0x8C, 0x12, 0x21,
        0x69, 0x01, 0x00,
        0xE9, 0x01, 0x00,
        0xC9, 0x34, 0x12,
        0x4C, 0x20, 0x80,
        0xEA,
        0x48,
        0x68,
        0x8B,
        0xAB,
        0x20, 0x30, 0x80,
        0x60,
        0x60,
    ])
    rom_bytes = create_dummy_lorom(code)
    with tempfile.TemporaryDirectory() as tmpdir:
        rom_path = os.path.join(tmpdir, "test.sfc")
        with open(rom_path, "wb") as f:
            f.write(rom_bytes)
        c_code = lift_snes_rom_to_c(rom_path, max_blocks=100)
        c_path = os.path.join(tmpdir, "test.c")
        exe_path = os.path.join(tmpdir, "test.exe")
        with open(c_path, "w") as f:
            f.write(c_code)
            f.write("\nint main() { return 0; }\n")
        print("Attempting to compile emitted C code...")
        return compile_c_to_exe(c_path, exe_path)

if __name__ == "__main__":
    if verify_compilation():
        print("Compilation test succeeded.")
    else:
        print("Compilation test failed.")
