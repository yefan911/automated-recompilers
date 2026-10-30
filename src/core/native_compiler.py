#!/usr/bin/env python3
"""
Native Compiler Driver for Automated Recompiler
Detects and interfaces with MSVC (Visual Studio 2022/2019), Clang, or GCC
to compile generated C code into native Windows executables (.exe).
"""

import os
import sys
import shutil
import subprocess
from typing import Optional, Dict, Tuple

_CACHED_MSVC_ENV = None
_CACHED_CL_PATH = None

def get_msvc_environment() -> Tuple[Optional[str], Optional[Dict[str, str]]]:
    """Finds Visual Studio installation and extracts environment variables."""
    global _CACHED_MSVC_ENV, _CACHED_CL_PATH
    if _CACHED_MSVC_ENV is not None:
        return _CACHED_CL_PATH, _CACHED_MSVC_ENV

    # 1. Check vswhere
    vswhere = r"C:\Program Files (x86)\Microsoft Visual Studio\Installer\vswhere.exe"
    vs_path = None
    if os.path.exists(vswhere):
        try:
            out = subprocess.check_output(
                [vswhere, "-latest", "-property", "installationPath"],
                text=True, errors="ignore"
            ).strip()
            if os.path.isdir(out):
                vs_path = out
        except Exception:
            pass

    if not vs_path:
        # Fallback to standard 2022 path
        fallback = r"C:\Program Files\Microsoft Visual Studio\2022\Community"
        if os.path.isdir(fallback):
            vs_path = fallback

    if not vs_path:
        return None, None

    vcvars = os.path.join(vs_path, "VC", "Auxiliary", "Build", "vcvars64.bat")
    if not os.path.isfile(vcvars):
        return None, None

    # Extract environment
    try:
        cmd = f'call "{vcvars}" && set'
        proc = subprocess.Popen(
            cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, errors="ignore"
        )
        stdout, _ = proc.communicate()
        env = {}
        for line in stdout.splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                env[k] = v

        cl_path = None
        for p in env.get("PATH", "").split(";"):
            cand = os.path.join(p, "cl.exe")
            if os.path.isfile(cand):
                cl_path = cand
                break

        _CACHED_MSVC_ENV = env
        _CACHED_CL_PATH = cl_path
        return cl_path, env
    except Exception as e:
        print(f"Error querying MSVC environment: {e}")
        return None, None


def compile_c_to_exe(c_source_path: str, output_exe_path: str, extra_libs: list = None) -> bool:
    """Compiles a C source file into a standalone Windows executable."""
    c_source_path = os.path.abspath(c_source_path)
    output_exe_path = os.path.abspath(output_exe_path)
    os.makedirs(os.path.dirname(output_exe_path), exist_ok=True)

    # 1. Try MSVC
    cl_path, msvc_env = get_msvc_environment()
    if cl_path and msvc_env:
        cmd = [
            cl_path,
            "/O2",               # Max speed optimization
            "/W3",               # Warning level 3
            f"/Fe:{output_exe_path}",
            c_source_path,
        ]
        if extra_libs:
            cmd.extend(extra_libs)
        else:
            cmd.extend(["user32.lib", "gdi32.lib"])

        print(f"[Compiler] Building with MSVC: {os.path.basename(c_source_path)} -> {os.path.basename(output_exe_path)}...")
        res = subprocess.run(cmd, env=msvc_env, capture_output=True, text=True, errors="ignore")
        if res.returncode == 0 and os.path.exists(output_exe_path):
            print(f"[Compiler] Build Successful: {output_exe_path}")
            return True
        else:
            print(f"[Compiler] MSVC compilation error (exit {res.returncode}):\n{res.stdout}\n{res.stderr}")

    # 2. Try GCC or Clang if in PATH
    for compiler in ["clang", "gcc"]:
        if shutil.which(compiler):
            cmd = [compiler, "-O2", c_source_path, "-o", output_exe_path]
            if extra_libs:
                cmd.extend(extra_libs)
            else:
                cmd.extend(["-luser32", "-lgdi32"])
            print(f"[Compiler] Building with {compiler}: {os.path.basename(output_exe_path)}...")
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode == 0:
                print(f"[Compiler] Build Successful: {output_exe_path}")
                return True

    print("Error: No working C compiler found (MSVC, Clang, or GCC).")
    return False


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else "build/recompiled_game.c"
    out = sys.argv[2] if len(sys.argv) > 2 else "build/recompiled_game.exe"
    success = compile_c_to_exe(src, out)
    sys.exit(0 if success else 1)
