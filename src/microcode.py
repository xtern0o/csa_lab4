from control_unit import *
from datapath import *
from isa import *


microcode_memory = []


def add_block(label_prefix: str, instructions: list[MicroInstruction]) -> int:
    """Добавляет блок микроинструкций в microcode_memory и возвращает индекс первой из них"""
    start_index = len(microcode_memory)

    for instr in instructions:
        instr.label = label_prefix
        microcode_memory.append(instr)

    return start_index



# --- FETCH

FETCH_IR = add_block("FETCH", [
    MicroInstruction(
        ir_latch=1,
        pc_sel=PcSel.PC_INC,
        pc_latch=1
    ),
])

FETCH_DISPATCH_SRC = add_block("FETCH_DISPATCH_SRC", [
    MicroInstruction(
        seq_branch=BranchCode.DISPATCH_SRC
    ),
])


HALT_ADDR = add_block("HALT", [
    MicroInstruction(
        hlt=1
    ),
])


# --- SRC FETCH

SRC_REG = add_block("SRC_REG_FETCH", [
    MicroInstruction(
        reg_src_sel=0xF,
        latch_tmp2=1,
        tmp2_sel=Tmp2Sel.SRC_REG,
        seq_branch=BranchCode.DISPATCH_DST
    ),
])


SRC_IMM = add_block("SRC_IMM_FETCH", [
    MicroInstruction(
        latch_tmp2=1,
        tmp2_sel=Tmp2Sel.INSTR_WORD,
        pc_sel=PcSel.PC_INC,
        pc_latch=1,
        seq_branch=BranchCode.DISPATCH_DST
    ),
])


SRC_INDIRECT = add_block("SRC_INDIRECT_FETCH", [
    MicroInstruction(
        reg_src_sel=0xF,
        ar_latch=1,
        mem_addr_sel=MemAddrSel.SRC_REG
    ),
    MicroInstruction(
        latch_tmp2=1,
        tmp2_sel=Tmp2Sel.MEM_OUT,
        seq_branch=BranchCode.DISPATCH_DST
    ),
])


SRC_PRE_DEC = add_block("SRC_PRE_DEC_FETCH", [
    # TMP1 = Rsrc (через 0xE); ALU = Rsrc - 4; Rsrc = ALU_OUT
    MicroInstruction(
        reg_dst_sel=0xE,
        latch_tmp1=1, tmp1_sel=Tmp1Sel.DST_REG,
        alu_right_sel=AluRightSel.FOUR,
        alu_op=AluOp.SUB,
        latch_reg=1, reg_wr_sel=RegWrSel.ALU_OUT,
        alu_res_latch=1,
    ),
    # AR = Rsrc (уже dec); TMP2 = MEM[AR]
    MicroInstruction(
        reg_src_sel=0xF,
        ar_latch=1, mem_addr_sel=MemAddrSel.SRC_REG,
        latch_tmp2=1, tmp2_sel=Tmp2Sel.MEM_OUT,
        seq_branch=BranchCode.DISPATCH_DST
    ),
])


SRC_POST_INC = add_block("SRC_POST_INC_FETCH", [
    # AR = Rsrc; TMP2 = MEM[AR]
    MicroInstruction(
        reg_src_sel=0xF,
        ar_latch=1, mem_addr_sel=MemAddrSel.SRC_REG,
        latch_tmp2=1, tmp2_sel=Tmp2Sel.MEM_OUT,
    ),
    # TMP1 = Rsrc (через 0xE); ALU = Rsrc + 4; Rsrc = ALU_OUT  (TMP2 не трогаем)
    MicroInstruction(
        reg_dst_sel=0xE,
        latch_tmp1=1, tmp1_sel=Tmp1Sel.DST_REG,
        alu_right_sel=AluRightSel.FOUR,
        alu_op=AluOp.ADD,
        latch_reg=1, reg_wr_sel=RegWrSel.ALU_OUT,
        alu_res_latch=1,
        seq_branch=BranchCode.DISPATCH_DST
    ),
])


# --- DST FETCH

DST_REG = add_block("DST_REG_FETCH", [
    MicroInstruction(
        reg_dst_sel=0xF,
        latch_tmp1=1,
        tmp1_sel=Tmp1Sel.DST_REG,
        seq_branch=BranchCode.DISPATCH_OP
    ),
])


DST_IMM = add_block("DST_IMM_FETCH", [
    MicroInstruction(
        latch_tmp1=1,
        tmp1_sel=Tmp1Sel.INSTR_WORD,
        pc_sel=PcSel.PC_INC,
        pc_latch=1,
        seq_branch=BranchCode.DISPATCH_OP
    ),
])


