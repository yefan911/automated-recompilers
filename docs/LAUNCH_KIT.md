# Automated Recompilers — Launch & Promotion Kit

This kit contains copy-paste-ready announcements, technical blog posts, social media threads, and community posts to promote the repository across different platforms.

---

## 1. Hacker News (news.ycombinator.com)

### Submission Title:
> **Show HN: Automated Game ROM Recompiler – AOT compile console ROMs to native C**

### Submission URL:
`https://github.com/yefan911/automated-recompilers`

### First Comment / Text Body:
```markdown
Hi HN! Over the past few months, we've seen remarkable single-game static recompilation projects (like Zelda64: Recompiled and Ship of Harkinian) demonstrate the power of Ahead-Of-Time (AOT) recompilation over traditional emulation: native 144+ FPS, zero JIT compilation stutter, instant startup, and direct hardware acceleration.

However, most recompilation efforts are painstakingly hand-tuned for a single game. We wanted to see how far we could take a *generic, automated* static recompilation pipeline across multiple retro console architectures.

We built an open-source framework that ingests binary console ROMs (GBA, N64, PS1, SNES) and translates them into standalone native C source code with an integrated hardware runtime (HAL), which is then compiled into a native `.exe` or Linux binary.

### How the Pipeline Works:

1. **Identification**: Scans headers, verifies checksums, resolves endianness (such as Big-Endian .z64 vs Byte-Swapped .v64), and calculates entry-point VRAM vectors.
2. **Recursive CFG Lifting**: Disassembles machine code starting from entry vectors, recursively tracing branches, mapping subroutine targets, and detecting spin loops.
3. **Multi-Architecture Instruction Lifters**:
   - **ARM7TDMI & Thumb-16** (GBA): Handles ALU conditional execution, memory transfers, and ARM/Thumb state switching (`BX`).
   - **MIPS I & III** (N64 / PS1): Resolves MIPS branch delay slots, R-type/I-type arithmetic, and jump target resolution.
   - **W65C816S** (SNES): Handles 24-bit banked addressing and dynamic register resizing (`REP`/`SEP`).
4. **C Code Generation**: Emits clean C functions (`bb_XXXXXXXX`) mapped to a virtual register context (`ArmCpuContext` / `MipsCpuContext`) and a unified `recomp_dispatch` trampoline.
5. **Native Compilation & Presentation**: Invokes MSVC, Clang, or GCC to output a standalone binary with a native desktop window (Win32 GDI / Framebuffer) and zero runtime emulator dependencies.

### Try It Immediately (100% Legal Reference Included):
We bundle a verified, legal homebrew test ROM (`roms/test/hello_gba.gba`) so you can run the entire pipeline end-to-end without needing proprietary game dumps:

```bash
git clone https://github.com/yefan911/automated-recompilers.git
cd automated-recompilers
pip install -r requirements-dev.txt

# Recompile the test ROM to native C and compile .exe:
python recompile.py roms/test/hello_gba.gba

# Run the native game window:
.\build\hello_gba.exe --window
```

We also include a dark-mode desktop GUI (`python recompile.py --ui`) and Shannon entropy visualization to map executable code segments versus compressed texture/audio blocks.

The project is fully open source under the MIT license. We would love feedback from compiler engineers, reverse engineers, and emulation enthusiasts on handling dynamic indirect jumps and expanding our ISA lifter coverage!

GitHub: https://github.com/yefan911/automated-recompilers
```

---

## 2. Reddit Posts

### Post A: r/emulation
**Title:**
> **[Open Source] Automated Game ROM Recompiler: AOT-translating GBA, N64, PS1, and SNES ROMs into standalone native PC executables**

**Flair:** Release / WIP

**Body:**
```markdown
Hey everyone!

Static recompilation has been transforming retro gaming recently (projects like *Ship of Harkinian*, *Zelda 64: Recompiled*, and *PS1Recomp*). The advantages over traditional emulators are huge: native performance, ultra-low input latency, no JIT cache stutter, and true native platform integration.

We've been working on an open-source framework called **Automated Game ROM Recompiler** (MIT License) that aims to make this process automated and multi-console.

Instead of writing a custom recompiler for one specific game, this tool provides:
1. **Multi-ISA Lifters:** ARM7TDMI (GBA), Thumb-16, MIPS I/III (N64/PS1), and W65C816S (SNES).
2. **Recursive CFG Tracer:** Traverses the binary from the entry vector, identifying basic blocks, branch conditions, and spin loops.
3. **C Code Emission:** Generates standard C code with register structs and an execution trampoline.
4. **Native Compilation:** Automatically builds a standalone `.exe` using your local C compiler (MSVC, Clang, or GCC).
5. **Built-in Presentation HAL:** Includes a native desktop window to display the rendered pixels.

### How to test it right now:
You don't need any commercial ROMs to try it. We include a verified homebrew GBA ROM in the repo:
```bash
python recompile.py roms/test/hello_gba.gba
.\build\hello_gba.exe --window
```

You can also run the desktop GUI with:
`python recompile.py --ui`

We'd love to hear your thoughts, feedback, and ideas from the community:
👉 Repo: https://github.com/yefan911/automated-recompilers
```

