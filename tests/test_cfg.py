import struct
import pytest
from src.lifter.cfg import BasicBlock, ControlFlowGraph, JumpTableInfo, JumpTableRecovery
from src.lifter.arm_lifter import ArmLifter, lift_rom_to_c


def test_basic_block_emit():
    block = BasicBlock(
        start_vram=0x08000000,
        end_vram=0x08000004,
        instructions=[
            {"pc": 0x08000000, "op": "BRANCH", "c_code": "return 0x080000C0;"}
        ],
        successors=[0x080000C0]
    )
    assert block.func_name == "bb_08000000"
    c_func = block.emit_c_function()
    assert "uint32_t bb_08000000(ArmCpuContext* ctx) {" in c_func
    assert "(void)ctx;" in c_func
    assert "return 0x080000C0;" in c_func


def test_cfg_add_and_query():
    cfg = ControlFlowGraph(entry_vram=0x08000000)
    b1 = BasicBlock(start_vram=0x08000000, successors=[0x08000020])
    b2 = BasicBlock(start_vram=0x08000020, successors=[])

    cfg.add_block(b1)
    cfg.add_block(b2)

    assert len(cfg) == 2
    assert cfg.has_block(0x08000000)
    assert cfg.has_block(0x08000020)
    assert not cfg.has_block(0x08000050)
    assert (0x08000000, 0x08000020) in cfg.edges

    protos = cfg.emit_prototypes()
    assert any("bb_08000000" in p for p in protos)
    assert any("recomp_dispatch" in p for p in protos)

    dispatch = "\n".join(cfg.emit_dispatch_switch())
    assert "case 0x08000000: next_pc = bb_08000000(&ctx); break;" in dispatch
    assert "case 0x08000020: next_pc = bb_08000020(&ctx); break;" in dispatch


def test_arm_lifter_build_cfg_hello_gba():
    with open("roms/test/hello_gba.gba", "rb") as f:
        rom = f.read()

    lifter = ArmLifter(rom, base_vram=0x08000000)
    cfg = lifter.build_cfg(0x08000000)

    # Must find at least the entry block and the payload block
    assert len(cfg) >= 2
    assert cfg.has_block(0x08000000)
    assert cfg.has_block(0x080000C0)

    # 0x08000000 should jump to 0x080000C0
    entry_block = cfg.get_block(0x08000000)
    assert 0x080000C0 in entry_block.successors


def test_arm_lifter_spin_loop_detection():
    # Spin loop opcode: b 0x08000000 (jumps to self)
    # Target = PC + 8 + (-2 << 2) = PC + 8 - 8 = PC
    rom = struct.pack("<I", 0xEAFFFFFE)
    lifter = ArmLifter(rom, base_vram=0x08000000)
    cfg = lifter.build_cfg(0x08000000)

    assert len(cfg) == 1
    block = cfg.get_block(0x08000000)
    assert block.instructions[0]["c_code"] == "return 0x00000000; /* infinite loop halt */"
    assert len(block.successors) == 0  # Does not queue self infinitely


def test_jump_table_info_and_cfg_integration():
    cfg = ControlFlowGraph(entry_vram=0x80200000)
    b1 = BasicBlock(start_vram=0x80200000, end_vram=0x80200010, is_terminal=True)
    cfg.add_block(b1)

    jt = JumpTableInfo(
        table_vram=0x80250000,
        entry_count=3,
        targets=[0x80200050, 0x80200080, 0x802000B0],
        source_pc=0x80200000,
        architecture="mips"
    )
    cfg.add_jump_table(jt)

    assert b1.terminator_type == "SWITCH"
    assert not b1.is_terminal
    assert b1.successors == [0x80200050, 0x80200080, 0x802000B0]
    assert (0x80200000, 0x80200050) in cfg.edges
    assert "Jump Table at 0x80250000" in b1.emit_c_function()


def test_recover_mips_jump_table():
    instructions = [
        {"pc": 0x80200400, "asm": "sltiu $at, $t0, 4", "c_code": ""},
        {"pc": 0x80200404, "asm": "lui $t1, 0x8020", "c_code": ""},
        {"pc": 0x80200408, "asm": "addiu $t1, $t1, 0x0500", "c_code": ""},
        {"pc": 0x8020040C, "asm": "sll $t2, $t0, 2", "c_code": ""},
        {"pc": 0x80200410, "asm": "addu $t1, $t1, $t2", "c_code": ""},
        {"pc": 0x80200414, "asm": "lw $t3, 0($t1)", "c_code": ""},
        {"pc": 0x80200418, "asm": "jr $t3", "c_code": "return ctx->r[11];"}
    ]
    mem = {
        0x80200500: 0x80200600,
        0x80200504: 0x80200640,
        0x80200508: 0x80200680,
        0x8020050C: 0x802006C0,
    }
    jt = JumpTableRecovery.recover_mips_jump_table(instructions, lambda addr: mem.get(addr, 0))
    assert jt is not None
    assert jt.table_vram == 0x80200500
    assert jt.entry_count == 4
    assert jt.targets == [0x80200600, 0x80200640, 0x80200680, 0x802006C0]


def test_recover_arm_jump_table():
    instructions = [
        {"pc": 0x08000100, "op": "CMP", "imm": 3, "c_code": "cmp r0, #3"},
        {"pc": 0x08000104, "op": "LDR_CONST", "val": 0x08000500, "c_code": "ldr r1, =0x08000500"},
        {"pc": 0x08000108, "op": "LDR", "c_code": "ldr pc, [r1, r0, lsl #2]"}
    ]
    mem = {
        0x08000500: 0x08000200,
        0x08000504: 0x08000240,
        0x08000508: 0x08000280,
    }
    jt = JumpTableRecovery.recover_arm_jump_table(instructions, lambda addr: mem.get(addr, 0))
    assert jt is not None
    assert jt.table_vram == 0x08000500
    assert jt.entry_count == 3
    assert jt.targets == [0x08000200, 0x08000240, 0x08000280]


def test_recover_snes_jump_table():
    instructions = [
        {"pc": 0x008000, "op": "CPX", "imm": 3, "c_code": "cpx #3"},
        {"pc": 0x008003, "op": "JMP_IND_X", "indirect_addr": 0x8500, "c_code": "jmp (0x8500,x)"}
    ]
    mem = {
        0x8500: 0x8100,
        0x8502: 0x8200,
        0x8504: 0x8300,
    }
    jt = JumpTableRecovery.recover_snes_jump_table(
        instructions,
        read_u16_func=lambda bank, off: mem.get(off, 0),
        bank=0x00
    )
    assert jt is not None
    assert jt.entry_count == 3
    assert jt.targets == [0x008100, 0x008200, 0x008300]

