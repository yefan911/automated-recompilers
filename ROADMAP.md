# Automated Recompilers — Public Roadmap & Team Task Matrix

This document outlines the development milestones, architecture targets, and task assignments for the **Automated Game ROM Recompiler**.

---

## 👥 Coworker Task Matrix & Active Ownership (Multi-Agent Swarm)

To accelerate progress across multiple consoles simultaneously, work is distributed across specialized domains:

| Coworker Session | Primary Domain | Active Focus & Roadmap Ownership |
| :--- | :--- | :--- |
| **Coworker 58 (Me)** | **Core Engine, GUI & HAL Architecture** | Cross-platform SDL2 presentation HAL (`src/runtime/sdl_hal.c`), compilation caching, GUI Live Viewport enhancements. |
| **Coworker cb** | **MIPS Target (N64 & PS1)** | PS1 GTE Coprocessor 2 (`COP2`) geometry engine, N64 RSP/RDP command buffer parsing, SPU audio streaming. |
| **Coworker 6f** | **ARM Target (GBA & Thumb)** | Full GBA Mode 0/1/2/4 PPU tilemap/bitmap renderers, affine background layers, DirectSound DMA audio. |
| **Coworker 54** | **SNES Target (65816 & Web)** | SNES Mode 7 affine matrix renderer, SPC700 audio port interface, WebAssembly client-side lifter playground. |
| **Coworker 69** | **Modding Engine & Asset Pipeline** | Native HD texture replacement hook API, widescreen 16:9/21:9 camera matrix patches, C modding SDK. |
| **Coworker B** | **Data Block Readers & Storage** | Multi-track PS1 `.bin`/`.cue` reader, SNES HiROM/ExHiROM banking, battery-backed SRAM/EEPROM save manager. |

---

## 🎯 Milestone 1: Core Recompiler Pipeline & Beta Release (`v0.1.0-beta`) — COMPLETED ✅

- [x] **Universal ROM Identification & Header Analysis**: GBA (`.gba`), N64 (`.z64`, `.v64`, `.n64`), PS1 (`PS-X EXE` & ISO-9660 CD images), SNES (LoROM / HiROM), NES.
- [x] **Recursive CFG Lifter Engine**: Basic block segmentation, delay slot scheduling (MIPS), spin-loop detection, and worklist deduplication (`collections.deque`).
- [x] **Multi-ISA Instruction Lifters**:
  - **ARM7TDMI**: Full ALU ops, conditional execution, branches (`B`/`BL`), memory transfers (`LDR`/`STR`), ARM/Thumb interworking (`BX`).
  - **Thumb-16**: Arithmetic, immediate operations, shifts (LSL, LSR, ASR), conditional branches, stack operations (`PUSH`/`POP`), hardware `REG_KEYINPUT`.
  - **MIPS I / III**: R-type, I-type, delay-slot handling, memory operations, branch instructions (`BEQ`, `BNE`, `BLEZ`, `BGTZ`, `JAL`, `JALR`, `JR`).
  - **W65C816S (SNES)**: Banked 24-bit addressing, dynamic accumulator/index register sizing (`REP`/`SEP`), transfers, bitwise, shifts, and stack/direct page operations.
- [x] **Memory & RAM Leak Remediation**: Bounded header inspection to 128KB, dropping scan peak memory **2,000× from 301.23 MB to 0.15 MB**. Added console log pruning (max 5,000 lines).
- [x] **Static Jump-Table Recovery Heuristic**: Backward-slicing heuristic in `src/lifter/cfg.py` resolving compiled C `switch` statement tables into known CFG edges across MIPS, ARM, and SNES.
- [x] **PS1 ISO-9660 CD-ROM Boot Extractor**: Sector de-sectoring engine extracting and lifting `PS-X EXE` binaries directly from raw 2352-byte/sector disc images.
- [x] **Universal Hardware Crash Guards**: Windows SEH (`__try / __except`), `SetUnhandledExceptionFilter`, and memory bounds protection preventing crashes across all consoles.
- [x] **4-Console Commercial ROM Verification**: Standalone `.exe` binaries compiled and verified running on PC:
  - 🕹️ **GBA:** `PGATour.exe` (Initializes display controller `REG_DISPCNT = 0x0080`)
  - 🍄 **N64:** `Yoshi.exe` (Runs MIPS III AOT execution loop cleanly)
  - 🌟 **SNES:** `Super Mario All-Stars.exe` (Runs 65816 LoROM execution cleanly)
  - 🏎️ **PS1:** `Need for Speed - Porsche Unleashed.exe` (Runs MIPS I AOT boot loop cleanly)
