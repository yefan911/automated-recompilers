#!/usr/bin/env python3
"""
Unit tests for the Modding SDK: HD Texture Replacement, Widescreen Patcher, and Hook Manager.
"""

import os
import json
import tempfile
import pytest

from src.modding.texture_manager import (
    TextureFormat,
    TextureMetadata,
    TextureManager,
    compute_texture_crc32,
)
from src.modding.widescreen import (
    AspectRatio,
    WidescreenMode,
    WidescreenPatcher,
)
from src.modding.hook_manager import (
    HookType,
    FunctionHook,
    HookManager,
)


def test_texture_crc32_deterministic():
    sample_data = b"\x00\x11\x22\x33\x44\x55\x66\x77" * 32
    crc1 = compute_texture_crc32(sample_data, 16, 16, TextureFormat.RGBA8888)
    crc2 = compute_texture_crc32(sample_data, 16, 16, TextureFormat.RGBA8888)
    assert crc1 == crc2
    assert isinstance(crc1, int)
    assert crc1 > 0

    # Differing dimensions with identical payload must yield different hashes due to dimension salt
    crc_diff_dim = compute_texture_crc32(sample_data, 8, 32, TextureFormat.RGBA8888)
    assert crc1 != crc_diff_dim

    # Differing formats must yield different hashes
    crc_diff_fmt = compute_texture_crc32(sample_data, 16, 16, TextureFormat.RGB565)
    assert crc1 != crc_diff_fmt


