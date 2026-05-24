from control_unit import *
from datapath import *
from isa import *

# static microcode memory
# code below is filling this memory
microcode_memory: list[MicroInstruction] = []


def add_block(label_prefix: str, instructions: list[MicroInstruction]) -> int:
    """
    Добавляет блок микроинструкций в microcode_memory
    и возвращает индекс первой из них
    """
    start_index = len(microcode_memory)

    for instr in instructions:
        instr.label = label_prefix
        microcode_memory.append(instr)

    return start_index


def branch2(skip_branch_code: BranchCode):
    """
    Генератор микрокод для 2-тактового branch'инга:
      - такт 1: вычисляет адрес и пропускает если условие НЕ выполнено
      - такт 2: защёлкивает PC (условие выполнено)
    """
    return [
        MicroInstruction(
            alu_right_sel=AluRightSel.TMP2,
            alu_op=AluOp.PASS_R,
            alu_res_latch=1,
            seq_branch=skip_branch_code,
            next_addr=0,
        ),
        MicroInstruction(
            pc_sel=PcSel.ALU_RES, pc_latch=1, seq_branch=BranchCode.END_MICRO
        ),
    ]


# --- FETCH

FETCH_IR = add_block(
    "FETCH_INSTRUCTION",
    [
        MicroInstruction(
            ir_latch=1,
            pc_sel=PcSel.PC_INC,
            pc_latch=1,
            seq_branch=BranchCode.DISPATCH_SRC,
        ),
    ],
)

HALT_ADDR = add_block(
    "HALT",
    [
        MicroInstruction(hlt=1),
    ],
)


# --- SRC FETCH

SRC_REG = add_block(
    "SRC_REG_FETCH",
    [
        MicroInstruction(
            reg_src_sel=0xF,
            latch_tmp2=1,
            tmp2_sel=Tmp2Sel.SRC_REG,
            seq_branch=BranchCode.DISPATCH_DST,
        ),
    ],
)


SRC_IMM = add_block(
    "SRC_IMM_FETCH",
    [
        MicroInstruction(
            latch_tmp2=1,
            tmp2_sel=Tmp2Sel.INSTR_WORD,
            pc_sel=PcSel.PC_INC,
            pc_latch=1,
            seq_branch=BranchCode.DISPATCH_DST,
        ),
    ],
)


SRC_INDIRECT = add_block(
    "SRC_INDIRECT_FETCH",
    [
        MicroInstruction(reg_src_sel=0xF, ar_latch=1, mem_addr_sel=MemAddrSel.SRC_REG),
        MicroInstruction(
            latch_tmp2=1, tmp2_sel=Tmp2Sel.MEM_OUT, seq_branch=BranchCode.DISPATCH_DST
        ),
    ],
)


SRC_PRE_DEC = add_block(
    "SRC_PRE_DEC_FETCH",
    [
        # TMP1 = Rsrc; ALU = Rsrc - 4; Rsrc = ALU_OUT
        MicroInstruction(
            reg_dst_sel=0xE,
            latch_tmp1=1,
            tmp1_sel=Tmp1Sel.DST_REG,
            alu_right_sel=AluRightSel.FOUR,
            alu_op=AluOp.SUB,
            latch_reg=1,
            reg_wr_sel=RegWrSel.ALU_OUT,
            alu_res_latch=1,
        ),
        # AR = Rsrc (уже dec); TMP2 = MEM[AR]
        MicroInstruction(
            reg_src_sel=0xF,
            ar_latch=1,
            mem_addr_sel=MemAddrSel.SRC_REG,
            latch_tmp2=1,
            tmp2_sel=Tmp2Sel.MEM_OUT,
            seq_branch=BranchCode.DISPATCH_DST,
        ),
    ],
)


SRC_POST_INC = add_block(
    "SRC_POST_INC_FETCH",
    [
        # AR = Rsrc; TMP2 = MEM[AR]
        MicroInstruction(
            reg_src_sel=0xF,
            ar_latch=1,
            mem_addr_sel=MemAddrSel.SRC_REG,
            latch_tmp2=1,
            tmp2_sel=Tmp2Sel.MEM_OUT,
        ),
        # TMP1 = Rsrc (0xE); ALU = Rsrc + 4; Rsrc = ALU_OUT
        MicroInstruction(
            reg_dst_sel=0xE,
            latch_tmp1=1,
            tmp1_sel=Tmp1Sel.DST_REG,
            alu_right_sel=AluRightSel.FOUR,
            alu_op=AluOp.ADD,
            latch_reg=1,
            reg_wr_sel=RegWrSel.ALU_OUT,
            alu_res_latch=1,
            seq_branch=BranchCode.DISPATCH_DST,
        ),
    ],
)


# --- DST FETCH

DST_REG = add_block(
    "DST_REG_FETCH",
    [
        MicroInstruction(
            reg_dst_sel=0xF,
            latch_tmp1=1,
            tmp1_sel=Tmp1Sel.DST_REG,
            seq_branch=BranchCode.DISPATCH_OP,
        ),
    ],
)


DST_IMM = add_block(
    "DST_IMM_FETCH",
    [
        MicroInstruction(
            latch_tmp1=1,
            tmp1_sel=Tmp1Sel.INSTR_WORD,
            pc_sel=PcSel.PC_INC,
            pc_latch=1,
            seq_branch=BranchCode.DISPATCH_OP,
        ),
    ],
)


