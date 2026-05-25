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
            seq_branch=BranchCode.DISPATCH_FAST,
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

# --- N-ary ops

NADD_INIT = add_block("NADD_INIT", [
    # latch_cnt = N из decoded.n, TMP1 = 0
    MicroInstruction(
        latch_cnt=1,
        alu_right_sel=AluRightSel.ZERO,
        alu_op=AluOp.PASS_R,
        alu_res_latch=1,
        latch_tmp1=1, tmp1_sel=Tmp1Sel.ALU_RES,
        seq_branch=BranchCode.NEXT,
    ),
])

NADD_LOOP = add_block("NADD_LOOP", [
    MicroInstruction(
        latch_tmp2=1, tmp2_sel=Tmp2Sel.INSTR_WORD,
        pc_sel=PcSel.PC_INC, pc_latch=1,
        seq_branch=BranchCode.NEXT,
    ),
    MicroInstruction(
        alu_right_sel=AluRightSel.TMP2,
        alu_op=AluOp.ADD,
        alu_res_latch=1,
        nzvc_latch=1,          # <- флаги здесь
        latch_tmp1=1, tmp1_sel=Tmp1Sel.ALU_RES,
        counter_dec=1,
        seq_branch=BranchCode.JCNT_Z,
        next_addr=0,
    ),
    MicroInstruction(
        seq_branch=BranchCode.JMP,
        next_addr=0,
    ),
])

NADD_END = add_block("NADD_END", [
    # res TMP1 -> R0
    MicroInstruction(
        reg_dst_sel=0,
        latch_reg=1, reg_wr_sel=RegWrSel.ALU_RES,
        seq_branch=BranchCode.END_MICRO,
    ),
])

microcode_memory[NADD_LOOP + 1].next_addr = NADD_END
microcode_memory[NADD_LOOP + 2].next_addr = NADD_LOOP


NMUL_INIT = add_block("NMUL_INIT", [
    # latch_cnt = N, TMP1 = 1
    MicroInstruction(
        latch_cnt=1,
        alu_right_sel=AluRightSel.ONE,
        alu_op=AluOp.PASS_R,
        alu_res_latch=1,
        latch_tmp1=1, tmp1_sel=Tmp1Sel.ALU_RES,
        seq_branch=BranchCode.NEXT,
    ),
])

NMUL_LOOP = add_block("NMUL_LOOP", [
    MicroInstruction(
        latch_tmp2=1, tmp2_sel=Tmp2Sel.INSTR_WORD,
        pc_sel=PcSel.PC_INC, pc_latch=1,
        seq_branch=BranchCode.NEXT,
    ),
    MicroInstruction(
        alu_right_sel=AluRightSel.TMP2,
        alu_op=AluOp.MUL,
        alu_res_latch=1,
        nzvc_latch=1,
        latch_tmp1=1, tmp1_sel=Tmp1Sel.ALU_RES,
        counter_dec=1,
        seq_branch=BranchCode.JCNT_Z,
        next_addr=0,   # -> NMUL_END
    ),
    MicroInstruction(
        seq_branch=BranchCode.JMP,
        next_addr=0,   # -> NMUL_LOOP
    ),
])

NMUL_END = add_block("NMUL_END", [
    MicroInstruction(
        reg_dst_sel=0,
        latch_reg=1, reg_wr_sel=RegWrSel.ALU_RES,
        seq_branch=BranchCode.END_MICRO,
    ),
])

microcode_memory[NMUL_LOOP + 1].next_addr = NMUL_END
microcode_memory[NMUL_LOOP + 2].next_addr = NMUL_LOOP

# --- Оптимизированные частовстречаемые операции
# --- Все математические операции ALU с адресацией IMM_REG и REG_REG
#     не подчиняются общему флоу, так как могут быть выполнены
#     за 1 такт, минуя выборку операндов и writeback 
#

def make_fast_rr(alu_op: AluOp, label: str) -> int:
    """src=REG, dst=REG - 1 такт"""
    return add_block(f"FAST_{label}_RR", [
        MicroInstruction(
            reg_src_sel=0xF, reg_dst_sel=0xF,
            latch_tmp1=1, tmp1_sel=Tmp1Sel.DST_REG,
            latch_tmp2=1, tmp2_sel=Tmp2Sel.SRC_REG,
            alu_right_sel=AluRightSel.TMP2,
            alu_op=alu_op,
            alu_res_latch=1, nzvc_latch=1,
            latch_reg=1, reg_wr_sel=RegWrSel.ALU_RES,
            seq_branch=BranchCode.END_MICRO,
        ),
    ])

