import pytest
from src.core.data_block_reader import create_block_reader

def test_snes_lorom_reader():
    reader = create_block_reader("roms/snes/Super Mario All-Stars and Super Mario World (axekin.com).sfc")
    # Reset vector bank 0x34 pc 0x8334 -> 0x348334 -> ROM offset 0x1A0334
    off = reader.vram_to_offset(0x348334)
    assert off == 0x1A0334
    assert reader.read_u8(0x348334) == 0x5A

def test_gba_reader():
    # GBA ROM PGATour.gba exists
    reader = create_block_reader("roms/gba/PGATour.gba")
    off = reader.vram_to_offset(0x08000000)
    assert off == 0
