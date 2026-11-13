# Console Compatibility

Last reviewed: **2026-11-13**, against published `main` at [`70251fd`](https://github.com/yefan911/automated-recompilers/commit/70251fd). This list covers every console recognized by this repository and identifies related console families without an implemented target. Development branches and local experiments may have additional features.

The recompiler currently provides **four prototype recompilation targets and one detection-only target**. Compatibility depends on the game's instructions, memory layout, and hardware use. Generating C or successfully running a bounded boot sequence does not establish complete game playability.

## Status definitions

| Status | Meaning |
| --- | --- |
| Verified homebrew | A homebrew program's generated native executable has automated execution checks. The result applies to that program and tested behavior. |
| Prototype | Detection, code generation, and a partial runtime exist. Hardware coverage and commercial gameplay remain incomplete. |
| Detection only | Header metadata can be inspected; no console-specific native recompilation pipeline exists. |
| Unsupported | No detector, lifter, or runtime for this console is implemented. |
| Unverified | The feature or game outcome has no recorded validation sufficient to claim compatibility. |

## Console matrix

File extensions below describe recognized layouts; detection generally examines file contents. A filename alone does not make an image compatible.

| Console / aliases | Input layouts | Detection and ROM reading | C generation / native execution | Compatibility status |
| --- | --- | --- | --- | --- |
| **Game Boy Advance (GBA)** | `.gba`, ARM7TDMI / ARMv4T with ARM and Thumb code | Header detection; linear cartridge address translation | ARM and Thumb lifters, partial BIOS/hardware shims, native runtime | **Prototype; verified bundled homebrew execution and Mode 3 framebuffer snapshot.** Commercial gameplay unverified. |
| **Nintendo 64 (N64)** | `.z64` big-endian, `.n64` word-swapped, `.v64` byte-swapped | Header detection and dump normalization for reads and lifting | Shared MIPS lifter and native runtime, with partial instruction/hardware coverage | **Prototype; verified synthetic homebrew execution.** Complete N64 CPU, RSP/RDP, and commercial gameplay support remain incomplete. |
| **PlayStation 1 (PS1 / PSX)** | Raw `PS-X EXE`; ISO-9660 data images (`.iso`, `.bin`) with supported 2048-byte or 2352-byte sectors | Executable header parsing; `SYSTEM.CNF` boot-path extraction; logical payload reads across sector boundaries | Shared MIPS lifter, partial GTE operations, native runtime | **Prototype.** Executable extraction and CPU/GTE behavior have tests; complete disc-driven gameplay, GPU, and SPU support remain incomplete. |
| **Super Nintendo (SNES / Super Famicom)** | `.sfc`, `.smc`; LoROM, HiROM, ExHiROM; optional 512-byte copier header | Header/reset-vector detection and shared banked cartridge mapping | W65C816S / 65816 lifter and native runtime | **Prototype; verified synthetic homebrew execution.** Complete PPU/APU, cartridge-chip, and commercial gameplay support remain incomplete. |
| **Nintendo Entertainment System (NES / Famicom cartridge images)** | iNES `.nes` headers | PRG/CHR size, mapper, mirroring, and reset-vector inspection | No 6502 lifter or NES native runtime; CLI does not recompile this target | **Detection only.** Reading a mapper number does not implement that mapper. Famicom Disk System images are unsupported. |

## Hardware and runtime limits

| Area | GBA | N64 | PS1 | SNES |
| --- | --- | --- | --- | --- |
| CPU translation | Partial ARM/Thumb; tested flags, memory transfers, and interworking | Partial shared MIPS implementation; no complete 64-bit/FPU coverage | Partial shared MIPS implementation; tested delay-slot behavior and selected GTE operations | Partial 65816; tested arithmetic, stack calls, and cartridge reads; M/X width-state joins and `PLP` restoration need CFG variants |
| Graphics | Mode 3 native framebuffer snapshot verified; prototype tile/palette paths; full PPU composition open | Presentation/framebuffer scaffolding; RSP/RDP display-list rendering open | Presentation scaffolding; complete GPU packet rendering open | VRAM/palette register handling and prototype rendering; complete PPU and Mode 7 output open |
| Audio | FIFO register storage; DMA mixing and host output open | Host audio pipeline open | SPU and CD audio pipeline open | SPC700 port storage/initial handshake; APU execution, mixing, and host output open |
| Input | Native Win32 keyboard/keypad plumbing; complete gameplay unverified | Prototype native keyboard/controller plumbing | Prototype native keyboard/controller plumbing | Prototype native keyboard/joypad plumbing |
| Persistent saves | SRAM/Flash/EEPROM disk persistence open | Controller Pak / FlashRAM persistence open | Complete memory-card support unverified | Battery-backed SRAM persistence open |

Unresolved code paths, unsupported instructions, approximate hardware behavior, and the `--max-blocks` discovery budget can limit execution. Increasing the budget does not supply missing hardware support. Widescreen, texture, and hook CLI options generate helpers; automatic integration into guest rendering/execution remains open.

### Image-specific limits

- **N64:** The reader and lifter normalize all three listed dump byte orders. Partial trailing words/pairs in swapped dumps are rejected. Dynamic overlays and full coprocessor behavior are not established by a successful ROM lift.
- **PS1:** Raw sectors support the tested Mode 1 and Mode 2 user-data offsets (16 and 24 bytes). Pass the data image or raw executable directly. Full `.cue` parsing, CDDA tracks, multi-disc handling, and runtime CD streaming remain open.
- **SNES:** LoROM, HiROM, and ExHiROM translation is implemented and tested, including copier-header removal. The lifter accepts up to 8 MiB of cartridge data plus an optional copier header. Large commercial cartridge mirroring, SRAM, and special chips such as Super FX and SA-1 are not established as compatible.
- **NES:** iNES metadata inspection includes trainer-aware reset-vector reads. NES 2.0's full extended metadata, mapper execution, and native NES gameplay are not established as supported.

## Recorded program results

These entries distinguish automated homebrew checks from the **historical commercial build/boot smoke checks recorded on 2026-11-02**. Commercial entries were not retested for this documentation update; no completion, audio, or save compatibility is implied.

| Console | Program / recorded ROM name | Recorded outcome | Evidence |
| --- | --- | --- | --- |
| GBA | Bundled `roms/test/hello_gba.gba` / generated GBA homebrew | Native execution and a 240 x 160 Mode 3 snapshot; the bundled example writes 2,400 pixels | [README walkthrough](../README.md#quick-start-in-60-seconds), [framebuffer regression](../tests/test_arm_semantics.py), [runtime tests](../tests/test_native_runtime.py) |
| N64 | Generated synthetic homebrew | Generated native executable runs headlessly with exit code 0 | [Runtime tests](../tests/test_native_runtime.py), [console tests](../tests/test_n64_console.py) |
| SNES | Generated synthetic homebrew | Generated native executable runs headlessly with exit code 0 | [Runtime tests](../tests/test_native_runtime.py), [65816 regressions](../tests/test_snes_semantics.py) |
| GBA | `PGATour.gba` | Historical native build/boot; display controller initialized to `REG_DISPCNT = 0x0080` | [Roadmap](../ROADMAP.md), [coordination history](../COORDINATION.md) |
| N64 | `Yoshi.z64` | Historical native build and bounded MIPS dispatch run | [Roadmap](../ROADMAP.md), [coordination history](../COORDINATION.md) |
| PS1 | Need for Speed - Porsche Unleashed, Track 01 | Historical boot-executable extraction, native build, and bounded MIPS boot run | [Roadmap](../ROADMAP.md), [reader/detector tests](../tests/test_core_readers_and_inspection.py) |
| SNES | Super Mario All-Stars and Super Mario World | Historical LoROM native build and bounded 65816 dispatch run | [Roadmap](../ROADMAP.md), [coordination history](../COORDINATION.md) |
| NES | Generated `hello_nes.nes` | Header/mapper/reset-vector checks only; no native execution | [NES console tests](../tests/test_nes_console.py) |

## Related consoles without an implemented target

The following platforms are **unsupported** by this repository. Shared processors, branding, or backward compatibility do not supply a detector, lifter, or hardware runtime here. This table records current scope rather than planned delivery dates.

| Console family | Platforms | Missing target support |
| --- | --- | --- |
| Earlier Nintendo handhelds | Game Boy, Game Boy Color | No SM83 CPU, cartridge mapper, or handheld hardware target |
| Later Nintendo handhelds | Nintendo DS / DSi, Nintendo 3DS / New 3DS | No dual-CPU/system runtime or console-specific image support |
| Other Nintendo systems | Virtual Boy, Nintendo 64DD | No dedicated image/device runtime support |
| Nintendo optical-disc systems | GameCube, Wii, Wii U | No PowerPC or console hardware target |
| Nintendo Switch systems | Switch, Switch 2 | No platform-specific executable or hardware target |
| Later PlayStation consoles | PlayStation 2, 3, 4, 5 | No console-specific CPU/system runtime |
| Sony handhelds | PSP, PlayStation Vita | No handheld-specific lifter/system runtime |
| Sega 8-bit systems | SG-1000, Master System, Game Gear | No Z80 or console hardware target |
| Sega 16-bit systems and add-ons | Mega Drive / Genesis, Sega CD, 32X | No 68000/Z80/SH-2 console pipeline or add-on runtime |
| Later Sega consoles | Saturn, Dreamcast | No SH-2/SH-4 console pipeline or hardware runtime |
| NEC and SNK systems | PC Engine / TurboGrafx-16 / CD, SuperGrafx, Neo Geo AES/MVS/CD, Neo Geo Pocket / Color | No console-specific CPU, media, or hardware pipeline |
| Atari and other classic consoles | Atari 2600/5200/7800, Lynx, Jaguar, ColecoVision, Intellivision, 3DO | No console-specific detector/lifter/runtime |
| Microsoft consoles | Xbox, Xbox 360, Xbox One, Xbox Series X/S | No console-specific executable/system runtime |

## Host platform compatibility

| Host | Current evidence | Limits |
| --- | --- | --- |
| Windows | CI tests Python 3.10-3.13; MSVC/Clang/GCC compiler discovery; native Win32 presentation | Install a supported native C compiler to build from source. GUI use requires Tkinter. |
| Linux | CI tests Python 3.10-3.13; GCC builds/runs the bundled GBA output with `-Wall -Wextra -Werror -O2` | Headless native execution is covered; a cross-platform guest display/audio HAL is still open. Generated binary names currently retain `.exe`. |
| macOS | No macOS CI validation recorded | Treat native builds and guest display as unverified. |
| Browser | Hosted CFG explorer and selected instruction examples | The browser demo does not run arbitrary ROMs or establish native game compatibility. |

## Checking a ROM and reporting compatibility

Inspect the console and input layout, then generate C or build the executable from the repository root:

```sh
python src/core/rom_detector.py path/to/game.rom
python recompile.py path/to/game.rom --no-build
python recompile.py path/to/game.rom
```

On this Windows development machine, use `py` in place of `python`. The detection-only NES target can be inspected with the first command; the compilation commands require one of the four implemented targets. Use the [bundled GBA quick start](../README.md#quick-start-in-60-seconds) for a reproducible native execution/snapshot example.

When reporting a result, include the repository commit, host OS/compiler, console, title/region/revision, ROM SHA-256, image layout, commands and block budget, and the furthest verified outcome: detected, generated C, built, booted, menus, gameplay, or completed. Report graphics, audio, input, and save behavior separately, with logs or screenshots where useful. Submit results through the [issue tracker](https://github.com/yefan911/automated-recompilers/issues).

## Source of truth

- [ROM detector](../src/core/rom_detector.py), [data-block readers](../src/core/data_block_reader.py), and [CLI target routing](../recompile.py).
- [ARM](../src/lifter/arm_lifter.py), [Thumb](../src/lifter/thumb_lifter.py), [MIPS](../src/lifter/mips_lifter.py), and [65816](../src/lifter/snes_lifter.py) lifters.
- [Reader/inspection regressions](../tests/test_core_readers_and_inspection.py), [native runtime checks](../tests/test_native_runtime.py), and [CI workflow](../.github/workflows/ci.yml).
- [Current roadmap](../ROADMAP.md) and [opcode inventory](OPCODE_COVERAGE.md). Opcode inventory percentages measure recognized instruction categories, not game compatibility rates.

Update this document when a detector, image layout, lifter, hardware feature, or recorded game result changes. Include the commit and validation evidence with each compatibility claim.
