# Automated Game ROM Recompiler

An automated static/hybrid recompilation framework that ingests video game console ROMs and translates them into standalone native PC applications (`.exe`) with a built-in Hardware Abstraction Layer (HAL).

Unlike traditional emulators that reinterpret or JIT-compile instructions at runtime on every run, an **Automated Recompiler** performs **Ahead-Of-Time (AOT) static translation** of foreign machine code into native C, which is then compiled into a high-performance native executable.

---

## Standalone Executable (`recompiler.exe`)

You can package the entire automated recompilation framework into a standalone binary that does not require Python:

```bash
# Package into dist/recompiler.exe
python package_exe.py

# Run the standalone binary directly:
.\dist\recompiler.exe roms/test/hello_gba.gba
.\dist\recompiler.exe --blocks roms/test/hello_gba.gba
```

---

## Directory Structure

```
automated_recompilers/
├── roms/                       # Place your dumped ROMs here
│   ├── gba/                    # Game Boy Advance ROMs (.gba)
│   ├── n64/                    # Nintendo 64 ROMs (.z64, .n64, .v64)
│   ├── ps1/                    # PlayStation 1 images (.bin/.cue, .iso, .exe)
│   ├── snes/                   # Super Nintendo ROMs (.sfc, .smc)
│   └── test/                   # Homebrew & diagnostic test ROMs
│
├── src/
│   ├── core/                   # ROM detection, block analysis & native compiler driver
│   │   ├── rom_detector.py     # Detects console format, endianness, entry vectors
│   │   ├── block_analyzer.py   # Shannon entropy map & CFG block inspector
│   │   ├── native_compiler.py  # MSVC / Clang / GCC compiler interface
│   │   └── create_test_rom.py  # Test ROM generator (ARM7TDMI Mode 3)
│   ├── lifter/                 # Binary disassemblers and IR code generators
│   │   ├── arm_lifter.py       # ARM7TDMI recursive CFG lifter & C code generator
│   │   ├── mips_lifter.py      # MIPS I / III lifter (N64 / PS1)
│   │   └── cfg.py              # Control Flow Graph & basic block manager
│   └── runtime/                # Hardware Abstraction Layer (Display, Audio, MMIO)
│
├── build/                      # Generated C sources (.c) and compiled binaries (.exe)
├── docs/                       # Architecture diagrams & case studies (N64Recomp, GBARecomp)
├── gui.py                      # Interactive desktop GUI application
├── package_exe.py              # Zero-dependency executable packaging utility
└── recompile.py                # Unified CLI entry point
```

---

## Interactive Graphical User Interface (GUI)

The framework includes a dark-themed desktop GUI for visual ROM selection, metadata inspection, real-time build logging, and instant game launching:

```bash
# Launch via CLI option
python recompile.py --ui

# Or launch directly
python gui.py

# Or launch with the standalone executable
.\dist\recompiler.exe --ui
```

---

## Step-by-Step Guide: How to Work on the Recompiler

### Step 1: Place Your Game ROMs
Copy your dumped ROM files into their respective folders:
* **Game Boy Advance:** Place `.gba` files in `roms/gba/`
* **Nintendo 64:** Place `.z64`, `.v64`, or `.n64` files in `roms/n64/`
* **PlayStation 1:** Place `.bin`, `.iso`, or `.exe` files in `roms/ps1/`

> **Note:** A 100% legal, standalone test ROM (`roms/test/hello_gba.gba`) is included and verified so you can test the pipeline immediately without commercial ROMs.

---

### Step 2: Scan and Identify Detected Games
Run the CLI without arguments to scan the workspace:
```bash
python recompile.py
```
This scans all subfolders in `roms/`, identifies the target console, detects endianness (e.g., Big-Endian `.z64` vs Little-Endian `.n64`), verifies checksums, and calculates entry-point VRAM addresses.

---

### Step 3: Inspect Structural Blocks & Control Flow
Inspect the internal structure of any ROM before recompiling:
```bash
python recompile.py --blocks roms/n64/Yoshi.z64
python recompile.py --blocks roms/test/hello_gba.gba
```
This provides:
1. **ROM Header Analysis:** Title, internal serial code, entry point, CRC.
2. **Shannon Entropy Map:** Identifies code segments vs. compressed assets (textures, audio).
3. **CFG Basic Block Breakdown:** Disassembles initial instructions, branch paths, and delay slots.

---

### Step 4: Recompile a ROM to Native C & Standalone `.exe`
Run the recompiler on a target ROM:
```bash
python recompile.py roms/test/hello_gba.gba
```
The automated pipeline executes four stages:
1. **Identification:** Reads the header and resolves the entry vector (`0x08000000`).
2. **Recursive CFG Lifter:** Disassembles basic blocks, traces loops (`subs`/`bne`), and maps subroutine calls (`bl`/`bx lr`).
3. **C Code Generation:** Emits `build/hello_gba_recompiled.c` containing:
   * CPU context state (`ArmCpuContext` registers & flags).
   * Virtual memory bus (EWRAM, IWRAM, VRAM, MMIO registers).
   * Global dispatch trampoline (`recomp_dispatch`).
   * Win32 presentation window.
4. **Native Compilation:** Automatically invokes your local C compiler (MSVC Visual Studio 2022, Clang, or GCC) to output `build/hello_gba.exe`.

> **Tip:** If you only want to generate the C source without compiling the binary, add `--no-build`:
> ```bash
> python recompile.py --no-build roms/test/hello_gba.gba
> ```

---

### Step 5: Run the Native Recompiled Game

#### A. Headless Mode (Fast Verification)
Runs the recompiled code directly from your terminal:
```bash
.\build\hello_gba.exe
```
**Output:**
```
=== Starting Automated Recompiled Game ===
[GBA HAL] REG_DISPCNT set to 0x0403 (Mode 3)
=== Recompiled execution finished successfully ===
  * REG_DISPCNT  : 0x0403 (Mode 3)
  * Pixels Drawn : 2400 pixels written to VRAM
```

#### B. Desktop Display Window Mode
Launch with the `--window` flag to open a native 720×480 desktop window displaying the pixels rendered by the game:
```bash
.\build\hello_gba.exe --window
```
* Shows the rendered framebuffer scaled 3× using the native Win32 GDI presentation layer.
* Press `ESC` or close the window to exit.

---

## How to Extend the Framework to New Consoles

1. **Add Instruction Lifters:** Add new ISA translators in `src/lifter/` (e.g., expand `mips_lifter.py` for N64/PS1 MIPS instructions).
2. **Connect to CFG Engine:** Use `ControlFlowGraph` in `src/lifter/cfg.py` to recursively trace basic blocks and resolve jump targets.
3. **Map the Console Memory Bus:** Implement console-specific read/write shims for RAM and hardware registers (e.g. N64 RDRAM at `0x80000000`, PS1 2MB RAM at `0x80000000`).
4. **Hardware Runtime (HAL):** Route display list microcodes (Fast3D / GTE) and audio buffers into the presentation runtime.

---

## Architectural References & Case Studies
Detailed analyses of leading open-source static recompilation projects are located in `docs/`:
* `docs/ARCHITECTURE.md`: Framework pipeline specification and design patterns.
* `docs/CASE_STUDIES.md`: Technical breakdowns of [N64Recomp](https://github.com/N64Recomp/N64Recomp), [Zelda64Recomp](https://github.com/Zelda64Recomp/Zelda64Recomp), [GBARecomp](https://github.com/mstan/gbarecomp), [GBA-Recomp](https://github.com/JRickey/gba-recomp), and [PS1Recomp](https://github.com/PS1Recomp/ps1-recomp).