def make_fast_ir(alu_op: AluOp, label: str) -> int:
    """src=IMM, dst=REG - 1 такт (читает immediate и двигает PC)"""
    return add_block(f"FAST_{label}_IR", [
        MicroInstruction(
            reg_dst_sel=0xF,
            latch_tmp1=1, tmp1_sel=Tmp1Sel.DST_REG,
            latch_tmp2=1, tmp2_sel=Tmp2Sel.INSTR_WORD,
            pc_sel=PcSel.PC_INC, pc_latch=1,
            alu_right_sel=AluRightSel.TMP2,
            alu_op=alu_op,
            alu_res_latch=1, nzvc_latch=1,
            latch_reg=1, reg_wr_sel=RegWrSel.ALU_RES,
            seq_branch=BranchCode.END_MICRO,
        ),
    ])

def make_fast_cmp_rr(label: str) -> int:
    """CMP REG/REG - без WB, только флаги"""
    return add_block(f"FAST_{label}_RR", [
        MicroInstruction(
            reg_src_sel=0xF, reg_dst_sel=0xF,
            latch_tmp1=1, tmp1_sel=Tmp1Sel.DST_REG,
            latch_tmp2=1, tmp2_sel=Tmp2Sel.SRC_REG,
            alu_right_sel=AluRightSel.TMP2,
            alu_op=AluOp.SUB,
            nzvc_latch=1,
            seq_branch=BranchCode.END_MICRO,
        ),
    ])

def make_fast_cmp_ir(label: str) -> int:
    """CMP IMM/REG - без WB"""
    return add_block(f"FAST_{label}_IR", [
        MicroInstruction(
            reg_dst_sel=0xF,
            latch_tmp1=1, tmp1_sel=Tmp1Sel.DST_REG,
            latch_tmp2=1, tmp2_sel=Tmp2Sel.INSTR_WORD,
            pc_sel=PcSel.PC_INC, pc_latch=1,
            alu_right_sel=AluRightSel.TMP2,
            alu_op=AluOp.SUB,
            nzvc_latch=1,
            seq_branch=BranchCode.END_MICRO,
        ),
    ])

def make_fast_unary_r(alu_op: AluOp, label: str) -> int:
    """унарные CLR/NEG/NOT - src=REG (операнд в src через DISPATCH_WB_UNARY)"""
    return add_block(f"FAST_{label}_R", [
        MicroInstruction(
            reg_src_sel=0xF,
            latch_tmp2=1, tmp2_sel=Tmp2Sel.SRC_REG,
            alu_right_sel=AluRightSel.TMP2,
            alu_op=alu_op,
            alu_res_latch=1, nzvc_latch=1,
            reg_dst_sel=0xF,
            latch_reg=1, reg_wr_sel=RegWrSel.ALU_RES,
            seq_branch=BranchCode.END_MICRO,
        ),
    ])

# ALU бинарные: (opcode, alu_op, label)
_BINARY_ALU = [
    (Opcode.MOVE, AluOp.PASS_R, "MOVE"),
    (Opcode.ADD,  AluOp.ADD,    "ADD"),
    (Opcode.ADC,  AluOp.ADC,    "ADC"),
    (Opcode.SUB,  AluOp.SUB,    "SUB"),
    (Opcode.SBC,  AluOp.SBC,    "SBC"),
    (Opcode.MUL,  AluOp.MUL,    "MUL"),
    (Opcode.AND_OP, AluOp.AND,  "AND"),
    (Opcode.OR_OP,  AluOp.OR,   "OR"),
    (Opcode.XOR,    AluOp.XOR,  "XOR"),
    (Opcode.ASL,    AluOp.ASL,  "ASL"),
    (Opcode.ASR,    AluOp.ASR,  "ASR"),
    (Opcode.LSL,    AluOp.LSL,  "LSL"),
    (Opcode.LSR,    AluOp.LSR,  "LSR"),
]

fast_exec_table: dict[tuple, int] = {}

for opcode, alu_op, label in _BINARY_ALU:
    rr = make_fast_rr(alu_op, label)
    ir = make_fast_ir(alu_op, label)
    fast_exec_table[(opcode, AddrMode.REG_DIRECT, AddrMode.REG_DIRECT)] = rr
    fast_exec_table[(opcode, AddrMode.IMMEDIATE,  AddrMode.REG_DIRECT)] = ir