DST_INDIRECT = add_block(
    "DST_INDIRECT_FETCH",
    [
        MicroInstruction(reg_dst_sel=0xF, ar_latch=1, mem_addr_sel=MemAddrSel.DST_REG),
        MicroInstruction(
            latch_tmp1=1, tmp1_sel=Tmp1Sel.MEM_OUT, seq_branch=BranchCode.DISPATCH_OP
        ),
    ],
)


DST_PRE_DEC = add_block(
    "DST_PRE_DEC_FETCH",
    [
        # TMP1 = Rdst; ALU = Rdst - 4; Rdst = ALU_OUT
        MicroInstruction(
            reg_dst_sel=0xF,
            latch_tmp1=1,
            tmp1_sel=Tmp1Sel.DST_REG,
            alu_right_sel=AluRightSel.FOUR,
            alu_op=AluOp.SUB,
            latch_reg=1,
            reg_wr_sel=RegWrSel.ALU_OUT,
            alu_res_latch=1,
        ),
        # AR = --Rdst; TMP1 = MEM[AR]
        MicroInstruction(
            reg_dst_sel=0xF,
            ar_latch=1,
            mem_addr_sel=MemAddrSel.DST_REG,
            latch_tmp1=1,
            tmp1_sel=Tmp1Sel.MEM_OUT,
            seq_branch=BranchCode.DISPATCH_OP,
        ),
    ],
)


DST_POST_INC = add_block(
    "DST_POST_INC_FETCH",
    [
        # AR = Rdst; TMP1 = MEM[AR]
        MicroInstruction(
            reg_dst_sel=0xF,
            ar_latch=1,
            mem_addr_sel=MemAddrSel.DST_REG,
            latch_tmp1=1,
            tmp1_sel=Tmp1Sel.MEM_OUT,
        ),
        # Rdst += 4
        MicroInstruction(
            reg_dst_sel=0xF,
            latch_tmp1=1,
            tmp1_sel=Tmp1Sel.DST_REG,
            alu_right_sel=AluRightSel.FOUR,
            alu_op=AluOp.ADD,
            latch_reg=1,
            reg_wr_sel=RegWrSel.ALU_OUT,
            alu_res_latch=1,
        ),
        # TMP1 = MEM[AR]
        MicroInstruction(
            latch_tmp1=1, tmp1_sel=Tmp1Sel.MEM_OUT, seq_branch=BranchCode.DISPATCH_OP
        ),
    ],
)

# --- Write back

WB_REG = add_block(
    "WB_REG",
    [
        MicroInstruction(
            reg_dst_sel=0xF,
            latch_reg=1,
            reg_wr_sel=RegWrSel.ALU_RES,
            seq_branch=BranchCode.END_MICRO,
        ),
    ],
)


WB_INDIRECT = add_block(
    "WB_INDIRECT",
    [
        MicroInstruction(
            reg_dst_sel=0xF,
            ar_latch=1,
            mem_addr_sel=MemAddrSel.DST_REG,
            mem_wr=1,
            mem_data_sel=MemDataSel.ALU_RES,
            seq_branch=BranchCode.END_MICRO,
        ),
    ],
)


WB_PRE_DEC = add_block(
    "WB_PRE_DEC",
    [
        # AR = --Rdst
        MicroInstruction(
            reg_dst_sel=0xF,
            ar_latch=1,
            mem_addr_sel=MemAddrSel.DST_REG,
            mem_wr=1,
            mem_data_sel=MemDataSel.ALU_RES,
            seq_branch=BranchCode.END_MICRO,
        ),
    ],
)


WB_POST_INC = add_block(
    "WB_POST_INC",
    [
        # AR contains original address of dst
        MicroInstruction(
            mem_wr=1, mem_data_sel=MemDataSel.ALU_RES, seq_branch=BranchCode.END_MICRO
        ),
    ],
)


# --- Exec

EXEC_MOVE = add_block(
    "EXEC_MOVE",
    [
        MicroInstruction(
            alu_right_sel=AluRightSel.TMP2,
            alu_op=AluOp.PASS_R,
            alu_res_latch=1,
            nzvc_latch=1,
            seq_branch=BranchCode.DISPATCH_WB,
        ),
    ],
)

EXEC_CLR = add_block(
    "EXEC_CLR",
    [
        MicroInstruction(
            alu_right_sel=AluRightSel.ZERO,
            alu_op=AluOp.PASS_R,
            alu_res_latch=1,
            nzvc_latch=1,
            seq_branch=BranchCode.DISPATCH_WB_UNARY,
        ),
    ],
)

EXEC_NEG = add_block(
    "EXEC_NEG",
    [
        MicroInstruction(
            latch_tmp1=1,
            tmp1_sel=Tmp1Sel.ZERO,
            alu_right_sel=AluRightSel.TMP2,
            alu_op=AluOp.SUB,
            alu_res_latch=1,
            nzvc_latch=1,
            seq_branch=BranchCode.DISPATCH_WB_UNARY,
        ),
    ],
)

EXEC_ADD = add_block(
    "EXEC_ADD",
    [
        MicroInstruction(
            alu_right_sel=AluRightSel.TMP2,
            alu_op=AluOp.ADD,
            alu_res_latch=1,
            nzvc_latch=1,
            seq_branch=BranchCode.DISPATCH_WB,
        ),
    ],
)

