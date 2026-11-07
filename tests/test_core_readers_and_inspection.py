import struct
import tracemalloc

import pytest

from src.core.block_analyzer import BlockDataAnalyzer
from src.core.create_test_rom import create_gba_test_rom, create_snes_test_rom
from src.core.data_block_reader import GbaReader, Ps1Reader, create_block_reader
from src.core.rom_detector import detect_nes, detect_ps1, detect_snes, inspect_file


def ps1_header(address=0x80010000, size=4096):
    header = bytearray(2048)
    header[:8] = b"PS-X EXE"
    struct.pack_into("<IIII", header, 0x10, address, 0x12345678, address, size)
    return header


def iso_record(lba, size, name, directory=False):
    name = name if isinstance(name, bytes) else name.encode("ascii")
    record = bytearray(33 + len(name) + (len(name) % 2 == 0))
    record[0] = len(record)
    struct.pack_into("<I", record, 2, lba)
    struct.pack_into(">I", record, 6, lba)
    struct.pack_into("<I", record, 10, size)
    struct.pack_into(">I", record, 14, size)
    record[25] = 2 if directory else 0
    record[28:32] = b"\x01\x00\x00\x01"
    record[32] = len(name)
    record[33:33 + len(name)] = name
    return record


@pytest.mark.parametrize("sector_size,user_offset", [(2048, 0), (2352, 16), (2352, 24)])
def test_ps1_reader_stitches_payload_and_limits_declared_text(tmp_path, sector_size, user_offset):
    image = bytearray(b"\xEE" * (sector_size * 5))
    header = ps1_header(size=2050)
    image[sector_size + user_offset:sector_size + user_offset + 2048] = header
    first = bytearray(2048)
    first[-2:] = b"\x11\x12"
    image[2 * sector_size + user_offset:2 * sector_size + user_offset + 2048] = first
    image[3 * sector_size + user_offset:3 * sector_size + user_offset + 4] = b"\x21\x22\x99\x99"
    path = tmp_path / "payload.bin"
    path.write_bytes(image)

    with Ps1Reader(str(path)) as reader:
        assert reader.read_bytes(0x80010000 + 2046, 4) == b"\x11\x12\x21\x22"
        assert reader.read_u32(0x80010000 + 2046) == 0x22211211
        assert reader.read_bytes(0x80010000, 2050) == bytes(first) + b"\x21\x22"
        assert reader.read_bytes(0x80010000 + 2049, 2) == b""
        assert reader.read_bytes(0xA0010000 + 2046, 4) == b"\x11\x12\x21\x22"
        assert reader.read_bytes(0x00010000 + 2046, 4) == b"\x11\x12\x21\x22"
        assert reader.read_bytes(0x20010000, 4) == b""
        assert reader.read_bytes(0x80010000, -1) == b""
        assert reader.read_bytes(0x8000FFFF, 1) == b""


def test_ps1_reader_rejects_truncated_text_and_invalid_addresses(tmp_path):
    path = tmp_path / "truncated.exe"
    path.write_bytes(ps1_header(size=8) + b"\x00" * 4)
    with pytest.raises(ValueError, match="truncated"):
        Ps1Reader(str(path))
    path.write_bytes(ps1_header(address=0x801FFFFC, size=8) + b"\x00" * 8)
    with pytest.raises(ValueError, match="valid PS-X EXE"):
        Ps1Reader(str(path))


@pytest.mark.parametrize("sector_size,user_offset", [(2048, 0), (2352, 16), (2352, 24)])
def test_ps1_detection_follows_nested_system_cnf_boot_path(tmp_path, sector_size, user_offset):
    image = bytearray(sector_size * 74)

    def write_sector(lba, data):
        offset = lba * sector_size + user_offset
        image[offset:offset + len(data)] = data

    pvd = bytearray(2048)
    pvd[:7] = b"\x01CD001\x01"
    pvd[40:47] = b"BOOT_CD"
    root = iso_record(20, 2048, b"\x00", True)
    pvd[156:156 + len(root)] = root
    write_sector(16, pvd)
    config = b"BOOT = cdrom:\\GAME\\BOOT.EXE;1\r\n"
    root_data = iso_record(21, len(config), "SYSTEM.CNF;1")
    root_data += iso_record(22, 2048, "GAME", True)
    write_sector(20, root_data)
    write_sector(21, config)
    write_sector(22, iso_record(70, 2056, "BOOT.EXE;1"))
    # This earlier executable must not override the explicit boot path.
    write_sector(24, ps1_header(address=0x80010000, size=8))
    write_sector(25, b"\x99" * 8)
    write_sector(70, ps1_header(address=0x80020000, size=8))
    write_sector(71, b"\x08\x00\xE0\x03\x00\x00\x00\x00")
    path = tmp_path / "boot.bin"
    path.write_bytes(image)

    info = inspect_file(str(path))
    assert info["entry_point"] == "0x80020000"
    assert info["initial_gp"] == "0x12345678"
    assert info["exe_offset"] == 70 * sector_size + user_offset
    assert info["title"] == "BOOT_CD"
    with create_block_reader(str(path)) as reader:
        assert reader.read_bytes(reader.text_vram, reader.text_size) == b"\x08\x00\xE0\x03\x00\x00\x00\x00"


