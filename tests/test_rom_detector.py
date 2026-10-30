import os
import struct
import tempfile
import pytest

from src.core.rom_detector import (
    detect_gba,
    detect_n64,
    detect_ps1,
    detect_nes,
    inspect_file,
    scan_roms_directory,
    GBA_LOGO_START,
)
from src.core.create_test_rom import create_gba_test_rom


def test_detect_gba_synthetic_rom():
    with tempfile.TemporaryDirectory() as tmpdir:
        rom_path = os.path.join(tmpdir, "test.gba")
        create_gba_test_rom(rom_path)

        with open(rom_path, "rb") as f:
            data = f.read()

        info = detect_gba(data)
        assert info is not None
        assert info["console"] == "Game Boy Advance (GBA)"
        assert info["title"] == "TEST RECOMP"
        assert info["game_code"] == "TREC"
        assert info["maker_code"] == "01"
        assert info["entry_point"] == "0x08000000"


def test_detect_gba_truncated():
    assert detect_gba(b"\x00" * 10) is None
    assert detect_gba(b"\x00" * 0xC0) is None


def test_detect_n64_formats():
    header_base = bytearray(0x40)
    # Entry point 0x80000400 at offset 0x08
    struct.pack_into(">I", header_base, 0x08, 0x80000400)
    # Title at 0x20
    header_base[0x20:0x2C] = b"SUPER MARIO "

    # 1. Big-endian .z64
    z64 = bytearray(header_base)
    z64[0:4] = b"\x80\x37\x12\x40"
    res_z64 = detect_n64(bytes(z64))
    assert res_z64 is not None
    assert res_z64["endianness"] == "Big-Endian (.z64)"
    assert res_z64["entry_point"] == "0x80000400"
    assert "SUPER MARIO" in res_z64["title"]

    # 2. Byte-swapped .v64
    v64 = bytearray(z64)
    for i in range(0, len(v64), 2):
        v64[i], v64[i + 1] = v64[i + 1], v64[i]
    res_v64 = detect_n64(bytes(v64))
    assert res_v64 is not None
    assert res_v64["endianness"] == "Byte-Swapped (.v64)"
    assert res_v64["entry_point"] == "0x80000400"

    # 3. Little-endian .n64
    n64 = bytearray(z64)
    for i in range(0, len(n64), 4):
        n64[i:i + 4] = n64[i:i + 4][::-1]
    res_n64 = detect_n64(bytes(n64))
    assert res_n64 is not None
    assert res_n64["endianness"] == "Little-Endian (.n64)"
    assert res_n64["entry_point"] == "0x80000400"


def test_detect_ps1_exe():
    exe_header = bytearray(0x800)
    exe_header[0:8] = b"PS-X EXE"
    struct.pack_into("<I", exe_header, 0x10, 0x80010000)  # PC
    struct.pack_into("<I", exe_header, 0x18, 0x80010000)  # text vram
    struct.pack_into("<I", exe_header, 0x1C, 0x20000)     # text size
    struct.pack_into("<I", exe_header, 0x30, 0x801FFFF0)  # SP

    res = detect_ps1(bytes(exe_header))
    assert res is not None
    assert "PlayStation 1" in res["console"]
    assert res["entry_point"] == "0x80010000"
    assert res["text_size"] == 0x20000


def test_detect_nes():
    nes_header = bytearray(16)
    nes_header[0:4] = b"NES\x1a"
    nes_header[4] = 2   # 2 * 16KB = 32KB PRG
    nes_header[5] = 1   # 1 * 8KB = 8KB CHR
    nes_header[6] = 0x01 # Vertical mirroring
    nes_header[7] = 0x00

    res = detect_nes(bytes(nes_header))
    assert res is not None
    assert res["prg_rom_size_kb"] == 32
    assert res["chr_rom_size_kb"] == 8
    assert res["mirroring"] == "Vertical"
    assert res["mapper_number"] == 0


def test_inspect_file_not_found():
    assert inspect_file("nonexistent_rom_file.bin") is None


def test_scan_roms_directory(capsys):
    scan_roms_directory("roms")
    captured = capsys.readouterr()
    assert "Scanning 'roms' for game ROMs..." in captured.out
