from dataclasses import dataclass

from datapath import *
from isa import *


@dataclass
class MicroInstruction:
    label: str = ""

    # Register File
    reg_src_sel: int = 0    # 0xF => take from IR.src; 0xE => take from IR.dst
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
    alu_right_sel: int = 0

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
        Конвертация микрокоманды в 64-битную бинарную строку (58 бит + 6 на выравнивание)
        """

        bin_str = (
            f"{self.hlt:01b}"

            # Register File
            f"{self.reg_src_sel:04b}"
            f"{self.reg_dst_sel:04b}"
            f"{self.reg_wr_sel:03b}"
            f"{self.latch_reg:01b}"

            # TMP
            f"{self.tmp1_sel:03b}"
            f"{self.tmp2_sel:03b}"
            f"{self.latch_tmp1:01b}"
            f"{self.latch_tmp2:01b}"

            # ALU
            f"{self.alu_op:05b}"
            f"{self.nzvc_latch:01b}"
            f"{self.alu_res_latch:01b}"
            f"{self.alu_right_sel:02b}"

            # Memory
            f"{self.mem_addr_sel:02b}"
            f"{self.mem_data_sel:03b}"
            f"{self.mem_rd:01b}"
            f"{self.mem_wr:01b}"

            # PC / IR
            f"{self.pc_sel:02b}"
            f"{self.pc_latch:01b}"
            f"{self.ir_latch:01b}"

            # IO
            f"{self.port_latch:01b}"
            f"{self.out_sel:02b}"
            f"{self.out_latch:01b}"
            f"{self.in_latch:01b}"

            # Sequencer
            f"{self.latch_cnt:01b}"
            f"{self.counter_dec:01b}"
            f"{self.seq_branch:05b}"
            f"{self.next_addr:08b}"

            # AR
            f"{self.ar_latch:01b}"
        )

        return bin_str.zfill(64)


class BranchCode(IntEnum):
    NEXT = 0    # mpc+1

    JMP = 1     # jmp anyway
    JZ = 2      # Z=1
    JNZ = 3     # Z=0
    JN = 4      # N=1
    JC = 5      # C=1
    JV = 6      # V=1
    
    JCNT_Z = 7  # counter == 0
    JNN = 8     # N=0
    JNC = 9    # C=0
    JNV = 10    # V=0
    JGE = 11    # N == V
    JLT = 12    # N != V
    JLE = 13    # Z=1 or N != V
    JGT = 14    # Z=0 and N == V
    
    END_MICRO = 15
    DISPATCH_SRC = 16
    DISPATCH_DST = 17
    DISPATCH_WB = 18
    DISPATCH_OP = 19
    

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
        src_dispatch_table: dict[AddrMode, int], 
        dst_dispatch_table: dict[AddrMode, int], 
        wb_dispatch_table: dict[AddrMode, int],
    ):
        self.dp = dp
        self.io = dp.io_controller

        self.microcode_memory = microcode_memory

        self.mpc = 0
        self.ir = 0
        self.counter = 0
        self.decoded: FlatInstruction | None = None

        self.mir: MicroInstruction | None
        if self.microcode_memory:
            self.mir = self.microcode_memory[self.mpc]
        else:
            self.mir = None        

        # маппинг для опкодов на микрокоманды в памяти
        self.opcode_to_mpc = opcode_to_mpc
        self.src_dispatch_table = src_dispatch_table
        self.dst_dispatch_table = dst_dispatch_table
        self.wb_dispatch_table = wb_dispatch_table
        

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
    
    # @property
    # def start_addr(self) -> int:
    #     """
    #     Шина start_addr: выход Instruction Decoder'а (маппинг opcode -> mpc).
    #     """
    #     flat = self.decode_instruction(self.ir)
    #     return self.opcode_to_mpc[flat.opcode]

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
            return 0  # 0 - адрес FETCH цикла
        
        # диспетчеризация для корректного флоу исполнения микрокоманды
        if code == BranchCode.DISPATCH_SRC:
            return self.src_dispatch_table[self.decoded.src_mode]
        if code == BranchCode.DISPATCH_DST:
            return self.dst_dispatch_table[self.decoded.dst_mode]
        if code == BranchCode.DISPATCH_OP:
            return self.opcode_to_mpc[self.decoded.opcode]
        if code == BranchCode.DISPATCH_WB:
            return self.wb_dispatch_table[self.decoded.dst_mode]
        
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
        
        src = self.decoded.src_reg if (mir.reg_src_sel == 0xF and self.decoded) else mir.reg_src_sel
        if mir.reg_dst_sel == 0xE and self.decoded:
            dst = self.decoded.src_reg
        elif mir.reg_dst_sel == 0xF and self.decoded:
            if OPCODE_NARG[self.decoded.opcode] == 1:
                dst = self.decoded.src_reg
            else:
                dst = self.decoded.dst_reg
        else:
            dst = mir.reg_dst_sel
        self.dp.signal_select_regs(src, dst)   

        if mir.ar_latch:
            self.dp.signal_latch_ar(MemAddrSel(mir.mem_addr_sel))
        
        if mir.latch_tmp1:
            self.dp.signal_latch_tmp1(Tmp1Sel(mir.tmp1_sel))
        if mir.latch_tmp2:
            self.dp.signal_latch_tmp2(Tmp2Sel(mir.tmp2_sel))

        # alu & flags
        self.dp.signal_alu(
            AluOp(mir.alu_op),
            AluRightSel(mir.alu_right_sel)
        )

        if mir.nzvc_latch:
            self.dp.signal_latch_nzvc()
        if mir.alu_res_latch:
            self.dp.signal_latch_alu_res()
            
        # register file
        if mir.latch_reg:
            self.dp.signal_latch_reg(RegWrSel(mir.reg_wr_sel))
        
        if mir.mem_wr:
            self.dp.signal_mem_write(MemDataSel(mir.mem_data_sel))

        # PC & IR
        if mir.ir_latch:
            self.ir = self.dp.instr_word
            self.decoded = self.decode_instruction(self.ir)
        if mir.pc_latch:
            self.dp.signal_latch_pc(PcSel(mir.pc_sel))
            
        # io controller
        if mir.port_latch:
            self.dp.signal_latch_port()
        if mir.out_latch:
            self.dp.signal_latch_out_data(OutSel(mir.out_sel))
        if mir.in_latch:
            self.dp.signal_latch_in_data()

        # control unit -> counter
        if mir.latch_cnt:
            flat = self.decode_instruction(self.ir)
            self.counter = flat.n if flat.n is not None else 0
        if mir.counter_dec:
            self.counter -= 1

        # секвенсор
        self.mpc = self.next_micro_addr()
        
        # MIR.next()
        if 0 <= self.mpc < len(self.microcode_memory):
            self.mir = self.microcode_memory[self.mpc]
        else:
            # выход за пределы микрокода
            self.mir = None
