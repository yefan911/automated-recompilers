import os
import struct
import pytest
from src.lifter.thumb_lifter import ThumbLifter
from src.lifter.arm_lifter import ArmLifter


def test_thumb_push_pop_instruction():
    # 0xB500: push {lr}
    # 0xBD00: pop {pc}
    code = struct.pack("<2H", 0xB500, 0xBD00)
    lifter = ThumbLifter(code, base_vram=0x08001000)
    ops, targets = lifter.lift_block(0x08001000)

    assert len(ops) == 2
    assert ops[0]["op"] == "PUSH"
    assert "mem_write32" in ops[0]["c_code"]
    assert ops[1]["op"] == "POP_PC"
    assert "return" in ops[1]["c_code"]


def test_thumb_imm_arithmetic():
    # 0x2005: mov r0, #5
    # 0x3003: add r0, #3
    # 0x3802: sub r0, #2
    code = struct.pack("<3H", 0x2005, 0x3003, 0x3802)
    lifter = ThumbLifter(code, base_vram=0x08002000)
    ops, targets = lifter.lift_block(0x08002000)

    assert len(ops) >= 3
    assert ops[0]["op"] == "MOV_IMM"
    assert "ctx->r[0] = 0x00000005" in ops[0]["c_code"]
    assert ops[1]["op"] == "ADD_IMM"
    assert "ctx->r[0] += 0x00000003" in ops[1]["c_code"]
    assert ops[2]["op"] == "SUB_IMM"
    assert "ctx->r[0] -= 0x00000002" in ops[2]["c_code"]


def test_thumb_branch_conditional():
    # 0xD102: bne +2 (target: PC + 4 + 4 = 0x08003008)
    code = struct.pack("<2H", 0xD102, 0x46C0) # bne, nop
    lifter = ThumbLifter(code, base_vram=0x08003000)
    ops, targets = lifter.lift_block(0x08003000)

    assert len(ops) == 1
    assert ops[0]["op"] == "B_COND"
    assert 0x08003008 in targets
    assert 0x08003002 in targets


def test_arm_to_thumb_interworking():
    # ARM block jumping to Thumb code via bx:
    # 0x08000000: ldr r1, =0x08000009 (Thumb target with bit 0 set)
    # 0x08000004: bx r1
    # 0x08000008: .word 0x08000011
    # At 0x08000010 (Thumb):
    # 0x08000010: mov r0, #42
    # 0x08000012: bx lr
    arm_bytes = bytearray(0x40)
    struct.pack_into("<I", arm_bytes, 0x00, 0xE59F1000) # ldr r1, [pc, #0] -> loads 0x08000011
    struct.pack_into("<I", arm_bytes, 0x04, 0xE12FFF11) # bx r1
    struct.pack_into("<I", arm_bytes, 0x08, 0x08000011) # Target address with bit 0 set
    struct.pack_into("<H", arm_bytes, 0x10, 0x202A)     # mov r0, #42
    struct.pack_into("<H", arm_bytes, 0x12, 0x4770)     # bx lr

    lifter = ArmLifter(bytes(arm_bytes), base_vram=0x08000000)
    cfg = lifter.build_cfg(0x08000000)

    # Both ARM block (0x08000000) and Thumb block (0x08000010) should be discovered!
    assert cfg.has_block(0x08000000)
    assert cfg.has_block(0x08000010)
    assert len(cfg) >= 2
