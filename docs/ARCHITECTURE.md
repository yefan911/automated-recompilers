# Automated Recompiler: System Architecture & Workflow

## Overview
This project is an automated framework to convert legacy console ROMs into standalone native PC executables. Unlike traditional emulators that reinterpret or JIT-compile instructions at runtime on every run, an **Automated Recompiler** performs **Ahead-Of-Time (AOT) static translation** of foreign machine code into native code, bundled with a lightweight Hardware Abstraction Layer (HAL).

---

## The 4-Stage Recompilation Pipeline

```
[ ROM Input ] (GBA, N64, PS1, SNES)
      │
      ▼
┌─────────────────────────────────────────────────────────────┐
│ 1. Core Ingestion & Analysis                                │
│    - Byte-swap normalization (.z64 / .n64 / .v64)           │
│    - Format & header detection (Title, Game Code, CRC)       │
│    - Memory map resolution (VRAM entry point, ROM offset)   │
└─────────────────────────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. Binary Lifting & Control Flow Graph (CFG) Construction   │
│    - Recursive descent disassembly from entry points        │
│    - Basic block segmentation (splitting at branches/jumps) │
│    - Translation of foreign ISA (ARM7TDMI / MIPS) to IR     │
│    - Constant pool extraction & switch table detection       │
└─────────────────────────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. Code Generation (C / Rust / LLVM)                        │
│    - Mapping foreign registers to local C/native variables   │
│    - Emitting basic block functions (`bb_<vram_address>`)   │
│    - Dispatch table for indirect branches (`jr`, `bx`)      │
│    - Trampoline fallback to interpreter for cold/unmapped   │
└─────────────────────────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. Hardware Abstraction Layer (HAL / Runtime)               │
│    - Virtual Memory Bus (Direct pointer paging / MMIO shims)│
│    - Display / GPU (SDL3 / Vulkan / RT64 HLE)               │
│    - Audio (SDL_Audio / miniaudio ring-buffers)             │
│    - Host input mapping & cycle scheduler                   │
└─────────────────────────────────────────────────────────────┘
      │
      ▼
[ Standalone Native Executable ] (.exe)
```

---

## Handling ROM Dumps

### How to place your dumped ROMs
Place your dumped ROM files into their respective folders:
* `roms/gba/`: Game Boy Advance `.gba` ROMs
* `roms/n64/`: Nintendo 64 `.z64`, `.n64`, `.v64` ROMs
* `roms/ps1/`: PlayStation 1 `.bin`, `.iso`, or `.exe` files
* `roms/snes/`: Super Nintendo `.sfc`, `.smc` ROMs
* `roms/test/`: Homebrew & diagnostic test ROMs

### How ROMs are dumped from real hardware:
* **GBA / GB:** Hardware dumpers like the **GBxCart RW** or an R4 flashcart with **NDS GBA Backup Tool**.
* **N64 / SNES:** Hardware tools like the **Open Source Cartridge Reader (OSCR)** or **Retrode 2**.
* **PS1:** Any standard PC DVD/CD drive using tools like **Redumper**, **DuckStation Disc Dumper**, or **ImgBurn** (BIN+CUE format).
