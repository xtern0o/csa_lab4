from dataclasses import dataclass
from enum import Enum


class Opcode(str, Enum):
    """
    Структура команд CISC-процессора
    """
    MOVE = "move"
    MOVEA = "movea"
    
    CLR = "clr"
    NEG = "neg"
    ADD = "add"
    SUB = "sub"
    MUL = "mul"
    DIV = "div"
    CMP = "cmp"
    
    NOT_OP = "not"
    AND_OP = "and"
    OR_OP  = "or"
    XOR    = "xor"
    
    ASL = "asl"
    ASR = "asr"
    LSL = "lsl"
    LSR = "lsr"
    
    JUMP = "jump"
    BCC  = "bcc"
    BCS  = "bcs"
    BEQ  = "beq"
    BNE  = "bne"
    BLT  = "blt"
    BGT  = "bgt"
    BLE  = "ble"
    BGE  = "bge"
    BMI  = "bmi"
    BPL  = "bpl"
    BVC  = "bvc"
    BVS  = "bvs"
    
    JSR  = "jsr"
    HALT = "halt"

    def __str__(self) -> str:
        return self.value
    

OPCODE_NARG = {
    Opcode.MOVE: 2, Opcode.MOVEA: 2, 
    Opcode.ADD: 2, Opcode.SUB: 2, Opcode.MUL: 2, Opcode.DIV: 2, Opcode.CMP: 2,
    Opcode.AND_OP: 2, Opcode.OR_OP: 2, Opcode.XOR: 2,
    Opcode.ASL: 2, Opcode.ASR: 2, Opcode.LSL: 2, Opcode.LSR: 2,
    
    Opcode.CLR: 1, Opcode.NEG: 1, Opcode.NOT_OP: 1,
    Opcode.JUMP: 1, Opcode.JSR: 1,
    Opcode.BCC: 1, Opcode.BCS: 1, Opcode.BEQ: 1, Opcode.BNE: 1, 
    Opcode.BLT: 1, Opcode.BGT: 1, Opcode.BLE: 1, Opcode.BGE: 1, 
    Opcode.BMI: 1, Opcode.BPL: 1, Opcode.BVC: 1, Opcode.BVS: 1,
    
    Opcode.HALT: 0
}


class AddrMode(int, Enum):
    DATA_REG_DIRECT = 0     # d0-d7
    ADDR_REG_DIRECT = 1     # a0-a7
    ADDR_REG_INDIRECT = 2   # (An)
    POST_INC = 3            # (An)+
    PRE_DEC = 4             # -(An)
    IMMEDIATE = 5           # 42


@dataclass
class Operand:
    mode: AddrMode      # режим адресации
    value: int          # register number OR number (for imm)


@dataclass
class Instruction:
    opcode: Opcode
    operands: list[Operand]

    def __post_init__(self):
        expected_narg = OPCODE_NARG[self.opcode]
        if expected_narg != len(self.operands):
            raise ValueError(
                f"Opcode {self.opcode}: expected: {expected_narg} args, but got: {len(self.operands)}"
            )