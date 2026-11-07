"""Compile generated C for architectural and runtime regression tests."""

import shutil
import subprocess
import sys

import pytest

from src.core.native_compiler import get_msvc_environment


@pytest.fixture(scope="session")
def native_c_compiler():
    cl, env = get_msvc_environment()
    compiler = cl or shutil.which("gcc") or shutil.which("clang")
    if compiler is None:
        pytest.skip("A native C compiler is required to execute generated code")
    return compiler, env if cl else None, bool(cl)


@pytest.fixture
def build_native(tmp_path, native_c_compiler):
    compiler, env, msvc = native_c_compiler
    build_count = 0

    def build(source, *, host_window=False):
        nonlocal build_count
        build_count += 1
        stem = f"native_{build_count}"
        src = tmp_path / f"{stem}.c"
        exe = tmp_path / (f"{stem}.exe" if sys.platform == "win32" else stem)
        src.write_text(source, encoding="utf-8")
        if msvc:
            command = [compiler, "/nologo", "/O2", "/W3", "/WX", f"/Fo{tmp_path / (stem + '.obj')}", f"/Fe{exe}", str(src)]
            if host_window:
                command.extend(["user32.lib", "gdi32.lib"])
        else:
            command = [compiler, "-std=c99", "-Wall", "-Wextra", "-Werror", "-O2", str(src), "-o", str(exe), "-lm"]
            if host_window and sys.platform == "win32":
                command.extend(["-luser32", "-lgdi32"])
        result = subprocess.run(command, env=env, cwd=tmp_path, capture_output=True, text=True, timeout=60)
        assert result.returncode == 0, result.stdout + result.stderr
        return exe

    return build


@pytest.fixture
def run_native(build_native):
    def run(source):
        exe = build_native(source)
        result = subprocess.run([str(exe)], capture_output=True, text=True, timeout=15)
        assert result.returncode == 0, result.stdout + result.stderr
        return result

    return run
