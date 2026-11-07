"""Execute generated 65816 blocks against register, flag, stack, and bus results."""

import struct

import pytest

from src.core.create_test_rom import create_snes_test_rom
from src.lifter.snes_lifter import SnesLifter, lift_snes_rom_to_c


CHECK = r'''
#define CHECK(expr) do { if (!(expr)) { fprintf(stderr, "Check failed at line %d: %s\n", __LINE__, #expr); return 1; } } while (0)
'''


def runtime_prefix(tmp_path, code=b"\x60", extras=()):
    rom = bytearray(0x10000)
    rom[:len(code)] = code
    for offset, payload in extras:
        rom[offset:offset + len(payload)] = payload
    struct.pack_into("<H", rom, 0x7FFC, 0x8000)
    path = tmp_path / "semantics.sfc"
    path.write_bytes(rom)
    source = lift_snes_rom_to_c(str(path), max_blocks=30)
    return source.split("#ifdef _WIN32\n/* Win32 Presentation Window", 1)[0] + CHECK


def emit_instruction(name, code, p=0x30, pc=0x8000):
    rom = bytearray(0x10000)
    offset = ((pc >> 16) & 0x7F) * 0x8000 + (pc & 0x7FFF)
    rom[offset:offset + len(code)] = code
    op, _ = SnesLifter(bytes(rom)).lift_instruction(pc, p)
    return f"uint32_t {name}(SnesCpuContext* ctx) {{\n(void)ctx;\n{op['c_code']}\nreturn 0;\n}}\n"


def test_snes_load_transfer_and_shift_flags(run_native, tmp_path):
    source = runtime_prefix(tmp_path)
    source += emit_instruction("lda8", bytes([0xA9, 0]))
    source += emit_instruction("ldx8", bytes([0xA2, 0x80]))
    source += emit_instruction("direct_page", bytes([0x5B]))
    source += emit_instruction("rotate", bytes([0x2A]))
    source += emit_instruction("cmp8", bytes([0xC9, 0x10]))
    source += emit_instruction("bit16", bytes([0x2C, 0x10, 0]), p=0)
    source += r'''
int main(void) {
    static SnesCpuContext cpu;
    cpu.p = 0x31; cpu.a = 0xAB42;
    lda8(&cpu); CHECK(cpu.a == 0xAB00 && (cpu.p & 0x83) == 3);
    cpu.x = 0xFF00; ldx8(&cpu); CHECK(cpu.x == 0x80 && (cpu.p & 0x82) == 0x80);
    cpu.a = 0x1234; direct_page(&cpu); CHECK(sizeof(cpu.dp) == 2 && cpu.dp == 0x1234);
    cpu.a = 0xAB80; cpu.p = 0x31; rotate(&cpu); CHECK(cpu.a == 0xAB01 && (cpu.p & 0x83) == 1);
    cpu.a = 0xAB0F; cmp8(&cpu); CHECK((cpu.p & 0x83) == 0x80);
    cpu.p = 0; cpu.a = 0; snes_write16(&cpu, 0x10, 0xC000);
    bit16(&cpu); CHECK((cpu.p & 0xC2) == 0xC2);
    return 0;
}
'''
    run_native(source)


