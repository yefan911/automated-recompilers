import os
import pytest
from src.core.data_block_reader import create_block_reader

def test_snes_lorom_reader(tmp_path):
    rom_path = "roms/snes/Super Mario All-Stars and Super Mario World (axekin.com).sfc"
    if not os.path.exists(rom_path):
        synth_rom = bytearray(0x200000)
        synth_rom[0x1A0334] = 0x5A
        rom_path = str(tmp_path / "test_lorom.sfc")
        with open(rom_path, "wb") as f:
            f.write(synth_rom)

    reader = create_block_reader(rom_path)
    # Reset vector bank 0x34 pc 0x8334 -> 0x348334 -> ROM offset 0x1A0334
    off = reader.vram_to_offset(0x348334)
    assert off == 0x1A0334
    assert reader.read_u8(0x348334) == 0x5A

def test_gba_reader(tmp_path):
    rom_path = "roms/gba/PGATour.gba"
    if not os.path.exists(rom_path):
        rom_path = "roms/test/hello_gba.gba"
        if not os.path.exists(rom_path):
            synth_rom = bytearray(1024)
            rom_path = str(tmp_path / "test_gba.gba")
            with open(rom_path, "wb") as f:
                f.write(synth_rom)

    reader = create_block_reader(rom_path)
    off = reader.vram_to_offset(0x08000000)
    assert off == 0

def test_ps1_reader(tmp_path):
    rom_path = "roms/ps1/Need for Speed - Porsche Unleashed (Track 01)(axekin.com).bin"
    if not os.path.exists(rom_path):
        # Create synthetic PS-X EXE
        import struct
        header = bytearray(2048)
        header[:8] = b"PS-X EXE"
        header[0x10:0x14] = struct.pack("<I", 0x80010000) # PC
        header[0x18:0x1C] = struct.pack("<I", 0x80010000) # text VRAM
        header[0x1C:0x20] = struct.pack("<I", 2048)       # size
        synth_cd = bytearray(2352 * 26)
        synth_cd[24*2352 + 24 : 24*2352 + 2072] = header
        synth_cd[25*2352 + 24 : 25*2352 + 28] = struct.pack("<I", 0x00001021)
        rom_path = str(tmp_path / "test_ps1.bin")
        with open(rom_path, "wb") as f:
            f.write(synth_cd)

    reader = create_block_reader(rom_path)
    off = reader.vram_to_offset(reader.text_vram)
    assert off is not None
    assert reader.read_u32(0x8009F838 if "Need for Speed" in rom_path else 0x80010000) == 0x00001021


def test_n64_reader(tmp_path):
    rom_path = "roms/n64/Yoshi.z64"
    if not os.path.exists(rom_path):
        import struct
        hdr = bytearray(0x2000)
        hdr[:4] = b"\x80\x37\x12\x40"
        hdr[0x08:0x0C] = struct.pack(">I", 0x80200400)
        rom_path = str(tmp_path / "test_n64.z64")
        with open(rom_path, "wb") as f:
            f.write(hdr)

    reader = create_block_reader(rom_path)
    # 0x80200400 maps to offset 0x1000
    off = reader.vram_to_offset(0x80200400)
    assert off == 0x1000

