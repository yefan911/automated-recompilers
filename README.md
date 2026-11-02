# Automated Game ROM Recompiler

[![CI](https://github.com/yefan911/automated-recompilers/actions/workflows/ci.yml/badge.svg)](https://github.com/yefan911/automated-recompilers/actions/workflows/ci.yml)
[![Build Executable](https://github.com/yefan911/automated-recompilers/actions/workflows/build-executable.yml/badge.svg)](https://github.com/yefan911/automated-recompilers/actions/workflows/build-executable.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Platform: Windows & Linux](https://img.shields.io/badge/platform-Windows%20%7C%20Linux-lightgrey.svg)](README.md)

An automated static/hybrid recompilation framework that ingests video game console ROMs and translates them into standalone native PC applications (`.exe` / Linux binary) with a built-in Hardware Abstraction Layer (HAL).

[**Quick Start**](#quick-start-in-60-seconds) • 
[**Showcase & CFG**](docs/SHOWCASE.md) • 
[**Opcode Coverage**](docs/OPCODE_COVERAGE.md) • 
[**Why Static Recompilation?**](#why-static-recompilation) • 
[**Architecture**](#four-stage-recompilation-pipeline) • 
[**Roadmap**](ROADMAP.md) • 
[**Contributing**](CONTRIBUTING.md) • 
[**Launch Kit**](docs/LAUNCH_KIT.md)

---

## Why Static Recompilation?

Traditional emulators execute guest console code at runtime using an interpreter loop or a Just-In-Time (JIT) dynamic compiler. In contrast, **Automated Recompilation** translates foreign machine instructions **Ahead-Of-Time (AOT)** into pure native C functions that are compiled into an executable binary.

| Feature | Interpreter / Traditional Emulator | Dynamic JIT Emulator | Automated Static Recompiler (AOT) |
| :--- | :--- | :--- | :--- |
| **Execution Model** | Runtime fetch-decode loop | Runtime JIT cache compilation | **Ahead-Of-Time (AOT) compilation to C** |
| **CPU Overhead** | High (50×–100× slowdown) | Medium (JIT compile overhead) | **Zero emulation overhead (native binary)** |
| **Micro-Stutter** | Low | High (compilation hitching) | **None (all code compiled at build time)** |
| **Frame Rates** | Locked to original console | Often hardcoded / complex hack | **Naturally unlocked high refresh rates** |
| **Portability** | Requires emulator install | Requires JIT support (`W^X` restrictions) | **Standalone single-file `.exe`** |
| **Modding Potential** | ROM patching / memory hacking | Memory patching | **Native C source modification & hook API** |

---

## Four-Stage Recompilation Pipeline

```
  ┌───────────────────────────────────────────────────────────┐
  │                      Target ROM File                      │
  │            (.gba, .z64, .n64, .v64, .exe, .sfc)           │
  └─────────────────────────────┬─────────────────────────────┘
                                │
                                ▼
  ┌───────────────────────────────────────────────────────────┐
  │  Stage 1: Identification (src/core/rom_detector.py)       │
  │  • Normalizes endianness (Big/Little/Byte-swapped)        │
  │  • Verifies logo & ROM checksums                          │
  │  • Resolves entry vectors & banked layout (LoROM/HiROM)   │
  └─────────────────────────────┬─────────────────────────────┘
                                │
                                ▼
  ┌───────────────────────────────────────────────────────────┐
  │  Stage 2: Recursive CFG Lift (src/lifter/)                │
  │  • Recursively traces basic blocks from entry points      │
  │  • ISA Lifters: ARM7TDMI, Thumb-16, MIPS I/III, 65816     │
  │  • Resolves delay slots & spin loops                      │
  └─────────────────────────────┬─────────────────────────────┘
                                │
                                ▼
  ┌───────────────────────────────────────────────────────────┐
  │  Stage 3: C Code Generation (src/lifter/cfg.py)           │
  │  • Emits clean `bb_XXXXXXXX` C functions                  │
  │  • Virtual register context (ArmCpuContext, MipsContext)  │
  │  • High-performance `recomp_dispatch` trampoline         │
  └─────────────────────────────┬─────────────────────────────┘
                                │
                                ▼
  ┌───────────────────────────────────────────────────────────┐
  │  Stage 4: Native Compile (src/core/native_compiler.py)    │
  │  • Links lightweight Hardware Abstraction Layer (HAL)     │
  │  • Compiles via MSVC, Clang, or GCC (-O2 optimizations)   │
  └─────────────────────────────┬─────────────────────────────┘
                                │
                                ▼
  ┌───────────────────────────────────────────────────────────┐
  │          Standalone Native Binary (.exe / elf)            │
  │       Runs natively on PC with Win32 / GDI window         │
  └───────────────────────────────────────────────────────────┘
```

---

## Demo Walkthrough

![Recompiler Pipeline Terminal Walkthrough](docs/demo/recompiler_terminal_walkthrough.gif)

> 📹 **Interactive HD Video Walkthrough:** [`docs/demo/recompiler_interactive_demo.webm`](docs/demo/recompiler_interactive_demo.webm)  
> 🌐 **Interactive Web Inspector & CFG Visualizer:** Open [`docs/index.html`](docs/index.html) in your browser.

---

## Quick Start in 60 Seconds

A 100% legal, standalone homebrew test ROM (`roms/test/hello_gba.gba`) is included so you can test the pipeline immediately without commercial ROM dumps.

### 1. Recompile the Test ROM
```bash
# Recompiles the ROM to native C and compiles the .exe
python recompile.py roms/test/hello_gba.gba
```

### 2. Run the Native Executable
```bash
# Launch with native Win32 window displaying rendered pixels:
.\build\hello_gba.exe --window
```

---

## Standalone Executable (`recompiler.exe`)

You can package the entire automated recompilation framework into a standalone binary that does not require Python or external dependencies:

```bash
# Package into dist/recompiler.exe
python package_exe.py

# Run directly:
.\dist\recompiler.exe roms/test/hello_gba.gba
.\dist\recompiler.exe --blocks roms/test/hello_gba.gba
```

---

## Interactive Graphical User Interface (GUI)

The framework includes a dark-themed desktop GUI for visual ROM selection, metadata inspection, Shannon entropy analysis, and one-click recompilation:

```bash
# Launch via CLI option
python recompile.py --ui

# Or launch directly
python gui.py

# Or launch with the standalone executable
.\dist\recompiler.exe --ui
```

---

## Directory Structure

```
automated_recompilers/
├── roms/                       # Dumped ROM workspace
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
│   │   ├── data_block_reader.py# Banking & data block reader interface
│   │   ├── native_compiler.py  # MSVC / Clang / GCC compiler interface
│   │   └── create_test_rom.py  # Test ROM generator (ARM7TDMI Mode 3)
│   ├── lifter/                 # Binary disassemblers and IR code generators
│   │   ├── arm_lifter.py       # ARM7TDMI recursive CFG lifter & C code generator
│   │   ├── thumb_lifter.py     # Thumb-16 lifter with ARM interworking (BX)
│   │   ├── mips_lifter.py      # MIPS I / III lifter (N64 / PS1)
│   │   ├── snes_lifter.py      # W65C816S lifter (SNES 24-bit banked ISA)
│   │   └── cfg.py              # Control Flow Graph & basic block manager
│   └── runtime/                # Hardware Abstraction Layer (Display, Audio, MMIO)
│
├── build/                      # Generated C sources (.c) and compiled binaries (.exe)
├── docs/                       # Architecture diagrams, case studies & launch kit
│   ├── ARCHITECTURE.md         # Framework technical design specification
│   ├── CASE_STUDIES.md         # Breakdowns of N64Recomp, GBARecomp, PS1Recomp
│   └── LAUNCH_KIT.md           # Community announcements, blog posts & social threads
├── gui.py                      # Interactive desktop GUI application
├── package_exe.py              # Zero-dependency executable packaging utility
├── recompile.py                # Unified CLI entry point
├── ROADMAP.md                  # Development milestones and planned features
└── CONTRIBUTING.md             # Developer setup and guide to adding instructions
```

---

## Supported Consoles & Instruction Lifters

| Console | CPU Architecture | Lifter Status | Notes |
| :--- | :--- | :--- | :--- |
| **Game Boy Advance** | ARM7TDMI (ARMv4T) + Thumb-16 | Complete (Core) | Full ALU, memory transfers, interworking (`BX`), Mode 3 video HAL |
| **Nintendo 64** | MIPS III (VR4300) | In Progress | Delay slot handling, conditional branches, CFG tracing |
| **PlayStation 1** | MIPS I (R3000A) | In Progress | MIPS I lifting, PS-X EXE detection |
| **Super Nintendo** | W65C816S | In Progress | 24-bit banked LoROM addressing, `REP`/`SEP` register sizing |

---

## Step-by-Step Guide: How to Recompile a Game

### Step 1: Scan and Inspect ROMs
Run the CLI without arguments to scan the workspace and identify console headers:
```bash
python recompile.py
```

Inspect the internal structure and Shannon entropy map of any ROM before recompiling:
```bash
python recompile.py --blocks roms/n64/testfile.z64
python recompile.py --blocks roms/test/hello_gba.gba
```
This generates:
1. **ROM Header Analysis:** Title, internal serial code, entry point, CRC.
2. **Shannon Entropy Map:** Visual graph identifying executable code vs. compressed audio/texture blocks.
3. **CFG Basic Block Breakdown:** Disassembles initial instructions, branch paths, and delay slots.

### Step 2: Recompile to Native C & Binary
```bash
python recompile.py roms/test/hello_gba.gba
```
*(Optional: add `--no-build` to generate `build/hello_gba_recompiled.c` without calling the native compiler)*

### Step 3: Run the Native Game
```bash
# Fast verification in terminal:
.\build\hello_gba.exe

# Open native 720×480 desktop presentation window:
.\build\hello_gba.exe --window
```

---

## Testing & Continuous Integration

Every commit is verified across Python 3.10 through 3.13 on Ubuntu and Windows. The CI pipeline compiles the generated C source with `-Wall -Wextra -Werror -O2` and runs it end-to-end.

To run the test suite locally:
```bash
pytest -v
```

---

## License

This project is licensed under the [MIT License](LICENSE).