def test_late_ps1_header_search_keeps_memory_bounded(tmp_path):
    path = tmp_path / "large.bin"
    with path.open("wb") as stream:
        stream.seek(100 * 1024 * 1024 - 1)
        stream.write(b"\x00")
        stream.seek(16 * 2352 + 24)
        stream.write(b"\x01CD001\x01")
        stream.seek(70 * 2352 + 24)
        stream.write(ps1_header(size=4))
        stream.seek(71 * 2352 + 24)
        stream.write(b"\x01\x02\x03\x04")
    tracemalloc.start()
    try:
        info = inspect_file(str(path))
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert info["exe_offset"] == 70 * 2352 + 24
    assert peak < 1024 * 1024
    with Ps1Reader(str(path)) as reader:
        assert reader.read_bytes(reader.text_vram, 4) == b"\x01\x02\x03\x04"
        reader.close()
        assert reader._file is None


def test_truncated_console_signatures_do_not_crash_detection():
    assert detect_ps1(b"PS-X EXE") is None
    assert detect_nes(b"NES\x1a") is None
    assert detect_ps1(b"\x00" * 100 + ps1_header()) is None


def test_nes_reset_vector_skips_trainer_and_empty_prg():
    header = bytearray(16)
    header[:4] = b"NES\x1a"
    header[4], header[6] = 1, 4
    rom = header + bytearray(512 + 16384)
    struct.pack_into("<H", rom, 16 + 512 + 16384 - 4, 0x8123)
    assert detect_nes(bytes(rom))["entry_point"] == "0x8123"
    header[4] = 0
    assert detect_nes(bytes(header))["entry_point"] is None


def test_snes_32kb_header_and_copier_translation(tmp_path):
    rom = bytearray(0x8000)
    rom[0] = 0x78
    rom[0x7FC0:0x7FC4] = b"TEST"
    rom[0x7FD5] = 0x20
    struct.pack_into("<H", rom, 0x7FFC, 0x8000)
    assert detect_snes(bytes(rom))["mapping"] == "LoROM"
    path = tmp_path / "headered.smc"
    path.write_bytes(b"\xAA" * 512 + rom)
    info = inspect_file(str(path))
    assert info["copier_header_size"] == 512
    assert info["header_offset"] == 0x81C0
    with create_block_reader(str(path)) as reader:
        assert reader.vram_to_offset(0x008000) == 512
        assert reader.read_u8(0x008000) == 0x78
        assert reader.read_bytes(0x00FFFF, 2) == b""
        assert reader.vram_to_offset(0x1008000) is None


@pytest.mark.parametrize("extended", [False, True])
def test_snes_hirom_translation_and_wram_exclusion(tmp_path, extended):
    rom = bytearray(0x500000 if extended else 0x400000)
    header = 0x40FFC0 if extended else 0xFFC0
    rom[header:header + 4] = b"TEST"
    rom[header + 0x15] = 0x25 if extended else 0x21
    struct.pack_into("<H", rom, header + 0x3C, 0x8000)
    rom[0] = 0x11
    rom[0x400000 if extended else 0x8000] = 0x22
    path = tmp_path / "hirom.sfc"
    path.write_bytes(rom)
    info = inspect_file(str(path))
    assert info["mapping"] == ("ExHiROM" if extended else "HiROM")
    with create_block_reader(str(path)) as reader:
        assert reader.read_u8(0xC00000) == 0x11
        assert reader.vram_to_offset(0x008000) == (0x408000 if extended else 0x8000)
        assert reader.vram_to_offset(0x808000) == 0x8000
        assert reader.vram_to_offset(0x400000) == (0x400000 if extended else 0)
        assert reader.vram_to_offset(0x7E8000) is None
        assert reader.vram_to_offset(0x7F8000) is None
        assert reader.vram_to_offset(0x007FFF) is None


def test_lorom_wram_banks_are_not_rom(tmp_path):
    path = tmp_path / "lorom.sfc"
    path.write_bytes(b"\x00" * 0x400000)
    with create_block_reader(str(path)) as reader:
        assert reader.vram_to_offset(0x7E8000) is None
        assert reader.vram_to_offset(0x7F8000) is None
        assert reader.vram_to_offset(0xFE8000) == 0x3F0000
        assert reader.vram_to_offset(0x400000) == 0x200000
        assert reader.vram_to_offset(0xC00000) == 0x200000
        assert reader.vram_to_offset(0x700000) is None


