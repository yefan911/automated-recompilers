#!/usr/bin/env python3
"""
Opcode Bounty & Good-First-Issue Generator for Automated Game ROM Recompiler.

Promotes developer onboarding and community contributions by turning unimplemented
opcodes across ARM7TDMI, Thumb-16, MIPS, and W65C816S into bite-sized, gamified tasks
with architectural specifications, code templates, and ready-to-run test cases.

Usage:
    python scripts/opcode_bounty.py                      # List available opcode bounties
    python scripts/opcode_bounty.py --isa "ARM Thumb-16" # Filter by ISA
    python scripts/opcode_bounty.py --generate-docs      # Output docs/CONTRIBUTOR_BOUNTIES.md
    python scripts/opcode_bounty.py --quest <OPCODE>     # Generate full issue template & test stub
"""

import argparse
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from scripts.opcode_coverage import ISA_DEFINITIONS

OPCODE_DETAILS = {
    # ARM7TDMI
    "SWP": {
        "summary": "Swap word between register and memory (atomic swap)",
        "isa": "ARM7TDMI (ARMv4T)",
        "file": "src/lifter/arm_lifter.py",
        "doc": "GBATEK ARM Memory Swaps (SWP / SWPB)",
        "c_stub": "uint32_t temp = mem_read32(ctx, ctx->r[rn]); mem_write32(ctx, ctx->r[rn], ctx->r[rm]); ctx->r[rd] = temp;",
        "test_hex": "E1010092"
    },
    "MRS": {
        "summary": "Move Program Status Register (CPSR/SPSR) to general register",
        "isa": "ARM7TDMI (ARMv4T)",
        "file": "src/lifter/arm_lifter.py",
        "doc": "GBATEK Status Register Access",
        "c_stub": "ctx->r[rd] = ctx->cpsr;",
        "test_hex": "E10F0000"
    },
    "MSR": {
        "summary": "Move general register to Program Status Register (CPSR/SPSR)",
        "isa": "ARM7TDMI (ARMv4T)",
        "file": "src/lifter/arm_lifter.py",
        "doc": "GBATEK Status Register Access",
        "c_stub": "ctx->cpsr = ctx->r[rm];",
        "test_hex": "E129F000"
    },
    # Thumb-16
    "LSL_IMM": {
        "summary": "Logical Shift Left by 5-bit Immediate",
        "isa": "ARM Thumb-16",
        "file": "src/lifter/thumb_lifter.py",
        "doc": "GBATEK Thumb Format 1: Move Shifted Register",
        "c_stub": "ctx->r[rd] = (uint32_t)(ctx->r[rm] << imm5);",
        "test_hex": "0008"
    },
    "LSR_IMM": {
        "summary": "Logical Shift Right by 5-bit Immediate",
        "isa": "ARM Thumb-16",
        "file": "src/lifter/thumb_lifter.py",
        "doc": "GBATEK Thumb Format 1: Move Shifted Register",
        "c_stub": "ctx->r[rd] = (uint32_t)(ctx->r[rm] >> imm5);",
        "test_hex": "0808"
    },
    "AND_REG": {
        "summary": "Bitwise AND between low registers (Rd = Rd & Rm)",
        "isa": "ARM Thumb-16",
        "file": "src/lifter/thumb_lifter.py",
        "doc": "GBATEK Thumb Format 5: ALU operations",
        "c_stub": "ctx->r[rd] = ctx->r[rd] & ctx->r[rm];",
        "test_hex": "4008"
    },
    "NEG_REG": {
        "summary": "Negate register (Rd = 0 - Rm)",
        "isa": "ARM Thumb-16",
        "file": "src/lifter/thumb_lifter.py",
        "doc": "GBATEK Thumb Format 5: ALU operations",
        "c_stub": "ctx->r[rd] = (uint32_t)(0 - ctx->r[rm]);",
        "test_hex": "4248"
    },
    # MIPS
    "MULT": {
        "summary": "Signed Multiply 32-bit registers into HI/LO",
        "isa": "MIPS I / III",
        "file": "src/lifter/mips_lifter.py",
        "doc": "MIPS Instruction Reference (MULT)",
        "c_stub": "int64_t prod = (int64_t)(int32_t)ctx->r[rs] * (int64_t)(int32_t)ctx->r[rt]; ctx->lo = (uint32_t)prod; ctx->hi = (uint32_t)(prod >> 32);",
        "test_hex": "00850018"
    },
    "MFHI": {
        "summary": "Move from HI register to destination register",
        "isa": "MIPS I / III",
        "file": "src/lifter/mips_lifter.py",
        "doc": "MIPS Instruction Reference (MFHI)",
        "c_stub": "ctx->r[rd] = ctx->hi;",
        "test_hex": "00001010"
    },
    "MFLO": {
        "summary": "Move from LO register to destination register",
        "isa": "MIPS I / III",
        "file": "src/lifter/mips_lifter.py",
        "doc": "MIPS Instruction Reference (MFLO)",
        "c_stub": "ctx->r[rd] = ctx->lo;",
        "test_hex": "00001012"
    },
    # SNES 65816
    "JSL": {
        "summary": "Jump to Subroutine Long (24-bit direct address)",
        "isa": "W65C816S",
        "file": "src/lifter/snes_lifter.py",
        "doc": "W65C816S Programming Manual: JSL",
        "c_stub": "/* Push return address and bank to stack */ return target_addr_24bit;",
        "test_hex": "220080A9"
    },
    "RTL": {
        "summary": "Return from Subroutine Long (pops 24-bit return PC + bank)",
        "isa": "W65C816S",
        "file": "src/lifter/snes_lifter.py",
        "doc": "W65C816S Programming Manual: RTL",
        "c_stub": "/* Pop bank and return address */ return ctx->return_addr;",
        "test_hex": "6B"
    }
}


