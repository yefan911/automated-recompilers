import os
from unittest.mock import Mock

from src.core import native_compiler


def test_msvc_discovery_accepts_mixed_case_path_and_caches_environment(tmp_path, monkeypatch):
    vs_path = tmp_path / "Visual Studio"
    vcvars = vs_path / "VC" / "Auxiliary" / "Build" / "vcvars64.bat"
    vcvars.parent.mkdir(parents=True)
    vcvars.touch()
    compiler_dir = vs_path / "VC" / "Tools" / "MSVC" / "bin"
    compiler_dir.mkdir(parents=True)
    compiler = compiler_dir / "cl.exe"
    compiler.touch()

    vswhere = r"C:\Program Files (x86)\Microsoft Visual Studio\Installer\vswhere.exe"
    path_value = f"{compiler_dir};C:\\Windows\\System32"
    vcvars_output = f"Path={path_value}\nINCLUDE=include-dir\nLIB=lib-dir\n"
    exists = native_compiler.os.path.exists
    monkeypatch.setattr(native_compiler.os.path, "exists", lambda path: path == vswhere or exists(path))
    check_output = Mock(return_value=str(vs_path) + "\n")
    process = Mock()
    process.communicate.return_value = (vcvars_output, "")
    popen = Mock(return_value=process)
    monkeypatch.setattr(native_compiler.subprocess, "check_output", check_output)
    monkeypatch.setattr(native_compiler.subprocess, "Popen", popen)
    monkeypatch.setattr(native_compiler, "_CACHED_MSVC_ENV", None)
    monkeypatch.setattr(native_compiler, "_CACHED_CL_PATH", None)

    cl_path, environment = native_compiler.get_msvc_environment()

    assert cl_path == os.fspath(compiler)
    assert environment["PATH"] == path_value
    assert environment["INCLUDE"] == "include-dir"
    assert environment["LIB"] == "lib-dir"
    cached_cl_path, cached_environment = native_compiler.get_msvc_environment()
    assert cached_cl_path == cl_path
    assert cached_environment is environment
    check_output.assert_called_once_with(
        [vswhere, "-latest", "-property", "installationPath"], text=True, errors="ignore"
    )
    popen.assert_called_once()