EXEC_ADC = add_block(
    "EXEC_ADC",
    [
        MicroInstruction(
            alu_right_sel=AluRightSel.TMP2,
            alu_op=AluOp.ADC,
            alu_res_latch=1,
            nzvc_latch=1,
            seq_branch=BranchCode.DISPATCH_WB,
        ),
    ],
)

EXEC_SUB = add_block(
    "EXEC_SUB",
    [
        MicroInstruction(
            alu_right_sel=AluRightSel.TMP2,
            alu_op=AluOp.SUB,
            alu_res_latch=1,
            nzvc_latch=1,
            seq_branch=BranchCode.DISPATCH_WB,
        ),
    ],
)

EXEC_SBC = add_block(
    "EXEC_SBC",
    [
        MicroInstruction(
            alu_right_sel=AluRightSel.TMP2,
            alu_op=AluOp.SBC,
            alu_res_latch=1,
            nzvc_latch=1,
            seq_branch=BranchCode.DISPATCH_WB,
        ),
    ],
)

EXEC_MUL = add_block(
    "EXEC_MUL",
    [
        MicroInstruction(
            alu_right_sel=AluRightSel.TMP2,
            alu_op=AluOp.MUL,
            alu_res_latch=1,
            nzvc_latch=1,
            seq_branch=BranchCode.DISPATCH_WB,
        ),
    ],
)

EXEC_DIV = add_block(
    "EXEC_DIV",
    [
        MicroInstruction(
            alu_right_sel=AluRightSel.TMP2,
            alu_op=AluOp.DIV,
            alu_res_latch=1,
            nzvc_latch=1,
            seq_branch=BranchCode.DISPATCH_WB,
        ),
    ],
)

EXEC_REM = add_block(
    "EXEC_REM",
    [
        MicroInstruction(
            alu_right_sel=AluRightSel.TMP2,
            alu_op=AluOp.REM,
            alu_res_latch=1,
            nzvc_latch=1,
            seq_branch=BranchCode.DISPATCH_WB,
        ),
    ],
)

EXEC_CMP = add_block(
    "EXEC_CMP",
    [
        MicroInstruction(
            alu_right_sel=AluRightSel.TMP2,
            alu_op=AluOp.SUB,
            nzvc_latch=1,
            seq_branch=BranchCode.END_MICRO,
        ),
    ],
)

EXEC_NOT = add_block(
    "EXEC_NOT",
    [
        MicroInstruction(
            alu_right_sel=AluRightSel.TMP2,
            alu_op=AluOp.NOT_B,
            alu_res_latch=1,
            nzvc_latch=1,
            seq_branch=BranchCode.DISPATCH_WB_UNARY,
        ),
    ],
)

EXEC_AND = add_block(
    "EXEC_AND",
    [
        MicroInstruction(
            alu_right_sel=AluRightSel.TMP2,
            alu_op=AluOp.AND,
            alu_res_latch=1,
            nzvc_latch=1,
            seq_branch=BranchCode.DISPATCH_WB,
        ),
    ],
)

EXEC_OR = add_block(
    "EXEC_OR",
    [
        MicroInstruction(
            alu_right_sel=AluRightSel.TMP2,
            alu_op=AluOp.OR,
            alu_res_latch=1,
            nzvc_latch=1,
            seq_branch=BranchCode.DISPATCH_WB,
        ),
    ],
)

EXEC_XOR = add_block(
    "EXEC_XOR",
    [
        MicroInstruction(
            alu_right_sel=AluRightSel.TMP2,
            alu_op=AluOp.XOR,
            alu_res_latch=1,
            nzvc_latch=1,
            seq_branch=BranchCode.DISPATCH_WB,
        ),
    ],
)

EXEC_ASL = add_block(
    "EXEC_ASL",
    [
        # TMP1 = значение (dst), TMP2 = сдвиг (src)
        MicroInstruction(
            alu_right_sel=AluRightSel.TMP2,
            alu_op=AluOp.ASL,
            alu_res_latch=1,
            nzvc_latch=1,
            seq_branch=BranchCode.DISPATCH_WB,
        ),
    ],
)

EXEC_ASR = add_block(
    "EXEC_ASR",
    [
        MicroInstruction(
            alu_right_sel=AluRightSel.TMP2,
            alu_op=AluOp.ASR,
            alu_res_latch=1,
            nzvc_latch=1,
            seq_branch=BranchCode.DISPATCH_WB,
        ),
    ],
)

EXEC_LSL = add_block(
    "EXEC_LSL",
    [
        MicroInstruction(
            alu_right_sel=AluRightSel.TMP2,
            alu_op=AluOp.LSL,
            alu_res_latch=1,
            nzvc_latch=1,
            seq_branch=BranchCode.DISPATCH_WB,
        ),
    ],
)

EXEC_LSR = add_block(
    "EXEC_LSR",
    [
        MicroInstruction(
            alu_right_sel=AluRightSel.TMP2,
            alu_op=AluOp.LSR,
            alu_res_latch=1,
            nzvc_latch=1,
            seq_branch=BranchCode.DISPATCH_WB,
        ),
    ],
)

# control-flow

