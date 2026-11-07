"""Execute generated MIPS C against architectural results, including edge cases."""

import shutil
import struct
import subprocess
import sys

import pytest

from src.core.native_compiler import get_msvc_environment
from src.lifter.mips_lifter import MipsLifter, lift_mips_rom_to_c


@pytest.fixture
def run_native(tmp_path):
    cl, env = get_msvc_environment()
    compiler = cl or shutil.which("gcc") or shutil.which("clang")
    if compiler is None:
        pytest.skip("A native C compiler is required for generated-code execution")

    def run(source):
        src = tmp_path / "semantics.c"
        exe = tmp_path / ("semantics.exe" if sys.platform == "win32" else "semantics")
        src.write_text(source, encoding="utf-8")
        if cl:
            cmd = [cl, "/nologo", "/O2", "/W3", "/WX", f"/Fo{tmp_path / 'semantics.obj'}", f"/Fe{exe}", str(src)]
        else:
            cmd = [compiler, "-std=c99", "-Wall", "-Wextra", "-Werror", "-O2", str(src), "-o", str(exe)]
        built = subprocess.run(cmd, env=env if cl else None, cwd=tmp_path, capture_output=True, text=True, timeout=60)
        assert built.returncode == 0, built.stdout + built.stderr
        result = subprocess.run([str(exe)], capture_output=True, text=True, timeout=15)
        assert result.returncode == 0, result.stdout + result.stderr

    return run


HEADER = """
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef struct { uint32_t r[32]; uint32_t hi, lo; } Cpu;
#define CHECK(expr) do { if (!(expr)) { fprintf(stderr, "Check failed at line %d: %s\\n", __LINE__, #expr); return 1; } } while (0)
"""


def emit_function(name, ops):
    return f"uint32_t {name}(Cpu* ctx) {{\n(void)ctx;\n" + "\n".join(op["c_code"] for op in ops) + "\n}\n"


def test_branch_and_call_delay_slot_state(run_native):
    base = 0x80001000
    # raw branch/call, delay slot, starting a0, expected PC, expected a0,
    # expected v0, expected ra. Every slot changes something the transfer uses.
    cases = [
        (0x10800003, 0x2484FFFF, 1, base + 8, 0, 0, 0),   # BEQ: slot makes equal
        (0x14800003, 0x2484FFFF, 1, base + 16, 0, 0, 0),  # BNE: slot makes equal
        (0x18800003, 0x24840001, 0, base + 16, 1, 0, 0),  # BLEZ: slot makes positive
        (0x1C800003, 0x2484FFFF, 1, base + 16, 0, 0, 0),  # BGTZ: slot makes zero
        (0x04800003, 0x24040000, 0xFFFFFFFF, base + 16, 0, 0, 0),  # BLTZ
        (0x04810003, 0x2404FFFF, 0, base + 16, 0xFFFFFFFF, 0, 0),  # BGEZ
        (0x00800008, 0x24040000, base + 32, base + 32, 0, 0, 0),  # JR: slot clears target
        (0x0C000404, 0x03E01021, 0, base + 16, 0, base + 8, base + 8),  # JAL: slot reads ra
        (0x0080F809, 0x03E01021, base + 32, base + 32, base + 32, base + 8, base + 8),  # JALR: slot reads ra
        (0x0080F809, 0x24040000, base + 32, base + 32, 0, 0, base + 8),  # JALR: slot clears target
        (0x00800009, 0, base + 32, base + 32, base + 32, 0, 0),  # JALR rd=zero: no link
        (0x04900003, 0x03E01021, 0xFFFFFFFF, base + 16, 0xFFFFFFFF, base + 8, base + 8),  # BLTZAL
        (0x04910003, 0x03E01021, 0xFFFFFFFF, base + 8, 0xFFFFFFFF, base + 8, base + 8),  # BGEZAL untaken: link visible
    ]
    source = HEADER
    checks = []
    for i, (raw, slot, a0, pc, final_a0, v0, ra) in enumerate(cases):
        ops, _ = MipsLifter(struct.pack(">2I", raw, slot), base_vram=base).lift_block(base)
        source += emit_function(f"case_{i}", ops)
        checks.extend([
            "memset(&cpu, 0, sizeof(cpu));",
            f"cpu.r[4] = 0x{a0:08X}u;",
            f"CHECK(case_{i}(&cpu) == 0x{pc:08X}u);",
            f"CHECK(cpu.r[4] == 0x{final_a0:08X}u);",
            f"CHECK(cpu.r[2] == 0x{v0:08X}u && cpu.r[31] == 0x{ra:08X}u && cpu.r[0] == 0);",
        ])
    source += "int main(void) { Cpu cpu;\n" + "\n".join(checks) + "\nreturn 0; }"
    run_native(source)


