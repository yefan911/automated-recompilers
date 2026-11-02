# 🏆 Contributor Opcode Bounties & Good First Issues

> Welcome! Contributing to static binary translation is one of the best ways to master compilers, computer architecture, and low-level C.
> Each bounty is a bite-sized, self-contained task with reference documentation and test templates.

## 🎮 Available Opcode Bounties by Architecture

### ARM7TDMI (ARMv4T) (Game Boy Advance (ARM))
Source file: `src/lifter/arm_lifter.py`

| Opcode | Description | Difficulty | Status |
| :--- | :--- | :---: | :---: |
| **`MLA`** | Standard instruction decoding & C lowering | Beginner (Good First Issue) | `WANTED` 🎯 |
| **`UMULL`** | Standard instruction decoding & C lowering | Intermediate | `WANTED` 🎯 |
| **`UMLAL`** | Standard instruction decoding & C lowering | Intermediate | `WANTED` 🎯 |
| **`SMULL`** | Standard instruction decoding & C lowering | Intermediate | `WANTED` 🎯 |
| **`SMLAL`** | Standard instruction decoding & C lowering | Intermediate | `WANTED` 🎯 |
| **`LDM`** | Standard instruction decoding & C lowering | Beginner (Good First Issue) | `WANTED` 🎯 |
| **`STM`** | Standard instruction decoding & C lowering | Beginner (Good First Issue) | `WANTED` 🎯 |
| **`SWP`** | Swap word between register and memory (atomic swap) | Beginner (Good First Issue) | `WANTED` 🎯 |
| **`SWPB`** | Standard instruction decoding & C lowering | Beginner (Good First Issue) | `WANTED` 🎯 |
| **`MSR`** | Move general register to Program Status Register (CPSR/SPSR) | Beginner (Good First Issue) | `WANTED` 🎯 |
| **`MRS`** | Move Program Status Register (CPSR/SPSR) to general register | Beginner (Good First Issue) | `WANTED` 🎯 |
| **`LDRSH`** | Standard instruction decoding & C lowering | Intermediate | `WANTED` 🎯 |
| **`LDRSB`** | Standard instruction decoding & C lowering | Intermediate | `WANTED` 🎯 |

### ARM Thumb-16 (Game Boy Advance (Thumb))
Source file: `src/lifter/thumb_lifter.py`

| Opcode | Description | Difficulty | Status |
| :--- | :--- | :---: | :---: |
| **`LSL_IMM`** | Logical Shift Left by 5-bit Immediate | Intermediate | `WANTED` 🎯 |
| **`LSR_IMM`** | Logical Shift Right by 5-bit Immediate | Intermediate | `WANTED` 🎯 |
| **`ASR_IMM`** | Standard instruction decoding & C lowering | Intermediate | `WANTED` 🎯 |
| **`AND_REG`** | Bitwise AND between low registers (Rd = Rd & Rm) | Intermediate | `WANTED` 🎯 |
| **`EOR_REG`** | Standard instruction decoding & C lowering | Intermediate | `WANTED` 🎯 |
| **`ORR_REG`** | Standard instruction decoding & C lowering | Intermediate | `WANTED` 🎯 |
| **`BIC_REG`** | Standard instruction decoding & C lowering | Intermediate | `WANTED` 🎯 |
| **`MVN_REG`** | Standard instruction decoding & C lowering | Intermediate | `WANTED` 🎯 |
| **`TST_REG`** | Standard instruction decoding & C lowering | Intermediate | `WANTED` 🎯 |
| **`NEG_REG`** | Negate register (Rd = 0 - Rm) | Intermediate | `WANTED` 🎯 |
| **`MUL_REG`** | Standard instruction decoding & C lowering | Intermediate | `WANTED` 🎯 |
| **`LDMIA`** | Standard instruction decoding & C lowering | Intermediate | `WANTED` 🎯 |
| **`STMIA`** | Standard instruction decoding & C lowering | Intermediate | `WANTED` 🎯 |

### MIPS I / III (Nintendo 64 & PlayStation 1)
Source file: `src/lifter/mips_lifter.py`

