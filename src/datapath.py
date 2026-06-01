from enum import IntEnum

WORD32_MASK = 0xFFFFFFFF
BYTE_MASK = 0xFF
STATIC_DATA_START = 0x200


def mask_word(word: int) -> int:
    return word & WORD32_MASK


def to_signed(value: int) -> int:
    value &= WORD32_MASK
    if value & 0x80000000:
        return value - 0x100000000
    return value


class RegWrSel(IntEnum):
    INPUT_DATA = 0
    MEM_OUT = 1
    ALU_RES = 2
    NZVC = 3
    INSTR_WORD = 4
    ALU_OUT = 5


class Tmp1Sel(IntEnum):
    ALU_RES = 0
    DST_REG = 1
    INSTR_WORD = 2
    MEM_OUT = 3
    ZERO = 4


class Tmp2Sel(IntEnum):
    SRC_REG = 0
    INSTR_WORD = 1
    MEM_OUT = 2


class AluRightSel(IntEnum):
    TMP2 = 0
    ZERO = 1
    ONE = 2
    FOUR = 3


class MemAddrSel(IntEnum):
    INSTR_WORD = 0
    SRC_REG = 1
    DST_REG = 2
    ALU_OUT = 3


class MemDataSel(IntEnum):
    SRC_REG = 0
    DST_REG = 1
    ALU_OUT = 2
    ALU_RES = 3
    INSTR_WORD = 4
    PC = 5


class PcSel(IntEnum):
    PC_INC = 0
    DST_REG = 1
    MEM_OUT = 2
    INSTR_WORD = 3
    ALU_RES = 4


class OutSel(IntEnum):
    SRC_REG = 0
    MEM_OUT = 1
    INSTR_WORD = 2
    ALU_RES = 3


class AluOp(IntEnum):
    ADD = 0  # l + r
    SUB = 1  # l - r
    MUL = 2  # l * r
    DIV = 3  # l // r
    REM = 4  # l % r
    AND = 5  # l & r
    OR = 6  # l | r
    XOR = 7  # l ^ r
    NOT_A = 8  # ~l
    NOT_B = 9  # ~r
    ASL = 10
    ASR = 11
    LSL = 12
    LSR = 13
    ADC = 16  # l + r + C
    SBC = 17  # l - r - C

    PASS_L = 18
    PASS_R = 19


class IOController:
    """I/O stream controller"""

    def __init__(self):
        self.input_tokens = []
        self.output_buffer = []

    def load_input_from_file(self, filepath: str) -> None:
        """Load tokens from file"""
        pass

    def dump_output_to_file(self, filepath: str) -> None:
        """Flush tokens biffer to file"""
        pass

    def read_token(self, port: int) -> int:
        """
        Чтение данных из порта:
        1 - числовой ввод
        2 - символьный вывод
        """
        if not self.input_tokens:
            raise EOFError("Input buffer is empty!")
        raw = self.input_tokens.pop(0)

        # 1 - числовой ввод, 3 - символьный ввод
        if port == 1:
            return int(raw)
        elif port == 3:
            if isinstance(raw, str):
                return ord(raw[0])
            return int(raw)
        return int(raw)

    def write_token(self, port: int, value: int) -> None:
        """
        Запись данных в порт:
        0 - числовой вывод
        2 - символьный вывод
        """
        if port == 0:
            self.output_buffer.append(str(to_signed(value)))
        elif port == 2:
            self.output_buffer.append(chr(value & BYTE_MASK))
        else:
            # -> /dev/null
            pass