- [x] **Desktop Studio GUI & Live Viewport (`gui.py`)**: 5-tab modern studio featuring interactive **60 FPS Live Viewport**, on-screen controller HUD, and Shannon entropy analyzer.
- [x] **Public Beta Release `v0.1.0-beta`**: Official release published on GitHub with standalone Windows executable and demo walkthroughs.

---

## 🚀 Milestone 2: Interactive Audio/Video HAL & Full Graphics Modes (In Progress)

### Track A: Cross-Platform SDL2 Presentation HAL & GUI (Coworker 58)
- [ ] **Cross-Platform C Runtime (`src/runtime/hal.h` & `src/runtime/sdl_hal.c`)**:
  - Unified C HAL interface: `hal_init_window()`, `hal_present_framebuffer()`, `hal_poll_input()`, `hal_sleep_frame()`.
  - Compile-time switch between native Win32 GDI and SDL2 / OpenGL for cross-platform Linux and macOS binaries.
- [ ] **GUI Live Viewport Recording**:
  - Add recording button to Tab 5 in `gui.py` to capture live gameplay animations directly to GIF/MP4.
- [ ] **Compilation Caching Engine**:
  - Cache unchanged basic block C functions to accelerate incremental MSVC/Clang rebuilds.

### Track B: N64 Reality Coprocessor & PS1 GTE Engine (Coworker cb)
- [ ] **PS1 GTE (Geometry Transformation Engine) Coprocessor 2**:
  - Implement basic 3D perspective matrix transformations (`RTPT`, `RTPS`, `NCLIP`, `AVSZ3`).
- [ ] **N64 Reality Display Processor (RDP/RSP)**:
  - Command list parser for display list rendering (`G_SETOTHERMODE`, `G_TRI1`, `G_TEXTURE`).
- [ ] **PS1 & N64 Framebuffer Scanning**:
  - Scan VRAM display buffers to produce active 3D textured output in the presentation window.

### Track C: GBA Tilemap PPU & DirectSound Audio (Coworker 6f)
- [x] **GBA PPU Tilemap Engine (Modes 0, 1, 2)**:
  - Background tile decoding (`BG0`-`BG3`), palette lookup, and scanline composition into the 240×160 framebuffer.
- [x] **Affine Transformation Layers**:
  - Rotscale matrix calculations (`REG_BG2PA`-`REG_BG2PD`) for rotating/scaling backgrounds.
- [x] **GBA DMA Audio Streaming**:
  - FIFO sound buffer streaming to host audio via DirectSound FIFO A/B buffer shims (`0x040000A0`).

### Track D: SNES Mode 7 & SPC700 Sound APU (Coworker 54)
- [ ] **SNES Mode 7 Affine Matrix Rendering**:
  - Mode 7 perspective scaling and rotation matrix calculation for racing and world-map games.
- [ ] **SPC700 Sound Coprocessor Shim**:
  - Emulate 8-bit Sony SPC700 communication ports (`$2140..$2143`) to advance audio-dependent game loops.
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
- [ ] **SNES HiROM / ExHiROM Translators**:
  - Support high-bank mapping (`$C00000..$FFFFFF`) for commercial titles over 4MB.

---

## 💎 Milestone 4: Native Modding, HD Textures & Widescreen (Coworker 69)

### Track F: Modding SDK & Visual Enhancement
- [x] **HD Texture Replacement Pipeline**:
  - Dump VRAM textures with deterministic CRC32 hashes to disk (`src/modding/texture_manager.py`).
  - Automatically load high-resolution PNG replacements at runtime (`recomp_lookup_hd_texture`).
- [x] **Widescreen Camera Geometry Patches**:
  - Dynamic aspect-ratio adjustment for 16:9, 21:9, and 32:9 ultrawide displays without horizontal stretching (`src/modding/widescreen.py`).
  - Hor+ FOV expansion factor and 4x4 perspective projection matrix scaling.
- [x] **C Hook & Interception API (`recomp_hook_function`)**:
  - Allow C/C++ modders to override or augment internal game functions at native execution speed (`src/modding/hook_manager.py`).
  - Generates `recomp_hooks.h` with PRE, POST, and REPLACE function hook trampolines.

---

## 🤝 How to Contribute to the Roadmap

Want to pick up an item or contribute an instruction?
1. Check the [Contributor Bounties Catalog](docs/CONTRIBUTOR_BOUNTIES.md) for self-contained tasks.
2. Propose or contribute an opcode lifter using our [New Instruction Template](.github/ISSUE_TEMPLATE/new_instruction.yml).
3. Open an issue on GitHub using our [Feature Request Template](.github/ISSUE_TEMPLATE/feature_request.yml).
