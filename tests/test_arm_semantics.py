"""Execute ARMv4T instructions and compare with architectural results."""

import struct
import subprocess

import pytest

from src.lifter.arm_codegen import ARM_FLAG_HELPERS
from src.lifter.arm_lifter import ArmLifter, lift_rom_to_c
from src.lifter.thumb_lifter import ThumbLifter


BASE = 0x08000000
HEADER = r'''
#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>
typedef struct { uint32_t r[16], cpsr; bool flag_z; uint8_t memory[1024]; } ArmCpuContext;
#define CHECK(expr) do { if (!(expr)) { fprintf(stderr, "Check failed at line %d: %s\n", __LINE__, #expr); return 1; } } while (0)
static inline uint8_t mem_read8(ArmCpuContext* ctx, uint32_t addr) { return addr < sizeof(ctx->memory) ? ctx->memory[addr] : 0; }
static inline uint16_t mem_read16(ArmCpuContext* ctx, uint32_t addr) { return mem_read8(ctx, addr) | ((uint16_t)mem_read8(ctx, addr + 1) << 8); }
static inline uint32_t mem_read32(ArmCpuContext* ctx, uint32_t addr) { return mem_read16(ctx, addr) | ((uint32_t)mem_read16(ctx, addr + 2) << 16); }
static inline void mem_write8(ArmCpuContext* ctx, uint32_t addr, uint8_t value) { if (addr < sizeof(ctx->memory)) ctx->memory[addr] = value; }
static inline void mem_write16(ArmCpuContext* ctx, uint32_t addr, uint16_t value) { mem_write8(ctx, addr, (uint8_t)value); mem_write8(ctx, addr + 1, (uint8_t)(value >> 8)); }
static inline void mem_write32(ArmCpuContext* ctx, uint32_t addr, uint32_t value) { mem_write16(ctx, addr, (uint16_t)value); mem_write16(ctx, addr + 2, (uint16_t)(value >> 16)); }
''' + ARM_FLAG_HELPERS


def emit_function(name, words, *, thumb=False):
    fmt = "H" if thumb else "I"
    lifter = (ThumbLifter if thumb else ArmLifter)(struct.pack(f"<{len(words)}{fmt}", *words), BASE)
    ops, _ = lifter.lift_block(BASE)
    return f"uint32_t {name}(ArmCpuContext* ctx) {{\n(void)ctx;\n" + "\n".join(op["c_code"] for op in ops) + "\nreturn 0;\n}\n"


def test_all_arm_conditions_and_conditional_side_effects(run_native):
    source = HEADER
    checks = []
    for cond in range(15):
        source += emit_function(f"branch_{cond}", [(cond << 28) | 0x0A000000])
    source += emit_function("conditional_store", [0x05810000, 0xE12FFF1E])  # STREQ r0,[r1]
    source += emit_function("conditional_add", [0x12900001, 0xE12FFF1E])    # ADDSNE r0,r0,#1
    for flags in range(16):
        n, z, c, v = (bool(flags & bit) for bit in (8, 4, 2, 1))
        conditions = [z, not z, c, not c, n, not n, v, not v, c and not z, not c or z, n == v, n != v, not z and n == v, z or n != v, True]
        checks.append(f"cpu.cpsr = 0x{flags << 28:08X}u; cpu.flag_z = {str(z).lower()};")
        for cond, taken in enumerate(conditions):
            checks.append(f"CHECK(branch_{cond}(&cpu) == 0x{BASE + (8 if taken else 4):08X}u);")
    source += "int main(void) { ArmCpuContext cpu = {0};\n" + "\n".join(checks) + r'''
    cpu.r[0] = 0x12345678; cpu.r[1] = 16; cpu.flag_z = false;
    conditional_store(&cpu); CHECK(mem_read32(&cpu, 16) == 0);
    cpu.flag_z = true; conditional_store(&cpu); CHECK(mem_read32(&cpu, 16) == 0x12345678u);
    cpu.r[0] = 0xFFFFFFFFu; cpu.flag_z = false;
    conditional_add(&cpu); CHECK(cpu.r[0] == 0 && cpu.flag_z && (cpu.cpsr & 0xF0000000u) == 0x60000000u);
    conditional_add(&cpu); CHECK(cpu.r[0] == 0);
    return 0;
}
'''
    run_native(source)