---

### Post B: r/programming & r/ReverseEngineering
**Title:**
> **Automated Recompilation: Translating foreign console machine code (ARM, MIPS, 65816) into native C with recursive CFG analysis**

**Body:**
```markdown
We've published **Automated Game ROM Recompiler**, an open-source framework exploring static ahead-of-time (AOT) binary translation for retro video game consoles.

### Technical Architecture
Unlike dynamic emulators that interpret opcodes in a fetch-decode-execute loop or compile blocks at runtime using a JIT, our recompiler parses raw console binaries at build time:
1. **Shannon Entropy Analysis**: Generates an entropy map of the ROM to distinguish high-entropy compressed assets/tables from executable code.
2. **Control Flow Graph (CFG) Reconstruction**: Starting at the console's reset/entry vector, basic blocks (`bb_XXXXXXXX`) are recursively mapped.
3. **Architecture-Specific Challenges**:
   - **MIPS Delay Slots**: Instructions in the delay slot of a branch are executed in semantic order before taking the branch target.
   - **ARM/Thumb Interworking**: State switches via `BX` are tracked across basic blocks to decode 32-bit ARM vs 16-bit Thumb instructions.
   - **SNES 65816 Accumulator/Index Dynamic Sizing**: Resolving 8-bit vs 16-bit operand widths controlled at runtime by `REP` and `SEP` flags.
4. **Intermediate Representation & C Emission**: Instructions are lowered to C statements operating on an architectural context struct (`ArmCpuContext` / `MipsCpuContext`), compiled cleanly with `-Wall -Wextra -Werror`.

Check out the code, architecture documents, and test cases:
GitHub: https://github.com/yefan911/automated-recompilers
```

---

## 3. Publication-Ready Technical Blog Post (Dev.to / Medium / Substack)

### Title:
# Inside an Automated Console Recompiler: Ahead-of-Time Translating ROMs to Native C

**Subtitle:** *Why static recompilation is replacing traditional emulation, and how we built an automated pipeline for GBA, N64, PS1, and SNES.*

---

### The Emulation Problem
For over thirty years, playing console video games on PCs has relied on emulation. Emulators simulate hardware at runtime in one of two ways:
1. **Interpretation:** An infinite loop that reads an opcode, switches on it, updates emulated registers, and repeats. This is accurate but slow.
2. **Just-In-Time (JIT) Compilation:** Blocks of guest machine code are translated into host machine code on the fly as they are executed. While fast, JITs introduce micro-stutter when new code blocks are encountered, require executable memory pages (`W^X` issues on modern platforms), and carry high runtime complexity.

### The New Paradigm: Static AOT Recompilation
Recently, the retro gaming world was stunned by projects like *Ship of Harkinian* (Nintendo 64) and *PS1Recomp* (PlayStation 1). These projects demonstrated that you can statically translate a game's machine code into native C or C++ **Ahead-Of-Time (AOT)**. 

Once recompiled:
- The game runs as a native PC binary (`.exe`).
- CPU utilization drops to negligible levels.
- Frame rates are unlocked from ancient console bottlenecks.
- Modding, widescreen rendering, and asset replacement become native C modifications.

However, existing recompilers are mostly built by hand for specific games. We set out to answer a question: **Can we build a unified, automated static recompilation framework for multiple retro consoles?**

Here is how our framework works.

---

### Stage 1: Identification & Header Analysis
Before disassembling anything, the recompiler must inspect the ROM structure. Each console has its own peculiarities:
- **Nintendo 64 ROMs** exist in three different byte-orders depending on the dump tool: Big-Endian (`.z64`), Byte-Swapped (`.v64`), or Little-Endian (`.n64`).
- **GBA ROMs** contain fixed Nintendo logo checksums and an entry branch at `0x08000000`.
- **SNES ROMs** use banked mapping systems (LoROM vs. HiROM) where internal headers live at either offset `0x7FB0` or `0xFFB0`.

Our detector module (`src/core/rom_detector.py`) normalizes byte orders, verifies checksums, and calculates the exact entry vector.

---

