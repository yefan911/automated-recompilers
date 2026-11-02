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
