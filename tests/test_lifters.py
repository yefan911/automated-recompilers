import struct
import pytest
from src.lifter.arm_lifter import ArmLifter, lift_rom_to_c
from src.lifter.mips_lifter import MipsLifter


def test_arm_lifter_branch():
    # Opcode 0xEA000002 = b 0x08000010 (offset +2 instructions from PC+8)
    rom = struct.pack("<I", 0xEA000002)
    lifter = ArmLifter(rom, base_vram=0x08000000)
    ops, targets = lifter.lift_block(0x08000000)

    assert len(ops) == 1
    assert ops[0]["op"] == "BRANCH"
    assert targets == [0x08000010]
    assert "return 0x08000010;" in ops[0]["c_code"]


def test_arm_lifter_mov_imm():
    # 0xE3A00404 = mov r0, #0x04000000 (4 ror 8)
    rom = struct.pack("<2I", 0xE3A00404, 0xEAFFFFFE)
    lifter = ArmLifter(rom, base_vram=0x08000000)
    ops, targets = lifter.lift_block(0x08000000)

    assert ops[0]["op"] == "MOV_IMM"
    assert ops[0]["rd"] == 0
    assert ops[0]["val"] == 0x04000000
    assert "ctx->r[0] = 0x04000000;" in ops[0]["c_code"]


def test_arm_lifter_ldr_const_and_strh():
    # ldr r1, [pc, #4] (offset 4 from pc+8 = +12 bytes = offset 0x0C)
    # strh r1, [r0]
    # b loop
    # const: 0x00000403
    rom = struct.pack("<4I",
        0xE59F1004,  # ldr r1, [pc, #4]
        0xE1C010B0,  # strh r1, [r0]
        0xEAFFFFFE,  # b loop
        0x00000403   # const at 0x0C
    )
    lifter = ArmLifter(rom, base_vram=0x08000000)
    ops, targets = lifter.lift_block(0x08000000)

    assert ops[0]["op"] == "LDR_CONST"
    assert ops[0]["rd"] == 1
    assert ops[0]["val"] == 0x00000403

    assert ops[1]["op"] == "STRH"
    assert "mem_write16(ctx, ctx->r[0], (uint16_t)ctx->r[1]);" in ops[1]["c_code"]


def test_mips_lifter_instructions():
    raw_instructions = [
        (0x00000000, "nop"),
        (0x00851021, "addu"),
        (0x27BDFFF8, "addiu"),
        (0x3C018002, "lui"),
        (0x34241000, "ori"),
        (0x8FA40008, "lw"),
        (0xAFA40008, "sw"),
        (0x03E00008, "jr"),
        (0x0C000010, "jal"),
    ]

    data = struct.pack(f">{len(raw_instructions)}I", *[r[0] for r in raw_instructions])
    lifter = MipsLifter(data, base_vram=0x80000000, is_big_endian=True)

    for i, (_, mnemonic) in enumerate(raw_instructions):
        addr = 0x80000000 + i * 4
        raw = lifter.read_u32(addr)
        info = lifter.lift_instruction(addr, raw)
        assert mnemonic in info["asm"].lower()
        assert info["c"] != ""


def test_lift_rom_to_c_output():
    c_source = lift_rom_to_c("roms/test/hello_gba.gba")
    assert "typedef struct" in c_source
    assert "ArmCpuContext" in c_source
    assert "uint32_t bb_08000000(ArmCpuContext* ctx)" in c_source
    assert "uint32_t bb_080000C0(ArmCpuContext* ctx)" in c_source
    assert "int main(int argc, char** argv)" in c_source
