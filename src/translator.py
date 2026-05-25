import argparse
import re
import sys

from isa import *


STATIC_DATA_START = 0x100

R0, R1, R2, R3, R4, R5 = range(6)
DSP = 6
RSP = 7


class Parser:
    RESERVED_WORDS = {
        "var",
        "!",
        "@",
        "dup",
        "swap",
        "over",
        "drop",
        ">r",
        "r>",
        "r@",
        "@+",
        "!+",
        "&",
        "|",
        "^",
        "~",
        "+",
        "-",
        "*",
        "/",
        "mod",
        "=",
        ">",
        "<",
        "d+",
        "n+",
        "n-",
        ".",
        "key",
        "nkey",
        "emit",
        "type",
        "s.",
        '."',
        "if",
        "else",
        "endif",
        "begin",
        "until",
        ":",
        ";",
        "'",
        "execute",
        "in",
        "out",
        "(",
        ")",
        "\\",
    }

    @staticmethod
    def tokenize(src_code: str) -> list[str]:
        """
        Токенизация forth-кода:
        - удаление комментариев вида '\\...'
        - замена символов переноса строк и табуляции на пробелы
        - удаление комментариев вида '(...)'

        -> возвращает готовый список токенов
        """
        src_code = re.sub(r"\\.*", "", src_code)
        src_code = re.sub(r"[\n\t]", " ", src_code)
        src_code = re.sub(r"\(.*?\)", "", src_code)

        # паттерн для поиска любых непробельных символов: \S+
        # паттерны для строковых литералов: ." ..." и "..."
        tokens = re.findall(r'\."\s+.*?"|".*?"|\S+', src_code)

        # все кроме строк - регистронезависимые токены
        tokens = [
            t if (t.startswith('."') or t.startswith('"')) else t.lower()
            for t in tokens
        ]

        return tokens