def test_arm_alu_and_shifter_flags(run_native):
    cases = [
        (0xE2900001, 0x7FFFFFFF, 0, 0, 0x80000000, 0x90000000),  # ADDS overflow
        (0xE2900001, 0xFFFFFFFF, 0, 0, 0, 0x60000000),           # ADDS carry
        (0xE2500001, 0, 0, 0, 0xFFFFFFFF, 0x80000000),           # SUBS borrow
        (0xE2500001, 0x80000000, 0, 0, 0x7FFFFFFF, 0x30000000),  # SUBS overflow
        (0xE2B00000, 0xFFFFFFFF, 0, 0x20000000, 0, 0x60000000),  # ADCS carry-in
        (0xE2D00000, 0, 0, 0, 0xFFFFFFFF, 0x80000000),           # SBCS borrow-in
        (0xE1B00080, 0x80000000, 0, 0, 0, 0x60000000),           # MOVS LSL #1, aliased rd/rm
        (0xE1B00020, 0x80000001, 0, 0, 0, 0x60000000),           # LSR #0 means 32
        (0xE1B00040, 0x80000000, 0, 0, 0xFFFFFFFF, 0xA0000000),  # ASR #0 means 32
        (0xE1B00060, 2, 0, 0x30000000, 0x80000001, 0x90000000), # RRX preserves V
        (0xE1B00110, 1, 32, 0, 0, 0x60000000),                 # register LSL 32
        (0xE1B00110, 1, 33, 0, 0, 0x40000000),                 # register LSL >32
        (0xE1B00110, 1, 0, 0x20000000, 1, 0x20000000),         # register LSL 0 preserves C
        (0xE0110000, 0xF0, 0x0F, 0x20000000, 0, 0x60000000),  # ANDS rd=rm, unshifted
        (0xE1910000, 0, 0x80000000, 0, 0x80000000, 0x80000000), # ORRS rd=rm
        (0xE1D10000, 0xFF, 0xFFFFFFFF, 0, 0xFFFFFF00, 0x80000000), # BICS rd=rm
    ]
    source = HEADER
    checks = []
    for i, (word, r0, r1, cpsr, result, flags) in enumerate(cases):
        source += emit_function(f"alu_{i}", [word, 0xE12FFF1E])
        checks.extend([
            f"cpu.r[0] = 0x{r0:08X}u; cpu.r[1] = {r1}; cpu.cpsr = 0x{cpsr:08X}u;",
            f"alu_{i}(&cpu); CHECK(cpu.r[0] == 0x{result:08X}u);",
            f"CHECK((cpu.cpsr & 0xF0000000u) == 0x{flags:08X}u && cpu.flag_z == {str(result == 0).lower()});",
        ])
    source += "int main(void) { ArmCpuContext cpu = {0};\n" + "\n".join(checks) + "\nreturn 0; }"
    run_native(source)


def test_thumb_arithmetic_shifts_and_multiple_loads(run_native):
    source = HEADER
    source += emit_function("arithmetic", [0x2000, 0x3801, 0x4770], thumb=True)  # MOVS; SUBS
    source += emit_function("shift", [0x4088, 0x4770], thumb=True)               # LSLS r0,r1
    source += emit_function("load", [0xC803, 0x4770], thumb=True)                # LDMIA r0!,{r0,r1}
    source += r'''
int main(void) {
    ArmCpuContext cpu = {0};
    arithmetic(&cpu); CHECK(cpu.r[0] == 0xFFFFFFFFu && (cpu.cpsr & 0xF0000000u) == 0x80000000u);
    cpu.r[0] = 1; cpu.r[1] = 32; shift(&cpu); CHECK(cpu.r[0] == 0 && (cpu.cpsr & 0xF0000000u) == 0x60000000u);
    cpu.r[0] = 1; cpu.r[1] = 33; shift(&cpu); CHECK(cpu.r[0] == 0 && (cpu.cpsr & 0xF0000000u) == 0x40000000u);
    mem_write32(&cpu, 16, 0xDEADBEEFu); mem_write32(&cpu, 20, 0x12345678u); cpu.r[0] = 16;
    load(&cpu); CHECK(cpu.r[0] == 0xDEADBEEFu && cpu.r[1] == 0x12345678u);
    return 0;
}
'''
    run_native(source)