def test_unsigned_comparison_addition_and_division(run_native):
    lifter = MipsLifter(b"")
    instructions = [0x0085102A, 0x0085102B, 0x24820001, 0x0085001A, 0x0085001B, 0x0085002B]
    source = HEADER
    for i, raw in enumerate(instructions):
        code = lifter.lift_instruction(0x80001000, raw)["c"]
        source += emit_function(f"arithmetic_{i}", [{"c_code": code}, {"c_code": "return 0;"}])
    source += """
int main(void) {
    Cpu cpu = {0};
    cpu.r[4] = 0xFFFFFFFFu; cpu.r[5] = 0;
    arithmetic_0(&cpu); CHECK(cpu.r[2] == 1);
    arithmetic_1(&cpu); CHECK(cpu.r[2] == 0);
    cpu.r[4] = 0; cpu.r[5] = 0x80000000u;
    arithmetic_0(&cpu); CHECK(cpu.r[2] == 0);
    arithmetic_1(&cpu); CHECK(cpu.r[2] == 1);
    arithmetic_5(&cpu); CHECK(cpu.r[0] == 0);
    cpu.r[4] = 0x7FFFFFFFu;
    arithmetic_2(&cpu); CHECK(cpu.r[2] == 0x80000000u);
    cpu.r[4] = 0xFFFFFFFFu;
    arithmetic_2(&cpu); CHECK(cpu.r[2] == 0);
    cpu.r[4] = 0x80000000u; cpu.r[5] = 0xFFFFFFFFu;
    arithmetic_3(&cpu); CHECK(cpu.lo == 0x80000000u && cpu.hi == 0);
    cpu.r[4] = 7; cpu.r[5] = 0;
    arithmetic_3(&cpu); CHECK(cpu.lo == 0xFFFFFFFFu && cpu.hi == 7);
    cpu.r[4] = 0xFFFFFFF9u;
    arithmetic_3(&cpu); CHECK(cpu.lo == 1 && cpu.hi == 0xFFFFFFF9u);
    arithmetic_4(&cpu); CHECK(cpu.lo == 0xFFFFFFFFu && cpu.hi == 0xFFFFFFF9u);
    cpu.r[4] = 0xFFFFFFF9u; cpu.r[5] = 3;
    arithmetic_3(&cpu); CHECK(cpu.lo == 0xFFFFFFFEu && cpu.hi == 0xFFFFFFFFu);
    return 0;
}
"""
    run_native(source)


def test_calls_follow_callee_blocks_and_return_through_dispatch(run_native):
    base = 0x80001000
    words = [
        0x03E08021,  # addu s0,ra,zero: save outer return (0)
        0x0C000408,  # jal helper at 0x80001020
        0x24040005,  # addiu a0,zero,5: call delay slot
        0x24420001,  # addiu v0,v0,1: caller continuation
        0x02000008,  # jr s0
        0,
        0, 0,
        0x24820001,  # helper: addiu v0,a0,1
        0x10000002,  # beq zero,zero,0x80001030
        0,
        0,
        0x03E00008,  # helper continuation: jr ra
        0x24420001,  # addiu v0,v0,1: return delay slot
    ]
    cfg = MipsLifter(struct.pack(f">{len(words)}I", *words), base_vram=base).build_cfg(base)
    source = HEADER + "uint32_t recomp_mips_dispatch(Cpu* ctx, uint32_t pc);\n"
    for block in cfg.sorted_blocks():
        source += emit_function(block.func_name, block.instructions)
    source += "uint32_t recomp_mips_dispatch(Cpu* ctx, uint32_t pc) { switch (pc) {\n"
    for block in cfg.sorted_blocks():
        source += f"case 0x{block.start_vram:08X}u: return {block.func_name}(ctx);\n"
    source += "default: return 0; } }\n"
    source += f"""
int main(void) {{
    Cpu cpu = {{0}};
    uint32_t pc = 0x{base:08X}u;
    unsigned steps = 0;
    while (pc && steps++ < 20) pc = recomp_mips_dispatch(&cpu, pc);
    CHECK(pc == 0 && steps == 4 && cpu.r[2] == 8 && cpu.r[31] == 0x8000100Cu);
    return 0;
}}
"""
    run_native(source)


def test_instruction_limit_preserves_fallthrough(run_native):
    base = 0x80001000
    words = [0] * 501 + [0x00000008, 0]
    ops, targets = MipsLifter(struct.pack(f">{len(words)}I", *words), base_vram=base).lift_block(base)
    assert targets == [base + 500 * 4]
    source = HEADER + emit_function("slice", ops)
    source += f"int main(void) {{ Cpu cpu = {{0}}; CHECK(slice(&cpu) == 0x{base + 500 * 4:08X}u); return 0; }}"
    run_native(source)


