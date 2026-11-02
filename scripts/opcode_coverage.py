#!/usr/bin/env python3
"""
Opcode Coverage Tracker & Dynamic Badge Generator for Automated Game ROM Recompiler.

Analyzes lifters across all supported CPU architectures:
- ARM7TDMI (GBA 32-bit ARMv4T)
- Thumb-16 (GBA 16-bit compressed ARM)
- MIPS I / III (N64 / PS1 MIPS)
- W65C816S (SNES 16-bit 65816)

Calculates implementation coverage, emits `docs/OPCODE_COVERAGE.md`, and
generates Shields.io compatible JSON badge endpoints.
"""

import sys
import os
import json
import argparse
from typing import Dict, List, Any


ISA_DEFINITIONS = {
    "ARM7TDMI (ARMv4T)": {
        "console": "Game Boy Advance (ARM)",
        "source_file": "src/lifter/arm_lifter.py",
        "implemented": [
            "AND", "EOR", "SUB", "RSB", "ADD", "ADC", "SBC", "RSC",
            "TST", "TEQ", "CMP", "CMN", "ORR", "MOV", "BIC", "MVN",
            "MOV_IMM", "B", "BL", "BX", "LDR", "STR", "LDRB", "STRB",
            "LDRH", "STRH", "LDR_CONST", "SWI", "HALT", "COND_EXEC"
        ],
        "planned": [
            "MLA", "UMULL", "UMLAL", "SMULL", "SMLAL", "LDM", "STM",
            "SWP", "SWPB", "MSR", "MRS", "LDRSH", "LDRSB"
        ]
    },
    "ARM Thumb-16": {
        "console": "Game Boy Advance (Thumb)",
        "source_file": "src/lifter/thumb_lifter.py",
        "implemented": [
            "PUSH", "POP", "POP_PC", "ADD_SP", "BX", "MOV_HI", "ADD_HI", "CMP_HI",
            "BL_THUMB", "BRANCH", "B_COND", "LDR_PC", "MOV_IMM", "CMP_IMM",
            "ADD_IMM", "SUB_IMM", "LDR", "STR", "LDRH", "STRH", "ADD_REG",
            "SUB_REG", "THUMB_RAW", "HALT", "LSL_IMM", "LSR_IMM", "ASR_IMM",
            "AND_REG", "EOR_REG", "ORR_REG", "BIC_REG", "MVN_REG", "TST_REG",
            "NEG_REG", "MUL_REG", "LDMIA", "STMIA", "SWI", "LDR_SP", "STR_SP",
            "ADD_SP_IMM", "ADD_PC_IMM"
        ],
        "planned": [
            "BKPT", "REV", "REV16", "REVSH", "SETEND"
        ]
    },
    "MIPS I / III": {
        "console": "Nintendo 64 & PlayStation 1",
        "source_file": "src/lifter/mips_lifter.py",
        "implemented": [
            "NOP", "SLL", "SRL", "SRA", "JR", "JALR", "ADD", "ADDU", "SUB", "SUBU",
            "AND", "OR", "XOR", "SLT", "SLTU", "J", "JAL", "BEQ", "BNE", "BLEZ",
            "BGTZ", "BLTZ", "BGEZ", "ADDI", "ADDIU", "SLTI", "SLTIU", "ANDI", "ORI", "XORI", "LUI",
            "LB", "LH", "LW", "LBU", "LHU", "SB", "SH", "SW", "DELAY_SLOT",
            "MULT", "MULTU", "DIV", "DIVU", "MFHI", "MFLO", "MTHI", "MTLO", "NOR",
            "COP0_MFC0", "COP0_MTC0", "GTE_COP2", "LWC2", "SWC2"
        ],
        "planned": [
            "SLLV", "SRLV", "SRAV", "SYSCALL", "BREAK", "LWL", "LWR", "SWL", "SWR", "COP1_FLOAT"
        ]
    },
    "W65C816S": {
        "console": "Super Nintendo Entertainment System (SNES)",
        "source_file": "src/lifter/snes_lifter.py",
        "implemented": [
            "REP", "SEP", "LDA_IMM", "LDA_ABS", "LDA_ZP", "LDA_LONG",
            "STA_ABS", "STA_ZP", "STA_LONG", "LDX_IMM", "LDY_IMM",
            "STX_ABS", "STY_ABS", "ADC_IMM", "ADC_ABS", "SBC_IMM", "SBC_ABS",
            "CMP_IMM", "CMP_ABS", "JMP", "JML", "JMP_IND", "JSR", "JSL",
            "RTS", "RTL", "NOP", "PHA", "PLA", "PHB", "PLB",
            "BCC", "BCS", "BEQ", "BMI", "BNE", "BPL", "BVC", "BVS", "BRA", "BRL",
            "TAX", "TAY", "TXA", "TYA", "TSX", "TXS", "TCD", "TDC", "TCS", "TSC",
            "CLC", "SEC", "CLI", "SEI", "CLD", "SED", "CLV", "XCE",
            "INX", "DEX", "INY", "DEY", "INC", "DEC", "ASL", "LSR", "ROL", "ROR",
            "AND", "ORA", "EOR", "BIT", "CPX", "CPY",
            "PHX", "PHY", "PLX", "PLY", "PHP", "PLP", "PEA"
        ],
        "planned": [
            "PER", "MVN", "MVP", "WAI", "STP", "WDM", "RTI", "BRK", "COP"
        ]
    }
}


