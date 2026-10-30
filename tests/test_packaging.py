import os
import subprocess
import sys
import pytest


def test_recompiler_spec_exists():
    assert os.path.isfile("recompiler.spec")
    with open("recompiler.spec", "r") as f:
        content = f.read()
    assert "recompile.py" in content
    assert "name='recompiler'" in content


def test_package_exe_help():
    result = subprocess.run(
        [sys.executable, "-c", "import package_exe; assert callable(package_exe.package_standalone_exe)"],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0
