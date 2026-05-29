import sys
import yaml
import argparse
import logging

from datapath import *
from control_unit import *
from isa import *
from microcode import *


STATIC_DATA_START = 0x200

log = logging.getLogger(__name__)


def load_bytes(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()


def load_input(path: str) -> dict[int, list]:
    """
    Чтение буферов портов
    """
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    if not raw:
        return {}
    result = {}
    for port, tokens in raw.items():
        parsed = []
        for token in tokens:
            if isinstance(token, str):
                parsed.append(token)
            elif isinstance(token, int):
                parsed.append(token)
            else:
                raise ValueError(f"Port {port}: unsupported token {token!r}")
        result[int(port)] = parsed
    return result


def make_io(port_buffers: dict[int, list]) -> IOController:
    """
    Создание IOController на основе поданных буферов
    """
    io = IOController()

    def read_token(port: int) -> int:
        buf = port_buffers.get(port, [])
        if not buf:
            raise StopIteration(f"Input buffer for port {port} is empty")
        raw = buf.pop(0)
        if port == 3:
            return ord(raw[0]) if isinstance(raw, str) else int(raw)
        return int(raw)

    io.read_token = read_token
    return io


def format_output(buf: list) -> str:
    return "".join(str(x) for x in buf)


def make_datapath(
    instr_bytes: bytes,
    data_bytes: bytes,
    io: IOController,
    data_mem_size: int,
) -> DataPath:
    """
    Создание Datapath и инициализация регистров нужными значениями
    """
    instr_mem = list(instr_bytes)
    dp = DataPath(
        instr_mem, io,
        data_memory_size=data_mem_size,
        instr_memory_size=max(len(instr_mem), 256),
    )
    # загружаем статическую память данных
    for i, b in enumerate(data_bytes):
        if i < data_mem_size:
            dp.data_memory[i] = b & 0xFF

    dp.registers[6] = data_mem_size     # DSP - конец памяти, стек растёт вниз
    dp.registers[7] = STATIC_DATA_START # RSP - начало памяти, стек растёт вверх
    return dp


def make_cu(dp: DataPath) -> ControlUnit:
    """
    Инициализация ControlUnit начальными значениями
    """
    cu = ControlUnit(
        dp, microcode_memory, opcode_to_mpc,
        src_dispatch_table, dst_dispatch_table,
        wb_dispatch_table, fast_exec_table,
    )
    cu.mpc = FETCH_IR
    cu.mir = microcode_memory[FETCH_IR]
    return cu


def fmt_regs(dp: DataPath) -> str:
    r = dp.registers
    return (
        f"R0={r[0]:>10}  R1={r[1]:>10}  R2={r[2]:>10}  R3={r[3]:>10}  "
        f"R4={r[4]:>10}  DSP={r[6]:#06x}  RSP={r[7]:#06x}"
    )


def fmt_flags(dp: DataPath) -> str:
    return (
        f"N={int(dp.flag_n)} Z={int(dp.flag_z)} "
        f"V={int(dp.flag_v)} C={int(dp.flag_c)}"
    )

def fmt_tick(tick: int, cu: ControlUnit, dp: DataPath) -> str:
    mir = cu.mir
    label = mir.label if mir else "?"
    return (
        f"tick={tick:5d}  pc={dp.pc:#06x} mpc={cu.mpc:3d} [{fmt_flags(dp)}] @ {label}\n"
        f"{fmt_regs(dp)}\n"
    )


def run_silent(cu: ControlUnit, dp: DataPath, tick_limit: int) -> int:
    tick = 0
    try:
        while cu.current_micro:
            cu.tick()
            tick += 1
            if tick > tick_limit:
                raise RuntimeError(f"tick limit {tick_limit} exceeded")
    except StopIteration:
        pass
    return tick


def run_verbose(cu: ControlUnit, dp: DataPath, tick_limit: int) -> int:
    """Потактовая трасировка - печатает каждый такт (все микрокоманды)"""
    tick = 0
    try:
        while cu.current_micro:
            log.debug(fmt_tick(tick, cu, dp))
            cu.tick()
            tick += 1
            if tick > tick_limit:
                raise RuntimeError(f"tick limit {tick_limit} exceeded")
    except StopIteration:
        log.debug(fmt_tick(tick, cu, dp))
    return tick


def run_instr_trace(cu: ControlUnit, dp: DataPath, tick_limit: int) -> int:
    """Трассировка на уровне инструкций - печатает только первый такт каждой инструкции"""
    tick = 0
    last_pc = -1
    try:
        while cu.current_micro:
            if dp.pc != last_pc and cu.mpc == FETCH_IR:
                last_pc = dp.pc
                opcode = cu.decoded.opcode if cu.decoded else "?"
                log.debug(
                    f"tick={tick:5d} "
                    f"pc={dp.pc:#06x} "
                    f"{str(opcode):<8} "
                    f"{fmt_regs(dp)} "
                    f"{fmt_flags(dp)}"
                )
            cu.tick()
            tick += 1
            if tick > tick_limit:
                raise RuntimeError(f"tick limit {tick_limit} exceeded")
    except StopIteration:
        pass
    return tick


def run_head_trace(cu: ControlUnit, dp: DataPath, tick_limit: int, head: int) -> int:
    """Трассировка первых N тиков, затем silent режим"""
    tick = 0
    last_pc = -1
    try:
        while cu.current_micro:
            if tick < head and dp.pc != last_pc and cu.mpc == FETCH_IR:
                last_pc = dp.pc
                opcode = cu.decoded.opcode if cu.decoded else "?"
                log.debug(
                    f"tick={tick:5d} "
                    f"pc={dp.pc:#06x} "
                    f"{str(opcode):<8} "
                    f"{fmt_regs(dp)} "
                    f"{fmt_flags(dp)}"
                )
            cu.tick()
            tick += 1
            if tick > tick_limit:
                raise RuntimeError(f"tick limit {tick_limit} exceeded")
    except StopIteration:
        pass
    return tick


def main():
    parser = argparse.ArgumentParser(
        description="CSA Lab4: forth | cisc | harv | mc | tick | binary | stream | port | pstr | prob1 | ~~cache~~ ",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("bin_file",
                        help="Binary instruction file from translator (.bin)")
    parser.add_argument("--data", "-d", metavar="DATA_FILE", default=None,
                        help="Binary static data file (.data)")
    parser.add_argument("--input", "-i", metavar="INPUT_FILE", default=None,
                        help="Port input buffers (.yaml)")
    parser.add_argument("--data-mem-size", type=int, default=4096,
                        help="Data memory size in bytes (default: 4096)")
    parser.add_argument("--tick-limit", type=int, default=100_000,
                        help="Maximum ticks before abort (default: 100000)")

    trace = parser.add_mutually_exclusive_group()
    trace.add_argument("--verbose", "-v", action="store_true",
                       help="Выводить каждый тик (каждую микрокоманду)")
    trace.add_argument("--trace", "-t", action="store_true",
                       help="Выводить каждую инструкцию ISA (покомандно)")
    trace.add_argument("--head", "-H", type=int, metavar="N", default=None,
                       help="Выводить первые N тиков")

    parser.add_argument("--listing", "-l", action="store_true",
                        help="Print decoded instruction listing before run")

    args = parser.parse_args()

    try:
        instr_bytes = load_bytes(args.bin_file)
    except FileNotFoundError:
        print(f"[!] error: '{args.bin_file}' not found", file=sys.stderr)
        sys.exit(1)

    data_bytes = b""

    if args.data:
        try:
            data_bytes = load_bytes(args.data)
        except FileNotFoundError:
            print(f"[!] error: data file '{args.data}' not found", file=sys.stderr)
            sys.exit(1)

    port_buffers: dict[int, list] = {}
    if args.input:
        try:
            port_buffers = load_input(args.input)
        except FileNotFoundError:
            print(f"[!] error: input file '{args.input}' not found", file=sys.stderr)
            sys.exit(1)
        except ValueError as e:
            print(f"[!] error in input file: {e}", file=sys.stderr)
            sys.exit(1)

    # листинг 
    if args.listing:
        log.info(f"--- listing: {args.bin_file} ---")
        try:
            instructions = Instruction.decode_all(instr_bytes)
            addr = 0
            for instr in instructions:
                size = instr.size_bytes()
                raw  = " ".join(f"{b:02x}" for b in instr_bytes[addr:addr + size])
                log.info(f"  {addr:#06x}  {str(instr):<35}  ; {raw}")
                addr += size
        except ValueError as e:
            print(f"[!] decode error: {e}", file=sys.stderr)

    io = make_io(port_buffers)
    dp = make_datapath(instr_bytes, data_bytes, io, args.data_mem_size)
    cu = make_cu(dp)

    # запуск
    if args.verbose:
        log.debug("=== Tick trace ===")
    elif args.trace:
        log.debug("=== Instruction trace ===")
    elif args.head:
        log.debug(f"=== Instruction trace (first {args.head} ticks) ===")

    try:
        if args.verbose:
            ticks = run_verbose(cu, dp, args.tick_limit)
        elif args.trace:
            ticks = run_instr_trace(cu, dp, args.tick_limit)
        elif args.head:
            ticks = run_head_trace(cu, dp, args.tick_limit, args.head)
        else:
            ticks = run_silent(cu, dp, args.tick_limit)
    except RuntimeError as e:
        print(f"\nsimulation aborted: {e}", file=sys.stderr)
        sys.exit(1)

    output = format_output(io.output_buffer)
    print(output)

    print(f"output: {io.output_buffer}", file=sys.stderr)
    print(f"ticks: {ticks}", file=sys.stderr)


if __name__ == "__main__":
    main()
