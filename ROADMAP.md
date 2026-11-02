# Automated Recompilers — Public Roadmap

This document outlines the development milestones, architecture targets, and feature roadmap for the **Automated Game ROM Recompiler**.

---

## 🎯 Current Status (v0.1.0 — Milestone 1)

- [x] **ROM Identification & Header Parsing**: GBA (.gba), N64 (.z64, .v64, .n64), PS1 (PS-X EXE), SNES (LoROM / HiROM), NES.
- [x] **Recursive CFG Lifter Engine**: Basic block segmentation, branch target resolution, delay slot scheduling (MIPS), spin-loop detection.
- [x] **Multi-ISA Instruction Lifters**:
  - **ARM7TDMI**: ALU ops, conditional execution, branches (`B`/`BL`), memory transfers (`LDR`/`STR`), ARM/Thumb interworking (`BX`).
  - **Thumb-16**: Arithmetic, immediate operations, conditional branches, stack operations (`PUSH`/`POP`).
  - **MIPS I / III**: R-type, I-type, delay-slot handling, memory operations, conditional branches (`BEQ`, `BNE`, `BLEZ`, `BGTZ`).
  - **W65C816S (SNES)**: Banked 24-bit addressing, accumulator/index sizing (`REP`/`SEP`), arithmetic, direct page access.
- [x] **C Code Generation & Emitted Runtime**: Register contexts (`ArmCpuContext`, `MipsCpuContext`, `SnesCpuContext`), `recomp_dispatch` trampoline, virtual memory bus shims.
- [x] **Desktop GUI & CLI**: Dark-mode GUI (`gui.py`), Shannon entropy visualization, block inspection, zero-dependency executable packaging (`package_exe.py`).
- [x] **Reference Verification**: 100% legal homebrew GBA ROM (`roms/test/hello_gba.gba`) compiling and running native Win32 GDI graphics out-of-the-box.

---

## 🚀 Milestone 2: Commercial ROM Scale & Dynamic Control Flow

- [ ] **Dynamic Jump Tables & Indirect Branches**:
  - Implement heuristic jump table detection for compiled C switch statements (`switch-case` recovery).
  - Fallback dynamic recompilation / interpreter trampoline for unresolved indirect register jumps (`jr $ra`, `bx rm`).
- [ ] **Address-Translator Integration**:
  - Banked LoROM / HiROM memory translation for SNES (via `data_block_reader`).
  - PS1 ISO-9660 filesystem parsing to extract and recompile `SYSTEM.CNF` boot executables.
- [ ] **Expanded Instruction Coverage**:
  - Extended ARM barrel shifter modes (ROR, RRX, ASR).
  - MIPS coprocessor instructions (COP0 exception registers, COP1 floating point, COP2 GTE for PS1).
  - SNES 65816 stack-relative and indirect indexed addressing modes.

---

## 🖥️ Milestone 3: Cross-Platform Hardware Abstraction Layer (HAL)

- [ ] **SDL2 / Modern Graphics Backend**:
  - Port Win32 GDI presentation window to SDL2 + OpenGL/Vulkan for cross-platform Linux and macOS support.
  - Native 60/120 FPS high-refresh rate support and aspect-ratio scaling (integer scaling, ultrawide).
- [ ] **Audio Streaming Backend**:
  - DMA audio buffer streaming (GBA Sound Channels, N64 AI, PS1 SPU).
- [ ] **Controller & Input Mapping**:
  - Plug-and-play XInput, DirectInput, and SDL2 game controller mapping.

---

## 🔮 Milestone 4: Native Modding & Asset Replacement

- [ ] **Asset Extraction & Replacement Hooks**:
  - Texture replacement pipeline (dumping internal VRAM textures to PNG, loading HD textures at runtime).
  - Widescreen camera patches and geometry hooks.
- [ ] **C API for Community Mods**:
  - Expose internal memory structures and function hooks for native C/C++ plugins without ROM patching.

---

## 🤝 How to Influence the Roadmap

Have a feature or console you want to see?
1. Open an issue on GitHub using our [Feature Request Template](.github/ISSUE_TEMPLATE/feature_request.yml).
2. Propose or contribute an opcode lifter using our [New Instruction Template](.github/ISSUE_TEMPLATE/new_instruction.yml).
3. Join discussions on architectural design in our GitHub Discussions or Discord.