def test_snes_binary_and_decimal_arithmetic(run_native, tmp_path):
    # opcode, width, a, operand, initial status, result, expected N/V/Z/C
    cases = [
        (0x69, 8, 0x7F, 0, 0x31, 0x80, 0xC0),
        (0x69, 8, 0xFF, 0, 0x31, 0, 3),
        (0xE9, 8, 0, 0, 0x30, 0xFF, 0x80),
        (0xE9, 8, 0x80, 1, 0x31, 0x7F, 0x41),
        (0x69, 16, 0x7FFF, 0, 1, 0x8000, 0xC0),
        (0xE9, 16, 0, 0, 0, 0xFFFF, 0x80),
        (0x69, 8, 0x49, 0x31, 0x38, 0x80, 0xC0),
        (0x69, 8, 0x99, 0, 0x39, 0, 3),
        (0xE9, 8, 0, 1, 0x39, 0x99, 0x80),
        (0x69, 16, 0x9999, 0, 9, 0, 3),
        (0xE9, 16, 0x1000, 1, 9, 0x0999, 1),
    ]
    source = runtime_prefix(tmp_path)
    checks = []
    for i, (opcode, width, a, operand, p, result, flags) in enumerate(cases):
        code = bytes([opcode]) + operand.to_bytes(width // 8, "little")
        source += emit_instruction(f"arithmetic_{i}", code, p)
        start_a = a | (0xAB00 if width == 8 else 0)
        final_a = result | (0xAB00 if width == 8 else 0)
        checks.append(f"cpu.a = 0x{start_a:04X}; cpu.p = 0x{p:02X}; arithmetic_{i}(&cpu); CHECK(cpu.a == 0x{final_a:04X} && (cpu.p & 0xC3) == 0x{flags:02X});")
    source += "int main(void) { static SnesCpuContext cpu;\n" + "\n".join(checks) + "\nreturn 0; }"
    run_native(source)


def test_snes_overflow_branches_and_bank_wrapping(run_native, tmp_path):
    source = runtime_prefix(tmp_path)
    source += emit_instruction("bvc", bytes([0x50, 2]))
    source += emit_instruction("bvs", bytes([0x70, 2]))
    source += r'''
int main(void) {
    static SnesCpuContext cpu;
    CHECK(bvc(&cpu) == 0x8004 && bvs(&cpu) == 0x8002);
    cpu.p = 0x40; CHECK(bvc(&cpu) == 0x8002 && bvs(&cpu) == 0x8004);
    return 0;
}
'''
    run_native(source)
    rom = bytearray(0x10000)
    rom[0x7FF0:0x7FF2] = bytes([0x80, 0x20])
    op, _ = SnesLifter(bytes(rom)).lift_instruction(0x00FFF0, 0x30)
    assert op["target"] == 0x000012


def test_snes_calls_follow_guest_stack_and_dispatch(run_native, tmp_path):
    code = bytes([0x20, 0x20, 0x80, 0xA9, 0x42, 0x85, 0x10, 0x4C, 0x30, 0x80])
    source = runtime_prefix(tmp_path, code, [(0x20, bytes([0xA9, 7, 0x60])), (0x30, bytes([0x60]))])
    source += r'''
int main(void) {
    static SnesCpuContext cpu;
    cpu.sp = 0x01FF; cpu.p = 0x30;
    CHECK(recomp_snes_dispatch(&cpu, 0x8000) == 0x8020);
    CHECK(cpu.sp == 0x01FD && snes_read8(&cpu, 0x01FF) == 0x80 && snes_read8(&cpu, 0x01FE) == 2);
    CHECK(recomp_snes_dispatch(&cpu, 0x8020) == 0x8003 && cpu.a == 7 && cpu.sp == 0x01FF);
    CHECK(recomp_snes_dispatch(&cpu, 0x8003) == 0x8030 && cpu.a == 0x42 && cpu.ram[0x10] == 0x42);
    return 0;
}
'''
    run_native(source)


def test_snes_long_calls_and_stack_operations(run_native, tmp_path):
    source = runtime_prefix(tmp_path)
    source += emit_instruction("call_long", bytes([0x22, 0x60, 0x80, 1]), pc=0x8040)
    source += emit_instruction("return_long", bytes([0x6B]), pc=0x018060)
    source += emit_instruction("push_a", bytes([0x48]))
    source += emit_instruction("pull_a", bytes([0x68]))
    source += r'''
int main(void) {
    static SnesCpuContext cpu;
    cpu.sp = 0x01FF; cpu.p = 0x30;
    CHECK(call_long(&cpu) == 0x018060 && cpu.sp == 0x01FC);
    CHECK(snes_read8(&cpu, 0x01FF) == 0 && snes_read8(&cpu, 0x01FE) == 0x80 && snes_read8(&cpu, 0x01FD) == 0x43);
    CHECK(return_long(&cpu) == 0x008044 && cpu.sp == 0x01FF && cpu.pb == 0);
    cpu.a = 0x1234; push_a(&cpu); CHECK(cpu.sp == 0x01FE && snes_read8(&cpu, 0x01FF) == 0x34);
    cpu.a = 0xAB00; pull_a(&cpu); CHECK(cpu.a == 0xAB34 && cpu.sp == 0x01FF && (cpu.p & 0x82) == 0);
    return 0;
}
'''
    run_native(source)


def test_snes_cartridge_mapping_and_copier_header(run_native, tmp_path):
    lifter = SnesLifter(bytes(0x400000))
    for address in (0x000000, 0x002100, 0x7E8000, 0x7F8000, 0x700000):
        assert not lifter.is_valid_address(address)
    path = tmp_path / "copier.smc"
    create_snes_test_rom(str(path))
    original = path.read_bytes()
    path.write_bytes(bytes(512) + original)
    source = lift_snes_rom_to_c(str(path), max_blocks=20).split("#ifdef _WIN32\n/* Win32 Presentation Window", 1)[0] + CHECK
    source += f"int main(void) {{ static SnesCpuContext cpu; CHECK(snes_read8(&cpu, 0x008000) == {original[0]}); CHECK(snes_read8(&cpu, 0x808000) == {original[0]}); CHECK(snes_read16(&cpu, 0x00FFFC) == 0x8000); return 0; }}"
    run_native(source)


@pytest.mark.parametrize("rom", [b"", bytes(0x7FFD)], ids=["empty", "missing-reset"])
def test_snes_rejects_missing_header_or_reset_vector(rom, tmp_path):
    path = tmp_path / "truncated.sfc"
    path.write_bytes(rom)
    with pytest.raises(ValueError):
        lift_snes_rom_to_c(str(path))


def test_snes_instruction_limit_preserves_continuation():
    lifter = SnesLifter(bytes([0xEA]) * 501)
    ops, targets, _ = lifter.lift_block(0, 0x8000)
    assert 0x81F4 in targets
    assert ops[-1]["op"] == "FALLTHROUGH"


def test_snes_reset_emulation_and_stack_page_wrapping(run_native, tmp_path):
    source = runtime_prefix(tmp_path)
    source += emit_instruction("exchange", bytes([0xFB]))
    source += r'''
int main(void) {
    static SnesCpuContext cpu;
    snes_init_context(&cpu);
    CHECK(cpu.e && cpu.sp == 0x01FF && cpu.p == 0x34);
    CHECK(snes_read8(&cpu, 0x2140) == 0xAA && snes_read8(&cpu, 0x2141) == 0xBB);
    exchange(&cpu); CHECK(!cpu.e && (cpu.p & 1));
    cpu.x = 0x1234; cpu.y = 0xABCD; cpu.sp = 0x2345;
    exchange(&cpu); CHECK(cpu.e && cpu.p == 0x34 && cpu.x == 0x34 && cpu.y == 0xCD && cpu.sp == 0x0145);
    cpu.sp = 0x0100; snes_push8(&cpu, 0x55);
    CHECK(cpu.sp == 0x01FF && cpu.ram[0x100] == 0x55);
    CHECK(snes_pop8(&cpu) == 0x55 && cpu.sp == 0x0100);
    return 0;
}
'''
    run_native(source)


def test_snes_vram_palette_and_mode7_register_latches(run_native, tmp_path):
    source = runtime_prefix(tmp_path) + r'''
int main(void) {
    static SnesCpuContext cpu;
    snes_init_context(&cpu);
    snes_write8(&cpu, 0x2115, 0x80); /* Increment after high byte. */
    snes_write8(&cpu, 0x2116, 0xFF); snes_write8(&cpu, 0x2117, 0x7F);
    snes_write8(&cpu, 0x2118, 0xAA); CHECK(cpu.vram_addr == 0x7FFF);
    snes_write8(&cpu, 0x2119, 0xBB);
    CHECK(cpu.vram[0xFFFE] == 0xAA && cpu.vram[0xFFFF] == 0xBB && cpu.vram_addr == 0x8000);
    snes_write8(&cpu, 0x2118, 0xCC); CHECK(cpu.vram[0] == 0xCC);
    snes_write8(&cpu, 0x2115, 0x81); snes_write8(&cpu, 0x2119, 0xDD);
    CHECK(cpu.vram[1] == 0xDD && cpu.vram_addr == 0x8020);
    snes_write8(&cpu, 0x2121, 255); snes_write8(&cpu, 0x2122, 0x34); snes_write8(&cpu, 0x2122, 0xFF);
    CHECK(cpu.cgram[510] == 0x34 && cpu.cgram[511] == 0x7F);
    snes_write8(&cpu, 0x2122, 0x56); CHECK(cpu.cgram[0] == 0x56);
    snes_write8(&cpu, 0x211F, 0x23); snes_write8(&cpu, 0x211F, 1);
    CHECK(cpu.m7x == 0x0123);
    return 0;
}
'''
    run_native(source)


def test_snes_decimal_arithmetic_matches_decimal_numbers(run_native, tmp_path):
    source = runtime_prefix(tmp_path)
    for name, code, p in [
        ("adc8", bytes([0x6D, 0x10, 0]), 0x38), ("sbc8", bytes([0xED, 0x10, 0]), 0x38),
        ("adc16", bytes([0x6D, 0x10, 0]), 8), ("sbc16", bytes([0xED, 0x10, 0]), 8),
    ]:
        source += emit_instruction(name, code, p)
    source += r'''
static uint16_t bcd(unsigned decimal) {
    return (uint16_t)((decimal % 10) | ((decimal / 10 % 10) << 4)
                   | ((decimal / 100 % 10) << 8) | ((decimal / 1000 % 10) << 12));
}
int main(void) {
    static SnesCpuContext cpu;
    const unsigned values[] = {0, 1, 9, 10, 99, 100, 999, 1000, 4999, 5000, 9999};
    for (unsigned carry = 0; carry < 2; carry++) {
        for (unsigned a = 0; a < 100; a++) {
            for (unsigned b = 0; b < 100; b++) {
                snes_write8(&cpu, 0x10, (uint8_t)bcd(b));
                unsigned sum = a + b + carry;
                cpu.a = (uint16_t)(0xAB00 | bcd(a)); cpu.p = (uint8_t)(0x38 | carry); adc8(&cpu);
                CHECK(cpu.a == (0xAB00 | bcd(sum % 100)));
                CHECK((cpu.p & 1) == (sum >= 100) && !!(cpu.p & 2) == (sum % 100 == 0));
                int difference = (int)a - (int)b - (int)(1 - carry);
                unsigned result = (unsigned)((difference + 100) % 100);
                cpu.a = (uint16_t)(0xAB00 | bcd(a)); cpu.p = (uint8_t)(0x38 | carry); sbc8(&cpu);
                CHECK(cpu.a == (0xAB00 | bcd(result)));
                CHECK((cpu.p & 1) == (difference >= 0) && !!(cpu.p & 2) == (result == 0));
            }
        }
        for (unsigned i = 0; i < sizeof(values) / sizeof(values[0]); i++) {
            for (unsigned j = 0; j < sizeof(values) / sizeof(values[0]); j++) {
                unsigned a = values[i], b = values[j], sum = a + b + carry;
                snes_write16(&cpu, 0x10, bcd(b));
                cpu.a = bcd(a); cpu.p = (uint8_t)(8 | carry); adc16(&cpu);
                CHECK(cpu.a == bcd(sum % 10000) && (cpu.p & 1) == (sum >= 10000));
                int difference = (int)a - (int)b - (int)(1 - carry);
                unsigned result = (unsigned)((difference + 10000) % 10000);
                cpu.a = bcd(a); cpu.p = (uint8_t)(8 | carry); sbc16(&cpu);
                CHECK(cpu.a == bcd(result) && (cpu.p & 1) == (difference >= 0));
            }
        }
    }
    return 0;
}
'''
    run_native(source)