### Stage 2: Recursive Control Flow Graph (CFG) Construction
A naive linear sweep across a ROM fails because consoles interleave executable code with raw assets (palettes, tiles, audio samples). If a disassembler tries to decode a compressed texture as MIPS or ARM code, it produces invalid instructions.

Instead, we use **Recursive CFG Analysis** (`src/lifter/cfg.py`):
1. Begin tracing strictly from known entry vectors (the reset vector).
2. Follow execution instruction-by-instruction.
3. When a branch or jump is encountered, create a **Basic Block** boundary.
4. Recursively enqueue the branch target address and the fall-through address.
5. Stop tracing along paths that hit terminal operations (`BX LR`, infinite halt loops).

---

### Stage 3: Architecture Lifters (ARM, MIPS, 65816)
Each processor architecture is lifted into intermediate C statements:

#### 1. MIPS Delay Slots (N64 / PS1)
In classic MIPS architecture, the instruction immediately following a jump or branch is executed *before* the branch is taken. In our lifter:
```python
# MIPS branch: Delay slot executed before jump
ir_ops.append(lift_delay_slot(pc + 4))
ir_ops.append({"op": "BNE", "c_code": f"if (ctx->r[{rs}] != ctx->r[{rt}]) {{ return {target}; }}"})
```

#### 2. ARM / Thumb Interworking (GBA)
The Game Boy Advance uses an ARM7TDMI processor that dynamically switches between 32-bit ARM mode and 16-bit Thumb mode using the `BX` (Branch and Exchange) instruction:
```c
// Emitted C for BX state exchange:
if (ctx->r[rm] & 1) {
    ctx->thumb_mode = 1;
    target_pc = ctx->r[rm] & ~1;
} else {
    ctx->thumb_mode = 0;
    target_pc = ctx->r[rm] & ~3;
}
```

---

### Stage 4: Emitting C & Compiling the Binary
Each discovered basic block becomes a distinct, optimize-friendly C function:
```c
/* Basic Block at 0x08000020 */
static uint32_t bb_08000020(ArmCpuContext *ctx) {
    ctx->r[0] = (uint32_t)(ctx->r[0] - 1);  /* SUBS r0, r0, #1 */
    if (ctx->r[0] != 0) {
        return 0x08000020;                  /* BNE loop */
    }
    return 0x08000028;
}
```

A central dispatch trampoline (`recomp_dispatch`) executes blocks in a fast switch loop until execution terminates.

The pipeline then invokes the host C compiler (Visual Studio MSVC, Clang, or GCC) with optimization flags (`-O2`), producing a native executable with a built-in Win32 presentation layer.

---

### How You Can Get Involved
The project is completely open source under the MIT License on GitHub:
👉 **https://github.com/yefan911/automated-recompilers**

We are actively working on:
- Expanded instruction coverage for MIPS coprocessors and SNES 65816 addressing modes.
- SDL2 / Vulkan cross-platform HAL backends for Linux and macOS.
- Dynamic jump table heuristic analysis.

Star the repo, check out the code, and join us in building the next generation of video game preservation tools!

---

## 4. Social Media Announcement (X / Twitter & Bluesky Thread)

**Tweet 1 (The Hook):**
> What if you could take ANY retro console ROM (GBA, N64, PS1, SNES) and turn it into a standalone native PC `.exe` with zero emulator overhead?
> 
> We're building **Automated Game ROM Recompiler** — an open-source AOT static recompilation framework.
> 
> 🧵 Here's how it works 👇

**Tweet 2 (The Difference):**
> Traditional emulators interpret or JIT-compile foreign machine code at runtime.
> 
> Our recompiler translates foreign binaries into native C Ahead-Of-Time (AOT) using recursive CFG analysis, then compiles directly with MSVC/Clang/GCC into a high-performance native app.

**Tweet 3 (Under the Hood):**
> The pipeline handles:
> 🕹️ Multi-ISA Lifters (ARM7TDMI, Thumb-16, MIPS I/III, 65816)
> 🔄 MIPS delay slot resolution & ARM/Thumb state switching
> 📊 Shannon entropy maps to detect code vs compressed textures
> 🖥️ Native desktop presentation window

**Tweet 4 (Visuals & Verification):**
> It includes a dark-mode desktop GUI and a 100% legal homebrew GBA test ROM so you can recompile and run your first game in 60 seconds with zero proprietary ROMs required.
> 
> [Attach screenshot / GIF of GUI running and Win32 window displaying pixels]

**Tweet 5 (Call to Action):**
> 100% Open Source (MIT):
> ⭐ Star the repo & check out the roadmap:
> https://github.com/yefan911/automated-recompilers
> 
> #retrogaming #emulation #gamedev #reverseengineering #systems