EXEC_JMP = add_block(
    "EXEC_JMP",
    [
        MicroInstruction(
            alu_right_sel=AluRightSel.TMP2,
            alu_op=AluOp.PASS_R,
            alu_res_latch=1,
            pc_sel=PcSel.ALU_RES,
            pc_latch=1,
            seq_branch=BranchCode.END_MICRO,
        ),
    ],
)

EXEC_BEQ = add_block("EXEC_BEQ", branch2(BranchCode.JNZ))
EXEC_BNE = add_block("EXEC_BNE", branch2(BranchCode.JZ))
EXEC_BMI = add_block("EXEC_BMI", branch2(BranchCode.JNN))
EXEC_BPL = add_block("EXEC_BPL", branch2(BranchCode.JN))
EXEC_BCS = add_block("EXEC_BCS", branch2(BranchCode.JNC))
EXEC_BCC = add_block("EXEC_BCC", branch2(BranchCode.JC))
EXEC_BVS = add_block("EXEC_BVS", branch2(BranchCode.JNV))
EXEC_BVC = add_block("EXEC_BVC", branch2(BranchCode.JV))
EXEC_BLT = add_block("EXEC_BLT", branch2(BranchCode.JGE))
EXEC_BGE = add_block("EXEC_BGE", branch2(BranchCode.JLT))
EXEC_BLE = add_block("EXEC_BLE", branch2(BranchCode.JGT))
EXEC_BGT = add_block("EXEC_BGT", branch2(BranchCode.JLE))

EXEC_OUT = add_block(
    "EXEC_OUT",
    [
        # 1) port = TMP1
        MicroInstruction(
            alu_op=AluOp.PASS_L,
            port_latch=1,
            seq_branch=BranchCode.NEXT,
        ),
        # 2) data = TMP2
        MicroInstruction(
            alu_right_sel=AluRightSel.TMP2,
            alu_op=AluOp.PASS_R,
            alu_res_latch=1,
            out_sel=OutSel.ALU_RES,
            out_latch=1,
            seq_branch=BranchCode.END_MICRO,
        ),
    ],
)

EXEC_IN = add_block(
    "EXEC_IN",
    [
        # 1) port = TMP1
        MicroInstruction(
            alu_op=AluOp.PASS_L,
            port_latch=1,
            seq_branch=BranchCode.NEXT,
        ),
        # 2) in[port] -> src_reg
        MicroInstruction(
            reg_dst_sel=0xE,
            latch_reg=1,
            reg_wr_sel=RegWrSel.INPUT_DATA,
            seq_branch=BranchCode.END_MICRO,
        ),
    ],
)

# --- Оптимизированные частовстречаемые операции

FAST_ADD_RR = add_block("FAST_ADD_RR", [
    MicroInstruction(
        reg_src_sel=0, reg_dst_sel=1,
        latch_tmp1=1, tmp1_sel=Tmp1Sel.DST_REG,
        latch_tmp2=1, tmp2_sel=Tmp2Sel.SRC_REG,
        alu_op=AluOp.ADD,
        latch_reg=1, reg_wr_sel=RegWrSel.ALU_OUT,
        nzvc_latch=1,
        seq_branch=BranchCode.END_MICRO,
    ),
])

FAST_ADD_IR = add_block("FAST_ADD_IR", [
    MicroInstruction(
        reg_dst_sel=1,
        latch_tmp1=1, tmp1_sel=Tmp1Sel.DST_REG,
        latch_tmp2=1, tmp2_sel=Tmp2Sel.INSTR_WORD,
        pc_sel=PcSel.PC_INC, pc_latch=1,
        alu_op=AluOp.ADD,
        latch_reg=1, reg_wr_sel=RegWrSel.ALU_OUT,
        nzvc_latch=1,
        seq_branch=BranchCode.END_MICRO,
    ),
])

src_dispatch_table = {
    AddrMode.REG_DIRECT: SRC_REG,
    AddrMode.IMMEDIATE: SRC_IMM,
    AddrMode.REG_INDIRECT: SRC_INDIRECT,
    AddrMode.PRE_DEC: SRC_PRE_DEC,
    AddrMode.POST_INC: SRC_POST_INC,
}

dst_dispatch_table = {
    AddrMode.REG_DIRECT: DST_REG,
    AddrMode.IMMEDIATE: DST_IMM,
    AddrMode.REG_INDIRECT: DST_INDIRECT,
    AddrMode.PRE_DEC: DST_PRE_DEC,
    AddrMode.POST_INC: DST_POST_INC,
}

wb_dispatch_table = {
    AddrMode.REG_DIRECT: WB_REG,
    AddrMode.REG_INDIRECT: WB_INDIRECT,
    AddrMode.PRE_DEC: WB_PRE_DEC,
    AddrMode.POST_INC: WB_POST_INC,
}

fast_exec_table = {
    (Opcode.ADD, AddrMode.REG_DIRECT, AddrMode.REG_DIRECT): FAST_ADD_RR,
    (Opcode.ADD, AddrMode.IMMEDIATE, AddrMode.REG_DIRECT): FAST_ADD_IR,

}