def test_recursive_guest_calls_use_bounded_dispatch(run_native):
    base = 0x80001000
    # A guest call loop should consume the caller's dispatch budget, without
    # recursively growing the native C stack inside a single dispatch step.
    ops, _ = MipsLifter(struct.pack(">2I", 0x0C000400, 0), base_vram=base).lift_block(base)
    source = HEADER + "uint32_t recomp_mips_dispatch(Cpu* ctx, uint32_t pc);\n"
    source += emit_function("call_loop", ops)
    source += "uint32_t recomp_mips_dispatch(Cpu* ctx, uint32_t pc) { (void)pc; return call_loop(ctx); }\n"
    source += """
int main(void) {
    Cpu cpu = {0};
    uint32_t pc = 0x80001000u;
    for (unsigned i = 0; i < 100000; ++i) pc = recomp_mips_dispatch(&cpu, pc);
    CHECK(pc == 0x80001000u && cpu.r[31] == 0x80001008u);
    return 0;
}
"""
    run_native(source)


def test_branch_target_wraps_to_guest_address_width():
    info = MipsLifter(b"").lift_instruction(0xFFFFFFFC, 0x10000001)
    assert info["targets"] == [4, 4]


@pytest.mark.parametrize("dump_order", ["z64", "n64", "v64", "ps1"])
def test_guest_memory_image_byte_order_and_bounds(tmp_path, run_native, dump_order):
    text_vram = 0x80000400 if dump_order != "ps1" else 0x80010000
    endian = ">" if dump_order != "ps1" else "<"
    payload = struct.pack(endian + "5I", 0x8C820010, 0x00000008, 0, 0, 0x12345678)
    if dump_order == "ps1":
        data = bytearray(2048)
        data[:8] = b"PS-X EXE"
        struct.pack_into("<I", data, 0x10, text_vram)
        struct.pack_into("<III", data, 0x14, 0x80018000, text_vram, len(payload))
        struct.pack_into("<I", data, 0x30, 0x801FFF00)
        data.extend(payload)
        rom = tmp_path / "test.exe"
    else:
        data = bytearray(0x1000)
        data[:4] = b"\x80\x37\x12\x40"
        struct.pack_into(">I", data, 8, text_vram)
        data[0x400:0x400 + len(payload)] = payload
        if dump_order == "n64":
            data = b"".join(data[i:i + 4][::-1] for i in range(0, len(data), 4))
        elif dump_order == "v64":
            data = b"".join(data[i:i + 2][::-1] for i in range(0, len(data), 2))
        rom = tmp_path / f"test.{dump_order}"
    rom.write_bytes(data)
    # Exclude the host window and original entry function, retaining generated
    # initialization, memory shims, basic blocks, and dispatch verbatim.
    source = lift_mips_rom_to_c(str(rom)).split("/* Main Entry & Win32 Presentation HAL */")[0]
    source += '#define CHECK(expr) do { if (!(expr)) { fprintf(stderr, "Check failed at line %d: %s\\n", __LINE__, #expr); return 1; } } while (0)\n'
    first = 0x78 if dump_order == "ps1" else 0x12
    half = 0x5678 if dump_order == "ps1" else 0x1234
    source += f"""
static MipsCpuContext cpu;
int main(void) {{
    mips_init_context(&cpu);
    CHECK(mips_read32(&cpu, 0x{text_vram + 16:08X}u) == 0x12345678u);
    cpu.r[4] = 0x{text_vram:08X}u;
    CHECK(recomp_mips_dispatch(&cpu, 0x{text_vram:08X}u) == 0);
    CHECK(cpu.r[2] == 0x12345678u);
    mips_write32(&cpu, 0x80000200u, 0x12345678u);
    CHECK(cpu.rdram[0x200] == 0x{first:02X});
    CHECK(mips_read16(&cpu, 0xA0000200u) == 0x{half:04X});
    mips_write16(&cpu, 0x80000202u, 0xBEEFu);
    CHECK(mips_read16(&cpu, 0x80000202u) == 0xBEEFu);
    mips_write32(&cpu, 0x807FFFFCu, 0x89ABCDEFu);
    CHECK(mips_read32(&cpu, 0x807FFFFCu) == 0x89ABCDEFu);
    mips_write32(&cpu, 0x807FFFFDu, 0);
    CHECK(mips_read32(&cpu, 0x807FFFFCu) == 0x89ABCDEFu && mips_read32(&cpu, 0x807FFFFDu) == 0);
    mips_write16(&cpu, 0x807FFFFFu, 0);
    CHECK(mips_read16(&cpu, 0x807FFFFFu) == 0);
    CHECK(mips_read8(&cpu, 0x80800000u) == 0);
    cpu.gte_data[12] = 0x80008000u;
    cpu.gte_data[13] = 0x80007FFFu;
    cpu.gte_data[14] = 0x7FFF7FFFu;
    gte_nclip(&cpu); CHECK(cpu.gte_data[24] == 0xFFFE0001u);
    {"CHECK(cpu.r[28] == 0x80018000u && cpu.r[29] == 0x801FFF00u);" if dump_order == "ps1" else ""}
    return 0;
}}
"""
    run_native(source)