DST_INDIRECT = add_block("DST_INDIRECT_FETCH", [
    MicroInstruction(
        reg_dst_sel=0xF,
        ar_latch=1,
        mem_addr_sel=MemAddrSel.DST_REG
    ),
    MicroInstruction(
        latch_tmp1=1,
        tmp1_sel=Tmp1Sel.MEM_OUT,
        seq_branch=BranchCode.DISPATCH_OP
    ),
])


DST_PRE_DEC = add_block("DST_PRE_DEC_FETCH", [
    # TMP1 = Rdst; ALU = Rdst - 4; Rdst = ALU_OUT
    MicroInstruction(
        reg_dst_sel=0xF,
        latch_tmp1=1, tmp1_sel=Tmp1Sel.DST_REG,
        alu_right_sel=AluRightSel.FOUR,
        alu_op=AluOp.SUB,
        latch_reg=1, reg_wr_sel=RegWrSel.ALU_OUT,
        alu_res_latch=1,
    ),
    # AR = Rdst (уже dec); TMP1 = MEM[AR]
    MicroInstruction(
        reg_dst_sel=0xF,
        ar_latch=1, mem_addr_sel=MemAddrSel.DST_REG,
        latch_tmp1=1, tmp1_sel=Tmp1Sel.MEM_OUT,
        seq_branch=BranchCode.DISPATCH_OP
    ),
])


DST_POST_INC = add_block("DST_POST_INC_FETCH", [
    # AR = Rdst; TMP1 = MEM[AR]
    MicroInstruction(
        reg_dst_sel=0xF,
        ar_latch=1, mem_addr_sel=MemAddrSel.DST_REG,
        latch_tmp1=1, tmp1_sel=Tmp1Sel.MEM_OUT,
    ),
    # Rdst += 4  (используем TMP1 временно — потом восстановим)
    MicroInstruction(
        reg_dst_sel=0xF,
        latch_tmp1=1, tmp1_sel=Tmp1Sel.DST_REG,
        alu_right_sel=AluRightSel.FOUR,
        alu_op=AluOp.ADD,
        latch_reg=1, reg_wr_sel=RegWrSel.ALU_OUT,
        alu_res_latch=1,
    ),
    # Восстанавливаем TMP1 = MEM[AR] (AR не менялся с шага 1)
    MicroInstruction(
        latch_tmp1=1, tmp1_sel=Tmp1Sel.MEM_OUT,
        seq_branch=BranchCode.DISPATCH_OP
    ),
])


# --- Write back

WB_REG = add_block("WB_REG", [
    MicroInstruction(
        reg_dst_sel=0xF,
        latch_reg=1,
        reg_wr_sel=RegWrSel.ALU_RES,
        seq_branch=BranchCode.END_MICRO
    ),
])


WB_INDIRECT = add_block("WB_INDIRECT", [
    MicroInstruction(
        reg_dst_sel=0xF,
        ar_latch=1,
        mem_addr_sel=MemAddrSel.DST_REG,
        mem_wr=1,
        mem_data_sel=MemDataSel.ALU_RES,
        seq_branch=BranchCode.END_MICRO
    ),
])


WB_PRE_DEC = add_block("WB_PRE_DEC", [
    # Rdst уже декрементирован, AR = Rdst
    MicroInstruction(
        reg_dst_sel=0xF,
        ar_latch=1,
        mem_addr_sel=MemAddrSel.DST_REG,
        mem_wr=1,
        mem_data_sel=MemDataSel.ALU_RES,
        seq_branch=BranchCode.END_MICRO
    ),
])


WB_POST_INC = add_block("WB_POST_INC", [
    # AR содержит оригинальный адрес dst (с DST_POST_INC шага 1)
    MicroInstruction(
        mem_wr=1,
        mem_data_sel=MemDataSel.ALU_RES,
        seq_branch=BranchCode.END_MICRO
    ),
])


# --- Exec

EXEC_MOVE = add_block("EXEC_MOVE", [
    MicroInstruction(
        latch_tmp1=1, tmp1_sel=Tmp1Sel.ZERO,
        alu_right_sel=AluRightSel.TMP2,
        alu_op=AluOp.ADD,
        alu_res_latch=1,
        nzvc_latch=1,
        seq_branch=BranchCode.DISPATCH_WB
    ),
])

EXEC_CLR = add_block("EXEC_CLR", [
    MicroInstruction(
        latch_tmp1=1, tmp1_sel=Tmp1Sel.ZERO,
        alu_right_sel=AluRightSel.ZERO,
        alu_op=AluOp.ADD,
        alu_res_latch=1,
        nzvc_latch=1,
        seq_branch=BranchCode.DISPATCH_WB
    ),
])

