from dataclasses import dataclass
from enum import Enum


class Opcode(str, Enum):
    """
    Структура команд CISC-процессора
    """

    MOVE = "move"

    CLR = "clr"
    NEG = "neg"
    ADD = "add"
    ADC = "adc"
    SUB = "sub"
    SBC = "sbc"
    MUL = "mul"
    DIV = "div"
    REM = "rem"
    CMP = "cmp"

    NADD = "nadd"
    NMUL = "nmul"

    NOT_OP = "not"
    AND_OP = "and"
    OR_OP = "or"
    XOR = "xor"

    ASL = "asl"
    ASR = "asr"
    LSL = "lsl"
    LSR = "lsr"

    JMP = "jmp"
    BCC = "bcc"
    BCS = "bcs"
    BEQ = "beq"
    BNE = "bne"
    BLT = "blt"
    BGT = "bgt"
    BLE = "ble"
    BGE = "bge"
    BMI = "bmi"
    BPL = "bpl"
    BVC = "bvc"
    BVS = "bvs"

    JSR = "jsr"
    RET = "ret"
    HALT = "halt"

    IN = "in"
    OUT = "out"

    def __str__(self) -> str:
        return self.value


# генерация порядковых номеров операций для микрокода
OPCODE_NUM = {opcode: idx for idx, opcode in enumerate(Opcode)}

OPCODE_NARG = {
    Opcode.MOVE: 2,
    Opcode.ADD: 2,
    Opcode.ADC: 2,
    Opcode.SUB: 2,
    Opcode.SBC: 2,
    Opcode.MUL: 2,
    Opcode.DIV: 2,
    Opcode.REM: 2,
    Opcode.CMP: 2,
    Opcode.IN: 2,
    Opcode.OUT: 2,
    Opcode.NADD: -1,
    Opcode.NMUL: -1,
    Opcode.AND_OP: 2,
    Opcode.OR_OP: 2,
    Opcode.XOR: 2,
    Opcode.ASL: 2,
    Opcode.ASR: 2,
    Opcode.LSL: 2,
    Opcode.LSR: 2,
    Opcode.CLR: 1,
    Opcode.NEG: 1,
    Opcode.NOT_OP: 1,
    Opcode.JMP: 1,
    Opcode.JSR: 1,
    Opcode.BCC: 1,
    Opcode.BCS: 1,
    Opcode.BEQ: 1,
    Opcode.BNE: 1,
    Opcode.BLT: 1,
    Opcode.BGT: 1,
    Opcode.BLE: 1,
    Opcode.BGE: 1,
    Opcode.BMI: 1,
    Opcode.BPL: 1,
    Opcode.BVC: 1,
    Opcode.BVS: 1,
    Opcode.HALT: 0,
    Opcode.RET: 0,
    Opcode.IN: 2,
    Opcode.OUT: 2,
}

BRANCH_OPCODES = {
    Opcode.JMP,
    Opcode.BCC,
    Opcode.BCS,
    Opcode.BEQ,
    Opcode.BNE,
    Opcode.BLT,
    Opcode.BGT,
    Opcode.BLE,
    Opcode.BGE,
    Opcode.BMI,
    Opcode.BPL,
    Opcode.BVC,
    Opcode.BVS,
}


class AddrMode(int, Enum):
    REG_DIRECT = 0  # Rn
    REG_INDIRECT = 1  # (Rn)
    POST_INC = 2  # (Rn)+
    PRE_DEC = 3  # -(Rn)
    IMMEDIATE = 4  # #value


@dataclass
class Operand:
    mode: AddrMode  # режим адресации
    value: int  # register number OR number (for imm)

    def __str__(self) -> str:
        sym = "R"
        if self.value == 6:
            sym += "[DSP]"
        elif self.value == 7:
            sym += "[RSP]"

        if self.mode == AddrMode.REG_DIRECT:
            return f"{sym}{self.value}"
        elif self.mode == AddrMode.REG_INDIRECT:
            return f"({sym}{self.value})"
        elif self.mode == AddrMode.POST_INC:
            return f"({sym}{self.value})+"
        elif self.mode == AddrMode.PRE_DEC:
            return f"-({sym}{self.value})"
        elif self.mode == AddrMode.IMMEDIATE:
            return f"#{self.value}"
        return str(self.value)


