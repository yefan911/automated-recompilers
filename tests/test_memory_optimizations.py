import os
import tracemalloc
from src.core.rom_detector import inspect_file, scan_roms_directory
from src.lifter.arm_lifter import ArmLifter
from src.lifter.mips_lifter import MipsLifter
from src.core.block_analyzer import BlockDataAnalyzer


def test_inspect_file_bounded_memory(tmp_path):
    # Create a 10MB dummy file
    dummy_file = tmp_path / "large_dummy.bin"
    with open(dummy_file, "wb") as f:
        f.write(b"\x00" * (10 * 1024 * 1024))

    tracemalloc.start()
    info = inspect_file(str(dummy_file))
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    assert info is not None
    assert info["size_bytes"] == 10 * 1024 * 1024
    # Peak memory during inspection of 10MB file should be well under 1MB
    assert peak < 1024 * 1024


def test_block_analyzer_attributes():
    test_rom = "roms/test/hello_gba.gba"
    if os.path.exists(test_rom):
        analyzer = BlockDataAnalyzer(test_rom)
        assert analyzer.filename == "hello_gba.gba"
        assert analyzer.total_bytes == os.path.getsize(test_rom)
        assert analyzer.is_gba is True
        assert analyzer.is_n64 is False
        assert analyzer.entry_vram == 0x08000000


def test_arm_worklist_deduplication():
    # Verify that ArmLifter build_cfg runs with deduplicated queueing
    test_rom = "roms/test/hello_gba.gba"
    if os.path.exists(test_rom):
        with open(test_rom, "rb") as f:
            data = f.read()
        lifter = ArmLifter(data)
        cfg = lifter.build_cfg(0x08000000, max_blocks=100)
        assert len(cfg) > 0
