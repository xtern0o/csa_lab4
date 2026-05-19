from dataclasses import dataclass


@dataclass
class MicroInstruction:
    # Register File
    reg_src_sel: int = 0
    reg_dst_sel: int = 0
    reg_wr_sel: int = 0
    latch_reg: int = 0

    # ALU
    alu1_sel: int = 0
    alu2_sel: int = 0
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

    def to_binary_string(self) -> str:
        """Конвертация микрокоманды в 50-битную бинарную строку (выравнивается до 7 байт)."""
        bin_str = (
            f"{self.reg_src_sel:02b}{self.reg_dst_sel:02b}{self.reg_wr_sel:03b}{self.latch_reg:01b}"
            f"{self.alu1_sel:02b}{self.alu2_sel:03b}{self.alu_op:05b}{self.nzvc_latch:01b}{self.alu_res_latch:01b}"
            f"{self.mem_addr_sel:02b}{self.mem_data_sel:03b}{self.mem_rd:01b}{self.mem_wr:01b}"
            f"{self.pc_sel:02b}{self.pc_latch:01b}{self.ir_latch:01b}"
            f"{self.port_latch:01b}{self.out_sel:02b}{self.out_latch:01b}{self.in_latch:01b}"
            f"{self.latch_cnt:01b}{self.counter_dec:01b}{self.seq_branch:03b}{self.next_addr:08b}"
            f"{self.ar_latch:01b}"
        )
        return bin_str.zfill(56)