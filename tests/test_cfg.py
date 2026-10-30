import struct
import pytest
from src.lifter.cfg import BasicBlock, ControlFlowGraph
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
