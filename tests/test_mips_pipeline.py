import os
import struct
import tempfile
import pytest
from src.lifter.mips_lifter import MipsLifter, lift_mips_rom_to_c


def test_mips_lifter_delay_slot():
    # Function that calls a helper:
    # 0x80001000: jal 0x80001010
    # 0x80001004: addiu $a0, $zero, 42  (DELAY SLOT)
    # 0x80001008: jr $ra
    # 0x8000100C: nop                   (DELAY SLOT)
    # 0x80001010: jr $ra
    # 0x80001014: nop                   (DELAY SLOT)
    test_code = struct.pack(">6I",
        0x0C000404,  # jal 0x80001010
        0x2404002A,  # addiu $a0, $zero, 42 (delay slot)
        0x03E00008,  # jr $ra
        0x00000000,  # nop
        0x03E00008,  # jr $ra
        0x00000000,  # nop
    )
    lifter = MipsLifter(test_code, base_vram=0x80001000, is_big_endian=True)
    ops, targets = lifter.lift_block(0x80001000)

    # First instruction in block should be the call
    delay_slot_op = [op for op in ops if op.get("op") == "DELAY_SLOT"]
    assert len(delay_slot_op) >= 1
    assert "ctx->r[4] = (uint32_t)((int32_t)ctx->r[0] + 42);" in delay_slot_op[0]["c_code"]


def test_mips_lifter_branch_conditional():
    # 0x80001000: bne $a0, $a1, 0x80001010 (offset +3 instructions from pc+4)
    # 0x80001004: addiu $v0, $zero, 1 (delay slot)
    test_code = struct.pack(">2I",
        0x14850003,  # bne $a0, $a1, +3
        0x24020001,  # addiu $v0, $zero, 1
    )
    lifter = MipsLifter(test_code, base_vram=0x80001000, is_big_endian=True)
    ops, targets = lifter.lift_block(0x80001000)

    assert 0x80001010 in targets
    assert 0x80001008 in targets  # fallthrough
    assert any("ctx->r[4] != ctx->r[5]" in op.get("c_code", "") for op in ops)


def test_mips_cfg_construction():
    # A simple loop in MIPS:
    # 0x80001000: addiu $a0, $a0, -1
    # 0x80001004: bne $a0, $zero, 0x80001000 (offset -2)
    # 0x80001008: nop (delay slot)
    test_code = struct.pack(">3I",
        0x2484FFFF,  # addiu $a0, $a0, -1
        0x1480FFFD,  # bne $a0, $zero, -3 (to 0x80001000)
        0x00000000,  # nop
    )
    lifter = MipsLifter(test_code, base_vram=0x80001000, is_big_endian=True)
    cfg = lifter.build_cfg(0x80001000)

    assert len(cfg) >= 1
    assert cfg.has_block(0x80001000)


def test_lift_mips_rom_to_c():
    with tempfile.TemporaryDirectory() as tmpdir:
        rom_path = os.path.join(tmpdir, "test.z64")
        header = bytearray(0x1000)
        header[0:4] = b"\x80\x37\x12\x40" # Big-endian N64
        struct.pack_into(">I", header, 0x08, 0x80000400) # Entry point
        header[0x20:0x30] = b"TEST MIPS RECOMP"

        # Code at entry point (offset 0x400):
        # addiu $sp, $sp, -8
        # jr $ra
        # nop
        code = struct.pack(">3I", 0x27BDFFF8, 0x03E00008, 0x00000000)
        header[0x400:0x400 + len(code)] = code

        with open(rom_path, "wb") as f:
            f.write(header)

        c_source = lift_mips_rom_to_c(rom_path, entry_point=0x80000400)
        assert "MipsCpuContext" in c_source
        assert "mips_read32" in c_source
        assert "mips_write32" in c_source
        assert "recomp_mips_dispatch" in c_source
        assert "uint32_t bb_80000400(MipsCpuContext* ctx)" in c_source
        assert "int main(int argc, char** argv)" in c_source