def format_quest(opcode: str) -> str:
    details = OPCODE_DETAILS.get(opcode, {
        "summary": f"Implement instruction {opcode}",
        "isa": "General ISA",
        "file": "src/lifter/",
        "doc": "Architecture Reference Manual",
        "c_stub": f"/* Emit C logic for {opcode} */",
        "test_hex": "0000"
    })

    return f"""# 🎯 Opcode Bounty: Implement `{opcode}` ({details['isa']})

## 📖 Task Overview
- **Instruction**: `{opcode}`
- **Description**: {details['summary']}
- **Target File**: `{details['file']}`
- **Reference Doc**: {details['doc']}

---

## 🛠️ Implementation Guide

### 1. Identify Opcode Decoding
In `{details['file']}`, locate the instruction decode block and handle `{opcode}`:

```python
# Lowering for {opcode}:
ir_ops.append({{
    "pc": pc,
    "op": "{opcode}",
    "c_code": "{details['c_stub']}"
}})
```

### 2. Test Case
Create a test in the corresponding `tests/test_*_lifter.py`:

```python
def test_lift_{opcode.lower()}():
    code = bytes.fromhex("{details['test_hex']}")
    # Assert lifted instruction matches expected C code
    # pytest -v tests/test_lifters.py
```

### 3. Verify
Run pytest to verify all tests pass:
```bash
pytest -v
```

Submit a PR with your fix and earn your spot on the contributor leaderboard! 🚀
"""


def generate_markdown_bounties() -> str:
    lines = [
        "# 🏆 Contributor Opcode Bounties & Good First Issues",
        "",
        "> Welcome! Contributing to static binary translation is one of the best ways to master compilers, computer architecture, and low-level C.",
        "> Each bounty is a bite-sized, self-contained task with reference documentation and test templates.",
        "",
        "## 🎮 Available Opcode Bounties by Architecture",
        ""
    ]

    for isa_name, isa_info in ISA_DEFINITIONS.items():
        planned = isa_info.get("planned", [])
        if not planned:
            continue
        lines.append(f"### {isa_name} ({isa_info['console']})")
        lines.append(f"Source file: `{isa_info['source_file']}`\n")
        lines.append("| Opcode | Description | Difficulty | Status |")
        lines.append("| :--- | :--- | :---: | :---: |")

        for op in planned:
            details = OPCODE_DETAILS.get(op, {})
            desc = details.get("summary", "Standard instruction decoding & C lowering")
            difficulty = "Beginner (Good First Issue)" if len(op) <= 4 else "Intermediate"
            lines.append(f"| **`{op}`** | {desc} | {difficulty} | `WANTED` 🎯 |")
        lines.append("")

    lines.append("## 🚀 How to Claim a Bounty")
    lines.append("1. Pick an opcode from the table above.")
    lines.append("2. Generate the starter template: `python scripts/opcode_bounty.py --quest <OPCODE>`")
    lines.append("3. Implement the instruction and its unit test.")
    lines.append("4. Open a pull request targeting `main`!")
    lines.append("")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Opcode Bounty & Good-First-Issue Generator.")
    parser.add_argument("--isa", help="Filter bounties by ISA name.")
    parser.add_argument("--quest", help="Generate full issue markdown for a specific opcode.")
    parser.add_argument("--generate-docs", action="store_true", help="Generate docs/CONTRIBUTOR_BOUNTIES.md.")

    args = parser.parse_args()

    if args.quest:
        print(format_quest(args.quest.upper()))
        return

    if args.generate_docs:
        md = generate_markdown_bounties()
        out_path = os.path.join(PROJECT_ROOT, "docs", "CONTRIBUTOR_BOUNTIES.md")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(md)
        print(f"[OK] Generated {out_path}")
        return

    print("\n==========================================================================")
    print("           AUTOMATED GAME ROM RECOMPILER — OPCODE BOUNTIES                ")
    print("==========================================================================\n")
    for isa_name, isa_info in ISA_DEFINITIONS.items():
        if args.isa and args.isa.lower() not in isa_name.lower():
            continue
        planned = isa_info.get("planned", [])
        print(f"[{isa_name}] ({len(planned)} open bounties):")
        print("  " + ", ".join(planned[:12]) + ("..." if len(planned) > 12 else ""))
        print()

    print("To view full implementation guide for an opcode:")
    print("    python scripts/opcode_bounty.py --quest <OPCODE>\n")


if __name__ == "__main__":
    main()