class Translator:
    WORD_SIZE = 4

    def __init__(self):
        # память программ
        self.instr_memory: list[Instruction] = []
        self.instr_addr = 0

        # статическая память данных
        self.data_memory: bytearray = bytearray()
        self.data_addr = STATIC_DATA_START

        # linking maps
        self.variables: dict[str, int] = {}  # name: data_addr
        self.functions: dict[str, int] = {}  # name: instr_addr

        self.control_flow_stack = []

    def add_instruction(
        self, opcode: Opcode, operands: list[Operand] | None = None
    ) -> Instruction:
        if operands is None:
            operands = []

        instr = Instruction(opcode, operands)
        self.instr_memory.append(instr)

        self.instr_addr += instr.size_bytes()

        return instr

    def translate(self, tokens: list[str]):
        """
        Транслятор Forth -> CISC instruction set

        - forth удобно транслировать линейно и однопроходно,
          поэтому я не использовал синтаксических деревьев
        - проблема control-flow инструкций решена так:
            - при встрече if запоминаем адрес инструкции
            - когда встречаем endif - вычисляем теккущий instr_addr
            - достаем из стека индекс, и меняем адрес перехода
              соответствующего if на текущий
        R1:         TOS:    stack[0]
        (DSP):      NOS:    stack[1]
        -(DSP):             stack[2]
        """

        tokens_iter = iter(tokens)

        for token in tokens_iter:
            if token == "var":
                var_name = next(tokens_iter)
                if var_name not in self.variables:
                    self.variables[var_name] = self.data_addr
                    self.data_addr += self.WORD_SIZE
                    self.data_memory.extend(b"\x00" * self.WORD_SIZE)

            elif token == ":":
                func_name = next(tokens_iter)
                self.functions[func_name] = self.instr_addr

            elif token == ";":
                self.add_instruction(Opcode.RET)

            elif token == "!":
                self.add_instruction(
                    Opcode.MOVE,
                    [Operand(AddrMode.POST_INC, DSP), Operand(AddrMode.REG_DIRECT, R1)],
                )
                self.add_instruction(
                    Opcode.MOVE,
                    [
                        Operand(AddrMode.REG_DIRECT, R1),
                        Operand(AddrMode.REG_INDIRECT, R0),
                    ],
                )
                self.add_instruction(
                    Opcode.MOVE,
                    [Operand(AddrMode.POST_INC, DSP), Operand(AddrMode.REG_DIRECT, R0)],
                )

            elif token == "@":
                self.add_instruction(
                    Opcode.MOVE,
                    [
                        Operand(AddrMode.REG_INDIRECT, R0),
                        Operand(AddrMode.REG_DIRECT, R0),
                    ],
                )

            elif token == "@+":
                self.add_instruction(
                    Opcode.MOVE,
                    [Operand(AddrMode.POST_INC, R0), Operand(AddrMode.REG_DIRECT, R1)],
                )
                self.add_instruction(
                    Opcode.MOVE,
                    [Operand(AddrMode.REG_DIRECT, R0), Operand(AddrMode.PRE_DEC, DSP)],
                )
                self.add_instruction(
                    Opcode.MOVE,
                    [
                        Operand(AddrMode.REG_DIRECT, R1),
                        Operand(AddrMode.REG_DIRECT, R0),
                    ],
                )

            elif token == "!+":
                self.add_instruction(
                    Opcode.MOVE,
                    [Operand(AddrMode.POST_INC, DSP), Operand(AddrMode.REG_DIRECT, R1)],
                )
                self.add_instruction(
                    Opcode.MOVE,
                    [Operand(AddrMode.REG_DIRECT, R1), Operand(AddrMode.POST_INC, R0)],
                )

            elif token == "dup":
                self.add_instruction(
                    Opcode.MOVE,
                    [Operand(AddrMode.REG_DIRECT, R0), Operand(AddrMode.PRE_DEC, DSP)],
                )

            elif token == "drop":
                self.add_instruction(
                    Opcode.MOVE,
                    [Operand(AddrMode.POST_INC, DSP), Operand(AddrMode.REG_DIRECT, R0)],
                )

            elif token == ">r":
                # data: ( x -- ), return: ( -- x)
                self.add_instruction(
                    Opcode.MOVE,
                    [Operand(AddrMode.REG_DIRECT, R0), Operand(AddrMode.PRE_DEC, RSP)],
                )
                self.add_instruction(
                    Opcode.MOVE,
                    [Operand(AddrMode.POST_INC, DSP), Operand(AddrMode.REG_DIRECT, R0)],
                )

            elif token == "r>":
                # data: ( -- x ), return: (x -- )
                self.add_instruction(
                    Opcode.MOVE,
                    [Operand(AddrMode.REG_DIRECT, R0), Operand(AddrMode.PRE_DEC, DSP)],
                )
                self.add_instruction(
                    Opcode.MOVE,
                    [Operand(AddrMode.POST_INC, RSP), Operand(AddrMode.REG_DIRECT, R0)],
                )

            elif token == "r@":
                # data: ( -- x ), return: (x -- x)
                self.add_instruction(
                    Opcode.MOVE,
                    [Operand(AddrMode.REG_DIRECT, R0), Operand(AddrMode.PRE_DEC, DSP)],
                )
                self.add_instruction(
                    Opcode.MOVE,
                    [
                        Operand(AddrMode.REG_INDIRECT, RSP),
                        Operand(AddrMode.REG_DIRECT, R0),
                    ],
                )

            elif token == "swap":
                # ( a b -- b a )
                # читаем а без сдвига указателя
                self.add_instruction(
                    Opcode.MOVE,
                    [
                        Operand(AddrMode.REG_INDIRECT, DSP),
                        Operand(AddrMode.REG_DIRECT, R1),
                    ],
                )
                # пишем b на место а в память
                self.add_instruction(
                    Opcode.MOVE,
                    [
                        Operand(AddrMode.REG_DIRECT, R0),
                        Operand(AddrMode.REG_INDIRECT, DSP),
                    ],
                )
                # делаем a новым TOS
                self.add_instruction(
                    Opcode.MOVE,
                    [
                        Operand(AddrMode.REG_DIRECT, R1),
                        Operand(AddrMode.REG_DIRECT, R0),
                    ],
                )

            elif token == "over":
                # ( a b -- a b a )
                self.add_instruction(
                    Opcode.MOVE,
                    [
                        Operand(AddrMode.REG_INDIRECT, DSP),
                        Operand(AddrMode.REG_DIRECT, R1),
                    ],
                )
                self.add_instruction(
                    Opcode.MOVE,
                    [Operand(AddrMode.REG_DIRECT, R0), Operand(AddrMode.PRE_DEC, DSP)],
                )
                self.add_instruction(
                    Opcode.MOVE,
                    [
                        Operand(AddrMode.REG_DIRECT, R1),
                        Operand(AddrMode.REG_DIRECT, R0),
                    ],
                )

            # коммутативная логика и арифмеика
            elif token in {"+", "*", "&", "|", "^"}:
                self.add_instruction(
                    Opcode.MOVE,
                    [Operand(AddrMode.POST_INC, DSP), Operand(AddrMode.REG_DIRECT, R1)],
                )

                if token == "+":
                    self.add_instruction(
                        Opcode.ADD,
                        [
                            Operand(AddrMode.REG_DIRECT, R1),
                            Operand(AddrMode.REG_DIRECT, R0),
                        ],
                    )
                elif token == "*":
                    self.add_instruction(
                        Opcode.MUL,
                        [
                            Operand(AddrMode.REG_DIRECT, R1),
                            Operand(AddrMode.REG_DIRECT, R0),
                        ],
                    )
                elif token == "&":
                    self.add_instruction(
                        Opcode.AND_OP,
                        [
                            Operand(AddrMode.REG_DIRECT, R1),
                            Operand(AddrMode.REG_DIRECT, R0),
                        ],
                    )
                elif token == "|":
                    self.add_instruction(
                        Opcode.OR_OP,
                        [
                            Operand(AddrMode.REG_DIRECT, R1),
                            Operand(AddrMode.REG_DIRECT, R0),
                        ],
                    )
                elif token == "^":
                    self.add_instruction(
                        Opcode.XOR,
                        [
                            Operand(AddrMode.REG_DIRECT, R1),
                            Operand(AddrMode.REG_DIRECT, R0),
                        ],
                    )

            # некоммутативная логика и арифметика
            elif token in {"-", "/", "mod"}:
                self.add_instruction(
                    Opcode.MOVE,
                    [Operand(AddrMode.POST_INC, DSP), Operand(AddrMode.REG_DIRECT, R1)],
                )

                if token == "-":
                    self.add_instruction(
                        Opcode.SUB,
                        [
                            Operand(AddrMode.REG_DIRECT, R0),
                            Operand(AddrMode.REG_DIRECT, R1),
                        ],
                    )
                elif token == "/":
                    self.add_instruction(
                        Opcode.DIV,
                        [
                            Operand(AddrMode.REG_DIRECT, R0),
                            Operand(AddrMode.REG_DIRECT, R1),
                        ],
                    )
                elif token == "mod":
                    self.add_instruction(
                        Opcode.REM,
                        [
                            Operand(AddrMode.REG_DIRECT, R0),
                            Operand(AddrMode.REG_DIRECT, R1),
                        ],
                    )

                self.add_instruction(
                    Opcode.MOVE,
                    [
                        Operand(AddrMode.REG_DIRECT, R1),
                        Operand(AddrMode.REG_DIRECT, R0),
                    ],
                )

            elif token in {"n+", "n*"}:
                # 3 n+ -> POP the N literal, then POP the N operands

                # pop literal n
                n_inst = self.instr_memory.pop()
                self.instr_addr -= n_inst.size_bytes()

                R0_push_inst = self.instr_memory.pop()
                self.instr_addr -= R0_push_inst.size_bytes()

                if (
                    n_inst.opcode != Opcode.MOVE
                    or n_inst.operands[0].mode != AddrMode.IMMEDIATE
                ):
                    raise Exception(f"Expected immediate value for N before {token}")

                num_args = n_inst.operands[0].value
                n_op_list: list[Operand] = []

                for _ in range(num_args):
                    arg_val_inst = self.instr_memory.pop()
                    self.instr_addr -= arg_val_inst.size_bytes()

                    arg_push_inst = self.instr_memory.pop()
                    self.instr_addr -= arg_push_inst.size_bytes()

                    if (
                        arg_val_inst.opcode != Opcode.MOVE
                        or arg_val_inst.operands[0].mode != AddrMode.IMMEDIATE
                    ):
                        raise Exception(
                            f"Only immediate values are supported "
                            f"for {token} arguments in hardware mapping"
                        )
                    n_op_list.insert(0, arg_val_inst.operands[0])

                opcode = Opcode.NADD if token == "n+" else Opcode.NMUL

                self.add_instruction(opcode, n_op_list)

            elif token == "~":
                self.add_instruction(Opcode.NOT_OP, [Operand(AddrMode.REG_DIRECT, R0)])

            elif token == "d+":
                # ( al ah bl bh -- rl rh )
                # R0 = bh, (DSP) = bl, -(DSP) = ah, --(DSP) = al
                self.add_instruction(
                    Opcode.MOVE,
                    [Operand(AddrMode.POST_INC, DSP), Operand(AddrMode.REG_DIRECT, R1)],
                )  # R1 = bl
                self.add_instruction(
                    Opcode.MOVE,
                    [Operand(AddrMode.POST_INC, DSP), Operand(AddrMode.REG_DIRECT, R2)],
                )  # R2 = ah
                self.add_instruction(
                    Opcode.MOVE,
                    [Operand(AddrMode.POST_INC, DSP), Operand(AddrMode.REG_DIRECT, R3)],
                )  # R3 = al

                # R0 = bh, R1 = bl
                # +
                # R2 = ah, R3 = al
                # ----------------
                # R0 = rh, (DSP) = rl
                self.add_instruction(
                    Opcode.ADD,
                    [
                        Operand(AddrMode.REG_DIRECT, R1),
                        Operand(AddrMode.REG_DIRECT, R3),
                    ],
                )
                self.add_instruction(
                    Opcode.ADC,
                    [
                        Operand(AddrMode.REG_DIRECT, R2),
                        Operand(AddrMode.REG_DIRECT, R0),
                    ],
                )

                # TOS = rh
                # NOS <- R3 = rl
                self.add_instruction(
                    Opcode.MOVE,
                    [Operand(AddrMode.REG_DIRECT, R3), Operand(AddrMode.PRE_DEC, DSP)],
                )

            # comparison processing
            elif token == "begin":
                # mark loop start
                loop_addr = self.instr_addr
                self.control_flow_stack.append(("begin", loop_addr))

            elif token == "until":
                _, loop_addr = self.control_flow_stack.pop()
                self.add_instruction(Opcode.CMP, [
                    Operand(AddrMode.IMMEDIATE, 0),
                    Operand(AddrMode.REG_DIRECT, R0)
                ])
                self.add_instruction(Opcode.BEQ, [Operand(AddrMode.IMMEDIATE, loop_addr)])

            elif token in {"=", "<", ">"}:
                self.add_instruction(Opcode.MOVE, [
                    Operand(AddrMode.POST_INC, DSP), Operand(AddrMode.REG_DIRECT, R1)
                ])
                self.add_instruction(Opcode.CMP, [
                    Operand(AddrMode.REG_DIRECT, R0), Operand(AddrMode.REG_DIRECT, R1)
                ])

                jmp_opcode = None
                if token == "=":   jmp_opcode = Opcode.BNE
                elif token == ">": jmp_opcode = Opcode.BLE
                elif token == "<": jmp_opcode = Opcode.BGE

                # if not -> jump to false branch
                jmp_inst = self.add_instruction(jmp_opcode, [Operand(AddrMode.IMMEDIATE, 0)])

                # true: R0 = 1
                self.add_instruction(Opcode.MOVE, [
                    Operand(AddrMode.IMMEDIATE, 1), Operand(AddrMode.REG_DIRECT, R0)
                ])
                end_jmp = self.add_instruction(Opcode.JMP, [Operand(AddrMode.IMMEDIATE, 0)])

                # false: R0 = 0
                jmp_inst.operands[0].value = self.instr_addr
                self.add_instruction(Opcode.MOVE, [
                    Operand(AddrMode.IMMEDIATE, 0), Operand(AddrMode.REG_DIRECT, R0)
                ])

                end_jmp.operands[0].value = self.instr_addr

            elif token == "if":
                # ( flag -- flag )
                # if R0 == 0, jump to else/endif
                self.add_instruction(Opcode.CMP, [
                    Operand(AddrMode.IMMEDIATE, 0),
                    Operand(AddrMode.REG_DIRECT, R0)
                ])
                jmp_inst = self.add_instruction(
                    Opcode.BEQ, [Operand(AddrMode.IMMEDIATE, 0)]
                )
                self.control_flow_stack.append(("if", jmp_inst))

            elif token == "else":
                if (
                    not self.control_flow_stack
                    or self.control_flow_stack[-1][0] != "if"
                ):
                    raise Exception("else without matching if")

                _, if_jmp = self.control_flow_stack.pop()
                else_jmp = self.add_instruction(Opcode.JMP, [Operand(AddrMode.IMMEDIATE, 0)])
                if_jmp.operands[0].value = self.instr_addr
                self.control_flow_stack.append(("else", else_jmp))

            elif token == "endif":
                if not self.control_flow_stack or self.control_flow_stack[-1][
                    0
                ] not in ("if", "else"):
                    raise Exception("endif without matching if/else")

                _, jmp_inst = self.control_flow_stack.pop()

                jmp_inst.operands[0].value = self.instr_addr

            # variable processing
            elif token in self.variables:
                self.add_instruction(
                    Opcode.MOVE,
                    [Operand(AddrMode.REG_DIRECT, R0), Operand(AddrMode.PRE_DEC, DSP)],
                )
                addr = self.variables[token]
                self.add_instruction(
                    Opcode.MOVE,
                    [
                        Operand(AddrMode.IMMEDIATE, addr),
                        Operand(AddrMode.REG_DIRECT, R0),
                    ],
                )

            elif token == "out":
                # ( data port -- )

                self.add_instruction(
                    Opcode.MOVE,
                    [Operand(AddrMode.POST_INC, DSP), Operand(AddrMode.REG_DIRECT, R1)],
                )  # R1 = val
                self.add_instruction(
                    Opcode.OUT,
                    [
                        Operand(AddrMode.REG_DIRECT, R1),
                        Operand(AddrMode.REG_DIRECT, R0),
                    ],
                )

                self.add_instruction(
                    Opcode.MOVE,
                    [Operand(AddrMode.POST_INC, DSP), Operand(AddrMode.REG_DIRECT, R0)],
                )

            elif token == "in":
                # R0 = port_number, R0 <- ports[port_number]
                self.add_instruction(
                    Opcode.IN,
                    [
                        Operand(AddrMode.REG_DIRECT, R0),
                        Operand(AddrMode.REG_DIRECT, R0),
                    ],
                )

            # number processing
            elif token.lstrip("-").isdigit():
                self.add_instruction(
                    Opcode.MOVE,
                    [Operand(AddrMode.REG_DIRECT, R0), Operand(AddrMode.PRE_DEC, DSP)],
                )
                val = int(token)
                self.add_instruction(
                    Opcode.MOVE,
                    [
                        Operand(AddrMode.IMMEDIATE, val),
                        Operand(AddrMode.REG_DIRECT, R0),
                    ],
                )

            # procedure processing
            elif token in self.functions:
                func_addr = self.functions[token]
                self.add_instruction(
                    Opcode.JSR, [Operand(AddrMode.IMMEDIATE, func_addr)]
                )

            elif token == "'":
                func_name = next(tokens_iter)
                subroutine_addr: int | None = self.functions.get(func_name)
                if subroutine_addr is None:
                    raise Exception(
                        f"Unknown subroutine '{func_name}' for execution token"
                    )
                self.add_instruction(
                    Opcode.MOVE,
                    [Operand(AddrMode.REG_DIRECT, R0), Operand(AddrMode.PRE_DEC, DSP)],
                )
                self.add_instruction(
                    Opcode.MOVE,
                    [
                        Operand(AddrMode.IMMEDIATE, subroutine_addr),
                        Operand(AddrMode.REG_DIRECT, R0),
                    ],
                )

            elif token == "execute":
                self.add_instruction(Opcode.JSR, [Operand(AddrMode.REG_DIRECT, R0)])
                self.add_instruction(
                    Opcode.MOVE,
                    [Operand(AddrMode.POST_INC, DSP), Operand(AddrMode.REG_DIRECT, R0)],
                )

            # port-mapped i/o control
            elif token == ".":
                # print numeric from TOS to port 0
                self.add_instruction(
                    Opcode.OUT,
                    [Operand(AddrMode.REG_DIRECT, R0), Operand(AddrMode.IMMEDIATE, 0)],
                )
                self.add_instruction(
                    Opcode.MOVE,
                    [Operand(AddrMode.POST_INC, DSP), Operand(AddrMode.REG_DIRECT, R0)],
                )

            elif token == "emit":
                # print char from TOS to port 2
                self.add_instruction(
                    Opcode.OUT,
                    [Operand(AddrMode.REG_DIRECT, R0), Operand(AddrMode.IMMEDIATE, 2)],
                )
                self.add_instruction(
                    Opcode.MOVE,
                    [Operand(AddrMode.POST_INC, DSP), Operand(AddrMode.REG_DIRECT, R0)],
                )

            elif token == "key":
                # read char from port 3 to TOS
                self.add_instruction(
                    Opcode.MOVE,
                    [Operand(AddrMode.REG_DIRECT, R0), Operand(AddrMode.PRE_DEC, DSP)],
                )
                self.add_instruction(
                    Opcode.IN,
                    [Operand(AddrMode.IMMEDIATE, 3), Operand(AddrMode.REG_DIRECT, R0)],
                )

            elif token == "nkey":
                self.add_instruction(
                    Opcode.MOVE,
                    [Operand(AddrMode.REG_DIRECT, R0), Operand(AddrMode.PRE_DEC, DSP)],
                )
                self.add_instruction(
                    Opcode.IN,
                    [Operand(AddrMode.IMMEDIATE, 1), Operand(AddrMode.REG_DIRECT, R0)],
                )

            elif token in {"type", "s."}:  # noqa: S105
                # print string from address in TOS to port 2
                # R0 = string address (pstr)
                self.add_instruction(
                    Opcode.MOVE,
                    [Operand(AddrMode.POST_INC, R0), Operand(AddrMode.REG_DIRECT, R4)],
                )  # R4 = length, R0 += 4

                loop_start = self.instr_addr
                self.add_instruction(
                    Opcode.CMP,
                    [Operand(AddrMode.IMMEDIATE, 0), Operand(AddrMode.REG_DIRECT, R4)],
                )
                exit_jmp = self.add_instruction(
                    Opcode.BEQ, [Operand(AddrMode.IMMEDIATE, 0)]
                )

                self.add_instruction(
                    Opcode.MOVE,
                    [Operand(AddrMode.POST_INC, R0), Operand(AddrMode.REG_DIRECT, R1)],
                )  # R1 = char
                self.add_instruction(
                    Opcode.OUT,
                    [Operand(AddrMode.REG_DIRECT, R1), Operand(AddrMode.IMMEDIATE, 2)],
                )

                self.add_instruction(
                    Opcode.SUB,
                    [Operand(AddrMode.IMMEDIATE, 1), Operand(AddrMode.REG_DIRECT, R4)],
                )
                self.add_instruction(
                    Opcode.JMP, [Operand(AddrMode.IMMEDIATE, loop_start)]
                )

                exit_jmp.operands[0].value = self.instr_addr
                # pop address from data stack
                self.add_instruction(
                    Opcode.MOVE,
                    [Operand(AddrMode.POST_INC, DSP), Operand(AddrMode.REG_DIRECT, R0)],
                )

            elif token.startswith('."'):
                # immediate print str; format: ." Hello"

                match = re.search(r'\."\s+(.*)"', token)
                text = match.group(1) if match else ""

                # pstr: length in the first word + chars
                str_addr = self.data_addr
                self.data_memory.extend(
                    len(text).to_bytes(self.WORD_SIZE, "little", signed=True)
                )
                self.data_addr += self.WORD_SIZE
                for char in text:
                    self.data_memory.extend(
                        ord(char).to_bytes(self.WORD_SIZE, "little", signed=True)
                    )
                    self.data_addr += self.WORD_SIZE

                # R0 = string pointer
                self.add_instruction(
                    Opcode.MOVE,
                    [
                        Operand(AddrMode.IMMEDIATE, str_addr),
                        Operand(AddrMode.REG_DIRECT, R0),
                    ],
                )
                # R4 = length
                self.add_instruction(
                    Opcode.MOVE,
                    [Operand(AddrMode.POST_INC, R0), Operand(AddrMode.REG_DIRECT, R4)],
                )

                loop_start = self.instr_addr
                self.add_instruction(
                    Opcode.CMP,
                    [Operand(AddrMode.IMMEDIATE, 0), Operand(AddrMode.REG_DIRECT, R4)],
                )
                exit_jmp = self.add_instruction(
                    Opcode.BEQ, [Operand(AddrMode.IMMEDIATE, 0)]
                )

                self.add_instruction(
                    Opcode.MOVE,
                    [Operand(AddrMode.POST_INC, R0), Operand(AddrMode.REG_DIRECT, R1)],
                )
                self.add_instruction(
                    Opcode.OUT,
                    [Operand(AddrMode.REG_DIRECT, R1), Operand(AddrMode.IMMEDIATE, 2)],
                )

                self.add_instruction(
                    Opcode.SUB,
                    [Operand(AddrMode.IMMEDIATE, 1), Operand(AddrMode.REG_DIRECT, R4)],
                )
                self.add_instruction(
                    Opcode.JMP, [Operand(AddrMode.IMMEDIATE, loop_start)]
                )

                exit_jmp.operands[0].value = self.instr_addr

            elif token.startswith('"') and token.endswith('"'):
                # string literal value: "..." ->
                # -> place pstr in data memory and push its address
                text = token[1:-1]

                str_addr = self.data_addr
                self.data_memory.extend(
                    len(text).to_bytes(self.WORD_SIZE, "little", signed=True)
                )
                self.data_addr += self.WORD_SIZE

                for char in text:
                    self.data_memory.extend(
                        ord(char).to_bytes(self.WORD_SIZE, "little", signed=True)
                    )
                    self.data_addr += self.WORD_SIZE

                self.add_instruction(
                    Opcode.MOVE,
                    [Operand(AddrMode.REG_DIRECT, R0), Operand(AddrMode.PRE_DEC, DSP)],
                )
                self.add_instruction(
                    Opcode.MOVE,
                    [
                        Operand(AddrMode.IMMEDIATE, str_addr),
                        Operand(AddrMode.REG_DIRECT, R0),
                    ],
                )

        self.add_instruction(Opcode.HALT)