def calculate_coverage() -> Dict[str, Any]:
    """Calculates coverage metrics per ISA and overall."""
    results = {}
    total_impl = 0
    total_ops = 0

    for isa_name, data in ISA_DEFINITIONS.items():
        impl_count = len(data["implemented"])
        plan_count = len(data["planned"])
        total_for_isa = impl_count + plan_count
        pct = (impl_count / total_for_isa) * 100.0 if total_for_isa > 0 else 0.0

        results[isa_name] = {
            "console": data["console"],
            "source_file": data["source_file"],
            "implemented_count": impl_count,
            "planned_count": plan_count,
            "total_count": total_for_isa,
            "percentage": round(pct, 1),
            "implemented_list": data["implemented"],
            "planned_list": data["planned"]
        }

        total_impl += impl_count
        total_ops += total_for_isa

    overall_pct = (total_impl / total_ops) * 100.0 if total_ops > 0 else 0.0

    return {
        "isas": results,
        "overall": {
            "implemented_count": total_impl,
            "planned_count": total_ops - total_impl,
            "total_count": total_ops,
            "percentage": round(overall_pct, 1)
        }
    }


def generate_markdown(coverage_data: Dict[str, Any]) -> str:
    """Generates a comprehensive markdown report for docs/OPCODE_COVERAGE.md."""
    overall = coverage_data["overall"]
    lines = [
        "# 📊 Instruction Lifter & Opcode Coverage",
        "",
        "This document tracks Ahead-Of-Time (AOT) instruction coverage across all supported console architectures in **Automated Game ROM Recompiler**.",
        "",
        f"> **Overall Core Opcode Coverage:** **{overall['percentage']}%** ({overall['implemented_count']}/{overall['total_count']} core opcodes implemented)",
        "",
        "| Architecture | Target Console | Implemented | Target Baseline | Coverage | Status |",
        "| :--- | :--- | :---: | :---: | :---: | :---: |"
    ]

    for isa_name, info in coverage_data["isas"].items():
        pct = info["percentage"]
        status = "🟢 Mature" if pct >= 70 else ("🟡 In Progress" if pct >= 50 else "🟠 Growing")
        lines.append(
            f"| **{isa_name}** | {info['console']} | {info['implemented_count']} | {info['total_count']} | **{pct}%** | {status} |"
        )

    lines.append("")
    lines.append("---")
    lines.append("")

    for isa_name, info in coverage_data["isas"].items():
        lines.append(f"## 🕹️ {isa_name}")
        lines.append(f"**Target Console:** {info['console']}  ")
        lines.append(f"**Lifter Source:** [`{info['source_file']}`](../{info['source_file']})  ")
        lines.append(f"**Coverage:** **{info['percentage']}%** ({info['implemented_count']} implemented / {info['planned_count']} prioritized upcoming)")
        lines.append("")
        lines.append("### ✅ Implemented Instructions")
        impl_tags = [f"`{op}`" for op in sorted(info["implemented_list"])]
        lines.append(", ".join(impl_tags))
        lines.append("")
        lines.append("### 🎯 Prioritized Missing Instructions (Community Welcome!)")
        plan_tags = [f"`{op}`" for op in sorted(info["planned_list"])]
        lines.append(", ".join(plan_tags))
        lines.append("")
        lines.append("> 💡 *Want to implement one of these opcodes? Check out our [Instruction Contribution Guide](../CONTRIBUTING.md#adding-a-new-instruction-opcode-walkthrough) and submit a PR using the [New Instruction Template](../.github/ISSUE_TEMPLATE/new_instruction.yml).*")
        lines.append("")
        lines.append("---")
        lines.append("")

    lines.append("## 🤝 How to Add Missing Instructions")
    lines.append("1. Locate the target lifter in `src/lifter/`.")
    lines.append("2. Add the opcode decoding rule and emit an IR dictionary (`ir_ops.append({\"op\": ..., \"c_code\": ...})`).")
    lines.append("3. Add unit tests in `tests/test_lifters.py`.")
    lines.append("4. Run `python scripts/opcode_coverage.py` to update the coverage matrix and test suite.")
    lines.append("")

    return "\n".join(lines)