def test_ps1_detection_applies_stack_offset_and_ignores_filename_extension(tmp_path):
    header = ps1_header(size=4)
    struct.pack_into("<II", header, 0x30, 0x80100000, 0x1000)
    path = tmp_path / "game.rom"
    path.write_bytes(header + b"\x01\x02\x03\x04")
    assert inspect_file(str(path))["initial_sp"] == "0x80101000"
    with create_block_reader(str(path)) as reader:
        assert isinstance(reader, Ps1Reader)
        assert reader.read_bytes(0x80010000, 4) == b"\x01\x02\x03\x04"


def n64_image(storage):
    data = bytearray(0x2000)
    data[:4] = b"\x80\x37\x12\x40"
    struct.pack_into(">I", data, 8, 0x80200400)
    data[0x20:0x28] = b"TEST N64"
    data[0x1000:0x100C] = bytes.fromhex("24020001 03e00008 00000000")
    unit = {"z64": 1, "v64": 2, "n64": 4}[storage]
    return b"".join(data[pos:pos + unit][::-1] for pos in range(0, len(data), unit))


@pytest.mark.parametrize("storage", ["z64", "v64", "n64"])
def test_n64_reader_and_analyzer_normalize_storage(tmp_path, capsys, storage):
    path = tmp_path / f"test.{storage}"
    path.write_bytes(n64_image(storage))
    with create_block_reader(str(path)) as reader:
        assert reader.vram_to_offset(0x80200400) == 0x1000
        assert reader.read_u32(0x80200400) == 0x24020001
        assert reader.read_bytes(0x80200401, 7) == bytes.fromhex("02000103e00008")
    analyzer = BlockDataAnalyzer(str(path))
    try:
        assert analyzer.entry_vram == 0x80200400
        analyzer.print_structural_blocks()
        analyzer.disassemble_basic_blocks(max_blocks=1)
        output = capsys.readouterr().out
        assert "TEST N64" in output
        assert f".{storage}" in output
        assert "24020001" in output
        assert "addiu $v0" in output
        assert "[DELAY SLOT]" in output
    finally:
        analyzer.close()


def test_file_backed_reader_rejects_negative_read_length(tmp_path):
    path = tmp_path / "large.gba"
    with path.open("wb") as stream:
        stream.write(b"\x5A")
        stream.seek(17 * 1024 * 1024 - 1)
        stream.write(b"\x00")
    with GbaReader(str(path)) as reader:
        assert reader._file is not None
        assert reader.read_bytes(0x08000000, -1) == b""
        assert reader.read_bytes(0x08000000, 1) == b"\x5A"
        assert reader.read_bytes(0x0DFFFFFF, 2) == b""


def test_analyzer_uses_gba_and_snes_instruction_lifters(tmp_path, capsys):
    gba = tmp_path / "test.gba"
    snes = tmp_path / "test.sfc"
    create_gba_test_rom(str(gba))
    create_snes_test_rom(str(snes))
    for path, expected_entry, instruction in [(gba, 0, "BRANCH"), (snes, 0, "SEI")]:
        analyzer = BlockDataAnalyzer(str(path))
        try:
            assert analyzer.entry_rom_offset == expected_entry
            analyzer.disassemble_basic_blocks(max_blocks=1)
            output = capsys.readouterr().out
            assert instruction in output
            assert "MIPS" not in output
        finally:
            analyzer.close()


def test_analyzer_reads_ps1_text_instead_of_header(tmp_path, capsys):
    path = tmp_path / "test.exe"
    path.write_bytes(ps1_header(size=8) + bytes.fromhex("0800e003 00000000"))
    analyzer = BlockDataAnalyzer(str(path))
    try:
        assert analyzer.entry_rom_offset == 2048
        analyzer.disassemble_basic_blocks(max_blocks=1)
        output = capsys.readouterr().out
        assert "03E00008" in output
        assert "jr $ra" in output
        assert "[DELAY SLOT]" in output
    finally:
        analyzer.close()


def test_analyzer_entropy_includes_partial_blocks_and_validates_ranges(tmp_path, capsys):
    path = tmp_path / "small.dat"
    path.write_bytes(b"\x00" * 10)
    analyzer = BlockDataAnalyzer(str(path))
    analyzer.scan_entropy_map(chunk_size=64, max_chunks=1)
    assert "0x000000 - 0x000009" in capsys.readouterr().out
    with pytest.raises(ValueError):
        analyzer.inspect_hex_block(-1, 8)
    with pytest.raises(ValueError):
        analyzer.scan_entropy_map(chunk_size=0)
    with pytest.raises(ValueError):
        analyzer.disassemble_basic_blocks(max_blocks=0)
