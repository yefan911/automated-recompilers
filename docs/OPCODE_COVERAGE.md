# 📊 Instruction Lifter & Opcode Coverage

This document tracks Ahead-Of-Time (AOT) instruction coverage across all supported console architectures in **Automated Game ROM Recompiler**.

> **Overall Core Opcode Coverage:** **75.3%** (174/231 core opcodes implemented)

| Architecture | Target Console | Implemented | Target Baseline | Coverage | Status |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **ARM7TDMI (ARMv4T)** | Game Boy Advance (ARM) | 30 | 43 | **69.8%** | 🟡 In Progress |
| **ARM Thumb-16** | Game Boy Advance (Thumb) | 24 | 37 | **64.9%** | 🟡 In Progress |
| **MIPS I / III** | Nintendo 64 & PlayStation 1 | 38 | 60 | **63.3%** | 🟡 In Progress |
| **W65C816S** | Super Nintendo Entertainment System (SNES) | 82 | 91 | **90.1%** | 🟢 Mature |

---

## 🕹️ ARM7TDMI (ARMv4T)
**Target Console:** Game Boy Advance (ARM)  
**Lifter Source:** [`src/lifter/arm_lifter.py`](../src/lifter/arm_lifter.py)  
**Coverage:** **69.8%** (30 implemented / 13 prioritized upcoming)

### ✅ Implemented Instructions
`ADC`, `ADD`, `AND`, `B`, `BIC`, `BL`, `BX`, `CMN`, `CMP`, `COND_EXEC`, `EOR`, `HALT`, `LDR`, `LDRB`, `LDRH`, `LDR_CONST`, `MOV`, `MOV_IMM`, `MVN`, `ORR`, `RSB`, `RSC`, `SBC`, `STR`, `STRB`, `STRH`, `SUB`, `SWI`, `TEQ`, `TST`

### 🎯 Prioritized Missing Instructions (Community Welcome!)
`LDM`, `LDRSB`, `LDRSH`, `MLA`, `MRS`, `MSR`, `SMLAL`, `SMULL`, `STM`, `SWP`, `SWPB`, `UMLAL`, `UMULL`

