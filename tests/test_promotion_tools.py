#!/usr/bin/env python3
"""
Unit tests for promotion automation tools:
- scripts/opcode_coverage.py
- scripts/generate_showcase.py
"""

import os
import sys
import json
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from scripts.opcode_coverage import calculate_coverage, generate_markdown, write_badge_json
from scripts.generate_showcase import (
    calculate_entropy,
    compute_entropy_slices,
    generate_mermaid_cfg,
    generate_markdown_showcase,
    generate_html_showcase
)
from src.lifter.arm_lifter import ArmLifter
from src.core.rom_detector import inspect_file


def test_opcode_coverage_calculation():
    coverage = calculate_coverage()
    assert "isas" in coverage
    assert "overall" in coverage

    isas = coverage["isas"]
    assert "ARM7TDMI (ARMv4T)" in isas
    assert "ARM Thumb-16" in isas
    assert "MIPS I / III" in isas
    assert "W65C816S" in isas

    overall = coverage["overall"]
    assert overall["implemented_count"] > 100
    assert overall["total_count"] > 150
    assert 0.0 < overall["percentage"] <= 100.0


def test_opcode_coverage_markdown_and_badges(tmp_path):
    coverage = calculate_coverage()
    md = generate_markdown(coverage)
    assert "# 📊 Instruction Lifter & Opcode Coverage" in md
    assert "ARM7TDMI" in md
    assert "W65C816S" in md

    # Write badge JSON to temp dir
    write_badge_json(coverage, str(tmp_path))
    badge_coverage_file = tmp_path / "badge_coverage.json"
    badge_consoles_file = tmp_path / "badge_consoles.json"
    coverage_file = tmp_path / "coverage.json"

    assert badge_coverage_file.exists()
    assert badge_consoles_file.exists()
    assert coverage_file.exists()

    with open(badge_coverage_file, "r") as f:
        data = json.load(f)
        assert data["schemaVersion"] == 1
        assert "Opcode Coverage" in data["label"]

    with open(badge_consoles_file, "r") as f:
        data = json.load(f)
        assert data["message"] == "GBA · N64 · PS1 · SNES"


def test_entropy_calculation():
    # Constant data has 0 entropy
    const_data = b"\x00" * 1024
    assert calculate_entropy(const_data) == 0.0

    # Diverse data has higher entropy
    random_like = bytes(range(256)) * 4
    ent = calculate_entropy(random_like)
    assert ent > 7.0

    slices = compute_entropy_slices(random_like, num_slices=4)
    assert len(slices) == 4
    assert slices[0]["entropy"] > 7.0


def test_generate_showcase_flow(tmp_path):
    rom_path = os.path.join(PROJECT_ROOT, "roms", "test", "hello_gba.gba")
    assert os.path.exists(rom_path)

    with open(rom_path, "rb") as f:
        rom_bytes = f.read()

    meta = inspect_file(rom_path)
    entropy_slices = compute_entropy_slices(rom_bytes, num_slices=8)
    lifter = ArmLifter(rom_bytes, base_vram=0x08000000)
    cfg = lifter.build_cfg(0x08000000)

    # Test Mermaid CFG generation
    mermaid_text = generate_mermaid_cfg(cfg)
    assert "graph TD" in mermaid_text
    assert "bb_08000000" in mermaid_text
    assert "-->" in mermaid_text

    # Test Markdown showcase generation
    md_output = generate_markdown_showcase(meta, cfg, entropy_slices, bench_time_ms=1.5)
    assert "Visual Showcase & Technical Architecture" in md_output
    assert "Discovered Basic Blocks" in md_output
    assert "Shannon Entropy" in md_output

    # Test HTML showcase generation
    html_output = generate_html_showcase(meta, cfg, entropy_slices, bench_time_ms=1.5)
    assert "<!DOCTYPE html>" in html_output
    assert "mermaid.initialize" in html_output
    assert "ArmCpuContext" in html_output


def test_opcode_bounty_tool():
    from scripts.opcode_bounty import format_quest, generate_markdown_bounties

    quest = format_quest("SWP")
    assert "Opcode Bounty: Implement `SWP`" in quest
    assert "ARM7TDMI" in quest
    assert "GBATEK" in quest
    assert "pytest -v" in quest

    md = generate_markdown_bounties()
    assert "# 🏆 Contributor Opcode Bounties" in md
    assert "ARM7TDMI" in md
    assert "ARM Thumb-16" in md
    assert "MIPS I / III" in md
    assert "W65C816S" in md
    assert "`WANTED` 🎯" in md


def test_benchmark_suite():
    from scripts.benchmark_suite import run_all_benchmarks

    res = run_all_benchmarks()
    assert "timestamp" in res
    assert "benchmarks" in res
    assert len(res["benchmarks"]) == 4

    for b in res["benchmarks"]:
        assert "architecture" in b
        assert b["ops_per_second"] > 0
        assert b["avg_latency_ms"] >= 0


def test_interactive_web_inspector_exists():
    index_path = os.path.join(PROJECT_ROOT, "docs", "index.html")
    assert os.path.exists(index_path)

    with open(index_path, "r", encoding="utf-8") as f:
        html = f.read()

    assert "<!DOCTYPE html>" in html
    assert "Automated Game ROM Recompiler" in html
    assert "GBA (ARM7TDMI)" in html
    assert "N64 (MIPS III)" in html
    assert "SNES (65816)" in html
    assert "PS1 (MIPS I)" in html
    assert "calculateBufferEntropy" in html

