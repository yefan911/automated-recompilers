## 📝 Summary of Changes

A concise description of the changes introduced in this pull request.

## 🎯 Target Component
- [ ] Core / Detector (`src/core/`)
- [ ] Instruction Lifter (`src/lifter/`)
  - [ ] ARM7TDMI (`arm_lifter.py`)
  - [ ] Thumb-16 (`thumb_lifter.py`)
  - [ ] MIPS I / III (`mips_lifter.py`)
  - [ ] 65816 (`snes_lifter.py`)
- [ ] CFG / Dispatch Trampoline (`cfg.py`)
- [ ] Hardware Runtime / HAL (`src/runtime/`)
- [ ] GUI / CLI / Packaging (`gui.py`, `recompile.py`, `package_exe.py`)
- [ ] Documentation / CI

## 🧪 Verification & Testing
- [ ] Ran `pytest -v` (All tests pass)
- [ ] Generated C output verified with clean compiler flags (`-Wall -Wextra -Werror`)
- [ ] Verified on test ROM: `python recompile.py roms/test/hello_gba.gba`

## 🔗 Related Issues
Closes #