| Opcode | Description | Difficulty | Status |
| :--- | :--- | :---: | :---: |
| **`SLLV`** | Standard instruction decoding & C lowering | Beginner (Good First Issue) | `WANTED` 🎯 |
| **`SRLV`** | Standard instruction decoding & C lowering | Beginner (Good First Issue) | `WANTED` 🎯 |
| **`SRAV`** | Standard instruction decoding & C lowering | Beginner (Good First Issue) | `WANTED` 🎯 |
| **`MULT`** | Signed Multiply 32-bit registers into HI/LO | Beginner (Good First Issue) | `WANTED` 🎯 |
| **`MULTU`** | Standard instruction decoding & C lowering | Intermediate | `WANTED` 🎯 |
| **`DIV`** | Standard instruction decoding & C lowering | Beginner (Good First Issue) | `WANTED` 🎯 |
| **`DIVU`** | Standard instruction decoding & C lowering | Beginner (Good First Issue) | `WANTED` 🎯 |
| **`MFHI`** | Move from HI register to destination register | Beginner (Good First Issue) | `WANTED` 🎯 |
| **`MFLO`** | Move from LO register to destination register | Beginner (Good First Issue) | `WANTED` 🎯 |
| **`MTHI`** | Standard instruction decoding & C lowering | Beginner (Good First Issue) | `WANTED` 🎯 |
| **`MTLO`** | Standard instruction decoding & C lowering | Beginner (Good First Issue) | `WANTED` 🎯 |
| **`NOR`** | Standard instruction decoding & C lowering | Beginner (Good First Issue) | `WANTED` 🎯 |
| **`SYSCALL`** | Standard instruction decoding & C lowering | Intermediate | `WANTED` 🎯 |
| **`BREAK`** | Standard instruction decoding & C lowering | Intermediate | `WANTED` 🎯 |
| **`LWL`** | Standard instruction decoding & C lowering | Beginner (Good First Issue) | `WANTED` 🎯 |
| **`LWR`** | Standard instruction decoding & C lowering | Beginner (Good First Issue) | `WANTED` 🎯 |
| **`SWL`** | Standard instruction decoding & C lowering | Beginner (Good First Issue) | `WANTED` 🎯 |
| **`SWR`** | Standard instruction decoding & C lowering | Beginner (Good First Issue) | `WANTED` 🎯 |
| **`COP0_MFC0`** | Standard instruction decoding & C lowering | Intermediate | `WANTED` 🎯 |
| **`COP0_MTC0`** | Standard instruction decoding & C lowering | Intermediate | `WANTED` 🎯 |
| **`COP1_FLOAT`** | Standard instruction decoding & C lowering | Intermediate | `WANTED` 🎯 |
| **`GTE_COP2`** | Standard instruction decoding & C lowering | Intermediate | `WANTED` 🎯 |

### W65C816S (Super Nintendo Entertainment System (SNES))
Source file: `src/lifter/snes_lifter.py`

| Opcode | Description | Difficulty | Status |
| :--- | :--- | :---: | :---: |
| **`PER`** | Standard instruction decoding & C lowering | Beginner (Good First Issue) | `WANTED` 🎯 |
| **`MVN`** | Standard instruction decoding & C lowering | Beginner (Good First Issue) | `WANTED` 🎯 |
| **`MVP`** | Standard instruction decoding & C lowering | Beginner (Good First Issue) | `WANTED` 🎯 |
| **`WAI`** | Standard instruction decoding & C lowering | Beginner (Good First Issue) | `WANTED` 🎯 |
| **`STP`** | Standard instruction decoding & C lowering | Beginner (Good First Issue) | `WANTED` 🎯 |
| **`WDM`** | Standard instruction decoding & C lowering | Beginner (Good First Issue) | `WANTED` 🎯 |
| **`RTI`** | Standard instruction decoding & C lowering | Beginner (Good First Issue) | `WANTED` 🎯 |
| **`BRK`** | Standard instruction decoding & C lowering | Beginner (Good First Issue) | `WANTED` 🎯 |
| **`COP`** | Standard instruction decoding & C lowering | Beginner (Good First Issue) | `WANTED` 🎯 |

## 🚀 How to Claim a Bounty
1. Pick an opcode from the table above.
2. Generate the starter template: `python scripts/opcode_bounty.py --quest <OPCODE>`
3. Implement the instruction and its unit test.
4. Open a pull request targeting `main`!
