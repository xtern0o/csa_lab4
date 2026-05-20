from dataclasses import dataclass

from datapath import *
from isa import *


@dataclass
class MicroInstruction:
    label: str = ""

    # Register File
    reg_src_sel: int = 0
    reg_dst_sel: int = 0
    reg_wr_sel: int = 0
    latch_reg: int = 0

    # Tmp Registers
    tmp1_sel: int = 0
    tmp2_sel: int = 0
    latch_tmp1: int = 0
    latch_tmp2: int = 0

    # ALU
    alu_op: int = 0
    nzvc_latch: int = 0
    alu_res_latch: int = 0

    # Data Memory
    mem_addr_sel: int = 0
    mem_data_sel: int = 0
    mem_rd: int = 0
    mem_wr: int = 0

    # Instruction Memory
    pc_sel: int = 0
    pc_latch: int = 0
    ir_latch: int = 0

    # IO Ports
    port_latch: int = 0
    out_sel: int = 0
    out_latch: int = 0
    in_latch: int = 0

    # Control Unit (Sequencer & Counter)
    latch_cnt: int = 0
    counter_dec: int = 0
    seq_branch: int = 0
    next_addr: int = 0
    
    # AR
    ar_latch: int = 0

    hlt: int = 0

    def to_binary_string(self) -> str:
        """
        Конвертация микрокоманды в 56-битную бинарную строку
        (выравнивается до 56 бит == 7 байт)
        """
        bin_str = (
            f"{self.hlt:01b}"
            f"{self.reg_src_sel:02b}{self.reg_dst_sel:02b}{self.reg_wr_sel:03b}{self.latch_reg:01b}"
            f"{self.tmp1_sel:03b}{self.tmp2_sel:03b}{self.latch_tmp1:01b}{self.latch_tmp2:01b}"
            f"{self.alu_op:05b}{self.nzvc_latch:01b}{self.alu_res_latch:01b}"
            f"{self.mem_addr_sel:02b}{self.mem_data_sel:03b}{self.mem_rd:01b}{self.mem_wr:01b}"
            f"{self.pc_sel:02b}{self.pc_latch:01b}{self.ir_latch:01b}"
            f"{self.port_latch:01b}{self.out_sel:02b}{self.out_latch:01b}{self.in_latch:01b}"
            f"{self.latch_cnt:01b}{self.counter_dec:01b}{self.seq_branch:05b}{self.next_addr:08b}"
            f"{self.ar_latch:01b}"
        )
        return bin_str.zfill(56)


class BranchCode(IntEnum):
    NEXT = 0
    JMP = 1
    JZ = 2      # Z=1
    JNZ = 3     # Z=0
    JN = 4      # N=1
    JC = 5      # C=1
    JV = 6      # V=1
    END_MICRO = 7
    JCNT_Z = 8  # counter == 0
    JNN = 9     # N=0
    JNC = 10    # C=0
    JNV = 11    # V=0
    JGE = 12    # N == V
    JLT = 13    # N != V
    JLE = 14    # Z=1 or N != V
    JGT = 15    # Z=0 and N == V
    DECODE = 16 # декодирование текущего IR и переход на нужный адрес
    

@dataclass
class FlatInstruction:
    """
    Плоское представление инструкции для удобной обработки
    (по сути обычное чтение нужных битов с IR)
    """
    opcode: Opcode

    src_mode: int | None
    dst_mode: int | None
    src_reg: int | None
    dst_reg: int | None

    n: int | None           # для n-арных инструкций
    has_src_imm: bool = False
    has_dst_imm: bool = False
   