def test_texture_manager_dump_and_replace():
    with tempfile.TemporaryDirectory() as tmpdir:
        dump_dir = os.path.join(tmpdir, "dumps")
        mods_dir = os.path.join(tmpdir, "mods")
        manager = TextureManager(dump_dir=dump_dir, mods_dir=mods_dir)

        raw_tex = b"\xAA\xBB\xCC\xDD" * 64
        meta = manager.dump_texture(raw_tex, 16, 16, TextureFormat.RGBA8888, name="BrickTexture")

        assert os.path.exists(meta.file_path)
        meta_json_path = os.path.join(dump_dir, f"tex_{meta.crc32:08X}.json")
        assert os.path.exists(meta_json_path)

        with open(meta_json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["crc32"] == meta.crc32
        assert data["width"] == 16
        assert data["height"] == 16
        assert data["format"] == "RGBA8888"

        # Register an HD replacement (64x64, 4x scale)
        hd_path = os.path.join(mods_dir, f"tex_{meta.crc32:08X}_hd.png")
        os.makedirs(mods_dir, exist_ok=True)
        with open(hd_path, "wb") as f:
            f.write(b"\x00" * 1024)

        rep = manager.register_replacement(
            crc32=meta.crc32,
            file_path=hd_path,
            width=64,
            height=64,
            orig_width=16,
            orig_height=16
        )
        assert rep.scale_factor == 4.0
        assert manager.get_replacement(meta.crc32) is not None

        c_interceptor = manager.emit_c_texture_interceptor()
        assert f"0x{meta.crc32:08X}" in c_interceptor
        assert "recomp_lookup_hd_texture" in c_interceptor


def test_texture_pack_manifest_loading():
    with tempfile.TemporaryDirectory() as tmpdir:
        pack_dir = os.path.join(tmpdir, "hd_pack")
        os.makedirs(pack_dir, exist_ok=True)

        manifest = {
            "title": "Ultra HD Pack",
            "version": "1.0",
            "textures": [
                {
                    "crc32": "0x12345678",
                    "file": "tex_12345678.png",
                    "width": 128,
                    "height": 128,
                    "format": "RGBA8888",
                    "scale": 4.0
                }
            ]
        }
        with open(os.path.join(pack_dir, "texture_pack.json"), "w", encoding="utf-8") as f:
            json.dump(manifest, f)

        # Create dummy texture file
        with open(os.path.join(pack_dir, "tex_12345678.png"), "wb") as f:
            f.write(b"\x89PNG\r\n\x1a\n")

        # Also create loose file
        with open(os.path.join(pack_dir, "tex_AABBCCDD.png"), "wb") as f:
            f.write(b"\x89PNG\r\n\x1a\n")

        manager = TextureManager()
        count = manager.load_texture_pack(pack_dir)
        assert count == 2
        assert manager.get_replacement(0x12345678) is not None
        assert manager.get_replacement(0xAABBCCDD) is not None


def test_widescreen_aspect_ratio_and_fov():
    # 16:9 on 4:3 native
    patcher = WidescreenPatcher(
        native_ratio=AspectRatio.RATIO_4_3,
        target_ratio=AspectRatio.RATIO_16_9,
        mode=WidescreenMode.HOR_PLUS
    )
    # FOV expansion: (16/9) / (4/3) = 4/3 = 1.333333
    assert pytest.approx(patcher.fov_multiplier, 0.001) == 1.333333
    # Projection X Scale: (4/3) / (16/9) = 3/4 = 0.75
    assert pytest.approx(patcher.projection_x_scale, 0.001) == 0.75

    # Test aspect ratio string parsing
    ar_16_9 = AspectRatio.from_string("16:9")
    assert ar_16_9 == AspectRatio.RATIO_16_9
    ar_21_9 = AspectRatio.from_string("21:9")
    assert ar_21_9 == AspectRatio.RATIO_21_9

    with pytest.raises(ValueError):
        AspectRatio.from_string("invalid_ratio")


def test_widescreen_projection_matrix_patch():
    patcher = WidescreenPatcher(
        native_ratio=AspectRatio.RATIO_4_3,
        target_ratio=AspectRatio.RATIO_16_9,
        mode=WidescreenMode.HOR_PLUS
    )

    # Standard 4x4 identity matrix
    identity = [
        1.0, 0.0, 0.0, 0.0,
        0.0, 1.0, 0.0, 0.0,
        0.0, 0.0, 1.0, 0.0,
        0.0, 0.0, 0.0, 1.0
    ]
    patched = patcher.patch_matrix_4x4(identity)
    assert pytest.approx(patched[0], 0.001) == 0.75
    assert patched[5] == 1.0  # Y scale unchanged (Hor+)

    with pytest.raises(ValueError):
        patcher.patch_matrix_4x4([1.0] * 8)


def test_widescreen_viewport_and_c_shim():
    patcher_pb = WidescreenPatcher(
        native_ratio=AspectRatio.RATIO_4_3,
        target_ratio=AspectRatio.RATIO_16_9,
        mode=WidescreenMode.PILLARBOX
    )
    # Target window: 1920x1080. Native 4:3 fit: 1440x1080.
    vp = patcher_pb.compute_viewport(1920, 1080)
    assert vp.width == 1440
    assert vp.height == 1080
    assert vp.pillar_left == 240
    assert vp.pillar_right == 240

    c_shim = patcher_pb.emit_c_widescreen_shim()
    assert "recomp_apply_widescreen_matrix" in c_shim
    assert "RECOMP_PROJECTION_X_SCALE" in c_shim


def test_hook_manager_lifecycle_and_trampolines():
    hm = HookManager()

    # Register hooks on VRAM 0x80010000
    h_pre = hm.register_hook(
        target_vram=0x80010000,
        hook_function_name="mod_log_entry",
        hook_type=HookType.HOOK_PRE,
        priority=10,
        description="Log subroutine entry"
    )
    h_post = hm.register_hook(
        target_vram=0x80010000,
        hook_function_name="mod_audit_return",
        hook_type=HookType.HOOK_POST,
        priority=50,
        description="Inspect return value"
    )

    hooks = hm.get_hooks(0x80010000)
    assert len(hooks) == 2
    assert hooks[0].hook_function_name == "mod_log_entry"
    assert hooks[1].hook_function_name == "mod_audit_return"

    # Test trampoline C code generation
    trampoline = hm.emit_c_hook_trampoline("bb_80010000", 0x80010000)
    assert "mod_log_entry(ctx, 0x80010000);" in trampoline
    assert "bb_80010000(ctx)" in trampoline
    assert "mod_audit_return(ctx, 0x80010000, ret_val);" in trampoline

    # Register REPLACE hook
    hm.register_hook(
        target_vram=0x80020000,
        hook_function_name="mod_custom_math",
        hook_type=HookType.HOOK_REPLACE,
        description="Override original math routine"
    )
    assert hm.has_replace_hook(0x80020000) is not None
    replace_trampoline = hm.emit_c_hook_trampoline("bb_80020000", 0x80020000)
    assert "mod_custom_math(ctx, 0x80020000);" in replace_trampoline
    assert "bb_80020000(ctx)" not in replace_trampoline

    # Header generation
    header = hm.emit_c_header()
    assert "RecompPreHookFn" in header
    assert "mod_log_entry" in header
    assert "mod_custom_math" in header

    # Unregister hook
    assert hm.unregister_hook(0x80010000, "mod_log_entry") is True
    assert len(hm.get_hooks(0x80010000)) == 1