EXEC_NEG = add_block("EXEC_NEG", [
    MicroInstruction(
        latch_tmp1=1, tmp1_sel=Tmp1Sel.ZERO,
        alu_right_sel=AluRightSel.TMP2,
        alu_op=AluOp.SUB,
        alu_res_latch=1,
        nzvc_latch=1,
        seq_branch=BranchCode.DISPATCH_WB
    ),
])

EXEC_ADD = add_block("EXEC_ADD", [
    MicroInstruction(
        alu_right_sel=AluRightSel.TMP2,
        alu_op=AluOp.ADD,
        alu_res_latch=1,
        nzvc_latch=1,
        seq_branch=BranchCode.DISPATCH_WB
    ),
])

EXEC_ADC = add_block("EXEC_ADC", [
    MicroInstruction(
        alu_right_sel=AluRightSel.TMP2,
        alu_op=AluOp.ADC,
        alu_res_latch=1,
        nzvc_latch=1,
        seq_branch=BranchCode.DISPATCH_WB
    ),
])

EXEC_SUB = add_block("EXEC_SUB", [
    MicroInstruction(
        alu_right_sel=AluRightSel.TMP2,
        alu_op=AluOp.SUB,
        alu_res_latch=1,
        nzvc_latch=1,
        seq_branch=BranchCode.DISPATCH_WB
    ),
])

EXEC_SBC = add_block("EXEC_SBC", [
    MicroInstruction(
        alu_right_sel=AluRightSel.TMP2,
        alu_op=AluOp.SBC,
        alu_res_latch=1,
        nzvc_latch=1,
        seq_branch=BranchCode.DISPATCH_WB
    ),
])

EXEC_MUL = add_block("EXEC_MUL", [
    MicroInstruction(
        alu_right_sel=AluRightSel.TMP2,
        alu_op=AluOp.MUL,
        alu_res_latch=1,
        nzvc_latch=1,
        seq_branch=BranchCode.DISPATCH_WB
    ),
])

EXEC_DIV = add_block("EXEC_DIV", [
    MicroInstruction(
        alu_right_sel=AluRightSel.TMP2,
        alu_op=AluOp.DIV,
        alu_res_latch=1,
        nzvc_latch=1,
        seq_branch=BranchCode.DISPATCH_WB
    ),
])

EXEC_REM = add_block("EXEC_REM", [
    MicroInstruction(
        alu_right_sel=AluRightSel.TMP2,
        alu_op=AluOp.REM,
        alu_res_latch=1,
        nzvc_latch=1,
        seq_branch=BranchCode.DISPATCH_WB
    ),
])

EXEC_CMP = add_block("EXEC_CMP", [
    MicroInstruction(
        alu_right_sel=AluRightSel.TMP2,
        alu_op=AluOp.SUB,
        nzvc_latch=1,
        seq_branch=BranchCode.END_MICRO
    ),
])


src_dispatch_table = {
    AddrMode.REG_DIRECT:   SRC_REG,
    AddrMode.IMMEDIATE:    SRC_IMM,
    AddrMode.REG_INDIRECT: SRC_INDIRECT,
    AddrMode.PRE_DEC:      SRC_PRE_DEC,
    AddrMode.POST_INC:     SRC_POST_INC,
}

dst_dispatch_table = {
    AddrMode.REG_DIRECT:   DST_REG,
    AddrMode.IMMEDIATE:    DST_IMM,
    AddrMode.REG_INDIRECT: DST_INDIRECT,
    AddrMode.PRE_DEC:      DST_PRE_DEC,
    AddrMode.POST_INC:     DST_POST_INC,
}

wb_dispatch_table = {
    AddrMode.REG_DIRECT:   WB_REG,
    AddrMode.REG_INDIRECT: WB_INDIRECT,
    AddrMode.PRE_DEC:      WB_PRE_DEC,
    AddrMode.POST_INC:     WB_POST_INC,
}

opcode_to_mpc = {
    Opcode.MOVE: EXEC_MOVE,
    Opcode.CLR:  EXEC_CLR,
    Opcode.NEG:  EXEC_NEG,
    Opcode.ADD:  EXEC_ADD,
    Opcode.ADC:  EXEC_ADC,
    Opcode.SUB:  EXEC_SUB,
    Opcode.SBC:  EXEC_SBC,
    Opcode.MUL:  EXEC_MUL,
    Opcode.DIV:  EXEC_DIV,
    Opcode.REM:  EXEC_REM,
    Opcode.CMP:  EXEC_CMP,
    Opcode.HALT: HALT_ADDR,
}