class DataPath:
    """
    Модель DataPath

    DataMemory (little-endian):
      - Байтовая адресация.
        Представляет собой список из (data_memory_size) чисел-байтов от 0 до 255
      - При чтении возвращает 32-битный набор i, i+1, i+2, i+3 байтов на линию mem_out
      - При записи перетирает i, i+1, i+2, i+3 байты
    InstrMemory (little-endian):
      - Байтовая адресация.
        Аналогично с DataMemory хранит числа-байты
      - При чтении возвращает данные на 32-битную шину instr_word

    """

    def __init__(
        self,
        instr_memory: list[int] | bytes,
        io_controller: IOController,
        data_memory_size: int = 1024,
        instr_memory_size: int = 1024,
    ):
        self.data_memory_size = data_memory_size
        self.data_memory = [0] * data_memory_size

        self.instr_memory_size = instr_memory_size
        self.instr_memory = [0] * instr_memory_size
        for i, b in enumerate(instr_memory):
            if i < instr_memory_size:
                self.instr_memory[i] = b & BYTE_MASK

        self.io_controller = io_controller

        # R0-R4 + DSP + RSP
        self.registers = [0] * 8
        
        self.registers[6] = data_memory_size    # DSP - конец памяти, стек растёт вниз
        self.registers[7] = STATIC_DATA_START   # RSP - начало памяти, стек растёт вверх

        self.src_sel = 0
        self.dst_sel = 0

        self.ar = 0

        self.pc = 0

        self.tmp1 = 0
        self.tmp2 = 0

        self._alu_out = 0
        self.alu_res = 0
        self.nzvc = 0

        # nzvc unpacked
        self.flag_n = False
        self.flag_z = False
        self.flag_v = False
        self.flag_c = False

        self.port = 0

    def latch_register(self, reg_idx: int, value: int):
        """Записать новое значение в регистр (открыть latch_reg)"""
        self.registers[reg_idx] = value & WORD32_MASK

    def assert_data_address(self, addr: int) -> None:
        """Проверка корректности адреса памяти"""
        if 0 <= addr < self.data_memory_size:
            return
        raise IndexError("data addr out of bounds of memory")

    def assert_instr_address(self, addr: int) -> None:
        """Проверка корректности адреса памяти инструкций"""
        if 0 <= addr < self.instr_memory_size:
            return
        raise IndexError("instr addr out of bounds of memory")

    @property
    def src_reg(self) -> int:
        """Текущее значение линии src_reg"""
        return self.registers[self.src_sel]

    @property
    def dst_reg(self) -> int:
        """Текущее значение линии dst_reg"""
        return self.registers[self.dst_sel]

    @property
    def alu_out(self) -> int:
        """Значение линии alu_out"""
        return self._alu_out

    @property
    def instr_word(self) -> int:
        """Значение линии instr_word"""
        self.assert_instr_address(self.pc)
        self.assert_instr_address(self.pc + 3)
        # little-endian сборка
        return (
            self.instr_memory[self.pc]
            | (self.instr_memory[self.pc + 1] << 8)
            | (self.instr_memory[self.pc + 2] << 16)
            | (self.instr_memory[self.pc + 3] << 24)
        )

    @property
    def mem_out(self) -> int:
        self.assert_data_address(self.ar)
        self.assert_data_address(self.ar + 3)
        # little-endian сборка
        return (
            self.data_memory[self.ar]
            | (self.data_memory[self.ar + 1] << 8)
            | (self.data_memory[self.ar + 2] << 16)
            | (self.data_memory[self.ar + 3] << 24)
        )

    @property
    def pc_inc(self) -> int:
        """Значение линии pc+4"""
        return self.pc + 4

    def signal_select_regs(self, src: int, dst: int):
        """Выставить линии выбора регистров"""
        self.src_sel = src & 0xF
        self.dst_sel = dst & 0xF

    def signal_latch_reg(self, wr_sel: RegWrSel):
        """Защелкнуть данные в целевой регистр (dst_reg) из выбранного источника"""
        if wr_sel == RegWrSel.INPUT_DATA:
            # допущение в рамках симулятора: i/o работает на частоте процессора
            value = self.io_controller.read_token(self.port)
        elif wr_sel == RegWrSel.MEM_OUT:
            value = self.mem_out
        elif wr_sel == RegWrSel.ALU_RES:
            value = self.alu_res
        elif wr_sel == RegWrSel.NZVC:
            value = self.nzvc
        elif wr_sel == RegWrSel.INSTR_WORD:
            value = self.instr_word
        elif wr_sel == RegWrSel.ALU_OUT:
            value = self.alu_out
        else:
            raise ValueError(f"Unknown RegWrSel: {wr_sel}")
        self.registers[self.dst_sel] = mask_word(value)

    def signal_latch_ar(self, addr_sel: MemAddrSel):
        """Address MUX -> защелка AR"""
        if addr_sel == MemAddrSel.INSTR_WORD:
            value = self.instr_word
        elif addr_sel == MemAddrSel.SRC_REG:
            value = self.src_reg
        elif addr_sel == MemAddrSel.DST_REG:
            value = self.dst_reg
        elif addr_sel == MemAddrSel.ALU_OUT:
            value = self.alu_out
        else:
            raise ValueError(f"Unknown MemAddrSel: {addr_sel}")
        self.ar = mask_word(value)

    def signal_mem_write(self, data_sel: MemDataSel):
        """Data MUX -> write mem (front mem_wr)"""
        self.assert_data_address(self.ar)
        self.assert_data_address(self.ar + 3)
        if data_sel == MemDataSel.SRC_REG:
            value = self.src_reg
        elif data_sel == MemDataSel.DST_REG:
            value = self.dst_reg
        elif data_sel == MemDataSel.ALU_OUT:
            value = self.alu_out
        elif data_sel == MemDataSel.ALU_RES:
            value = self.alu_res
        elif data_sel == MemDataSel.INSTR_WORD:
            value = self.instr_word
        elif data_sel == MemDataSel.PC:
            value = self.pc
        else:
            raise ValueError(f"Unknown MemDataSel: {data_sel}")

        value = mask_word(value)
        self.data_memory[self.ar] = value & BYTE_MASK
        self.data_memory[self.ar + 1] = (value >> 8) & BYTE_MASK
        self.data_memory[self.ar + 2] = (value >> 16) & BYTE_MASK
        self.data_memory[self.ar + 3] = (value >> 24) & BYTE_MASK

    def signal_latch_pc(self, pc_sel: PcSel):
        """PC MUX -> PC"""
        if pc_sel == PcSel.PC_INC:
            value = self.pc_inc
        elif pc_sel == PcSel.DST_REG:
            value = self.dst_reg
        elif pc_sel == PcSel.MEM_OUT:
            value = self.mem_out
        elif pc_sel == PcSel.INSTR_WORD:
            value = self.instr_word
        elif pc_sel == PcSel.ALU_RES:
            value = self.alu_res
        else:
            raise ValueError(f"Unknown PcSel: {pc_sel}")
        self.pc = mask_word(value)

    def signal_latch_tmp1(self, sel: Tmp1Sel):
        if sel == Tmp1Sel.ALU_RES:
            value = self.alu_res
        elif sel == Tmp1Sel.DST_REG:
            value = self.dst_reg
        elif sel == Tmp1Sel.INSTR_WORD:
            value = self.instr_word
        elif sel == Tmp1Sel.MEM_OUT:
            value = self.mem_out
        elif sel == Tmp1Sel.ZERO:
            value = 0
        else:
            raise ValueError(f"Unknown Tmp1Sel: {sel}")
        self.tmp1 = mask_word(value)

    def signal_latch_tmp2(self, sel: Tmp2Sel):
        if sel == Tmp2Sel.SRC_REG:
            value = self.src_reg
        elif sel == Tmp2Sel.INSTR_WORD:
            value = self.instr_word
        elif sel == Tmp2Sel.MEM_OUT:
            value = self.mem_out
        else:
            raise ValueError(f"Unknown Tmp2Sel: {sel}")
        self.tmp2 = mask_word(value)

    def _eval_alu(self, alu_op: AluOp, left: int, right: int) -> tuple[int, int]:
        """
        Расчет результата на левой и правой ноге через ALU
        при текущих условиях (текущих контрольных сигналах)
        """
        a = to_signed(left)
        b = to_signed(right)

        res, c, v = 0, 0, 0

        if alu_op == AluOp.ADD:
            ans = left + right
            res = mask_word(ans)
            c = 1 if ans > WORD32_MASK else 0
            v = 1 if (left ^ res) & ~(left ^ right) & 0x80000000 else 0
        elif alu_op == AluOp.ADC:
            ans = left + right + self.flag_c
            res = mask_word(ans)
            c = 1 if ans > WORD32_MASK else 0
            v = 1 if (left ^ res) & ~(left ^ right) & 0x80000000 else 0
        elif alu_op == AluOp.SUB:
            ans = left - right
            res = mask_word(ans)
            c = 1 if left < right else 0
            v = 1 if (left ^ right) & (left ^ res) & 0x80000000 else 0
        elif alu_op == AluOp.SBC:
            ans = left - right - self.flag_c
            res = mask_word(ans)
            c = 1 if left < (right + self.flag_c) else 0
            v = 1 if (left ^ right) & (left ^ res) & 0x80000000 else 0
        elif alu_op == AluOp.MUL:
            res = mask_word(a * b)
        elif alu_op == AluOp.DIV:
            if b == 0:
                raise ValueError("division by zero")
            sign = -1 if (a < 0) ^ (b < 0) else 1
            res = mask_word(sign * (abs(a) // abs(b)))
        elif alu_op == AluOp.REM:
            if b == 0:
                raise ValueError("division by zero")
            val = abs(a) % abs(b)
            if a < 0:
                val = -val
            res = mask_word(val)
        elif alu_op == AluOp.AND:
            res = mask_word(left & right)
        elif alu_op == AluOp.OR:
            res = mask_word(left | right)
        elif alu_op == AluOp.XOR:
            res = mask_word(left ^ right)
        elif alu_op == AluOp.NOT_A:
            res = mask_word(~left)
        elif alu_op == AluOp.NOT_B:
            res = mask_word(~right)
        elif alu_op == AluOp.ASL or alu_op == AluOp.LSL:
            shift = right & 0x1F
            c = 1 if (left & (1 << (32 - shift))) else 0
            res = mask_word(left << shift)
        elif alu_op == AluOp.ASR:
            shift = right & 0x1F
            c = 1 if (left & (1 << (shift - 1))) else 0
            res = mask_word(a >> shift)
        elif alu_op == AluOp.LSR:
            shift = right & 0x1F
            c = 1 if (left & (1 << (shift - 1))) else 0
            res = mask_word(left >> shift)
        elif alu_op == AluOp.PASS_L:
            res = mask_word(left)
        elif alu_op == AluOp.PASS_R:
            res = mask_word(right)
        else:
            raise ValueError(f"Unknown AluOp: {alu_op}")

        n = 1 if (res & 0x80000000) != 0 else 0
        z = 1 if res == 0 else 0
        nzvc = (n << 3) | (z << 2) | (v << 1) | c
        return res, nzvc

    def signal_alu(self, alu_op: AluOp, right_sel: AluRightSel):
        if right_sel == AluRightSel.TMP2:
            right = self.tmp2
        elif right_sel == AluRightSel.ZERO:
            right = 0
        elif right_sel == AluRightSel.ONE:
            right = 1
        elif right_sel == AluRightSel.FOUR:
            right = 4

        self._alu_out, self._alu_out_nzvc = self._eval_alu(alu_op, self.tmp1, right)

    def signal_latch_nzvc(self):
        """NZVC latch"""
        self.nzvc = self._alu_out_nzvc
        self.flag_n = bool(self.nzvc & 0b1000)
        self.flag_z = bool(self.nzvc & 0b0100)
        self.flag_v = bool(self.nzvc & 0b0010)
        self.flag_c = bool(self.nzvc & 0b0001)

    def signal_latch_alu_res(self):
        """ALU_RES latch"""
        self.alu_res = self.alu_out

    def signal_latch_port(self):
        """PORT latch"""
        self.port = mask_word(self.alu_out)

    def signal_latch_out_data(self, out_sel: OutSel):
        """Out MUX select и немедленная отправка"""
        if out_sel == OutSel.SRC_REG:
            value = self.src_reg
        elif out_sel == OutSel.MEM_OUT:
            value = self.mem_out
        elif out_sel == OutSel.INSTR_WORD:
            value = self.instr_word
        elif out_sel == OutSel.ALU_RES:
            value = self.alu_res
        else:
            raise ValueError(f"Unknown OutSel: {out_sel}")
        self.io_controller.write_token(self.port, mask_word(value))