@dataclass
class Instruction:
    opcode: Opcode
    operands: list[Operand]

    def __post_init__(self):
        expected_narg = OPCODE_NARG[self.opcode]
        if expected_narg != -1 and expected_narg != len(self.operands):
            raise ValueError(
                f"Opcode {self.opcode}: expected: {expected_narg} args, "
                f"but got: {len(self.operands)}"
            )

    def to_bytes(self) -> bytes:
        """
        Преобразование инструкции в бинарный код (immutable bytes sequence)
        Little-Endian
        """
        opcode_num = OPCODE_NUM[self.opcode]
        src_byte = 0x00
        dest_byte = 0x00
        reserve_byte = 0x00

        extra_words = bytearray()

        if OPCODE_NARG[self.opcode] == -1:
            reserve_byte = len(self.operands) & 0xFF
            for op in self.operands:
                if op.mode == AddrMode.IMMEDIATE:
                    extra_words.extend(
                        op.value.to_bytes(4, byteorder="little", signed=True)
                    )
        else:
            if len(self.operands) >= 1:
                op1 = self.operands[0]

                register_val = op1.value if op1.mode != AddrMode.IMMEDIATE else 0
                src_byte = (op1.mode.value << 4) | (register_val & 0xF)

                if op1.mode == AddrMode.IMMEDIATE:
                    extra_words.extend(
                        op1.value.to_bytes(
                            4,
                            byteorder="little",
                            signed=True,
                        )
                    )

            if len(self.operands) == 2:
                op2 = self.operands[1]

                register_val = op2.value if op2.mode != AddrMode.IMMEDIATE else 0
                dest_byte = (op2.mode.value << 4) | (register_val & 0xF)

                if op2.mode == AddrMode.IMMEDIATE:
                    extra_words.extend(
                        op2.value.to_bytes(4, byteorder="little", signed=True)
                    )

        result_word = bytes([dest_byte, src_byte, reserve_byte, opcode_num])
        return result_word + bytes(extra_words)

    def size_bytes(self) -> int:
        """
        Вычисление итогового размера инструкции без выполнения
        полного цикла превращения в байт-код
        """
        size = 4
        if len(self.operands) >= 1:
            size += (self.operands[0].mode == AddrMode.IMMEDIATE) * 4
        if len(self.operands) == 2:
            size += (self.operands[1].mode == AddrMode.IMMEDIATE) * 4
        return size

    def __str__(self):
        opcode_str = str(self.opcode.value).upper()
        if not self.operands:
            return opcode_str

        operands_str = ", ".join(str(op) for op in self.operands)
        return f"{opcode_str:<6} {operands_str}"
    
    @classmethod
    def from_bytes(cls, data: bytes | list[int], offset: int = 0) -> tuple["Instruction", int]:
        """
        Десериализация инструкции из байтов начиная с offset
        Возвращает (Instruction, new_offset)
        """
        if offset + 4 > len(data):
            raise ValueError(f"Not enough bytes at offset {offset:#x}")
        
        word = (
            data[offset]
            | (data[offset + 1] << 8)
            | (data[offset + 2] << 16)
            | (data[offset + 3] << 24)
        )
        offset += 4

        dest_byte = word & 0xFF
        src_byte = (word >> 8)  & 0xFF
        reserve = (word >> 16) & 0xFF
        opcode_num = (word >> 24) & 0xFF

        opcode = list(Opcode)[opcode_num]

        def read_imm() -> tuple[int, int]:
            nonlocal offset
            if offset + 4 > len(data):
                raise ValueError(f"Expected immediate at offset {offset:#x}")
            val = (
                data[offset]
                | (data[offset + 1] << 8)
                | (data[offset + 2] << 16)
                | (data[offset + 3] << 24)
            )
            if val & 0x80000000:
                val -= 0x100000000
            offset += 4
            return val
        
        # n-арные
        if OPCODE_NARG[opcode] == -1:
            n = reserve
            operands = [Operand(AddrMode.IMMEDIATE, read_imm()) for _ in range(n)]
            return cls(opcode, operands), offset
        
        # noarg
        if OPCODE_NARG[opcode] == 0:
            return cls(opcode, []), offset
        
        src_mode = AddrMode((src_byte >> 4) & 0xF)
        src_val  = src_byte & 0xF
        dst_mode = AddrMode((dest_byte >> 4) & 0xF)
        dst_val  = dest_byte & 0xF

        # unary
        if OPCODE_NARG[opcode] == 1:
            if src_mode == AddrMode.IMMEDIATE:
                val = read_imm()
                return cls(opcode, [Operand(AddrMode.IMMEDIATE, val)]), offset
            return cls(opcode, [Operand(src_mode, src_val)]), offset
        
        # 2arg
        src_imm_val = read_imm() if src_mode == AddrMode.IMMEDIATE else None
        dst_imm_val = read_imm() if dst_mode == AddrMode.IMMEDIATE else None

        src_op = Operand(src_mode, src_imm_val if src_mode == AddrMode.IMMEDIATE else src_val)
        dst_op = Operand(dst_mode, dst_imm_val if dst_mode == AddrMode.IMMEDIATE else dst_val)

        return cls(opcode, [src_op, dst_op]), offset
    
    @classmethod
    def decode_all(cls, data: bytes | list[int]) -> list["Instruction"]:
        """Десериализация всех инструкций из байтового потока"""
        instructions = []
        offset = 0
        while offset < len(data):
            instr, offset = cls.from_bytes(data, offset)
            instructions.append(instr)
        return instructions
