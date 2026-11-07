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
    assert "arm_sub(ctx, ctx->r[1], ctx->r[2], 1, true)" in ops[5]["c_code"]

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
    assert "mem_read32(ctx," in ops[0]["c_code"]

    assert ops[1]["op"] == "STR"
    assert "mem_write32(ctx," in ops[1]["c_code"]

    assert ops[2]["op"] == "LDRB"
    assert "mem_read8(ctx," in ops[2]["c_code"]

    assert ops[3]["op"] == "STRB"
    assert "mem_write8(ctx," in ops[3]["c_code"]

    assert ops[4]["op"] == "LDRH"
    assert "mem_read16(ctx," in ops[4]["c_code"]


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
    assert "mem_write16(ctx," in ops[1]["c_code"]
    assert "(uint16_t)ctx->r[1]" in ops[1]["c_code"]


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
    assert "gba_bios_swi" in c_source


def test_arm_lifter_swi():
    # 0xEF000004: swi 0x04 (IntrWait)
    # 0xE12FFF1E: bx lr
    rom = struct.pack("<2I", 0xEF000004, 0xE12FFF1E)
    lifter = ArmLifter(rom, base_vram=0x08000000)
    ops, targets = lifter.lift_block(0x08000000)

    assert len(ops) == 2
    assert ops[0]["op"] == "SWI"
    assert "gba_bios_swi(ctx, 0x04)" in ops[0]["c_code"]
    assert ops[1]["op"] == "BX"


def test_mips_mult_div_branch_gte():
    raw_instructions = [
        (0x00850018, "mult"),
        (0x00850019, "multu"),
        (0x0085001A, "div"),
        (0x0085001B, "divu"),
        (0x00001010, "mfhi"),
        (0x00001012, "mflo"),
        (0x00800011, "mthi"),
        (0x00800013, "mtlo"),
        (0x00851027, "nor"),
        (0x04010005, "bgez"),
        (0x04000005, "bltz"),
        (0x18800005, "blez"),
        (0x1C800005, "bgtz"),
        (0x28850005, "slti"),
        (0x2C850005, "sltiu"),
        (0x38851234, "xori"),
        (0x40051000, "mfc0"),
        (0x40851000, "mtc0"),
        (0x4A000001, "rtps"),
        (0x4A000030, "rtpt"),
        (0x4A000006, "nclip"),
        (0x4A00002D, "avsz3"),
        (0x4A00002E, "avsz4"),
        (0x4A000028, "sqr"),
        (0xC8850004, "lwc2"),
        (0xE8850004, "swc2"),
    ]
    data = struct.pack(f">{len(raw_instructions)}I", *[r[0] for r in raw_instructions])
    lifter = MipsLifter(data, base_vram=0x80000000, is_big_endian=True)
    for i, (_, mnemonic) in enumerate(raw_instructions):
        addr = 0x80000000 + i * 4
        raw = lifter.read_u32(addr)
        info = lifter.lift_instruction(addr, raw)
        assert mnemonic in info["asm"].lower()
        assert info["c"] != ""


def test_mips_signed_loads_and_zero_reg():
    # Test LH vs LHU, LB vs LBU, and zero-register protection
    raw = [
        0x84850004,  # lh $a1, 4($a0)  -> signed 16-bit
        0x94850004,  # lhu $a1, 4($a0) -> unsigned 16-bit
        0x80850004,  # lb $a1, 4($a0)  -> signed 8-bit
        0x90850004,  # lbu $a1, 4($a0) -> unsigned 8-bit
        0x8C800004,  # lw $zero, 4($a0)-> rt=0 ($zero write protection)
    ]
    data = struct.pack(f">{len(raw)}I", *raw)
    lifter = MipsLifter(data, base_vram=0x80000000, is_big_endian=True)

    lh_info = lifter.lift_instruction(0x80000000, raw[0])
    assert "lh" in lh_info["asm"]
    assert "(int16_t)" in lh_info["c"]  # signed cast

    lhu_info = lifter.lift_instruction(0x80000004, raw[1])
    assert "lhu" in lhu_info["asm"]
    assert "(int16_t)" not in lhu_info["c"]

    lb_info = lifter.lift_instruction(0x80000008, raw[2])
    assert "lb" in lb_info["asm"]
    assert "(int8_t)" in lb_info["c"]  # signed cast

    lbu_info = lifter.lift_instruction(0x8000000C, raw[3])
    assert "lbu" in lbu_info["asm"]
    assert "(int8_t)" not in lbu_info["c"]

    lw_zero_info = lifter.lift_instruction(0x80000010, raw[4])
    assert "ctx->r[0]" not in lw_zero_info["c"]  # $zero is not written to


def test_arm_lifter_shift_edge_cases():
    # 0xE1A00021 = mov r0, r1, lsr #0 -> encodes LSR #32 -> 0 in ARM
    # 0xE1A00041 = mov r0, r1, asr #0 -> encodes ASR #32
    # 0xE1A00061 = mov r0, r1, ror #0 -> encodes RRX #1
    raw = [0xE1A00021, 0xE1A00041, 0xE1A00061, 0xEAFFFFFE]
    rom = struct.pack("<4I", *raw)
    lifter = ArmLifter(rom, base_vram=0x08000000)
    ops, _ = lifter.lift_block(0x08000000)

    # Check that no invalid "<< 32" was generated in C code
    for op in ops:
        assert "<< 32" not in op["c_code"]

