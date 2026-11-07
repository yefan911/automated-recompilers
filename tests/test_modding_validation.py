"""Exercise mod input validation and execute generated C modding helpers."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

import recompile
from src.core.create_test_rom import create_gba_test_rom
from src.modding.hook_manager import HookManager, HookType
from src.modding.texture_manager import TextureFormat, TextureManager, TextureMetadata


def test_texture_manifest_is_transactional_and_counts_unique_entries(tmp_path):
    (tmp_path / "tex_12345678.png").write_bytes(b"image")
    item = {"crc32": "0x12345678", "width": 128, "height": 128}
    manifest = tmp_path / "texture_pack.json"
    manifest.write_text(json.dumps({"textures": [item, item]}), encoding="utf-8")
    manager = TextureManager()
    assert manager.load_texture_pack(tmp_path) == 1
    assert manager.get_replacement(0x12345678).data_size == 5
    assert manager.load_texture_pack(tmp_path) == 1
    original = manager.get_replacement(0x12345678)
    manifest.write_text(json.dumps({"textures": [dict(item, width=256), dict(item, width=-1)]}), encoding="utf-8")
    with pytest.raises(ValueError):
        manager.load_texture_pack(tmp_path)
    assert manager.get_replacement(0x12345678) is original


@pytest.mark.parametrize("absolute", [False, True])
def test_texture_manifest_rejects_paths_outside_pack(absolute, tmp_path):
    pack = tmp_path / "pack"
    pack.mkdir()
    outside = tmp_path / "outside.png"
    outside.write_bytes(b"image")
    path = str(outside) if absolute else "../outside.png"
    (pack / "texture_pack.json").write_text(json.dumps({"textures": [{"crc32": "0x12345678", "file": path}]}), encoding="utf-8")
    with pytest.raises(ValueError, match="relative|leaves"):
        TextureManager().load_texture_pack(pack)


@pytest.mark.parametrize("scale", [float("nan"), float("inf"), 0, -1, 10**1000, 1e-300], ids=["nan", "inf", "zero", "negative", "huge", "underflow"])
def test_texture_metadata_rejects_invalid_c_float_scales(scale):
    with pytest.raises(ValueError):
        TextureMetadata(0x12345678, 16, 16, TextureFormat.RGBA8888, 0, scale_factor=scale)


def test_texture_replacements_require_dimensions_files_and_valid_crc(tmp_path):
    file = tmp_path / "texture.png"
    file.write_bytes(b"image")
    manager = TextureManager()
    for crc, width, orig_width in [(-1, 16, 16), (2**32, 16, 16), (True, 16, 16), (1, 0, 16), (1, 16, 0)]:
        with pytest.raises(ValueError):
            manager.register_replacement(crc, file, width, 16, orig_width, 16)
    with pytest.raises(ValueError, match="not found"):
        manager.register_replacement(1, tmp_path / "missing.png", 16, 16, 16, 16)
    metadata = manager.register_replacement(1, file, 16, 16, 16, 16)
    metadata.width = -1
    with pytest.raises(ValueError):
        manager.emit_c_texture_interceptor()


def test_texture_paths_and_scale_survive_c_generation(run_native):
    manager = TextureManager()
    manager.replacements[0x12345678] = TextureMetadata(
        0x12345678, 128, 128, TextureFormat.RGBA8888, 0,
        scale_factor=1.125, file_path='C:\\mods\\folder "quoted"\\line\n9.png',
    )
    source = manager.emit_c_texture_interceptor() + r'''
#include <stdio.h>
int main(void) {
    const RecompHdTextureEntry* entry = recomp_lookup_hd_texture(0x12345678u);
    if (!entry || entry->width != 128 || entry->scale_factor != 1.125f) return 1;
    if (strcmp(entry->file_path, "C:/mods/folder \"quoted\"/line\n9.png") != 0) return 2;
    if (recomp_lookup_hd_texture(0xFFFFFFFFu) != NULL) return 3;
    return 0;
}
'''
    run_native(source)


def test_hooks_execute_priority_phases_and_propagate_post_results(run_native):
    manager = HookManager()
    manager.register_hook(0x80010000, "pre_second", HookType.HOOK_PRE, 20)
    manager.register_hook(0x80010000, "pre_first", HookType.HOOK_PRE, 10, description="*/\nreturn 999; /*")
    manager.register_hook(0x80010000, "replace_original", HookType.HOOK_REPLACE, 1)
    manager.register_hook(0x80010000, "post_second", HookType.HOOK_POST, 20)
    manager.register_hook(0x80010000, "post_first", HookType.HOOK_POST, 10)
    source = manager.emit_c_header() + r'''
typedef struct { unsigned trace; unsigned original_calls; } Context;
void pre_first(void* ctx, uint32_t pc) { (void)pc; ((Context*)ctx)->trace = ((Context*)ctx)->trace * 10 + 1; }
void pre_second(void* ctx, uint32_t pc) { (void)pc; ((Context*)ctx)->trace = ((Context*)ctx)->trace * 10 + 2; }
uint32_t replace_original(void* ctx, uint32_t pc) { (void)pc; ((Context*)ctx)->trace = ((Context*)ctx)->trace * 10 + 3; return 10; }
uint32_t post_first(void* ctx, uint32_t pc, uint32_t result) { (void)pc; ((Context*)ctx)->trace = ((Context*)ctx)->trace * 10 + 4; return result + 1; }
uint32_t post_second(void* ctx, uint32_t pc, uint32_t result) { (void)pc; ((Context*)ctx)->trace = ((Context*)ctx)->trace * 10 + 5; return result * 2; }
uint32_t bb_80010000(void* ctx) { ((Context*)ctx)->original_calls++; return 99; }
uint32_t hooked(void* ctx) {
'''
    source += manager.emit_c_hook_trampoline("bb_80010000", 0x80010000) + "\n}\n"
    source += "int main(void) { Context ctx = {0}; return !(hooked(&ctx) == 22 && ctx.trace == 12345 && ctx.original_calls == 0); }"
    run_native(source)


@pytest.mark.parametrize("name", ["bad-name", "return", "name); injected(", "_Reserved"])
def test_hook_identifiers_are_validated_at_registration_and_emission(name):
    manager = HookManager()
    with pytest.raises(ValueError):
        manager.register_hook(0x80010000, name)
    hook = manager.register_hook(0x80010000, "valid_hook")
    hook.hook_function_name = name
    with pytest.raises(ValueError):
        manager.emit_c_header()


def test_cli_reports_malformed_texture_pack_without_traceback(tmp_path):
    rom = tmp_path / "test.gba"
    create_gba_test_rom(str(rom))
    pack = tmp_path / "pack"
    pack.mkdir()
    (pack / "texture_pack.json").write_text("{broken", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(Path(recompile.__file__)), str(rom), "--no-build", "--load-textures", str(pack)],
        cwd=tmp_path, capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 1
    assert "Invalid texture pack manifest" in result.stdout
    assert "Traceback" not in result.stderr
    assert not (tmp_path / "build" / "test_recompiled.c").exists()
