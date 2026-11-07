import os
import subprocess
import sys
import tempfile
import pytest
import recompile
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
            try:
                os.remove(expected_c)
            except OSError:
                pass
        expected_exe = os.path.join("build", "cli_test.exe")
        if os.path.exists(expected_exe):
            try:
                os.remove(expected_exe)
            except OSError:
                pass
        expected_bin = os.path.join("build", "cli_test")
        if os.path.exists(expected_bin):
            try:
                os.remove(expected_bin)
            except OSError:
                pass


def test_e2e_recompile_cli_blocks():
    result = subprocess.run(
        [sys.executable, "recompile.py", "--blocks", "roms/test/hello_gba.gba"],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0
    assert "STRUCTURAL ROM BLOCK BREAKDOWN" in result.stdout
    assert "CONTROL FLOW GRAPH" in result.stdout


def test_e2e_recompile_cli_with_modding_flags():
    with tempfile.TemporaryDirectory() as tmpdir:
        test_rom = os.path.join(tmpdir, "mod_test.gba")
        create_gba_test_rom(test_rom)

        result = subprocess.run(
            [sys.executable, "recompile.py", test_rom, "--no-build", "--widescreen", "16:9", "--enable-hooks"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        assert "[Modding] Injected Hor+ Widescreen" in result.stdout
        assert "[Modding] Injected native C Hook & Interception API" in result.stdout

        expected_c = os.path.join("build", "mod_test_recompiled.c")
        assert os.path.isfile(expected_c)
        with open(expected_c, "r") as f:
            content = f.read()
        assert "RECOMP_WIDESCREEN_H" in content
        assert "RECOMP_HOOKS_H" in content

        # Clean up
        if os.path.exists(expected_c):
            os.remove(expected_c)


@pytest.mark.parametrize("args", [["--blocks"], ["--no-build"]])
def test_cli_missing_rom_argument(args):
    result = subprocess.run(
        [sys.executable, "recompile.py", *args],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 2
    assert "Please provide a ROM path" in result.stdout
    assert "Traceback" not in result.stderr


def test_cli_missing_rom_file(tmp_path):
    result = subprocess.run(
        [sys.executable, "recompile.py", str(tmp_path / "missing.gba")],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 1
    assert "Could not analyze" in result.stdout


@pytest.mark.parametrize("options", [
    ["--max-blocks", "0"], ["--max-blocks", "-1"], ["--max-blocks", "text"],
    ["--max-blocks"], ["--widescreen", "invalid"], ["--load-textures"],
    ["--unknown-option"],
])
def test_cli_rejects_invalid_options_without_traceback(options):
    result = subprocess.run(
        [sys.executable, "recompile.py", "roms/test/hello_gba.gba", *options],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 2
    assert "Traceback" not in result.stderr


@pytest.mark.parametrize(
    "console",
    ["Game Boy Advance", "Nintendo 64", "PlayStation 1", "Super Nintendo"],
)
def test_cli_propagates_compiler_failure(console, tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["recompile.py", "test.rom"])
    monkeypatch.setattr(
        recompile,
        "inspect_file",
        lambda path: {"console": console, "filename": "test.rom"},
    )
    for lifter in ("lift_rom_to_c", "lift_mips_rom_to_c", "lift_snes_rom_to_c"):
        monkeypatch.setattr(recompile, lifter, lambda *args, **kwargs: "int main(void) { return 0; }")
    monkeypatch.setattr(recompile, "compile_c_to_exe", lambda *args: False)

    assert recompile.main() == 1
    output = capsys.readouterr().out
    assert "Compilation failed" in output
    assert "RECOMPILATION COMPLETE" not in output