class ControlUnit:
    def __init__(
        self,
        dp: DataPath,
        microcode_memory: list[MicroInstruction],
        opcode_to_mpc: dict[Opcode, int],
    ):
        self.dp = dp
        self.io = dp.io_controller

        self.microcode_memory = microcode_memory
        
        self.mpc = 0
        self.ir = 0
        self.counter = 0

        self.mir: MicroInstruction | None
        if self.microcode_memory:
            self.mir = self.microcode_memory[self.mpc]
        else:
            self.mir = None        

        # маппинг для опкодов на микрокоманды в памяти
        self.opcode_to_mpc = opcode_to_mpc

    @property
    def current_micro(self) -> MicroInstruction | None:
        """Шина current_micro: идет от MIR на Sequencer и другие компоненты"""
        return self.mir
    
    @property
    def mpc_inc(self) -> int:
        """Шина mpc_inc: значение mpc + 1"""
        return self.mpc + 1

    @property
    def next_addr(self) -> int:
        """Шина next_addr из поля текущей микрокоманды (MIR)"""
        return self.mir.next_addr if self.mir else 0
    
    @property
    def start_addr(self) -> int:
        """
        Шина start_addr: выход Instruction Decoder'а (маппинг opcode -> mpc).
        """
        flat = self.decode_instruction(self.ir)
        return self.opcode_to_mpc[flat.opcode]

    @property
    def instr_word(self) -> int:
        """Шина instr_word: приходит с DataPath"""
        return self.dp.instr_word
    
    def decode_instruction(self, ir: int) -> FlatInstruction:
        """
        Декодирование инструкции на ir для обработки
        """
        opcode_val = (ir >> 24) & 0xFF
        opcode = list(Opcode)[opcode_val] 
        reserve = (ir >> 16) & 0xFF
        src_desc = (ir >> 8) & 0xFF
        dst_desc = ir & 0xFF

        src_mode = (src_desc >> 4) & 0xF
        src_reg = src_desc & 0xF
        dst_mode = (dst_desc >> 4) & 0xF
        dst_reg = dst_desc & 0xF

        n = None
        if opcode in {Opcode.NADD, Opcode.NMUL}:
            n = reserve
        
        has_src_imm = (src_mode == AddrMode.IMMEDIATE.value)
        has_dst_imm = (dst_mode == AddrMode.IMMEDIATE.value)

        return FlatInstruction(
            opcode=opcode,
            src_mode=src_mode,
            dst_mode=dst_mode,
            src_reg=src_reg,
            dst_reg=dst_reg,
            n=n,
            has_src_imm=has_src_imm,
            has_dst_imm=has_dst_imm,
        )
    
    def next_micro_addr(self) -> int:
        """
        Логика Sequencer
        Входы:
          - MIR по линии current_micro
          - nzvc по линии nzvc
        Выходы:
          - линия next_addr
        """
        code = self.current_micro.seq_branch

        if code == BranchCode.JMP:
            return self.current_micro.next_addr

        # условные переходы
        if code == BranchCode.JZ and self.dp.flag_z:
            return self.current_micro.next_addr
        if code == BranchCode.JNZ and not self.dp.flag_z:
            return self.current_micro.next_addr
        if code == BranchCode.JN and self.dp.flag_n:
            return self.current_micro.next_addr
        if code == BranchCode.JC and self.dp.flag_c:
            return self.current_micro.next_addr
        if code == BranchCode.JV and self.dp.flag_v:
            return self.current_micro.next_addr
        if code == BranchCode.JNN and not self.dp.flag_n:
            return self.current_micro.next_addr
        if code == BranchCode.JNC and not self.dp.flag_c:
            return self.current_micro.next_addr
        if code == BranchCode.JNV and not self.dp.flag_v:
            return self.current_micro.next_addr
        
        # комбинированные условия для сравнений
        if code == BranchCode.JGE and (self.dp.flag_n == self.dp.flag_v):
            return self.current_micro.next_addr
        if code == BranchCode.JLT and (self.dp.flag_n != self.dp.flag_v):
            return self.current_micro.next_addr
        if code == BranchCode.JLE and (self.dp.flag_z or (self.dp.flag_n != self.dp.flag_v)):
            return self.current_micro.next_addr
        if code == BranchCode.JGT and (not self.dp.flag_z and (self.dp.flag_n == self.dp.flag_v)):
            return self.current_micro.next_addr
        
        # счетчик 0
        if code == BranchCode.JCNT_Z and self.counter == 0:
            return self.current_micro.next_addr
        
        # конец микропрограммы
        if code == BranchCode.END_MICRO:
            # в нашей схеме END_MICRO можно использовать для перехода в начало FETCH цикла
            # Но если у нас DECODE сразу прыгает - то вот так:
            return 0  # пусть 0 - адрес FETCH цикла по умолчанию
            
        if code == BranchCode.DECODE:
            return self.start_addr
        
        return self.mpc + 1
    
    def tick(self):
        """
        Моделирование одного такта процессора
        Разделено на физические фазы
        """
        mir = self.current_micro
        if not mir:
            raise RuntimeError("MicroInstruction is None -> halt")
        
        if mir.hlt:
            raise StopIteration("HALT")

        # Фаза 1 - Сигналы

        self.dp.signal_select_regs(mir.reg_src_sel, mir.reg_dst_sel)

        if mir.latch_tmp1:
            self.dp.signal_latch_tmp1(Tmp1Sel(mir.tmp1_sel))
        if mir.latch_tmp2:
            self.dp.signal_latch_tmp2(Tmp2Sel(mir.tmp2_sel))

        self.dp.signal_alu(AluOp(mir.alu_op))

        # Фаза 2 - Сохранение (защелки)
        
        # data mem
        if mir.ar_latch:
            self.dp.signal_latch_ar(MemAddrSel(mir.mem_addr_sel))
        if mir.mem_wr:
            self.dp.signal_mem_write(MemDataSel(mir.mem_data_sel))
            
        # alu & flags
        if mir.nzvc_latch:
            self.dp.signal_latch_nzvc()
        if mir.alu_res_latch:
            self.dp.signal_latch_alu_res()
            
        # register file
        if mir.latch_reg:
            self.dp.signal_latch_reg(RegWrSel(mir.reg_wr_sel))
            
        # io controller
        if mir.port_latch:
            self.dp.signal_latch_port()
        if mir.out_latch:
            self.dp.signal_latch_out_data(OutSel(mir.out_sel))
        if mir.in_latch:
            self.dp.signal_latch_in_data()

        # instr memory
        if mir.ir_latch:
            self.ir = self.dp.instr_word
        if mir.pc_latch:
            self.dp.signal_latch_pc(PcSel(mir.pc_sel))
            
        # control unit -> counter
        if mir.latch_cnt:
            flat = self.decode_instruction(self.ir)
            self.counter = flat.n if flat.n is not None else 0
        if mir.counter_dec:
            self.counter -= 1

        # Фаза 3 - секвенсор

        self.mpc = self.next_micro_addr()
        
        # MIR.next()
        if 0 <= self.mpc < len(self.microcode_memory):
            self.mir = self.microcode_memory[self.mpc]
        else:
            # выход за пределы микрокода
            self.mir = None
