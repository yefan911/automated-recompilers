#!/usr/bin/env python3
"""
Automated Recompilation Benchmarking Suite

Measures CFG construction speed, instruction lift throughput (ops/second),
and memory efficiency across ARM7TDMI, Thumb-16, MIPS I/III, and W65C816S lifters.

Usage:
    python scripts/benchmark_suite.py
    python scripts/benchmark_suite.py --json
"""

import argparse
import json
import os
import sys
import time

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.lifter.arm_lifter import ArmLifter
from src.lifter.thumb_lifter import ThumbLifter
from src.lifter.mips_lifter import MipsLifter
from src.lifter.snes_lifter import SnesLifter


def benchmark_arm_lifter(iterations: int = 50) -> dict:
    """Benchmark ARM7TDMI lifter on hello_gba.gba entry point."""
    rom_path = os.path.join(PROJECT_ROOT, "roms", "test", "hello_gba.gba")
    if not os.path.exists(rom_path):
        return {"status": "skipped", "reason": "hello_gba.gba not found"}

    with open(rom_path, "rb") as f:
        rom_bytes = f.read()

    start_time = time.perf_counter()
    total_blocks = 0
    total_ops = 0

    for _ in range(iterations):
        lifter = ArmLifter(rom_bytes, base_vram=0x08000000)
        cfg = lifter.build_cfg(0x08000000)
        total_blocks += len(cfg.blocks)
        total_ops += sum(len(b.instructions) for b in cfg.blocks.values())

    elapsed = time.perf_counter() - start_time
    ops_per_sec = (total_ops / elapsed) if elapsed > 0 else 0
    avg_latency_ms = (elapsed / iterations) * 1000.0

    return {
        "architecture": "ARM7TDMI (GBA)",
        "iterations": iterations,
        "elapsed_seconds": round(elapsed, 4),
        "avg_latency_ms": round(avg_latency_ms, 3),
        "ops_per_second": round(ops_per_sec, 1),
        "blocks_per_iteration": total_blocks // iterations,
        "ops_per_iteration": total_ops // iterations
    }


def benchmark_thumb_lifter(iterations: int = 100) -> dict:
    """Benchmark Thumb-16 lifter with a synthetic subroutine."""
    # Synthetic Thumb-16 instructions (MOV, ADD, CMP, BNE, PUSH, POP, BX)
    thumb_code = bytes([
        0x01, 0x20,  # MOV R0, #1
        0x02, 0x30,  # ADD R0, #2
        0x0A, 0x28,  # CMP R0, #10
        0xFD, 0xD1,  # BNE -3
        0x01, 0xB4,  # PUSH {r0}
        0x01, 0xBC,  # POP {r0}
        0x70, 0x47,  # BX LR
    ])

    start_time = time.perf_counter()
    total_ops = 0

    for _ in range(iterations):
        lifter = ThumbLifter(thumb_code, base_vram=0x08000100)
        ops, targets = lifter.lift_block(0x08000100)
        total_ops += len(ops)

    elapsed = time.perf_counter() - start_time
    ops_per_sec = (total_ops / elapsed) if elapsed > 0 else 0
    avg_latency_ms = (elapsed / iterations) * 1000.0

    return {
        "architecture": "ARM Thumb-16 (GBA)",
        "iterations": iterations,
        "elapsed_seconds": round(elapsed, 4),
        "avg_latency_ms": round(avg_latency_ms, 3),
        "ops_per_second": round(ops_per_sec, 1),
        "ops_per_iteration": total_ops // iterations
    }


