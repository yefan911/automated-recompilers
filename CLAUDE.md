# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working in this repository.

## Project

Automated Game ROM Recompiler — AOT-translates console ROMs (GBA, N64, PS1, SNES) into standalone native PC executables. Four-stage pipeline per ROM: **identify** (header/console/endianness/entry-point) → **recursive CFG lift** (disassemble + trace basic blocks) → **emit C** (with HAL + dispatch trampoline) → **native compile** to `.exe`.

## Commands

- **Python on this machine is not on PATH.** Use the full path: `/c/Users/parra/AppData/Local/Programs/Python/Python313/python` (or `py`). Do not run bare `python`/`python3`.
- **Tests:** `pytest -v` (all). Single test: `pytest -v tests/test_lifters.py::test_arm_lifter_branch`. CI runs on Python 3.10–3.13 on ubuntu with `gcc`; the e2e step compiles `build/hello_gba_recompiled.c` with `gcc -Wall -Wextra -Werror -O2` and runs it, so generated C must compile cleanly.
- **Recompile a ROM:** `python recompile.py roms/test/hello_gba.gba` (adds `--no-build` to emit C only, `--max-blocks N` for large ROMs, `--blocks <rom>` to inspect).
- **GUI:** `python recompile.py --ui` or `python gui.py`.
- **Standalone binary:** `python package_exe.py` → `dist/recompiler.exe`.
- **Block analysis:** `python recompile.py --blocks roms/n64/Yoshi.z64`.

## Architecture

- `src/core/` — `rom_detector.py` (console/endianness/entry detection: GBA, N64, PS1, NES; **SNES detection is missing**), `block_analyzer.py` (entropy map + MIPS CFG disassembly — **N64-only, big-endian only**), `native_compiler.py` (MSVC/Clang/GCC driver), `create_test_rom.py`.
- `src/lifter/` — `cfg.py` (`BasicBlock` + `ControlFlowGraph`, emits `bb_XXXXXXXX` functions and a `recomp_dispatch` switch), `arm_lifter.py` (ARM7TDMI), `thumb_lifter.py` (Thumb-16), `mips_lifter.py` (MIPS I/III, N64/PS1). Each lifter: `lift_block(pc) → (ir_ops, targets)`; the top-level `lift_*_rom_to_c()` reads the ROM, builds the CFG, emits C.
- `src/runtime/` — HAL (currently empty; display/audio/MMIO shims go here).
- `recompile.py` dispatches on detected console: GBA → ARM, N64/PS1 → MIPS. **SNES has no branch.**
- Conventions: lifers do `sys.path.insert(0, <project root>)`; IR ops are dicts with `op`, `pc`, `c_code`; C output uses `ArmCpuContext`/`MipsCpuContext`, `mem_read8/16/32`, `mem_write8/16/32`.

## Multi-agent coordination

This repo is worked on by more than one Claude session. **`COORDINATION.md` is the shared team board** — the group chat. All teammates read/write it: claim tasks under `## Active Claims` before starting, update status, and leave `## Handoffs` notes. Do not edit files a teammate has claimed.

- Peer session **"game file data blocks"** owns the **data-block reader / detector** side (`src/core/data_block_reader.py`, `detect_snes`, PS1 ISO-9660 boot-EXE parsing). It does **not** own lifters.
- **Lifters (`src/lifter/`) are my domain.** When adding a new console, write the lifter here and consume the peer's reader as a black box — don't reimplement address translation.
- Don't commit to `main` while a teammate is mid-work; coordinate merges via the board.

## Gotchas

- `block_analyzer.py` is hard-coded to N64 big-endian layout; it prints wrong data on other consoles. Prefer `inspect_file()` to detect the console first.
- PS1 ROMs in `roms/ps1` are CD images (ISO 9660, volume `NFS_NTSC`), not raw `PS-X EXE` — `detect_ps1` doesn't match them yet.
- `roms/snes/...Super Mario All-Stars and Super Mario World (axekin.com).sfc` is **LoROM**: header at `0x7FB0`, reset vector bank `0xA9` / PC `0x8000` → 24-bit `0xA98000` → ROM offset `0x14C000`. SNES CPU is the W65C816S (65816): 24-bit addresses, 16-bit regs, 8/16-bit instructions, little-endian.