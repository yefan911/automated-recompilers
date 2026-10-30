# Case Studies: How Modern Static Recompilers Work

This document analyzes the internal engineering of production static recompilers:
* [N64Recomp](https://github.com/N64Recomp/N64Recomp) & [Zelda64Recomp](https://github.com/Zelda64Recomp/Zelda64Recomp)
* [mstan/gbarecomp](https://github.com/mstan/gbarecomp)
* [JRickey/gba-recomp](https://github.com/JRickey/gba-recomp)
* [PS1Recomp](https://github.com/PS1Recomp/ps1-recomp) & [RetroPortingToolKit psxrecomp](https://github.com/RetroPortingToolKit/psxrecomp)

---

## 1. N64Recomp & Zelda64Recomp

### Core Philosophy
Instead of emulating the N64's MIPS VR4300i CPU at runtime, N64Recomp takes the game binary and translates every original MIPS function into a native C function.

### Key Implementation Details:
1. **Instruction-Level Translation:**
   Each MIPS instruction is lifted into a corresponding C expression modifying an execution context `ctx`:
   ```c
   // addiu $r4, $r4, 0x20
   ctx->r4 = ADD32(ctx->r4, 0x20);
   ```

2. **Branch Delay Slots:**
   MIPS architectures execute the instruction immediately following a jump or branch before the jump takes effect (delay slot). N64Recomp handles this by duplicating or reordering the delay slot instruction directly into the branch evaluation path.

3. **Indirect Calls & Virtual Tables:**
   Dynamic indirect jumps (such as `jalr $25`) cannot be resolved statically to a single function. N64Recomp translates these to dynamic lookups:
   ```c
   LOOKUP_FUNC(ctx->r25)(rdram, ctx);
   ```

4. **Overlays (Dynamic Code Swapping):**
   N64 games swap level/actor code into RDRAM on the fly. The N64Recomp runtime tracks which overlay section is currently loaded at any VRAM address, allowing `LOOKUP_FUNC` to dynamically dispatch to the active overlay's recompiled C function.

5. **Graphics & RT64:**
   Instead of cycle-accurate LLE of the Reality Coprocessor (RSP/RDP), N64Recomp hooks the high-level graphics microcode (Fast3D / F3DEX2 display lists) and passes them to **RT64**, a modern renderer that outputs directly to DirectX 12 or Vulkan with unlocked framerates and ray tracing.

---

## 2. GBARecomp & GBA-Recomp

### Dual-ISA Handling (ARM + Thumb)
The Game Boy Advance's ARM7TDMI processor runs in two modes:
* **ARM mode:** 32-bit instructions with conditional execution fields on every instruction.
* **Thumb mode:** 16-bit compressed instructions with limited register access.

### Memory & Execution Architecture:
1. **Linear ROM Mapping:**
   Unlike disc-based consoles or bank-switched cartridges, GBA ROMs are mapped continuously into memory starting at `0x08000000`. This makes basic block discovery much more direct.

2. **RAM-Resident Code (IWRAM):**
   Critical loops and sound mixing routines in GBA games are copied via DMA into fast 32KB Internal Work RAM (`0x03000000`).
   * **Hybrid Approach ([mstan/gbarecomp](https://github.com/mstan/gbarecomp)):** Uses static AOT translation for 99% of ROM code, and maintains a lightweight fallback interpreter strictly for unmapped/dynamic IWRAM execution.
   * **Ahead-Of-Time Mapping ([JRickey/gba-recomp](https://github.com/JRickey/gba-recomp)):** Maps callers and callees ahead of time using Ghidra binary analysis to achieve a 0-interpreter native executable.

3. **Interrupt & Hardware Synchronization:**
   The recompiled CPU thread executes basic blocks in chunks matching a cycle quota (e.g. 280 cycles per scanline). At scanline boundaries, the runtime ticks the PPU and DMA, updates timer registers, and triggers VBlank/HBlank IRQs by modifying the CPU's CPSR flag.

---

## 3. PS1Recomp & psxrecomp

### MIPS R3000A & Coprocessors
1. **GTE (Geometry Transformation Engine):**
   PS1 3D calculations rely on Coprocessor 2 (GTE) for fixed-point matrix multiplication, lighting, and perspective projections. PS1 recompilers translate GTE instructions into vectorized SIMD instructions on the host PC (x86 SSE/AVX or ARM NEON).

2. **BIOS Syscall High-Level Emulation (HLE):**
   Instead of executing the original Sony PS1 BIOS binary, calls to the BIOS jump tables (`0xA0`, `0xB0`, `0xC0`) are hooked with native C implementations of kernel memory allocation, GPU packet dispatch, and CD-ROM file streaming.

---

## 4. Lessons for Our Automated Recompiler Framework

To build a tool that can recompile arbitrary ROMs automatically:
1. **Combine AOT with Fallback Dispatch:**
   * Emit native C functions for all discoverable basic blocks.
   * Route any unresolved indirect jump (`LOOKUP_FUNC`) through a dispatch table. If a target is missing, invoke a fallback interpreter rather than crashing.
2. **Automated Jump Table Detection:**
   * Recognize compiler-generated switch table patterns during binary lifting to turn computed jumps into native C `switch-case` blocks.
3. **Decouple Hardware via Modular HAL:**
   * The recompiled code should only interact with a unified `CpuContext` struct and standard read/write callbacks (`mem_read32`, `mem_write32`).
