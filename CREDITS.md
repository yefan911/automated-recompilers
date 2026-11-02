# Third-Party Credits & Acknowledgments

The Automated Game ROM Recompiler framework draws inspiration, reverse-engineering architectural patterns, and hardware specification research from the broader open-source emulation, decompilation, and static recompilation communities.

We gratefully acknowledge and credit the following pioneering projects, authors, and communities:

---

## 1. Nintendo 64 (N64) Recompilation

### **[N64Recomp](https://github.com/N64Recomp/N64Recomp)** & **[Zelda64Recomp](https://github.com/Zelda64Recomp/Zelda64Recomp)**
* **Authors:** Mr-Wiseguy, Zelda64Recomp Team
* **License:** **MIT License**
* **Inspirations & Technical Architectural Patterns:**
  * Recursive basic-block control flow graph (CFG) extraction from MIPS machine binaries.
  * Static jump-table recovery heuristics via MIPS backward-slicing (`SLTIU`, `LUI`, `ADDIU`, `LW`, `JR`).
  * MIPS branch delay slot normalization when lowering to native C.
  * Modern runtime abstractions (`N64ModernRuntime`) for memory protection, audio ring buffers, and graphics HAL.

---

## 2. Game Boy Advance (GBA) & ARM7TDMI Recompilation

### **[JRickey/gba-recomp](https://github.com/JRickey/gba-recomp)**
* **Author:** JRickey
* **License:** **Apache License 2.0**
* **Inspirations & Technical Architectural Patterns:**
  * Clean-room ARM7TDMI and Thumb-16 execution models and instruction decomposition.
  * GBA hardware register MMIO mapping (`REG_DISPCNT`, `REG_VCOUNT`, `REG_KEYINPUT`, `REG_IME`, `REG_IE`, `REG_IF`).
  * Scanline-based timing loop (1,232 cycles per scanline, 228 scanlines per frame, V-Blank / H-Blank interrupts).
  * High-Level Emulation (HLE) BIOS SWI routines (`Div`, `Sqrt`, `CpuSet`, `CpuFastSet`, `ArcTan2`, `BitUnPack`).

### **[arcanite24/gb-recompiled](https://github.com/arcanite24/gb-recompiled)**
* **Author:** arcanite24
* **License:** **MIT License**
* **Inspirations & Technical Architectural Patterns:**
  * Portable C99 code generation for standalone compilation across GCC, Clang, and MSVC.
  * Separation of concerns between CPU translation, memory bus abstraction, and runtime presentation.

### **[mstan/gbarecomp](https://github.com/mstan/gbarecomp)**
* **Author:** mstan, R.A.I.D. community
* **Inspirations:**
  * ARM/Thumb interworking state transitions on bit 0 of PC (`BX` / `BLX`).

---

## 3. Super Nintendo (SNES) & W65C816S Recompilation

### **[sp00nznet/snesrecomp](https://github.com/sp00nznet/snesrecomp)**
* **Author:** sp00nznet
* **License:** **MIT License**
* **Inspirations & Technical Architectural Patterns:**
  * 65816 dynamic register width tracking (`M` flag for Accumulator 8/16-bit, `X` flag for Index registers 8/16-bit).
  * Static basic-block path splitting on `REP` (reset status bits) and `SEP` (set status bits).
  * WRAM memory mirroring across Banks `$00-$3F` and `$80-$BF` for Direct Page (`$0000-$00FF`) and Stack (`$0100-$01FF`).

### **[AndreaOrru/gilgamesh](https://github.com/AndreaOrru/gilgamesh)**
* **Author:** Andrea Orru
* **License:** **BSD 2-Clause ("Simplified") License**
* **Inspirations & Technical Architectural Patterns:**
  * SNES reverse-engineering and disassembly analysis.
  * Static jump table scanning for `JMP ($xxxx,X)` (opcode `0x7C`).

### **[Junior-Jones Static Recomp Suite](https://github.com/Junior-Jones)**
*(SimCity, Civilization, Jungle Strike, Top Gear, Rock N' Roll Racing SNES Static Recomps)*
* **Author:** Junior-Jones
* **License:** **zlib License**
* **Inspirations & Technical Architectural Patterns:**
  * Standalone native Windows executable packaging.
  * Joypad 1 auto-read emulation via registers `$4218` and `$4219`.
  * Windowed desktop presentation and aspect-ratio-correct scaling.

---

## 4. PlayStation 1 (PS1) & MIPS-I Recompilation

### **[RetroPortingToolKit/psxrecomp](https://github.com/RetroPortingToolKit/psxrecomp)**
* **Author:** mstan, RetroPortingToolKit / R.A.I.D. community
* **License:** **PolyForm Noncommercial 1.0.0** (OpenBIOS clean-room runtime under **MIT License**)
* **Inspirations & Technical Architectural Patterns:**
  * ISO-9660 `SYSTEM.CNF` boot parsing to identify entry executables (`BOOT = cdrom:\SLUS_XXX.XX;1`).
  * OpenBIOS clean-room BIOS syscall dispatch table (`A`, `B`, `C` vector routines).
  * Note: Per the PolyForm Noncommercial terms, all recompiler code in this repository is clean-room authored under our permissive MIT license, referencing public hardware specifications and the MIT-licensed OpenBIOS syscall architecture.

### **[PS1Recomp/ps1-recomp](https://github.com/PS1Recomp/ps1-recomp)**
* **Authors:** PS1Recomp Team
* **License:** **GPLv3**
* **Inspirations & Technical Architectural Patterns:**
  * Clean-room hardware specification reference for MIPS-I R3000A GTE (Geometry Transformation Engine) and DMA channels.

---

## 5. Modern Architecture & Decoupled Frame Timing

### **[TGP482/XboxXBE-Recomp](https://github.com/TGP482/XboxXBE-Recomp)** & **[gothamor/gta-vcs-recomp](https://github.com/gothamor/gta-vcs-recomp)**
* **Authors:** TGP482, gothamor
* **Inspirations & Technical Architectural Patterns:**
  * Decoupling fixed console game logic ticks from high-refresh presentation loops (60/120/240 FPS).
  * Windows Structured Exception Handling (SEH) crash guards (`__try / __except`) preventing abrupt process termination.

---

## 6. Communities

* **[r/recomps](https://www.reddit.com/r/recomps/)** & **[r/decomps](https://www.reddit.com/r/decomps/)**: The reddit communities for sharing progress, discussing static recompilation architectures, and coordinating native porting initiatives.
* **[recomp.fyi](https://recomp.fyi)**: Community dashboard tracking active decompilation, static recompilation, and native port projects.
