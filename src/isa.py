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