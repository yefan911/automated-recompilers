# Contributing to Automated Game ROM Recompiler

Thank you for your interest in contributing! Whether you're adding support for new instructions, extending the Hardware Abstraction Layer (HAL), improving ROM detection, or fixing bugs, all contributions are welcome.

---

## 🏛️ Project Architecture Overview

The recompiler operates in four distinct stages:

```
[ ROM Binary ] 
      │
      ▼
1. Core Detector (src/core/rom_detector.py)
      │  Identifies console, endianness, header checksums, entry vector
      ▼
2. CFG & Disassembler (src/lifter/)
      │  Recursively discovers basic blocks, decodes opcodes, traces branches
      ▼
3. C Code Generator (src/lifter/cfg.py & lifters)
      │  Emits standalone C source with CPU register contexts & dispatch trampoline
      ▼
4. Native Compiler Driver (src/core/native_compiler.py)
      │  Compiles C into native executable (.exe / binary) via MSVC, Clang, or GCC
      ▼
[ Standalone Native Executable ]
```

---

## 🛠️ Development Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yefan911/automated-recompilers.git
   cd automated-recompilers
   ```

2. **Set up a Python virtual environment (Python 3.10 to 3.13):**
   ```bash
   python -m venv .venv
   # On Windows:
   .venv\Scripts\activate
   # On Linux/macOS:
   source .venv/bin/activate
   ```

3. **Install development dependencies:**
   ```bash
   pip install -r requirements-dev.txt
   ```

4. **Run the test suite:**
   ```bash
   pytest -v
   ```
   All tests should pass cleanly.

5. **Test the end-to-end recompilation pipeline:**
   ```bash
   python recompile.py roms/test/hello_gba.gba
   ```
   This generates `build/hello_gba_recompiled.c` and compiles it into `build/hello_gba.exe` (or Linux binary).

---

## 💡 Adding a New Instruction Opcode (Walkthrough)

The most common and helpful community contribution is adding missing opcodes to our instruction lifters in `src/lifter/`.

### Example: Adding a MIPS instruction to `src/lifter/mips_lifter.py`

1. **Locate the lifter:**
   - ARM7TDMI: `src/lifter/arm_lifter.py`
   - Thumb-16: `src/lifter/thumb_lifter.py`
   - MIPS I / III: `src/lifter/mips_lifter.py`
   - SNES 65816: `src/lifter/snes_lifter.py`

2. **Decode the instruction:**
   Extract opcode fields (e.g., `rs`, `rt`, `rd`, `imm`) from the raw instruction word.

3. **Emit an IR operation dictionary:**
   Every lifted instruction returns an IR operation dictionary:
   ```python
   ir_ops.append({
       "op": "ADDU",
       "pc": pc,
       "c_code": f"ctx->r[{rd}] = (uint32_t)(ctx->r[{rs}] + ctx->r[{rt}]);"
   })
   ```

4. **Handle branch targets (if control flow changes):**
   If the instruction alters the PC (like `BEQ` or `J`), append target addresses to `targets`:
   ```python
   targets.append(target_pc)
   ```

5. **Add a unit test in `tests/`:**
   Add a targeted test in `tests/test_lifters.py` or console-specific test file:
   ```python
   def test_mips_addu():
       # Assemble or provide instruction bytes, lift block, assert C code
       ...
   ```

6. **Verify clean compilation:**
   Ensure generated C code compiles under `-Wall -Wextra -Werror`:
   ```bash
   pytest -v
   ```

---

## 📋 Pull Request Guidelines

Before submitting your PR:
- [ ] Run `pytest -v` to ensure all tests pass.
- [ ] Ensure any newly generated C compiles with `gcc -Wall -Wextra -Werror -O2` or MSVC without warnings.
- [ ] Avoid committing copyrighted commercial ROMs. Only homebrew ROMs or synthetic binary test cases belong in the repo.
- [ ] Link any related issues or roadmap items in your PR description.

---

## 💬 Getting Help & Discussions

If you have questions about ISA specifications, binary translation edge cases, or architecture design:
- Open a discussion in [GitHub Discussions](https://github.com/yefan911/automated-recompilers/discussions).
- Open an issue for questions or feature suggestions.
