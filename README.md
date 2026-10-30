# Automated Game ROM Recompiler

An experimental automated static/hybrid recompilation framework that ingests video game console ROMs and translates them into standalone native PC applications (C/C++ / modern graphics HAL).

---

## Directory Structure

```
automated_recompilers/
├── roms/                       # Place your game ROMs here
│   ├── gba/                    # Game Boy Advance ROMs (.gba, .bin)
│   ├── n64/                    # Nintendo 64 ROMs (.z64, .n64, .v64)
│   ├── ps1/                    # PlayStation 1 images (.bin/.cue, .iso, .exe)
│   ├── snes/                   # Super Nintendo ROMs (.sfc, .smc)
│   └── test/                   # Open-source homebrew & test ROMs
│
├── src/
│   ├── core/                   # ROM format parsers, endianness & header identification
│   ├── lifter/                 # Disassembler (Capstone/LLVM) and IR generator
│   ├── codegen/                # C/C++ emitter and dynamic dispatch trampoline generator
│   └── runtime/                # Hardware Abstraction Layer (HAL) for GPU, Audio, and Memory
│
├── build/                      # Build outputs and generated C code
└── docs/                       # Architectural analysis and console specifications
```

---

## ROM Guidelines

### 1. Where to put your dumped ROMs
You can copy your legally dumped ROM files directly into their respective folders under `roms/`:
* **Game Boy Advance:** Place `.gba` files in `roms/gba/` (recommended first target: clean linear 32MB memory layout).
* **Nintendo 64:** Place `.z64` (big-endian preferred), `.v64`, or `.n64` files in `roms/n64/`.
* **PlayStation 1:** Place `.bin` or `.exe` files in `roms/ps1/`.

### 2. Can we test without commercial ROMs?
Yes! Public-domain homebrew ROMs and hardware test suites (e.g., Peter Lemon's bare-metal console tests, GBA homebrew demos) will be included in `roms/test/` to test instruction lifting, memory mapping, and rendering backends without needing copyright-protected assets.
