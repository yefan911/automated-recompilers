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

- **[N64Recomp](https://github.com/Mr-Wiseguy/N64Recomp)** — Tool to statically recompile N64 binaries into native C code using offline analysis, powering *Zelda 64: Recompiled*.
- **[Zelda 64: Recompiled](https://github.com/Zelda64Recomp/Zelda64Recomp)** — Native PC recompilation of *The Legend of Zelda: Majora's Mask* and *Ocarina of Time* featuring high framerates, ray tracing support, and ultra-wide rendering.
- **[Ship of Harkinian](https://github.com/HarbourMasters/ShipofHarkinian)** — Native PC port of *The Legend of Zelda: Ocarina of Time* created through complete decompilation, featuring 60+ FPS, free camera controls, and texture packs.
- **[2 Ship 2 Harkinian](https://github.com/HarbourMasters/2Ship2Harkinian)** — Native PC port of *The Legend of Zelda: Majora's Mask*.
- **[sm64-port](https://github.com/n64decomp/sm64)** — Full C decompilation and native PC port of *Super Mario 64*.
- **[Perfect Dark PC Port](https://github.com/fgsfdsfgs/perfect_dark)** — Native PC source port of Rare's classic N64 shooter.

---

## PlayStation 1 Recompilations

- **[PS1Recomp](https://github.com/Mr-Wiseguy/PS1Recomp)** — Static recompiler for PlayStation 1 MIPS-I binaries into native C code.
- **[Dino Crisis Recompilation](https://github.com/gemini35/dino-crisis-recomp)** — Reverse-engineered PC port and native modernization of Capcom's classic survival horror.
- **[WipEout PC Port](https://github.com/phoboslab/wipeout-rewrite)** — Complete rewrite and native PC port of the PS1 Psygnosis classic by Dominic Szablewski.

---

## Game Boy Advance & Nintendo DS

- **[pokeemerald / pokeruby / pokefirered](https://github.com/pret/pokeemerald)** — Complete decompilation of Pokémon Emerald, Ruby, and FireRed to matching C, allowing native PC compilation and ROM hacking.
- **[Sonic Advance Decompilation](https://github.com/Sonicadvance1)** — Decompilation and native execution project for Game Boy Advance.
- **[GBA Static Recomp Research](https://github.com/yefan911/automated-recompilers)** — Recursive basic block lifter for ARM7TDMI & Thumb-16 with automatic ARM/Thumb interworking resolution.

---

## Super Nintendo (SNES) & 16-Bit

- **[Zelda 3 PC Port (zelda3)](https://github.com/snesrev/zelda3)** — Reverse-engineered native PC reimplementation of *The Legend of Zelda: A Link to the Past*, written in C with widescreen 16:9 support and audio enhancements.
- **[Super Mario World PC Port (smw)](https://github.com/snesrev/smw)** — Native C reimplementation of *Super Mario World* for modern operating systems.
- **[65816 LoROM Lifter](https://github.com/yefan911/automated-recompilers)** — Automated 24-bit banked LoROM recursive lifter translating SNES machine code into C.

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