> 💡 *Want to implement one of these opcodes? Check out our [Instruction Contribution Guide](../CONTRIBUTING.md#adding-a-new-instruction-opcode-walkthrough) and submit a PR using the [New Instruction Template](../.github/ISSUE_TEMPLATE/new_instruction.yml).*

---

## 🕹️ ARM Thumb-16
**Target Console:** Game Boy Advance (Thumb)  
**Lifter Source:** [`src/lifter/thumb_lifter.py`](../src/lifter/thumb_lifter.py)  
**Coverage:** **64.9%** (24 implemented / 13 prioritized upcoming)

### ✅ Implemented Instructions
`ADD_HI`, `ADD_IMM`, `ADD_REG`, `ADD_SP`, `BL_THUMB`, `BRANCH`, `BX`, `B_COND`, `CMP_HI`, `CMP_IMM`, `HALT`, `LDR`, `LDRH`, `LDR_PC`, `MOV_HI`, `MOV_IMM`, `POP`, `POP_PC`, `PUSH`, `STR`, `STRH`, `SUB_IMM`, `SUB_REG`, `THUMB_RAW`

### 🎯 Prioritized Missing Instructions (Community Welcome!)
`AND_REG`, `ASR_IMM`, `BIC_REG`, `EOR_REG`, `LDMIA`, `LSL_IMM`, `LSR_IMM`, `MUL_REG`, `MVN_REG`, `NEG_REG`, `ORR_REG`, `STMIA`, `TST_REG`

> 💡 *Want to implement one of these opcodes? Check out our [Instruction Contribution Guide](../CONTRIBUTING.md#adding-a-new-instruction-opcode-walkthrough) and submit a PR using the [New Instruction Template](../.github/ISSUE_TEMPLATE/new_instruction.yml).*

---

## 🕹️ MIPS I / III
**Target Console:** Nintendo 64 & PlayStation 1  
**Lifter Source:** [`src/lifter/mips_lifter.py`](../src/lifter/mips_lifter.py)  
**Coverage:** **63.3%** (38 implemented / 22 prioritized upcoming)

### ✅ Implemented Instructions
`ADD`, `ADDI`, `ADDIU`, `ADDU`, `AND`, `ANDI`, `BEQ`, `BGTZ`, `BLEZ`, `BNE`, `DELAY_SLOT`, `J`, `JAL`, `JALR`, `JR`, `LB`, `LBU`, `LH`, `LHU`, `LUI`, `LW`, `NOP`, `OR`, `ORI`, `SB`, `SH`, `SLL`, `SLT`, `SLTI`, `SLTIU`, `SLTU`, `SRA`, `SRL`, `SUB`, `SUBU`, `SW`, `XOR`, `XORI`

### 🎯 Prioritized Missing Instructions (Community Welcome!)
`BREAK`, `COP0_MFC0`, `COP0_MTC0`, `COP1_FLOAT`, `DIV`, `DIVU`, `GTE_COP2`, `LWL`, `LWR`, `MFHI`, `MFLO`, `MTHI`, `MTLO`, `MULT`, `MULTU`, `NOR`, `SLLV`, `SRAV`, `SRLV`, `SWL`, `SWR`, `SYSCALL`

> 💡 *Want to implement one of these opcodes? Check out our [Instruction Contribution Guide](../CONTRIBUTING.md#adding-a-new-instruction-opcode-walkthrough) and submit a PR using the [New Instruction Template](../.github/ISSUE_TEMPLATE/new_instruction.yml).*

---

## 🕹️ W65C816S
**Target Console:** Super Nintendo Entertainment System (SNES)  
**Lifter Source:** [`src/lifter/snes_lifter.py`](../src/lifter/snes_lifter.py)  
**Coverage:** **90.1%** (82 implemented / 9 prioritized upcoming)

### ✅ Implemented Instructions
`ADC_ABS`, `ADC_IMM`, `AND`, `ASL`, `BCC`, `BCS`, `BEQ`, `BIT`, `BMI`, `BNE`, `BPL`, `BRA`, `BRL`, `BVC`, `BVS`, `CLC`, `CLD`, `CLI`, `CLV`, `CMP_ABS`, `CMP_IMM`, `CPX`, `CPY`, `DEC`, `DEX`, `DEY`, `EOR`, `INC`, `INX`, `INY`, `JML`, `JMP`, `JMP_IND`, `JSL`, `JSR`, `LDA_ABS`, `LDA_IMM`, `LDA_LONG`, `LDA_ZP`, `LDX_IMM`, `LDY_IMM`, `LSR`, `NOP`, `ORA`, `PEA`, `PHA`, `PHB`, `PHP`, `PHX`, `PHY`, `PLA`, `PLB`, `PLP`, `PLX`, `PLY`, `REP`, `ROL`, `ROR`, `RTL`, `RTS`, `SBC_ABS`, `SBC_IMM`, `SEC`, `SED`, `SEI`, `SEP`, `STA_ABS`, `STA_LONG`, `STA_ZP`, `STX_ABS`, `STY_ABS`, `TAX`, `TAY`, `TCD`, `TCS`, `TDC`, `TSC`, `TSX`, `TXA`, `TXS`, `TYA`, `XCE`

### 🎯 Prioritized Missing Instructions (Community Welcome!)
`BRK`, `COP`, `MVN`, `MVP`, `PER`, `RTI`, `STP`, `WAI`, `WDM`

> 💡 *Want to implement one of these opcodes? Check out our [Instruction Contribution Guide](../CONTRIBUTING.md#adding-a-new-instruction-opcode-walkthrough) and submit a PR using the [New Instruction Template](../.github/ISSUE_TEMPLATE/new_instruction.yml).*

---

## 🤝 How to Add Missing Instructions
1. Locate the target lifter in `src/lifter/`.
2. Add the opcode decoding rule and emit an IR dictionary (`ir_ops.append({"op": ..., "c_code": ...})`).
3. Add unit tests in `tests/test_lifters.py`.
4. Run `python scripts/opcode_coverage.py` to update the coverage matrix and test suite.
