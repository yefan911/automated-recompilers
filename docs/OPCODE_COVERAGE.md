# 📊 Instruction Lifter & Opcode Coverage

This document tracks Ahead-Of-Time (AOT) instruction coverage across all supported console architectures in **Automated Game ROM Recompiler**.

> **Overall Core Opcode Coverage:** **84.9%** (208/245 core opcodes implemented)

| Architecture | Target Console | Implemented | Target Baseline | Coverage | Status |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **ARM7TDMI (ARMv4T)** | Game Boy Advance (ARM) | 30 | 43 | **69.8%** | 🟡 In Progress |
| **ARM Thumb-16** | Game Boy Advance (Thumb) | 42 | 47 | **89.4%** | 🟢 Mature |
| **MIPS I / III** | Nintendo 64 & PlayStation 1 | 54 | 64 | **84.4%** | 🟢 Mature |
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
**Coverage:** **89.4%** (42 implemented / 5 prioritized upcoming)

### ✅ Implemented Instructions
`ADD_HI`, `ADD_IMM`, `ADD_PC_IMM`, `ADD_REG`, `ADD_SP`, `ADD_SP_IMM`, `AND_REG`, `ASR_IMM`, `BIC_REG`, `BL_THUMB`, `BRANCH`, `BX`, `B_COND`, `CMP_HI`, `CMP_IMM`, `EOR_REG`, `HALT`, `LDMIA`, `LDR`, `LDRH`, `LDR_PC`, `LDR_SP`, `LSL_IMM`, `LSR_IMM`, `MOV_HI`, `MOV_IMM`, `MUL_REG`, `MVN_REG`, `NEG_REG`, `ORR_REG`, `POP`, `POP_PC`, `PUSH`, `STMIA`, `STR`, `STRH`, `STR_SP`, `SUB_IMM`, `SUB_REG`, `SWI`, `THUMB_RAW`, `TST_REG`

### 🎯 Prioritized Missing Instructions (Community Welcome!)
`BKPT`, `REV`, `REV16`, `REVSH`, `SETEND`

> 💡 *Want to implement one of these opcodes? Check out our [Instruction Contribution Guide](../CONTRIBUTING.md#adding-a-new-instruction-opcode-walkthrough) and submit a PR using the [New Instruction Template](../.github/ISSUE_TEMPLATE/new_instruction.yml).*

---

## 🕹️ MIPS I / III
**Target Console:** Nintendo 64 & PlayStation 1  
**Lifter Source:** [`src/lifter/mips_lifter.py`](../src/lifter/mips_lifter.py)  
**Coverage:** **84.4%** (54 implemented / 10 prioritized upcoming)

### ✅ Implemented Instructions
`ADD`, `ADDI`, `ADDIU`, `ADDU`, `AND`, `ANDI`, `BEQ`, `BGEZ`, `BGTZ`, `BLEZ`, `BLTZ`, `BNE`, `COP0_MFC0`, `COP0_MTC0`, `DELAY_SLOT`, `DIV`, `DIVU`, `GTE_COP2`, `J`, `JAL`, `JALR`, `JR`, `LB`, `LBU`, `LH`, `LHU`, `LUI`, `LW`, `LWC2`, `MFHI`, `MFLO`, `MTHI`, `MTLO`, `MULT`, `MULTU`, `NOP`, `NOR`, `OR`, `ORI`, `SB`, `SH`, `SLL`, `SLT`, `SLTI`, `SLTIU`, `SLTU`, `SRA`, `SRL`, `SUB`, `SUBU`, `SW`, `SWC2`, `XOR`, `XORI`

### 🎯 Prioritized Missing Instructions (Community Welcome!)
`BREAK`, `COP1_FLOAT`, `LWL`, `LWR`, `SLLV`, `SRAV`, `SRLV`, `SWL`, `SWR`, `SYSCALL`

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