def benchmark_mips_lifter(iterations: int = 50) -> dict:
    """Benchmark MIPS lifter on synthetic MIPS binary."""
    # Synthetic MIPS instructions
    import struct
    instructions = [
        0x3C088020,  # LUI $t0, 0x8020
        0x25080410,  # ADDIU $t0, $t0, 0x0410
        0x15000002,  # BNE $t0, $zero, +2
        0x00000000,  # NOP (delay slot)
        0x03E00008,  # JR $ra
        0x00000000,  # NOP
    ]
    rom_bytes = struct.pack(f">{len(instructions)}I", *instructions)
    entry = 0x80200400

    start_time = time.perf_counter()
    total_ops = 0

    for _ in range(iterations):
        lifter = MipsLifter(rom_bytes, base_vram=entry)
        cfg = lifter.build_cfg(entry, max_blocks=20)
        total_ops += sum(len(b.instructions) for b in cfg.blocks.values())

    elapsed = time.perf_counter() - start_time
    ops_per_sec = (total_ops / elapsed) if elapsed > 0 else 0
    avg_latency_ms = (elapsed / iterations) * 1000.0

    return {
        "architecture": "MIPS I / III (N64 / PS1)",
        "iterations": iterations,
        "elapsed_seconds": round(elapsed, 4),
        "avg_latency_ms": round(avg_latency_ms, 3),
        "ops_per_second": round(ops_per_sec, 1),
        "ops_per_iteration": total_ops // iterations
    }


def benchmark_snes_lifter(iterations: int = 50) -> dict:
    """Benchmark SNES W65C816S lifter."""
    # Synthetic SNES sequence (SEI, CLC, XCE, REP #$30, LDA #$01FF, STA $00, RTS)
    snes_bytes = bytes([
        0x78,        # SEI
        0x18,        # CLC
        0xFB,        # XCE
        0xC2, 0x30,  # REP #$30
        0xA9, 0xFF, 0x01,  # LDA #$01FF
        0x85, 0x00,  # STA $00
        0x60         # RTS
    ])

    start_time = time.perf_counter()
    total_ops = 0

    for _ in range(iterations):
        lifter = SnesLifter(snes_bytes, is_lorom=True)
        cfg = lifter.build_cfg(entry_bank=0x00, entry_pc=0x8000, max_blocks=10)
        total_ops += sum(len(b.instructions) for b in cfg.blocks.values())

    elapsed = time.perf_counter() - start_time
    ops_per_sec = (total_ops / elapsed) if elapsed > 0 else 0
    avg_latency_ms = (elapsed / iterations) * 1000.0

    return {
        "architecture": "W65C816S (SNES)",
        "iterations": iterations,
        "elapsed_seconds": round(elapsed, 4),
        "avg_latency_ms": round(avg_latency_ms, 3),
        "ops_per_second": round(ops_per_sec, 1),
        "ops_per_iteration": total_ops // iterations
    }


def run_all_benchmarks() -> dict:
    results = [
        benchmark_arm_lifter(),
        benchmark_thumb_lifter(),
        benchmark_mips_lifter(),
        benchmark_snes_lifter()
    ]
    return {"timestamp": time.time(), "benchmarks": results}


def print_table(results: dict):
    print("\n=========================================================================================")
    print("                    AUTOMATED GAME ROM RECOMPILER — BENCHMARK RESULTS                     ")
    print("=========================================================================================\n")
    print(f"{'Architecture':<26} | {'Avg Latency':<14} | {'Throughput (Ops/sec)':<22} | {'Ops / Run':<10}")
    print("-" * 85)
    for b in results["benchmarks"]:
        if b.get("status") == "skipped":
            print(f"{b.get('architecture', 'Unknown'):<26} | SKIPPED ({b.get('reason')})")
            continue
        arch = b["architecture"]
        lat = f"{b['avg_latency_ms']:.3f} ms"
        tp = f"{b['ops_per_second']:,.1f} ops/s"
        ops = str(b.get("ops_per_iteration", "-"))
        print(f"{arch:<26} | {lat:<14} | {tp:<22} | {ops:<10}")
    print("=========================================================================================\n")


def main():
    parser = argparse.ArgumentParser(description="Run lifter performance benchmarks.")
    parser.add_argument("--json", action="store_true", help="Output raw JSON results")
    args = parser.parse_args()

    results = run_all_benchmarks()
    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print_table(results)


if __name__ == "__main__":
    main()