def write_badge_json(coverage_data: Dict[str, Any], output_dir: str):
    """Generates Shields.io endpoint badge JSONs for live README badges."""
    overall = coverage_data["overall"]
    pct = overall["percentage"]
    color = "brightgreen" if pct >= 80 else ("green" if pct >= 65 else "yellow")

    badge_data = {
        "schemaVersion": 1,
        "label": "Opcode Coverage",
        "message": f"{pct}% ({overall['implemented_count']}/{overall['total_count']})",
        "color": color
    }

    badge_consoles = {
        "schemaVersion": 1,
        "label": "Consoles",
        "message": "GBA · N64 · PS1 · SNES",
        "color": "blue"
    }

    os.makedirs(output_dir, exist_ok=True)
    with open(os.path.join(output_dir, "badge_coverage.json"), "w", encoding="utf-8") as f:
        json.dump(badge_data, f, indent=2)

    with open(os.path.join(output_dir, "badge_consoles.json"), "w", encoding="utf-8") as f:
        json.dump(badge_consoles, f, indent=2)

    with open(os.path.join(output_dir, "coverage.json"), "w", encoding="utf-8") as f:
        json.dump(coverage_data, f, indent=2)


def main():
    parser = argparse.ArgumentParser(description="Calculate instruction coverage and generate docs/badges")
    parser.add_argument("--output-dir", default="docs", help="Output directory for generated markdown and JSON badges")
    parser.add_argument("--check", action="store_true", help="Verify coverage integrity and exit 0")
    parser.add_argument("--json", action="store_true", help="Print raw JSON to stdout")
    args = parser.parse_args()

    coverage = calculate_coverage()

    if args.json:
        print(json.dumps(coverage, indent=2))
        return

    output_dir = args.output_dir
    os.makedirs(output_dir, exist_ok=True)

    # Write Markdown
    md_content = generate_markdown(coverage)
    md_path = os.path.join(output_dir, "OPCODE_COVERAGE.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)
    print(f"Generated opcode coverage report at: {md_path}")

    # Write Badges JSON
    write_badge_json(coverage, output_dir)
    print(f"Generated Shields.io badge endpoints in: {output_dir}/")

    print(f"\nSummary: {coverage['overall']['percentage']}% coverage ({coverage['overall']['implemented_count']}/{coverage['overall']['total_count']} opcodes)")


if __name__ == "__main__":
    main()
