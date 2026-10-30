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


def test_arm_lifter_bx():
    # Opcode 0xE12FFF1E = bx lr (r14)
    rom = struct.pack("<I", 0xE12FFF1E)
    lifter = ArmLifter(rom, base_vram=0x08000000)
    ops, targets = lifter.lift_block(0x08000000)

    assert len(ops) == 1
    assert ops[0]["op"] == "BX"
    assert ops[0]["rm"] == 14
    assert "return ctx->r[14];" in ops[0]["c_code"]
    assert len(targets) == 0


def test_arm_lifter_mov_imm():
    # 0xE3A00404 = mov r0, #0x04000000 (4 ror 8)
    rom = struct.pack("<2I", 0xE3A00404, 0xEAFFFFFE)
    lifter = ArmLifter(rom, base_vram=0x08000000)
    ops, targets = lifter.lift_block(0x08000000)

    assert ops[0]["op"] == "MOV_IMM"
    assert ops[0]["rd"] == 0
    assert ops[0]["val"] == 0x04000000
    assert "ctx->r[0] = 0x04000000;" in ops[0]["c_code"]


def test_arm_lifter_alu_ops():
    # 0xE0810002: add r0, r1, r2
    # 0xE0410002: sub r0, r1, r2
    # 0xE0010002: and r0, r1, r2
    # 0xE1810002: orr r0, r1, r2
    # 0xE0210002: eor r0, r1, r2
    # 0xE1510002: cmp r1, r2
    # 0xE1C10002: bic r0, r1, r2
    # 0xE12FFF1E: bx lr
    rom = struct.pack("<8I",
        0xE0810002,
        0xE0410002,
        0xE0010002,
        0xE1810002,
        0xE0210002,
        0xE1510002,
        0xE1C10002,
        0xE12FFF1E
    )
    lifter = ArmLifter(rom, base_vram=0x08000000)
    ops, targets = lifter.lift_block(0x08000000)

    assert ops[0]["op"] == "ADD"
    assert "ctx->r[0] = ctx->r[1] + ctx->r[2];" in ops[0]["c_code"]

    assert ops[1]["op"] == "SUB"
    assert "ctx->r[0] = ctx->r[1] - ctx->r[2];" in ops[1]["c_code"]

    assert ops[2]["op"] == "AND"
    assert "ctx->r[0] = ctx->r[1] & ctx->r[2];" in ops[2]["c_code"]

    assert ops[3]["op"] == "ORR"
    assert "ctx->r[0] = ctx->r[1] | ctx->r[2];" in ops[3]["c_code"]

    assert ops[4]["op"] == "EOR"
    assert "ctx->r[0] = ctx->r[1] ^ ctx->r[2];" in ops[4]["c_code"]

    assert ops[5]["op"] == "CMP"
    assert "ctx->flag_z = ((ctx->r[1] - (ctx->r[2])) == 0);" in ops[5]["c_code"]

    assert ops[6]["op"] == "BIC"
    assert "ctx->r[0] = ctx->r[1] & ~(ctx->r[2]);" in ops[6]["c_code"]


def test_arm_lifter_memory_transfers():
    # 0xE5910004: ldr r0, [r1, #4]
    # 0xE5810004: str r0, [r1, #4]
    # 0xE5D10004: ldrb r0, [r1, #4]
    # 0xE5C10004: strb r0, [r1, #4]
    # 0xE1D100B4: ldrh r0, [r1, #4]
    # 0xE12FFF1E: bx lr
    rom = struct.pack("<6I",
        0xE5910004,
        0xE5810004,
        0xE5D10004,
        0xE5C10004,
        0xE1D100B4,
        0xE12FFF1E
    )
    lifter = ArmLifter(rom, base_vram=0x08000000)
    ops, targets = lifter.lift_block(0x08000000)

    assert ops[0]["op"] == "LDR"
    assert "mem_read32(ctx, ctx->r[1] + 4)" in ops[0]["c_code"]

    assert ops[1]["op"] == "STR"
    assert "mem_write32(ctx, ctx->r[1] + 4, ctx->r[0])" in ops[1]["c_code"]

    assert ops[2]["op"] == "LDRB"
    assert "mem_read8(ctx, ctx->r[1] + 4)" in ops[2]["c_code"]

    assert ops[3]["op"] == "STRB"
    assert "mem_write8(ctx, ctx->r[1] + 4, (uint8_t)ctx->r[0])" in ops[3]["c_code"]

    assert ops[4]["op"] == "LDRH"
    assert "mem_read16(ctx, ctx->r[1] + 4)" in ops[4]["c_code"]


def test_arm_lifter_ldr_const_and_strh():
    # ldr r1, [pc, #4]
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
    assert "mem_read8" in c_source
    assert "mem_write8" in c_source
    assert "mem_read16" in c_source
    assert "mem_write16" in c_source
    assert "mem_read32" in c_source
    assert "mem_write32" in c_source
    assert "uint32_t bb_08000000(ArmCpuContext* ctx)" in c_source
    assert "uint32_t bb_080000C0(ArmCpuContext* ctx)" in c_source
    assert "int main(int argc, char** argv)" in c_source
