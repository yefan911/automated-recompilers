# -*- mode: python ; coding: utf-8 -*-

import os
import sys

block_cipher = None

a = Analysis(
    ['recompile.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('docs', 'docs'),
        ('roms/test', 'roms/test'),
    ],
    hiddenimports=[
        'src',
        'src.core',
        'src.core.rom_detector',
        'src.core.block_analyzer',
        'src.core.create_test_rom',
        'src.core.native_compiler',
        'src.lifter',
        'src.lifter.cfg',
        'src.lifter.arm_lifter',
        'src.lifter.mips_lifter',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='recompiler',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
