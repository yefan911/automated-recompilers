# Automated Recompilers — Public Roadmap & Team Task Matrix

This document outlines the development milestones, architecture targets, and task assignments for the **Automated Game ROM Recompiler**.

## Current implementation status — 2026-11-07

The framework provides ROM inspection, static C generation, and prototype runtimes. The baseline audit was merged in **PR #19**. Current local validation passes **200 tests on Windows/Python 3.13**, including generated C execution for instruction semantics, cartridge reads, memory bounds, modding helpers, failure handling, and packed PS1 GTE screen coordinates. CI now covers Python 3.10–3.13 on Ubuntu and Windows. Validation results and the handoff are recorded in [COORDINATION.md](COORDINATION.md).

The [public browser demo](https://yefan911.github.io/automated-recompilers/) loads the bundled GBA homebrew's generated CFG and selectable C blocks. It also provides selected JavaScript instruction examples and the native framebuffer result. Repository topics, demo links, social preview assets, and a focused [launch kit](docs/LAUNCH_KIT.md) support community discovery.

The studio viewport displays ROM data and native GBA framebuffer snapshots. Continuous guest framebuffer streaming into the studio, accurate graphics across all consoles, host audio, and commercial game playability remain open work. Opcode coverage measures recognized instructions; architectural behavior is checked separately by executing generated C.

---

## 👥 Unified Terminal Subagent Architecture & Coworker Task Matrix

The table records team domains for work that can be assigned to in-terminal subagents. Current task ownership is recorded in `COORDINATION.md`.

| Subagent / Coworker | Primary Domain | Active Focus & Roadmap Ownership |
| :--- | :--- | :--- |
| **Subagent 1 (Graphics & HAL)** | **Data Block Reading & Live Windowed Output** | Extracting asset data blocks (tiles, palettes, background maps) from ROMs via `src/core/data_block_reader.py` and blitting decoded framebuffers to the 60 FPS presentation window across GBA, N64, SNES, and PS1. |
| **Subagent 2 (Roadmap & Release)** | **Architecture Roadmap, Claims & Task Matrix** | Maintaining `ROADMAP.md`, `COORDINATION.md`, milestone release planning, task synchronization, and documentation integrity. |
| **Subagent 3 (QA & Bug Hunting)** | **Systematic Bug Hunting & Edge-Case Auditing** | Fuzzing instruction lifters, auditing memory bus boundary shims, identifying unhandled opcodes, fixing pointer/integer overflow hazards, and maintaining 100% CI pass rate. |
| **Coworker cb** | **MIPS Target (N64 & PS1)** | PS1 GTE Coprocessor 2 (`COP2`) 3D geometry engine, N64 RSP/RDP command buffer parsing, SPU audio streaming. |
| **Coworker 6f** | **ARM Target (GBA & Thumb)** | Full GBA Mode 0/1/2/4 PPU tilemap/bitmap renderers, affine background layers, DirectSound DMA audio. |
| **Coworker 54** | **SNES Target (65816 & Web)** | SNES Mode 7 affine matrix renderer, SPC700 audio port interface, WebAssembly client-side lifter playground. |
| **Coworker 69** | **Modding Engine & Asset Pipeline** | Native HD texture replacement hook API, widescreen 16:9/21:9 camera matrix patches, C modding SDK. |
| **Coworker B** | **Data Block Readers & Storage** | Multi-track PS1 `.bin`/`.cue` reader, SNES HiROM/ExHiROM banking, battery-backed SRAM/EEPROM save manager. |

---

## 🎯 Milestone 1: Prototype Recompiler Pipeline & Beta Release (`v0.1.0-beta`) — Delivered

- [x] **ROM Identification & Header Analysis**: GBA (`.gba`), N64 (`.z64`, `.v64`, `.n64`), PS1 (`PS-X EXE` & ISO-9660 CD images), SNES (LoROM / HiROM / ExHiROM with copier headers), NES.
- [x] **Recursive CFG Lifter Engine**: Basic block segmentation, delay slot scheduling (MIPS), spin-loop detection, and worklist deduplication (`collections.deque`).
- [x] **Multi-ISA Instruction Lifters**:
  - **ARM7TDMI**: ALU operations and NZCV flags, conditional execution, branches (`B`/`BL`), byte/halfword/word transfers and address writeback, ARM/Thumb interworking (`BX`).
  - **Thumb-16**: Arithmetic, immediate operations, shifts (LSL, LSR, ASR), conditional branches, stack operations (`PUSH`/`POP`), hardware `REG_KEYINPUT`.
  - **MIPS I / III**: R-type, I-type, delay-slot handling, memory operations, branch instructions (`BEQ`, `BNE`, `BLEZ`, `BGTZ`, `JAL`, `JALR`, `JR`), GTE Coprocessor 2 shims.
  - **W65C816S (SNES)**: Banked cartridge addressing, tracked `REP`/`SEP` widths, binary/decimal arithmetic and flags, transfers, shifts, and guest stack calls. Width changes restored by `PLP` and joins reached with different M/X states still need CFG variants.
- [x] **Memory & RAM Leak Remediation**: Bounded header inspection to 128KB, dropping scan peak memory **2,000× from 301.23 MB to 0.15 MB**. Added console log pruning (max 5,000 lines).
- [x] **Static Jump-Table Recovery Heuristic**: Backward-slicing heuristic in `src/lifter/cfg.py` resolving compiled C `switch` statement tables into known CFG edges across MIPS, ARM, and SNES.
- [x] **PS1 ISO-9660 CD-ROM Boot Extractor**: Sector de-sectoring engine extracting and lifting `PS-X EXE` binaries directly from raw 2352-byte/sector disc images.
- [x] **Windows Runtime Failure Handling**: MSVC SEH guards return failure from headless GBA, MIPS, and SNES dispatch. Headless MIPS faults print diagnostics without a modal dialog.
- [x] **Historical Commercial ROM Build and Boot Smoke Checks** (2026-11-02): Standalone binaries compiled and exercised with a limited dispatch budget:
  - 🕹️ **GBA:** `PGATour.exe` (Initializes display controller `REG_DISPCNT = 0x0080`)
  - 🍄 **N64:** `Yoshi.exe` (Runs MIPS III AOT execution loop cleanly)
  - 🌟 **SNES:** `Super Mario All-Stars.exe` (Runs 65816 LoROM execution cleanly)
  - 🏎️ **PS1:** `Need for Speed - Porsche Unleashed.exe` (Runs MIPS I AOT boot loop cleanly)
- [x] **Desktop Studio GUI & ROM Viewport (`gui.py`)**: Five tabs for ROM metadata, recompilation, C inspection, entropy, ROM data preview, and native GBA framebuffer snapshots. Preview images and readers are reused; worker threads queue updates for the Tk thread.
- [x] **Public Beta Release `v0.1.0-beta`**: Official release published on GitHub with standalone Windows executable and demo walkthroughs.

---

## 🚀 Milestone 2: Interactive Audio/Video HAL, Data Block Reading & Window Rendering (In Progress)

### Track A: Data Block Reading & Live Windowed Output (Subagent 1 & Coworker 58)
- [x] **ROM Data Block Translators (`src/core/data_block_reader.py`)**:
  - Address translation for GBA linear VRAM (`0x08000000`), SNES 24-bit banked LoROM (`0x8000` base), and PS1 2352-byte CD sector offsets.
  - N64 dump normalization and PS1 logical reads across Mode 1/Mode 2 sector payload boundaries; SNES LoROM/HiROM/ExHiROM ROM windows exclude RAM and IO.
- [x] **Native GBA Framebuffer Snapshots**:
  - Generated binaries support `--headless --framebuffer <file.ppm>`; the studio displays the resulting 240×160 image.
- [ ] **Continuous Guest Framebuffer Streaming into the Studio**:
  - Connect a running native guest to the studio viewport and controller input.
- [ ] **Accurate Tilemap & Palette Window Compositing**:
  - Read raw character tile data blocks and 15-bit BGR palette blocks from ROM and VRAM.
  - Composite multi-layer tilemaps and active framebuffers directly into the 32-bit RGB display window buffer.
- [ ] **Cross-Platform C Runtime (`src/runtime/hal.h` & `src/runtime/sdl_hal.c`)**:
  - Unified C HAL interface: `hal_init_window()`, `hal_present_framebuffer()`, `hal_poll_input()`, `hal_sleep_frame()`.
  - Compile-time switch between native Win32 GDI and SDL2 / OpenGL for cross-platform Linux and macOS binaries.
- [ ] **Compilation Caching Engine**:
  - Cache unchanged basic block C functions to accelerate incremental MSVC/Clang rebuilds.

### Track B: N64 Reality Coprocessor & PS1 GTE Engine (Coworker cb)
- [x] **PS1 GTE (Geometry Transformation Engine) Coprocessor 2**:
  - Basic 3D perspective matrix transformations (`RTPT`, `RTPS`, `NCLIP`, `AVSZ3`).
- [ ] **N64 Reality Display Processor (RDP/RSP)**:
  - Command list parser for display list rendering (`G_SETOTHERMODE`, `G_TRI1`, `G_TEXTURE`).
- [ ] **PS1 & N64 Framebuffer Scanning**:
  - Scan VRAM display buffers to produce active 3D textured output in the presentation window.

### Track C: GBA Tilemap PPU & DirectSound Audio (Coworker 6f)
- [x] **Prototype GBA Bitmap and Tile Rendering**:
  - Mode 3 framebuffer conversion is verified by the homebrew snapshot test. Tile and palette rendering paths are present.
- [ ] **Accurate PPU Composition and Affine Layers**:
  - Complete background priorities, transparency, affine addressing, sprites, windows, and palette behavior with visual regressions.
- [ ] **GBA DMA Audio and Host Streaming**:
  - FIFO A register storage is present. FIFO B, DMA scheduling, mixing, and host audio output remain to be connected.

### Track D: SNES Mode 7 & SPC700 Sound APU (Coworker 54)
- [x] **Generated GBA CFG Browser Explorer**:
  - Load exported homebrew CFG JSON, inspect individual generated C blocks, and retain independent console/example selections. Other console tabs contain illustrative examples.
- [ ] **SNES Mode 7 Affine Matrix Rendering**:
  - Mode 7 perspective scaling and rotation matrix calculation for racing and world-map games.
- [x] **Prototype SPC700 Communication Ports**:
  - `$2140..$2143` storage and the initial `$AA/$BB` IPL handshake are implemented.
- [ ] **SPC700 Execution and Host Audio**:
  - Replace the port echo with the APU upload protocol, sound execution, mixing, and audio output.
- [ ] **WebAssembly In-Browser Lifter**:
  - Compile core lifters to WebAssembly for zero-install browser recompilation on GitHub Pages.

---

## 🔮 Milestone 3: Storage, Saves & Multi-Disc Support

### Track E: Save Data & Banking (Coworker B)
- [ ] **Battery-Backed Save State System**:
  - GBA SRAM / Flash (64KB/128KB) / EEPROM save file mapping (`.sav`).
  - N64 Controller Pak & FlashRAM save files.
  - SNES Battery-Backed SRAM (`ctx->ram` persistent disk synchronization).
- [ ] **Multi-Track PS1 Disc Parsing**:
  - Full `.cue` cue-sheet parser reading CDDA audio tracks alongside Mode 2 data tracks.
- [x] **SNES HiROM / ExHiROM ROM Address Translators**:
  - Shared mapping is used by readers, disassembly, and generated cartridge reads, including copier-header removal.
- [ ] **Commercial Cartridge Compatibility**:
  - Validate SRAM, special cartridge chips, ROM mirroring, and titles over 4 MiB.

---

## 💎 Milestone 4: Native Modding, HD Textures & Widescreen (Coworker 69)

### Track F: Modding SDK & Visual Enhancement
- [x] **Texture Catalog and Lookup Helpers**:
  - Dump supplied texture buffers, load validated pack metadata, and generate `recomp_lookup_hd_texture`. C paths are escaped and malformed manifests fail without partially replacing the catalog.
- [x] **Widescreen Geometry Helpers**:
  - Compute aspect ratios, Hor+ FOV multipliers, and projection-matrix scaling for callers in `src/modding/widescreen.py`.
- [x] **C Hook Header and Trampoline Generation**:
  - Generate PRE, POST, and REPLACE hooks with validated symbols and priority ordering. Native tests verify the resulting return value.
- [ ] **Automatic Runtime Mod Integration**:
  - Connect texture decoding/upload, camera hooks, and hook trampolines to generated guest execution. CLI flags currently emit helper headers; game rendering requires these call sites.

---

## 🤝 How to Contribute to the Roadmap

Want to pick up an item or contribute an instruction?
1. Check the [Contributor Bounties Catalog](docs/CONTRIBUTOR_BOUNTIES.md) for self-contained tasks.
2. Propose or contribute an opcode lifter using our [New Instruction Template](.github/ISSUE_TEMPLATE/new_instruction.yml).
3. Open an issue on GitHub using our [Feature Request Template](.github/ISSUE_TEMPLATE/feature_request.yml).