if __name__ == "__main__":
    parser_cli = argparse.ArgumentParser(description="Forth -> CISC binary translator")
    parser_cli.add_argument("source", help="source .forth file")
    parser_cli.add_argument("output", help="output binary file")
    parser_cli.add_argument("--listing", help="human-readable listing file (.txt)")
    parser_cli.add_argument("--data", help="output static data binary file")
    args = parser_cli.parse_args()

    # читаем исходник
    try:
        with open(args.source, "r", encoding="utf-8") as f:
            src = f.read()
    except FileNotFoundError:
        print(f"[!] error: src file '{args.source}' not found :((((", file=sys.stderr)
        sys.exit(1)

    # транслируем
    tokens = Parser.tokenize(src)
    t = Translator()
    try:
        t.translate(tokens)
    except Exception as e:
        print(f"[!] translation error: {e}", file=sys.stderr)
        sys.exit(1)

    # бинарник инструкций
    binary = bytearray()
    for instr in t.instr_memory:
        binary.extend(instr.to_bytes())

    with open(args.output, "wb") as f:
        f.write(binary)
    print(f"written: {args.output} ({len(binary)} bytes, {len(t.instr_memory)} instructions)")

    # бинарник статических данных
    if args.data:
        with open(args.data, "wb") as f:
            f.write(t.data_memory)
        print(f"data written:   {args.data} ({len(t.data_memory)} bytes)")

    # человекочитаемый листинг
    if args.listing:
        with open(args.listing, "w", encoding="utf-8") as f:
            f.write(f"; source: {args.source}\n")
            f.write(f"; instructions: {len(t.instr_memory)}, binary size: {len(binary)} bytes\n")

            if t.variables:
                f.write("\n; variables (static data):\n")
                for name, addr in t.variables.items():
                    f.write(f";   {name} @ 0x{addr:04x} ({addr})\n")

            if t.functions:
                f.write("\n; functions:\n")
                for name, addr in t.functions.items():
                    f.write(f";   {name} @ 0x{addr:04x} ({addr})\n")

            f.write("\n; instructions:\n")
            addr = 0
            for instr in t.instr_memory:
                size = instr.size_bytes()
                raw = instr.to_bytes().hex(" ")
                f.write(f"  0x{addr:04x}  {str(instr):<30}  ; {raw}\n")
                addr += size

        print(f"listing written: {args.listing}")