import os
import subprocess
import sys
import tempfile
from src.core.create_test_rom import create_gba_test_rom


def test_e2e_recompile_cli_no_args():
    result = subprocess.run(
        [sys.executable, "recompile.py"],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0
    assert "AUTOMATED GAME ROM RECOMPILER FRAMEWORK" in result.stdout
    assert "hello_gba.gba" in result.stdout


def test_e2e_recompile_cli_rom_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        test_rom = os.path.join(tmpdir, "cli_test.gba")
        create_gba_test_rom(test_rom)

        result = subprocess.run(
            [sys.executable, "recompile.py", test_rom],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        assert "ROM Identification & Header Analysis" in result.stdout
        assert "Emitted recompiled source:" in result.stdout or "Emitted native C source code" in result.stdout
        assert "RECOMPILATION COMPLETE" in result.stdout or "Recompilation succeeded!" in result.stdout

        expected_c = os.path.join("build", "cli_test_recompiled.c")
        assert os.path.isfile(expected_c)
        with open(expected_c, "r") as f:
            content = f.read()
        assert "ArmCpuContext" in content

        # Clean up generated test output
        if os.path.exists(expected_c):
            os.remove(expected_c)


def test_e2e_recompile_cli_blocks():
    result = subprocess.run(
        [sys.executable, "recompile.py", "--blocks", "roms/test/hello_gba.gba"],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0
    assert "STRUCTURAL ROM BLOCK BREAKDOWN" in result.stdout
    assert "CONTROL FLOW GRAPH" in result.stdout
