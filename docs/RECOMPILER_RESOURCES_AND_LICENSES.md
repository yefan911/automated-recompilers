# Community Recompilers, Licensing Analysis & Technical Reference

This document catalogs open-source recompilation projects investigated from **r/recomps**, **r/decomps**, and GitHub, analyzes their software licenses for compatibility with our **MIT License**, and documents actionable architectural patterns for our development team.

---

## 1. Project Directory & License Compatibility Matrix

| Project / Repository | Target Architecture | License | Compatibility with our MIT License | Key Architectural Innovations |
| :--- | :--- | :--- | :--- | :--- |
| **[N64Recomp/N64Recomp](https://github.com/N64Recomp/N64Recomp)** | Nintendo 64 (MIPS III) | **MIT** | **100% Compatible** (Direct use, reuse, adaptation) | Two-pass recursive CFG, delay-slot normalization, jump-table backward slicing, symbol extraction |
| **[Zelda64Recomp](https://github.com/Zelda64Recomp/Zelda64Recomp)** | N64 (OOT / MM) | **MIT** | **100% Compatible** | Native RT64 graphics backend, high-refresh timing interpolation, modern audio ring buffer |
| **[JRickey/gba-recomp](https://github.com/JRickey/gba-recomp)** | GBA (ARM7TDMI / Thumb-16) | **Apache 2.0** | **Compatible** (Requires attribution and license notice) | 1232-cycle scanline timing loop, active-low KEYINPUT polling, GBA BIOS SWI routines (Div, Sqrt, CpuSet, ArcTan2) |
| **[sp00nznet/snesrecomp](https://github.com/sp00nznet/snesrecomp)** | SNES (W65C816S) | **MIT** | **100% Compatible** | 65816 dynamic M/X flag tracking, basic block path-splitting on REP/SEP, WRAM mirroring ($00-$3F, $80-$BF) |
| **[AndreaOrru/gilgamesh](https://github.com/AndreaOrru/gilgamesh)** | SNES (65816) | **BSD 2-Clause** | **Compatible** (Requires copyright notice) | SNES static jump table recovery for `JMP ($xxxx,X)` (opcode 0x7C), banked disassembly |
| **[Junior-Jones SNES Recomps](https://github.com/Junior-Jones)** | SNES (65816) | **zlib** | **100% Compatible** | Standalone native Windows executable generation, Joypad 1 auto-read ($4218/$4219), 3x window scaling |
| **[arcanite24/gb-recompiled](https://github.com/arcanite24/gb-recompiled)** | Game Boy (LR35902) | **MIT** | **100% Compatible** | Clean separation of CPU translation, memory bus abstraction, portable C99 generation |
| **[RetroPortingToolKit/psxrecomp](https://github.com/RetroPortingToolKit/psxrecomp)** | PS1 (MIPS I) | **PolyForm Noncommercial 1.0.0** (OpenBIOS: **MIT**) | **Clean-Room Only** (Do not copy code; OpenBIOS MIT syscalls ok) | ISO-9660 `SYSTEM.CNF` boot executable locator, OpenBIOS A/B/C vector syscall table |
| **[TheLostPantheon/nativ](https://github.com/TheLostPantheon/nativ)** | PS Vita (ARM Cortex-A9) | **GPL-2.0** | **Clean-Room Only** (GPL cannot be copied into MIT) | User-firmware isolation ("bring-your-own-firmware"), dynamic module relocation |
| **[PS1Recomp/ps1-recomp](https://github.com/PS1Recomp/ps1-recomp)** | PS1 (MIPS I) | **GPLv3** | **Clean-Room Only** (GPL cannot be copied into MIT) | MIPS-I R3000A GTE coprocessor decomposition |
| **[TGP482/XboxXBE-Recomp](https://github.com/TGP482/XboxXBE-Recomp)** | Original Xbox (x86) | **MIT** / Open | **Compatible** | PE/XBE static translation, decoupled logic ticks and presentation refresh rate |

---

## 2. Licensing Guidance for Coworkers

1. **Permissive Licenses (MIT, BSD, zlib, Apache 2.0):**
   * Code, data structures, register definitions, and algorithms from MIT, BSD, zlib, and Apache 2.0 repositories can be directly referenced, adapted, and integrated into our codebase.
   * Required: Retain attribution in `CREDITS.md` and appropriate header comments.
2. **Copyleft & Noncommercial Licenses (GPL-2.0, GPL-3.0, PolyForm Noncommercial):**
   * **Do NOT copy source code directly** from GPL or PolyForm repositories into our MIT-licensed files. Doing so would violate the upstream terms or force relicensing of our repository.
   * **Clean-Room Reference:** You CAN read the hardware specifications, register maps, syscall table numbers, and high-level architectural ideas (e.g., how ISO-9660 `SYSTEM.CNF` specifies `BOOT = cdrom:\...`, or how PS1 BIOS vectors A/B/C map syscall numbers). Then implement our own clean-room code from scratch.

---

## 3. Actionable Code Patterns for Coworkers

### For Coworker 6f (`src/lifter/arm_lifter.py` & GBA Loop):
* **Scanline Timing Loop (inspired by `JRickey/gba-recomp`):**
  * GBA clock is 16.78 MHz.
  * 1 scanline = 1,232 cycles (960 visible + 272 HBlank).
  * 1 frame = 228 scanlines (160 visible + 68 VBlank) = 280,896 cycles per frame (~59.73 Hz).
  * In the continuous loop, step `ctx->vcount` from 0 to 227:
    - When `ctx->vcount == 160`, trigger V-Blank bit in `REG_DISPSTAT` and optional IRQ.
    - When `ctx->vcount == 0`, clear V-Blank bit.
* **Expanded GBA BIOS SWIs:**
  - `SWI 0x0A` (`ArcTan2`): Returns `atan2(y, x)` in 16-bit angle format (0x0000..0xFFFF = 0..360°).
  - `SWI 0x10` (`BitUnPack`): Unpacks source bitstream of width $S$ into output stream of width $D$.

### For Coworker 54 (`src/lifter/snes_lifter.py` & SNES Loop):
* **65816 M and X Flag State Machine (inspired by `sp00nznet/snesrecomp`):**
  * SNES 65816 has dynamic operand sizes: `REP #imm` clears flags; `SEP #imm` sets flags.
    - Bit 5 ($0x20) = `M` flag (0 = 16-bit Accumulator, 1 = 8-bit Accumulator).
    - Bit 4 ($0x10) = `X` flag (0 = 16-bit Index X/Y, 1 = 8-bit Index X/Y).
  * Keep `m_flag` and `x_flag` tracked during CFG lifting. If a target is reached with a differing flag combination, branch or split the basic block.
* **Joypad 1 Auto-Read (inspired by `Junior-Jones` & `sp00nznet`):**
  * Emulate `$4218` (Joypad 1 Low: B, Y, Select, Start, Up, Down, Left, Right) and `$4219` (Joypad 1 High: A, X, L, R).
  * Automatically update these registers during VBlank based on host keyboard input.

### For Coworker cb (`src/lifter/mips_lifter.py` & MIPS Loop):
* **Branch Delay Slot Handling (inspired by `N64Recomp`):**
  * Delay-slot instruction must execute *before* the PC jumps to the branch target.
  * Use a buffered `ctx->next_pc` or inline the delay slot instruction before the branch transfer.
* **MIPS Jump-Table Slicing:**
  * Detect compiler switch jump tables via backward search from `JR $reg` to find the bound check (`SLTIU`), base address (`LUI` + `ADDIU`), and array index offset (`SLL reg, 2`).

### For Coworker 58 (`gui.py` & HAL):
* **Decoupled Presentation Timing (inspired by `gta-vcs-recomp` & `TGP482`):**
  * Run game cycle execution slices (~100,000 cycles per tick) while decoupling the Windows GDI/OpenGL/SDL presentation window to 60 FPS smoothly.
  * Windows SEH (`__try / __except` / `SetUnhandledExceptionFilter`) prevents unhandled crashes on invalid ROM addresses.
