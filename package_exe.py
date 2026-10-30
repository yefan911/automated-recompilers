#!/usr/bin/env python3
"""
Standalone Executable Packaging Utility
Part of Automated Recompiler Framework.

Packages the entire Automated Recompiler CLI, detectors, and lifters
into a standalone, zero-dependency executable (recompiler.exe) using PyInstaller.
"""

import os
import sys
import shutil
import subprocess

def package_standalone_exe() -> bool:
    print("\n========================================================")
    print("  AUTOMATED RECOMPILER: STANDALONE EXECUTABLE PACKAGER")
    print("========================================================\n")

    # 1. Verify PyInstaller is installed
    try:
        import PyInstaller
        print(f"[1/4] Found PyInstaller version {PyInstaller.__version__}")
    except ImportError:
        print("[1/4] PyInstaller not found. Installing via pip...")
        res = subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=False)
        if res.returncode != 0:
            print("Error: Failed to install PyInstaller.")
            return False

    # 2. Run PyInstaller
    spec_file = "recompiler.spec"
    dist_dir = os.path.abspath("dist")
    build_dir = os.path.abspath("build/pyinstaller")
    os.makedirs(dist_dir, exist_ok=True)
    os.makedirs(build_dir, exist_ok=True)

    print(f"\n[2/4] Packaging 'recompile.py' using {spec_file}...")
    cmd = [
        sys.executable,
        "-m", "PyInstaller",
        "--clean",
        "--noconfirm",
        "--distpath", dist_dir,
        "--workpath", build_dir,
        spec_file
    ]

    res = subprocess.run(cmd, check=False)
    if res.returncode != 0:
        print(f"\nError: PyInstaller build failed with exit code {res.returncode}")
        return False

    exe_name = "recompiler.exe" if sys.platform == "win32" else "recompiler"
    output_exe = os.path.join(dist_dir, exe_name)

    if not os.path.isfile(output_exe):
        print(f"Error: Expected output binary '{output_exe}' was not produced.")
        return False

    size_mb = os.path.getsize(output_exe) / (1024 * 1024)
    print(f"\n[3/4] Successfully created standalone binary: {output_exe} ({size_mb:.2f} MB)")

    # 3. Smoke Test the standalone executable
    print("\n[4/4] Performing smoke test on generated standalone binary...")
    test_run = subprocess.run([output_exe], capture_output=True, text=True, check=False)
    if test_run.returncode == 0 and "AUTOMATED GAME ROM RECOMPILER FRAMEWORK" in test_run.stdout:
        print("  [PASS] Standalone binary smoke test PASSED!")
    else:
        print(f"  Warning: Smoke test returned code {test_run.returncode}:\n{test_run.stdout}\n{test_run.stderr}")

    print("\n========================================================")
    print(f"  PACKAGING COMPLETE: {os.path.basename(output_exe)}")
    print("========================================================")
    print("You can now distribute this standalone binary with no Python installation required!")
    print(f"\nUsage:")
    print(f"    .{os.sep}dist{os.sep}{exe_name} roms/test/hello_gba.gba")
    print(f"    .{os.sep}dist{os.sep}{exe_name} --blocks roms/test/hello_gba.gba\n")
    return True

if __name__ == "__main__":
    success = package_standalone_exe()
    sys.exit(0 if success else 1)
