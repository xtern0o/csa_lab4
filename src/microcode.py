from control_unit import *
from datapath import *
from isa import *


microcode_memory = []
opcode_to_microcode = {}

instr_fetch = [
    MicroInstruction(
        label="FETCH_IR_PC",
        ir_latch=1,
        pc_sel=PcSel.PC_INC,
        pc_latch=1,
    ),
    MicroInstruction(
        label="FETCH_DECODE",
        seq_branch=BranchCode.DECODE,
    ),
]

nop = [
    MicroInstruction(label="NOP"),
]

