"""Check standalone runtime arguments and Windows hardware exception handling."""

import re
import subprocess

import pytest

from src.core.create_test_rom import create_gba_test_rom, create_n64_test_rom, create_snes_test_rom
from src.lifter.arm_lifter import lift_rom_to_c
from src.lifter.mips_lifter import lift_mips_rom_to_c
from src.lifter.snes_lifter import lift_snes_rom_to_c


CONSOLES = [
    pytest.param("gba", create_gba_test_rom, lift_rom_to_c, id="gba"),
    pytest.param("z64", create_n64_test_rom, lift_mips_rom_to_c, id="n64"),
    pytest.param("sfc", create_snes_test_rom, lift_snes_rom_to_c, id="snes"),
]


@pytest.mark.parametrize("extension,create_rom,lift", CONSOLES)
def test_standalone_runtime_arguments_and_execution(extension, create_rom, lift, build_native, tmp_path):
    rom = tmp_path / f"homebrew.{extension}"
    create_rom(str(rom))
    exe = build_native(lift(str(rom)), host_window=True)
    result = subprocess.run([str(exe), "--headless"], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
    invalid = subprocess.run([str(exe), "--unknown"], capture_output=True, text=True, timeout=15)
    assert invalid.returncode == 2
    assert "Unknown" in invalid.stderr


@pytest.mark.parametrize("extension,create_rom,lift", CONSOLES)
def test_hardware_exception_returns_failure_without_headless_dialog(
    extension, create_rom, lift, build_native, native_c_compiler, tmp_path,
):
    if not native_c_compiler[2]:
        pytest.skip("Windows hardware exception handling requires MSVC")
    rom = tmp_path / f"fault.{extension}"
    create_rom(str(rom))
    source = lift(str(rom))
    block = re.search(r"uint32_t bb_[0-9A-F]+\([^;]*?\)\s*\{", source)
    assert block is not None
    # Fault in an emitted guest block so the executable's real outer handler
    # must report failure. A synthetic guest ROM cannot access host pointers.
    source = source[:block.end()] + "\n    *(volatile uint32_t*)0 = 1;\n" + source[block.end():]
    exe = build_native(source, host_window=True)
    options = ["--headless"]
    if extension == "gba":
        options.extend(["--framebuffer", str(tmp_path / "fault.ppm")])
    result = subprocess.run([str(exe), *options], capture_output=True, text=True, timeout=15)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "exception" in (result.stdout + result.stderr).lower()
    assert not (tmp_path / "fault.ppm").exists()