opcode_to_mpc = {
    Opcode.MOVE: EXEC_MOVE,
    Opcode.CLR: EXEC_CLR,
    Opcode.NEG: EXEC_NEG,
    Opcode.ADD: EXEC_ADD,
    Opcode.ADC: EXEC_ADC,
    Opcode.SUB: EXEC_SUB,
    Opcode.SBC: EXEC_SBC,
    Opcode.MUL: EXEC_MUL,
    Opcode.DIV: EXEC_DIV,
    Opcode.REM: EXEC_REM,
    Opcode.CMP: EXEC_CMP,
    Opcode.HALT: HALT_ADDR,
    Opcode.NOT_OP: EXEC_NOT,
    Opcode.AND_OP: EXEC_AND,
    Opcode.OR_OP: EXEC_OR,
    Opcode.XOR: EXEC_XOR,
    Opcode.ASL: EXEC_ASL,
    Opcode.ASR: EXEC_ASR,
    Opcode.LSL: EXEC_LSL,
    Opcode.LSR: EXEC_LSR,
    Opcode.JMP: EXEC_JMP,
    Opcode.BEQ: EXEC_BEQ,
    Opcode.BNE: EXEC_BNE,
    Opcode.BMI: EXEC_BMI,
    Opcode.BPL: EXEC_BPL,
    Opcode.BCS: EXEC_BCS,
    Opcode.BCC: EXEC_BCC,
    Opcode.BVS: EXEC_BVS,
    Opcode.BVC: EXEC_BVC,
    Opcode.BLT: EXEC_BLT,
    Opcode.BGE: EXEC_BGE,
    Opcode.BLE: EXEC_BLE,
    Opcode.BGT: EXEC_BGT,
    Opcode.IN: EXEC_IN,
    Opcode.OUT: EXEC_OUT,
}

# Регрессионные тесты после оптимизации PASS_L/PASS_R
# Вставить в конец microcode.py


def make_cu(prog, initial_regs=None, data_memory_setup=None,
            input_tokens=None, mem_size=256):
    instr_bytes = b"".join(instr.to_bytes() for instr in prog)
    instr_mem   = list(instr_bytes)
    io  = IOController()
    if input_tokens:
        io.input_tokens = list(input_tokens)
    dp  = DataPath(instr_mem, io, data_memory_size=mem_size,
                   instr_memory_size=max(len(instr_mem), 64))
    if initial_regs:
        for reg, val in initial_regs.items():
            dp.registers[reg] = val & 0xFFFFFFFF
    if data_memory_setup:
        for addr, val in data_memory_setup:
            val = val & 0xFFFFFFFF
            dp.data_memory[addr]   =  val        & 0xFF
            dp.data_memory[addr+1] = (val >>  8) & 0xFF
            dp.data_memory[addr+2] = (val >> 16) & 0xFF
            dp.data_memory[addr+3] = (val >> 24) & 0xFF
    cu = ControlUnit(dp, microcode_memory, opcode_to_mpc,
                     src_dispatch_table, dst_dispatch_table, wb_dispatch_table)
    cu.mpc = FETCH_IR
    cu.mir = microcode_memory[FETCH_IR]
    return cu, dp


def run(cu, dp, limit=500):
    tick = 0
    try:
        while True:
            if cu.current_micro is None:
                break
            cu.tick()
            tick += 1
            if tick > limit:
                raise RuntimeError(f"Tick limit exceeded at {tick}")
    except StopIteration:
        pass
    return dp


def mem32(dp, addr):
    return (dp.data_memory[addr]
            | (dp.data_memory[addr+1] << 8)
            | (dp.data_memory[addr+2] << 16)
            | (dp.data_memory[addr+3] << 24))


def R(n):    return Operand(AddrMode.REG_DIRECT,   n)
def IMM(v):  return Operand(AddrMode.IMMEDIATE,    v)
def IND(n):  return Operand(AddrMode.REG_INDIRECT, n)
def PRE(n):  return Operand(AddrMode.PRE_DEC,      n)
def POST(n): return Operand(AddrMode.POST_INC,     n)
def HALT():  return Instruction(Opcode.HALT, [])