def test_arm_address_writeback_shifted_offsets_and_pc_load(run_native):
    source = HEADER
    source += emit_function("writeback", [0xE4812004, 0xE5310004, 0xE12FFF1E]) # STR post; LDR pre decrement!
    source += emit_function("shifted_load", [0xE7910102, 0xE12FFF1E])          # LDR r0,[r1,r2,LSL #2]
    source += emit_function("load_pc", [0xE591F000, 0xE12FFF1E])              # LDR pc,[r1]
    source += r'''
int main(void) {
    ArmCpuContext cpu = {0};
    cpu.r[1] = 16; cpu.r[2] = 0x12345678u;
    writeback(&cpu); CHECK(cpu.r[1] == 16 && cpu.r[0] == 0x12345678u && mem_read32(&cpu, 16) == 0x12345678u);
    cpu.r[1] = 32; cpu.r[2] = 2; mem_write32(&cpu, 40, 0x87654321u);
    shifted_load(&cpu); CHECK(cpu.r[0] == 0x87654321u);
    cpu.r[1] = 48; mem_write32(&cpu, 48, 0x08001003u);
    CHECK(load_pc(&cpu) == 0x08001000u);
    return 0;
}
'''
    run_native(source)


def test_arm_and_thumb_pc_reads(run_native):
    source = HEADER
    source += emit_function("arm_pc", [0xE1A0000F, 0xE12FFF1E])
    source += emit_function("thumb_pc", [0x4678, 0x4770], thumb=True)
    source += f"int main(void) {{ ArmCpuContext cpu = {{0}}; arm_pc(&cpu); CHECK(cpu.r[0] == 0x{BASE + 8:08X}u); thumb_pc(&cpu); CHECK(cpu.r[0] == 0x{BASE + 4:08X}u); return 0; }}"
    run_native(source)


@pytest.mark.parametrize("thumb", [False, True])
def test_instruction_limit_preserves_fallthrough(thumb):
    fmt, nop = ("H", 0x46C0) if thumb else ("I", 0xE1A00000)
    lifter = (ThumbLifter if thumb else ArmLifter)(struct.pack(f"<1001{fmt}", *([nop] * 1001)), BASE)
    ops, targets = lifter.lift_block(BASE)
    continuation = BASE + 1000 * (2 if thumb else 4)
    assert continuation in targets
    assert ops[-1]["op"] == "FALLTHROUGH"


def test_arm_cfg_includes_final_thumb_halfword():
    data = bytearray(16)
    struct.pack_into("<3I", data, 0, 0xE59F1000, 0xE12FFF11, BASE + 15)
    struct.pack_into("<H", data, 14, 0x4770)
    cfg = ArmLifter(bytes(data), BASE).build_cfg(BASE)
    assert cfg.has_block(BASE + 14)
    assert cfg.get_block(BASE + 14).instructions[0]["op"] == "BX"


def test_gba_native_framebuffer_snapshot(build_native, tmp_path):
    exe = build_native(lift_rom_to_c("roms/test/hello_gba.gba"), host_window=True)
    frame_path = tmp_path / "snapshot.ppm"
    result = subprocess.run([str(exe), "--headless", "--framebuffer", str(frame_path)], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "0x0403 (Mode 3)" in result.stdout
    assert "2400 pixels" in result.stdout
    data = frame_path.read_bytes()
    header = b"P6\n240 160\n255\n"
    assert data.startswith(header)
    pixels = data[len(header):]
    assert len(pixels) == 240 * 160 * 3
    assert pixels[:3] == bytes([248, 0, 0])
    assert pixels[2400 * 3:] == bytes((240 * 160 - 2400) * 3)
    bad = subprocess.run([str(exe), "--framebuffer"], capture_output=True, text=True, timeout=15)
    assert bad.returncode == 2
