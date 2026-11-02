# Automated Game ROM Recompiler — Release `v0.1.0-beta` (2026-11-02)

Welcome to the official release of the **Automated Game ROM Recompiler**! This release marks our Ahead-Of-Time (AOT) static binary translation framework supporting **Game Boy Advance, Nintendo 64, PlayStation 1, and Super Nintendo** ROMs into standalone native PC executables.

---

## 📦 Pre-Built Standalone Binaries (No Python Required)
Download the zero-dependency native executable for your operating system:

- 🪟 **Windows x64:** [`recompiler-windows-x64.exe`](https://github.com/yefan911/automated-recompilers/releases/download/v0.1.0-beta/recompiler-windows-x64.exe)
- 🐧 **Linux x64:** [`recompiler-linux-x64`](https://github.com/yefan911/automated-recompilers/releases/download/v0.1.0-beta/recompiler-linux-x64)

```bash
# Quick CLI test on bundled legal homebrew ROM:
.\recompiler-windows-x64.exe roms/test/hello_gba.gba

# Launch with interactive Desktop GUI:
.\recompiler-windows-x64.exe --ui
```

---

## 🚀 Key Feature Highlights in This Release

### 1. Multi-Console Recursive CFG Lifters
- **ARM7TDMI & Thumb-16 (GBA):** Full ALU operations, conditional execution, barrel shifters, and `BX` ARM/Thumb interworking state transitions.
- **MIPS I / III (N64 / PS1):** Branch delay-slot scheduling, R-type/I-type arithmetic, load-delay emulation, and jump target resolution.
- **W65C816S (SNES):** LoROM 24-bit banked address mapping, dynamic accumulator/index register sizing (`REP`/`SEP`), transfers, bitwise, shifts, and long jumps (`JML`/`JSL`/`RTL`).

### 2. Zero-Stutter AOT Compilation Pipeline
- Translates foreign machine code directly into clean, standalone **C99 source code** (`build/*_recompiled.c`).
- Static register contexts (`ArmCpuContext`, `MipsCpuContext`, `SnesCpuContext`) eliminate JIT compilation overhead, micro-stutters, and interpreter loops.
- Automatic compiler dispatch using **MSVC Visual Studio**, **Clang**, or **GCC** to produce native desktop binaries.

### 3. Memory & RAM Optimizations (2,000× Improvement)
- Bounded ROM header reads to 128KB in `inspect_file()`, dropping peak directory scanning memory from **301.23 MB down to 0.15 MB**.
- Migrated CFG worklist queues to `collections.deque` with visited-block tracking to prevent duplicate block traversal and memory exhaustion on commercial ROMs.
- Added real-time GUI console log pruning (max 5,000 lines) with thread-safe UI scheduling.

### 4. Developer & Showcase Tooling
- **Visual CFG Showcase:** [SHOWCASE.md](docs/SHOWCASE.md) and interactive [showcase.html](docs/showcase.html) featuring native Mermaid.js flowcharts and Shannon entropy heatmaps.
- **Micro-Benchmark Suite:** [BENCHMARKS.md](docs/BENCHMARKS.md) measuring instruction lifter throughput and latency.
- **Gamified Contributor Bounties:** [CONTRIBUTOR_BOUNTIES.md](docs/CONTRIBUTOR_BOUNTIES.md) cataloging good-first-issue opcodes with automated quest templates.
- **Awesome List:** [AWESOME_RECOMPILATION.md](docs/AWESOME_RECOMPILATION.md) curating leading open-source static recompilation projects.

---

## 📊 Opcode Coverage (79.7% (192/241 core opcodes implemented))

| Architecture | Target Console | Implemented / Total | Coverage % |
| :--- | :--- | :---: | :---: |
| **ARM7TDMI (ARMv4T)** | Game Boy Advance (ARM) | 30 / 43 | **69.8%** |
| **ARM Thumb-16** | Game Boy Advance (Thumb) | 42 / 47 | **89.4%** |
| **MIPS I / III** | Nintendo 64 & PlayStation 1 | 38 / 60 | **63.3%** |
| **W65C816S** | Super Nintendo Entertainment System (SNES) | 82 / 91 | **90.1%** |

---

## ⚡ Lifter Performance Benchmarks

| Architecture | Throughput | Mean Latency | Instruction Set |
| :--- | :---: | :---: | :--- |
| **GBA (ARM7TDMI)** | ~6.5M ops/sec | 0.15 µs | 32-bit RISC + Barrel Shifter |
| **N64 (MIPS III)** | ~4.8M ops/sec | 0.21 µs | 64-bit RISC + Branch Delay Slots |
| **PS1 (MIPS I)** | ~5.2M ops/sec | 0.19 µs | 32-bit RISC + Virtual Bus |
| **SNES (W65C816S)** | ~9.1M ops/sec | 0.11 µs | 16-bit CISC + 24-bit Banked VRAM |

---

## 🤝 Get Involved
- **Report Bugs:** [Open an Issue](https://github.com/yefan911/automated-recompilers/issues/new?template=bug_report.yml)
- **Claim an Opcode Bounty:** [Contributor Bounties Catalog](docs/CONTRIBUTOR_BOUNTIES.md)
- **Read the Contributing Guide:** [CONTRIBUTING.md](CONTRIBUTING.md)

**Full Changelog**: https://github.com/yefan911/automated-recompilers/commits/v0.1.0-beta