if __name__ == "__main__":
    passed = 0
    failed = 0

    def check(name, cond, msg=""):
        global passed, failed
        if cond:
            print(f"  OK  {name}")
            passed += 1
        else:
            print(f"  FAIL {name}  {msg}")
            failed += 1

    # ------------------------------------------------------------------
    print("=== MOVE (PASS_R) ===")

    cu, dp = make_cu([Instruction(Opcode.MOVE, [R(0), R(1)]), HALT()],
                     initial_regs={0: 42, 1: 0})
    run(cu, dp)
    check("MOVE R0,R1", dp.registers[1] == 42, f"R1={dp.registers[1]}")

    cu, dp = make_cu([Instruction(Opcode.MOVE, [IMM(99), R(2)]), HALT()])
    run(cu, dp)
    check("MOVE #99,R2", dp.registers[2] == 99, f"R2={dp.registers[2]}")

    cu, dp = make_cu([Instruction(Opcode.MOVE, [R(0), IND(1)]), HALT()],
                     initial_regs={0: 77, 1: 40},
                     data_memory_setup=[(40, 0)])
    run(cu, dp)
    check("MOVE R0,(R1) indirect dst", mem32(dp, 40) == 77, f"mem[40]={mem32(dp, 40)}")

    cu, dp = make_cu([Instruction(Opcode.MOVE, [IND(0), R(1)]), HALT()],
                     initial_regs={0: 20, 1: 0},
                     data_memory_setup=[(20, 123)])
    run(cu, dp)
    check("MOVE (R0),R1 indirect src", dp.registers[1] == 123, f"R1={dp.registers[1]}")

    # MOVE flags: Z=1 for zero
    cu, dp = make_cu([Instruction(Opcode.MOVE, [IMM(0), R(0)]), HALT()])
    run(cu, dp)
    check("MOVE #0,R0 -> Z=1", dp.flag_z, f"Z={dp.flag_z}")

    # MOVE flags: N=1 for negative
    cu, dp = make_cu([Instruction(Opcode.MOVE, [IMM(-1), R(0)]), HALT()])
    run(cu, dp)
    check("MOVE #0xFFFFFFFF,R0 -> N=1", dp.flag_n, f"N={dp.flag_n}")

    # ------------------------------------------------------------------
    print("=== CLR (PASS_R ZERO) ===")

    cu, dp = make_cu([Instruction(Opcode.CLR, [R(0)]), HALT()],
                     initial_regs={0: 0xDEADBEEF})
    run(cu, dp)
    check("CLR R0 -> 0", dp.registers[0] == 0, f"R0={dp.registers[0]}")
    check("CLR R0 -> Z=1", dp.flag_z, f"Z={dp.flag_z}")


    cu, dp = make_cu([Instruction(Opcode.CLR, [IND(0)]), HALT()],
                     initial_regs={0: 20},
                     data_memory_setup=[(20, 0xFFFFFFFF)])
    run(cu, dp)
    check("CLR (R0) indirect", mem32(dp, 20) == 0, f"mem[20]={mem32(dp, 20)}")

    cu, dp = make_cu([Instruction(Opcode.CLR, [PRE(0)]), HALT()],
                     initial_regs={0: 24},
                     data_memory_setup=[(20, 0xABCD)])
    run(cu, dp)
    check("CLR -(R0) pre-dec reg", dp.registers[0] == 20, f"R0={dp.registers[0]}")
    check("CLR -(R0) pre-dec val", mem32(dp, 20) == 0, f"mem[20]={mem32(dp, 20)}")

    cu, dp = make_cu([Instruction(Opcode.CLR, [POST(0)]), HALT()],
                     initial_regs={0: 30},
                     data_memory_setup=[(30, 0x1234)])
    run(cu, dp)
    check("CLR (R0)+ post-inc reg", dp.registers[0] == 34, f"R0={dp.registers[0]}")
    check("CLR (R0)+ post-inc val", mem32(dp, 30) == 0, f"mem[30]={mem32(dp, 30)}")

    # ------------------------------------------------------------------
    print("=== NEG (SUB с Tmp1Sel.ZERO) ===")

    cu, dp = make_cu([Instruction(Opcode.NEG, [R(0)]), HALT()],
                     initial_regs={0: 5})
    run(cu, dp)
    check("NEG R0: 5->-5", dp.registers[0] == 0xFFFFFFFB, f"R0={dp.registers[0]:#010x}")

    cu, dp = make_cu([Instruction(Opcode.NEG, [R(0)]),
                      Instruction(Opcode.NEG, [R(0)]), HALT()],
                     initial_regs={0: 12345})
    run(cu, dp)
    check("NEG x2 -> исходное", dp.registers[0] == 12345, f"R0={dp.registers[0]}")

    cu, dp = make_cu([Instruction(Opcode.NEG, [R(0)]), HALT()],
                     initial_regs={0: 0})
    run(cu, dp)
    check("NEG 0 -> 0, Z=1", dp.registers[0] == 0 and dp.flag_z,
          f"R0={dp.registers[0]} Z={dp.flag_z}")

    cu, dp = make_cu([Instruction(Opcode.NEG, [IND(0)]), HALT()],
                     initial_regs={0: 20},
                     data_memory_setup=[(20, 10)])
    run(cu, dp)
    check("NEG (R0) indirect", mem32(dp, 20) == 0xFFFFFFF6,
          f"mem[20]={mem32(dp, 20):#010x}")

    # ------------------------------------------------------------------
    print("=== ADD/SUB/MUL ===")

    cu, dp = make_cu([Instruction(Opcode.ADD, [R(0), R(1)]), HALT()],
                     initial_regs={0: 3, 1: 5})
    run(cu, dp)
    check("ADD R0,R1", dp.registers[1] == 8, f"R1={dp.registers[1]}")

    cu, dp = make_cu([Instruction(Opcode.ADD, [IMM(7), R(1)]), HALT()],
                     initial_regs={1: 10})
    run(cu, dp)
    check("ADD #7,R1", dp.registers[1] == 17, f"R1={dp.registers[1]}")

    cu, dp = make_cu([Instruction(Opcode.SUB, [R(0), R(1)]), HALT()],
                     initial_regs={0: 3, 1: 10})
    run(cu, dp)
    check("SUB R0,R1", dp.registers[1] == 7, f"R1={dp.registers[1]}")

    cu, dp = make_cu([Instruction(Opcode.MUL, [R(0), R(1)]), HALT()],
                     initial_regs={0: 6, 1: 7})
    run(cu, dp)
    check("MUL R0,R1 (6*7=42)", dp.registers[1] == 42, f"R1={dp.registers[1]}")

    # ------------------------------------------------------------------
    print("=== JMP (PASS_R) ===")

    p = [
        Instruction(Opcode.JMP,  [IMM(16)]),         # [0] 8 байт
        Instruction(Opcode.ADD,  [IMM(99), R(0)]),   # [8] 8 байт <- пропустить
        HALT(),                                       # [20]
    ]
    cu, dp = make_cu(p, initial_regs={0: 0})
    run(cu, dp)
    check("JMP #20 пропускает ADD", dp.registers[0] == 0, f"R0={dp.registers[0]}")

    p = [
        Instruction(Opcode.MOVE, [IMM(20), R(0)]),   # [0] 8 байт
        Instruction(Opcode.JMP,  [R(0)]),             # [8] 4 байта
        Instruction(Opcode.ADD,  [IMM(99), R(1)]),   # [12] <- пропустить
        HALT(),                                       # [20]
    ]
    cu, dp = make_cu(p, initial_regs={1: 0})
    run(cu, dp)
    check("JMP R0 indirect", dp.registers[1] == 0, f"R1={dp.registers[1]}")

    # ------------------------------------------------------------------
    print("=== branch2 (PASS_R) ===")


    # BEQ taken
    p = [
        Instruction(Opcode.CMP, [R(0), R(1)]),       # [0]
        Instruction(Opcode.BEQ, [IMM(20)]),           # [4]
        Instruction(Opcode.ADD, [IMM(99), R(2)]),     # [12]
        HALT(),                                       # [20]
    ]
    cu, dp = make_cu(p, initial_regs={0: 5, 1: 5, 2: 0})
    run(cu, dp)
    check("BEQ taken (R0==R1)", dp.registers[2] == 0, f"R2={dp.registers[2]}")

    # BEQ not taken
    cu, dp = make_cu(p, initial_regs={0: 3, 1: 5, 2: 0})
    run(cu, dp)
    check("BEQ not taken (R0!=R1)", dp.registers[2] == 99, f"R2={dp.registers[2]}")

    # BNE taken
    p = [
        Instruction(Opcode.CMP, [R(0), R(1)]),
        Instruction(Opcode.BNE, [IMM(20)]),
        Instruction(Opcode.ADD, [IMM(99), R(2)]),
        HALT(),
    ]
    cu, dp = make_cu(p, initial_regs={0: 3, 1: 5, 2: 0})
    run(cu, dp)
    check("BNE taken", dp.registers[2] == 0, f"R2={dp.registers[2]}")

    # BLT taken (signed)
    p = [
        Instruction(Opcode.CMP, [R(0), R(1)]),
        Instruction(Opcode.BLT, [IMM(20)]),
        Instruction(Opcode.ADD, [IMM(99), R(2)]),
        HALT(),
    ]
    cu, dp = make_cu(p, initial_regs={0: 10, 1: 3, 2: 0})  # 3 < 10
    run(cu, dp)
    check("BLT taken (3 < 10)", dp.registers[2] == 0, f"R2={dp.registers[2]}")

    # BGE taken
    p = [
        Instruction(Opcode.CMP, [R(0), R(1)]),
        Instruction(Opcode.BGE, [IMM(20)]),
        Instruction(Opcode.ADD, [IMM(99), R(2)]),
        HALT(),
    ]
    cu, dp = make_cu(p, initial_regs={0: 3, 1: 10, 2: 0})  # 10 >= 3
    run(cu, dp)
    check("BGE taken (10 >= 3)", dp.registers[2] == 0, f"R2={dp.registers[2]}")

    # Цикл
    loop = [
        Instruction(Opcode.ADD, [R(2), R(1)]),        # [0]  sum += i
        Instruction(Opcode.ADD, [IMM(1), R(2)]),       # [4]  i++
        Instruction(Opcode.CMP, [R(0), R(2)]),         # [12] cmp N,i
        Instruction(Opcode.BLE, [IMM(0)]),             # [20] if i<=N goto 0
        HALT(),                                        # [28]
    ]
    cu, dp = make_cu(loop, initial_regs={0: 5, 1: 0, 2: 1})
    run(cu, dp, limit=1000)
    check("Loop sum 1..5=15", dp.registers[1] == 15, f"R1={dp.registers[1]}")

    # ------------------------------------------------------------------
    print("=== OUT (PASS_L + PASS_R) ===")

    cu, dp = make_cu([Instruction(Opcode.OUT, [R(0), IMM(0)]), HALT()],
                     initial_regs={0: 42})
    run(cu, dp)
    check("OUT R0,#0: '42'",
          dp.io_controller.output_buffer == ['42'],
          f"buf={dp.io_controller.output_buffer}")

    cu, dp = make_cu([Instruction(Opcode.OUT, [R(0), IMM(2)]), HALT()],
                     initial_regs={0: ord('A')})
    run(cu, dp)
    check("OUT R0,#2: 'A'",
          dp.io_controller.output_buffer == ['A'],
          f"buf={dp.io_controller.output_buffer}")

    cu, dp = make_cu([Instruction(Opcode.OUT, [IMM(255), IMM(0)]), HALT()])
    run(cu, dp)
    check("OUT #255,#0 imm src",
          dp.io_controller.output_buffer == ['255'],
          f"buf={dp.io_controller.output_buffer}")

    cu, dp = make_cu([Instruction(Opcode.OUT, [IND(0), IMM(0)]), HALT()],
                     initial_regs={0: 20},
                     data_memory_setup=[(20, 777)])
    run(cu, dp)
    check("OUT (R0),#0 indirect src",
          dp.io_controller.output_buffer == ['777'],
          f"buf={dp.io_controller.output_buffer}")

    cu, dp = make_cu([Instruction(Opcode.OUT, [POST(0), IMM(0)]), HALT()],
                     initial_regs={0: 30},
                     data_memory_setup=[(30, 123)])
    run(cu, dp)
    check("OUT (R0)+,#0 post-inc",
          dp.registers[0] == 34 and dp.io_controller.output_buffer == ['123'],
          f"R0={dp.registers[0]} buf={dp.io_controller.output_buffer}")

    # ------------------------------------------------------------------
    print("=== IN (PASS_L) ===")

    cu, dp = make_cu([Instruction(Opcode.IN, [R(0), IMM(1)]), HALT()],
                     input_tokens=[42])
    run(cu, dp)
    check("IN R0,#1: R0=42", dp.registers[0] == 42, f"R0={dp.registers[0]}")


    cu, dp = make_cu([Instruction(Opcode.IN, [R(0), IMM(3)]), HALT()],
                     input_tokens=['A'])
    run(cu, dp)
    check("IN R0,#3: R0=ord('A')=65", dp.registers[0] == 65, f"R0={dp.registers[0]}")

    cu, dp = make_cu([
        Instruction(Opcode.IN,  [R(0), IMM(1)]),
        Instruction(Opcode.OUT, [R(0), IMM(0)]),
        HALT()
    ], input_tokens=[123])
    run(cu, dp)
    check("IN+OUT echo: '123'",
          dp.io_controller.output_buffer == ['123'],
          f"buf={dp.io_controller.output_buffer}")

    # ------------------------------------------------------------------
    print("=== Режимы адресации (регрессия) ===")

    # ADD все режимы src
    cu, dp = make_cu([Instruction(Opcode.ADD, [IND(0), R(1)]), HALT()],
                     initial_regs={0: 20, 1: 100},
                     data_memory_setup=[(20, 13)])
    run(cu, dp)
    check("ADD (R0),R1 indirect", dp.registers[1] == 113, f"R1={dp.registers[1]}")

    cu, dp = make_cu([Instruction(Opcode.ADD, [PRE(0), R(1)]), HALT()],
                     initial_regs={0: 24, 1: 200},
                     data_memory_setup=[(20, 9)])
    run(cu, dp)
    check("ADD -(R0),R1 pre-dec reg", dp.registers[0] == 20, f"R0={dp.registers[0]}")
    check("ADD -(R0),R1 pre-dec val", dp.registers[1] == 209, f"R1={dp.registers[1]}")

    cu, dp = make_cu([Instruction(Opcode.ADD, [POST(0), R(1)]), HALT()],
                     initial_regs={0: 30, 1: 50},
                     data_memory_setup=[(30, 15)])
    run(cu, dp)
    check("ADD (R0)+,R1 post-inc reg", dp.registers[0] == 34, f"R0={dp.registers[0]}")
    check("ADD (R0)+,R1 post-inc val", dp.registers[1] == 65, f"R1={dp.registers[1]}")

    # ADD dst режимы
    cu, dp = make_cu([Instruction(Opcode.ADD, [R(0), IND(1)]), HALT()],
                     initial_regs={0: 77, 1: 40},
                     data_memory_setup=[(40, 11)])
    run(cu, dp)
    check("ADD R0,(R1) indirect dst", mem32(dp, 40) == 88, f"mem[40]={mem32(dp, 40)}")

    cu, dp = make_cu([Instruction(Opcode.ADD, [R(0), PRE(1)]), HALT()],
                     initial_regs={0: 5, 1: 44},
                     data_memory_setup=[(40, 33)])
    run(cu, dp)
    check("ADD R0,-(R1) pre-dec dst reg", dp.registers[1] == 40, f"R1={dp.registers[1]}")
    check("ADD R0,-(R1) pre-dec dst val", mem32(dp, 40) == 38, f"mem[40]={mem32(dp, 40)}")

    cu, dp = make_cu([Instruction(Opcode.ADD, [R(0), POST(1)]), HALT()],
                     initial_regs={0: 20, 1: 50},
                     data_memory_setup=[(50, 7)])
    run(cu, dp)
    check("ADD R0,(R1)+ post-inc dst reg", dp.registers[1] == 54, f"R1={dp.registers[1]}")
    check("ADD R0,(R1)+ post-inc dst val", mem32(dp, 50) == 27, f"mem[50]={mem32(dp, 50)}")

    # Комбо: -(R0),(R1)+
    cu, dp = make_cu([Instruction(Opcode.ADD, [PRE(0), POST(1)]), HALT()],
                     initial_regs={0: 24, 1: 50},
                     data_memory_setup=[(20, 9), (50, 7)])
    run(cu, dp)
    check("ADD -(R0),(R1)+ src_dec", dp.registers[0] == 20, f"R0={dp.registers[0]}")
    check("ADD -(R0),(R1)+ dst_inc", dp.registers[1] == 54, f"R1={dp.registers[1]}")
    check("ADD -(R0),(R1)+ result",  mem32(dp, 50) == 16, f"mem[50]={mem32(dp, 50)}")

    # ------------------------------------------------------------------
    print(f"\n{'='*40}")
    print(f"Result: {passed} passed, {failed} failed")
    if failed == 0:
        print("All tests passed!")
    else:
        print("There are failed tests!")