fast_exec_table[(Opcode.CMP, AddrMode.REG_DIRECT, AddrMode.REG_DIRECT)] = make_fast_cmp_rr("CMP")
fast_exec_table[(Opcode.CMP, AddrMode.IMMEDIATE,  AddrMode.REG_DIRECT)] = make_fast_cmp_ir("CMP")

FAST_CLR_R = add_block("FAST_CLR_R", [
    MicroInstruction(
        reg_src_sel=0xF, reg_dst_sel=0xF,
        alu_right_sel=AluRightSel.ZERO,
        alu_op=AluOp.PASS_R,
        alu_res_latch=1, nzvc_latch=1,
        latch_reg=1, reg_wr_sel=RegWrSel.ALU_RES,
        seq_branch=BranchCode.END_MICRO,
    ),
])
fast_exec_table[(Opcode.CLR, AddrMode.REG_DIRECT, AddrMode.REG_DIRECT)] = FAST_CLR_R

FAST_NEG_R = add_block("FAST_NEG_R", [
    MicroInstruction(
        reg_src_sel=0xF, reg_dst_sel=0xF,
        latch_tmp1=1, tmp1_sel=Tmp1Sel.ZERO,
        latch_tmp2=1, tmp2_sel=Tmp2Sel.SRC_REG,
        alu_right_sel=AluRightSel.TMP2,
        alu_op=AluOp.SUB,
        alu_res_latch=1, nzvc_latch=1,
        latch_reg=1, reg_wr_sel=RegWrSel.ALU_RES,
        seq_branch=BranchCode.END_MICRO,
    ),
])
fast_exec_table[(Opcode.NEG, AddrMode.REG_DIRECT, AddrMode.REG_DIRECT)] = FAST_NEG_R


def make_fast_branch_imm(skip_code: BranchCode, label: str) -> int:
    return add_block(f"FAST_{label}_IMM", [
        MicroInstruction(
            latch_tmp2=1, tmp2_sel=Tmp2Sel.INSTR_WORD,
            pc_sel=PcSel.PC_INC, pc_latch=1,   
            alu_right_sel=AluRightSel.TMP2,
            alu_op=AluOp.PASS_R,
            alu_res_latch=1,
            seq_branch=skip_code,
            next_addr=0,
        ),
        # 2) перезаписываем PC адресом перехода
        MicroInstruction(
            pc_sel=PcSel.ALU_RES, pc_latch=1,
            seq_branch=BranchCode.END_MICRO,
        ),
    ])


_BRANCHES = [
    (Opcode.BEQ, BranchCode.JNZ, "BEQ"),
    (Opcode.BNE, BranchCode.JZ,  "BNE"),
    (Opcode.BMI, BranchCode.JNN, "BMI"),
    (Opcode.BPL, BranchCode.JN,  "BPL"),
    (Opcode.BCS, BranchCode.JNC, "BCS"),
    (Opcode.BCC, BranchCode.JC,  "BCC"),
    (Opcode.BVS, BranchCode.JNV, "BVS"),
    (Opcode.BVC, BranchCode.JV,  "BVC"),
    (Opcode.BLT, BranchCode.JGE, "BLT"),
    (Opcode.BGE, BranchCode.JLT, "BGE"),
    (Opcode.BLE, BranchCode.JGT, "BLE"),
    (Opcode.BGT, BranchCode.JLE, "BGT"),
]

for opcode, skip_code, label in _BRANCHES:
    addr = make_fast_branch_imm(skip_code, label)
    fast_exec_table[(opcode, AddrMode.IMMEDIATE, AddrMode.REG_DIRECT)] = addr

FAST_JMP_IMM = add_block("FAST_JMP_IMM", [
    MicroInstruction(
        latch_tmp2=1, tmp2_sel=Tmp2Sel.INSTR_WORD,
        alu_right_sel=AluRightSel.TMP2,
        alu_op=AluOp.PASS_R,
        alu_res_latch=1,
        pc_sel=PcSel.ALU_RES, pc_latch=1,
        seq_branch=BranchCode.END_MICRO,
    ),
])
fast_exec_table[(Opcode.JMP, AddrMode.IMMEDIATE, AddrMode.REG_DIRECT)] = FAST_JMP_IMM

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
    Opcode.NADD: NADD_INIT,
    Opcode.NMUL: NMUL_INIT,
}
