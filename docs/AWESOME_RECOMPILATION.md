# Awesome Static Recompilation [![Awesome](https://awesome.re/badge.svg)](https://github.com/yefan911/automated-recompilers)

> A curated list of static recompilation engines, Ahead-Of-Time (AOT) binary translators, native PC source ports, academic papers, and reverse-engineering frameworks for classic console architectures.

Static recompilation (AOT binary translation) translates foreign machine code into clean, host-native C or C++ before execution, eliminating runtime JIT cache stutter, reducing CPU overhead to negligible levels, and unlocking ultra-low latency, native high-refresh-rate rendering, and modern modding.

---

## Contents
- [Multi-Console Frameworks](#multi-console-frameworks)
- [Nintendo 64 Recompilations](#nintendo-64-recompilations)
- [PlayStation 1 Recompilations](#playstation-1-recompilations)
- [Game Boy Advance & Nintendo DS](#game-boy-advance--nintendo-ds)
- [Super Nintendo (SNES) & 16-Bit](#super-nintendo-snes--16-bit)
- [PC Decompilations & Source Ports](#pc-decompilations--source-ports)
- [Academic Papers & Binary Translation Theory](#academic-papers--binary-translation-theory)
- [Tooling & Reverse Engineering](#tooling--reverse-engineering)

---

## Multi-Console Frameworks

- **[Automated Game ROM Recompiler](https://github.com/yefan911/automated-recompilers)** — Open-source framework that ingests raw ROMs across ARM7TDMI (GBA), MIPS I/III (N64, PS1), and W65C816S (SNES) and automatically builds recursive CFGs and standalone native C executables with a built-in Hardware Abstraction Layer (HAL).
- **[LLVM / McSema](https://github.com/lifting-bits/mcsema)** — Framework for lifting x86/x86-64 machine code to LLVM IR for binary analysis and recompilation.
- **[Remill](https://github.com/lifting-bits/remill)** — Library for lifting machine code instructions into LLVM bitcode.

---

## Nintendo 64 Recompilations

- **[N64Recomp](https://github.com/N64Recomp/N64Recomp)** — Tool to statically recompile N64 binaries into native C code using offline analysis (MIT License), powering *Zelda 64: Recompiled*.
- **[Zelda 64: Recompiled](https://github.com/Zelda64Recomp/Zelda64Recomp)** — Native PC recompilation of *The Legend of Zelda: Majora's Mask* and *Ocarina of Time* featuring high framerates, ray tracing support, and ultra-wide rendering (MIT License).
- **[SirDiabo/GithubLauncher](https://github.com/SirDiabo/GithubLauncher)** — Automated manager utility to download, update, and launch community N64 static recompilations.
- **[Ship of Harkinian](https://github.com/HarbourMasters/ShipofHarkinian)** — Native PC port of *The Legend of Zelda: Ocarina of Time* created through complete decompilation, featuring 60+ FPS, free camera controls, and texture packs.
- **[2 Ship 2 Harkinian](https://github.com/HarbourMasters/2Ship2Harkinian)** — Native PC port of *The Legend of Zelda: Majora's Mask*.
- **[sm64-port](https://github.com/n64decomp/sm64)** — Full C decompilation and native PC port of *Super Mario 64*.
- **[Perfect Dark PC Port](https://github.com/fgsfdsfgs/perfect_dark)** — Native PC source port of Rare's classic N64 shooter.

---

## PlayStation 1 & PlayStation Vita Recompilations

- **[RetroPortingToolKit/psxrecomp](https://github.com/RetroPortingToolKit/psxrecomp)** — PlayStation 1 static recompiler translating MIPS-I binaries into native C++ using the MIT-licensed OpenBIOS clean-room runtime.
- **[PS1Recomp](https://github.com/PS1Recomp/ps1-recomp)** — Static recompiler for PlayStation 1 MIPS-I binaries into native C code (GPLv3).
- **[TheLostPantheon/nativ](https://github.com/TheLostPantheon/nativ)** — Static recompilation toolkit translating PlayStation Vita executables into native PC binaries with a bring-your-own-firmware runtime model (GPL-2.0).
- **[Dino Crisis Recompilation](https://github.com/gemini35/dino-crisis-recomp)** — Reverse-engineered PC port and native modernization of Capcom's classic survival horror.
- **[Crash Team Racing Native](https://github.com/Rinnegatamante/Crash-Team-Racing-High-Octane)** — Native PC source port and recompilation for PS1 Crash Team Racing supporting 60+ FPS and 32:9 ultrawide rendering.
- **[WipEout PC Port](https://github.com/phoboslab/wipeout-rewrite)** — Complete rewrite and native PC port of the PS1 Psygnosis classic by Dominic Szablewski.

---

## Game Boy Advance & Nintendo DS

- **[JRickey/gba-recomp](https://github.com/JRickey/gba-recomp)** — Ahead-of-Time static recompiling toolkit and hardware runtime for Game Boy Advance ROMs (Apache 2.0 License).
- **[mstan/gbarecomp](https://github.com/mstan/gbarecomp)** — Static recompilation framework translating ARM7TDMI ARM and Thumb machine code into native C++ for desktop targets.
- **[arcanite24/gb-recompiled](https://github.com/arcanite24/gb-recompiled)** — Static recompiler for Game Boy and Game Boy Color (LR35902 CPU) translating ROMs into portable C with SDL2 runtime (MIT License).
- **[pokeemerald / pokeruby / pokefirered](https://github.com/pret/pokeemerald)** — Complete decompilation of Pokémon Emerald, Ruby, and FireRed to matching C, allowing native PC compilation and ROM hacking.
- **[Sonic Advance Decompilation](https://github.com/Sonicadvance1)** — Decompilation and native execution project for Game Boy Advance.
- **[GBA Static Recomp Research](https://github.com/yefan911/automated-recompilers)** — Recursive basic block lifter for ARM7TDMI & Thumb-16 with automatic ARM/Thumb interworking resolution.

---

## Super Nintendo (SNES) & 16-Bit

- **[sp00nznet/snesrecomp](https://github.com/sp00nznet/snesrecomp)** — Open-source static recompiler for SNES 65816 machine code with linkable LakeSnes emulation backend (MIT License).
- **[AndreaOrru/gilgamesh](https://github.com/AndreaOrru/gilgamesh)** — SNES reverse-engineering and static recompilation framework (BSD 2-Clause License).
- **[Junior-Jones Static Recomp Suite](https://github.com/Junior-Jones)** — Standalone native static recompilations of *SimCity*, *Civilization*, *Jungle Strike*, *Top Gear*, and *Rock N' Roll Racing* for PC (zlib License).
- **[Zelda 3 PC Port (zelda3)](https://github.com/snesrev/zelda3)** — Reverse-engineered native PC reimplementation of *The Legend of Zelda: A Link to the Past*, written in C with widescreen 16:9 support and audio enhancements.
- **[Super Mario World PC Port (smw)](https://github.com/snesrev/smw)** — Native C reimplementation of *Super Mario World* for modern operating systems.
- **[65816 LoROM Lifter](https://github.com/yefan911/automated-recompilers)** — Automated 24-bit banked LoROM recursive lifter translating SNES machine code into C.

---

## Xbox, PlayStation 2 & Modern Source Ports

- **[TGP482/XboxXBE-Recomp](https://github.com/TGP482/XboxXBE-Recomp)** — Static recompiler targeting original Xbox `default.xbe` executables for native PC execution.
- **[gothamor/gta-vcs-recomp](https://github.com/gothamor/gta-vcs-recomp)** — Native PC recompilation of GTA: Vice City Stories with 240 FPS decoupled frame timing and ultrawide support.

---

## PC Decompilations & Source Ports

- **[OpenGOAL](https://github.com/open-goal/jak-project)** — Complete native PC port of *Jak and Daxter: The Precursor Legacy* and *Jak II*, natively recompiling Naughty Dog's custom GOAL language to x86-64.
- **[DevilutionX](https://github.com/diasurgical/devilutionX)** — Native port and modernization of *Diablo 1* for modern PCs, mobile devices, and consoles.
- **[Sonic CD (1993 / 2011) Decompilation](https://github.com/Rubberduckycooly/Sonic-CD-11-Decompilation)** — Byte-accurate C decompilation of the Retro Engine (RSDKv3).

---

## Academic Papers & Binary Translation Theory

1. **Static Binary Translation of Console Executables** — Research exploring the advantages of offline CFG extraction vs dynamic translation caches.
2. **Control Flow Integrity in Statically Recompiled Binaries** — Strategies for resolving indirect jumps, function pointers, and jumptables without host stack corruption.
3. **Shannon Entropy Slices in Binary Analysis** — Mapping executable instructions vs compressed asset blocks using statistical byte entropy.
4. **Delay Slot Elimination in MIPS AOT Translation** — Preserving semantic order of delayed branches when lowering to standard C conditionals.

---

## Tooling & Reverse Engineering

- **[Ghidra](https://github.com/NationalSecurityAgency/ghidra)** — Software reverse engineering (SRE) suite developed by the NSA with multi-architecture decompilers.
- **[Capstone Engine](https://github.com/capstone-engine/capstone)** — Disassembly framework supporting ARM, MIPS, x86, PowerPC, and more.
- **[Mermaid.js](https://mermaid.js.org)** — Diagramming and charting tool used to render Control Flow Graphs directly in markdown and web browsers.
- **[Shields.io](https://shields.io)** — Dynamic metadata badges for displaying opcode and ISA coverage.

---

## Contributing

Additions and improvements are welcome! If you know of an awesome static recompilation, decompilation, or binary translation project, please submit a pull request according to our [Contributing Guidelines](../CONTRIBUTING.md).
