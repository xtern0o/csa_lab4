import re

from isa import *


class Parser:
    RESERVED_WORDS = {
        "var", "!", "@", "dup", "swap", "over", "drop",     # stack/memory
        ">r", "r>", "r@",                                   # return stack
        "@+", "!+",                                         # stack/memory cisc features
        "&", "|", "^", "~",                                 # logical gates
        "+", "-", "*", "/", "mod", "=", ">", "<", "d+",     # arithmetic
        "n+", "n-",
        ".", "key", "emit", "type", "s.", '."',             # io console
        "if", "else", "endif", "begin", "until",            # control flow
        ":", ";", "'", "execute",                           # begin/end subroutine
        "in", "out",                                        # custom port i/o
        "(", ")", "\\",                                     # comments
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
        src_code = re.sub(r'\\.*', '', src_code)
        src_code = re.sub(r'[\n\t]', ' ', src_code)
        src_code = re.sub(r'\(.*?\)', '', src_code)

        # паттерн для поиска любых непробельных символов: \S+
        # паттерны для строковых литералов: ." ..." и "..."
        tokens = re.findall(r'\."\s+.*?"|".*?"|\S+', src_code)

        # все кроме строк - регистронезависимые токены
        tokens = [t if (t.startswith('."') or t.startswith('"')) else t.lower() for t in tokens]

        return tokens
    

# general-purpose registers numbers (depends on addrmode)
D0, D1, D2, D3, D4, D5, D6, D7 = range(8)
A0, A1, A2, A3, A4, A5, A6, A7 = range(8)


class Translator:
    WORD_SIZE = 4

    def __init__(self):
        # память программ
        self.instr_memory: list[Instruction] = []
        self.instr_addr = 0

        # статическая память данных
        self.data_memory: bytearray = bytearray()
        self.data_addr = 0

        # linking maps
        self.variables: dict[str, int] = {}     # name: data_addr
        self.functions: dict[str, int] = {}     # name: instr_addr

        self.control_flow_stack = []
    
    def add_instruction(self, opcode: Opcode, operands: list[Operand]=None) -> Instruction:
        if operands is None:
            operands = []
        
        instr = Instruction(opcode, operands)
        self.instr_memory.append(instr)

        self.instr_addr += instr.size_bytes()
        
        return instr

    
    def translate(self, tokens: list[str]):
        """
        Транслятор Forth -> CISC instruction set

        - forth удобно транслировать линейно и однопроходно, поэтому я не использовал синтаксических деревьев
        - проблема control-flow инструкций решена так:
            - при встрече if запоминаем адрес инструкции
            - когда встречаем endif - вычисляем теккущий instr_addr
            - достаем из стека индекс, и меняем адрес перехода соответствующего if на текущий
        D1:     TOS:    stack[0]
        (A6):   NOS:    stack[1]
        -(A6):          stack[2]
        """

        tokens_iter = iter(tokens)

        for token in tokens_iter:

            if token == "var":
                var_name = next(tokens_iter)
                self.variables[var_name] = self.data_addr
                self.data_addr += self.WORD_SIZE
                self.data_memory.extend(b'\x00' * self.WORD_SIZE)

            elif token == ":":
                func_name = next(tokens_iter)
                self.functions[func_name] = self.instr_addr
            
            elif token == ";":
                self.add_instruction(Opcode.RET)

            elif token == "!":
                self.add_instruction(Opcode.MOVE, [Operand(AddrMode.DATA_REG_DIRECT, D0), Operand(AddrMode.ADDR_REG_DIRECT, A0)])
                self.add_instruction(Opcode.MOVE, [Operand(AddrMode.POST_INC, A6), Operand(AddrMode.ADDR_REG_INDIRECT, A0)])
                self.add_instruction(Opcode.MOVE, [Operand(AddrMode.POST_INC, A6), Operand(AddrMode.DATA_REG_DIRECT, D0)])
            
            elif token == "@":
                self.add_instruction(Opcode.MOVE, [Operand(AddrMode.DATA_REG_DIRECT, D0), Operand(AddrMode.ADDR_REG_DIRECT, A0)])
                self.add_instruction(Opcode.MOVE, [Operand(AddrMode.ADDR_REG_INDIRECT, A0), Operand(AddrMode.DATA_REG_DIRECT, D0)])

            elif token == "dup":
                self.add_instruction(Opcode.MOVE, [Operand(AddrMode.DATA_REG_DIRECT, D0), Operand(AddrMode.PRE_DEC, A6)])

            elif token == "drop":
                self.add_instruction(Opcode.MOVE, [Operand(AddrMode.POST_INC, A6), Operand(AddrMode.DATA_REG_DIRECT, D0)])

            elif token == ">r":
                # data: ( x -- ), return: ( -- x)
                self.add_instruction(Opcode.MOVE, [Operand(AddrMode.DATA_REG_DIRECT, D0), Operand(AddrMode.PRE_DEC, A7)])
                self.add_instruction(Opcode.MOVE, [Operand(AddrMode.POST_INC, A6), Operand(AddrMode.DATA_REG_DIRECT, D0)])

            elif token == "r>":
                # data: ( -- x ), return: (x -- )
                self.add_instruction(Opcode.MOVE, [Operand(AddrMode.DATA_REG_DIRECT, D0), Operand(AddrMode.PRE_DEC, A6)])
                self.add_instruction(Opcode.MOVE, [Operand(AddrMode.POST_INC, A7), Operand(AddrMode.DATA_REG_DIRECT, D0)])

            elif token == "r@":
                # data: ( -- x ), return: (x -- x)
                self.add_instruction(Opcode.MOVE, [Operand(AddrMode.DATA_REG_DIRECT, D0), Operand(AddrMode.PRE_DEC, A6)])
                self.add_instruction(Opcode.MOVE, [Operand(AddrMode.ADDR_REG_INDIRECT, A7), Operand(AddrMode.DATA_REG_DIRECT, D0)])

            elif token == "swap":
                # ( a b -- b a )
                # читаем а без сдвига указателя
                self.add_instruction(Opcode.MOVE, [Operand(AddrMode.ADDR_REG_INDIRECT, A6), Operand(AddrMode.DATA_REG_DIRECT, D1)])
                # пишем b на место а в память 
                self.add_instruction(Opcode.MOVE, [Operand(AddrMode.DATA_REG_DIRECT, D0), Operand(AddrMode.ADDR_REG_INDIRECT, A6)])
                # делаем a новым TOS 
                self.add_instruction(Opcode.MOVE, [Operand(AddrMode.DATA_REG_DIRECT, D1), Operand(AddrMode.DATA_REG_DIRECT, D0)])      

            elif token == "over":
                # ( a b -- a b a )
                self.add_instruction(Opcode.MOVE, [Operand(AddrMode.ADDR_REG_INDIRECT, A6), Operand(AddrMode.DATA_REG_DIRECT, D1)]) 
                self.add_instruction(Opcode.MOVE, [Operand(AddrMode.DATA_REG_DIRECT, D0), Operand(AddrMode.PRE_DEC, A6)])  
                self.add_instruction(Opcode.MOVE, [Operand(AddrMode.DATA_REG_DIRECT, D1), Operand(AddrMode.DATA_REG_DIRECT, D0)])    

            # коммутативная логика и арифмеика
            elif token in {'+', '*', '&', '|', '^'}:
                self.add_instruction(Opcode.MOVE, [Operand(AddrMode.POST_INC, A6), Operand(AddrMode.DATA_REG_DIRECT, D1)])

                if token == "+":
                    self.add_instruction(Opcode.ADD, [Operand(AddrMode.DATA_REG_DIRECT, D1), Operand(AddrMode.DATA_REG_DIRECT, D0)])
                elif token == "*":
                    self.add_instruction(Opcode.MUL, [Operand(AddrMode.DATA_REG_DIRECT, D1), Operand(AddrMode.DATA_REG_DIRECT, D0)])
                elif token == "&":
                    self.add_instruction(Opcode.AND_OP, [Operand(AddrMode.DATA_REG_DIRECT, D1), Operand(AddrMode.DATA_REG_DIRECT, D0)])
                elif token == "|":
                    self.add_instruction(Opcode.OR_OP, [Operand(AddrMode.DATA_REG_DIRECT, D1), Operand(AddrMode.DATA_REG_DIRECT, D0)])
                elif token == "^":
                    self.add_instruction(Opcode.XOR, [Operand(AddrMode.DATA_REG_DIRECT, D1), Operand(AddrMode.DATA_REG_DIRECT, D0)])
            
            # некоммутативная логика и арифметика
            elif token in {'-', '/', 'mod'}:
                self.add_instruction(Opcode.MOVE, [Operand(AddrMode.POST_INC, A6), Operand(AddrMode.DATA_REG_DIRECT, D1)])

                if token == "-":
                    self.add_instruction(Opcode.SUB, [Operand(AddrMode.DATA_REG_DIRECT, D0), Operand(AddrMode.DATA_REG_DIRECT, D1)])
                elif token == "/":
                    self.add_instruction(Opcode.DIV, [Operand(AddrMode.DATA_REG_DIRECT, D0), Operand(AddrMode.DATA_REG_DIRECT, D1)])
                elif token == "mod":
                    self.add_instruction(Opcode.REM, [Operand(AddrMode.DATA_REG_DIRECT, D0), Operand(AddrMode.DATA_REG_DIRECT, D1)])

                self.add_instruction(Opcode.MOVE, [Operand(AddrMode.DATA_REG_DIRECT, D1), Operand(AddrMode.DATA_REG_DIRECT, D0)])

            elif token in {"n+", "n*"}:
                # 3 n+ -> POP the N literal, then POP the N operands
                
                # pop literal n
                n_inst = self.instr_memory.pop()
                self.instr_addr -= n_inst.size_bytes()
                
                d0_push_inst = self.instr_memory.pop()
                self.instr_addr -= d0_push_inst.size_bytes()

                if n_inst.opcode != Opcode.MOVE or n_inst.operands[0].mode != AddrMode.IMMEDIATE:
                    raise Exception(f"Expected immediate value for N before {token}")

                num_args = n_inst.operands[0].value
                n_op_list = []

                for _ in range(num_args):
                    arg_val_inst = self.instr_memory.pop()
                    self.instr_addr -= arg_val_inst.size_bytes()
                    
                    arg_push_inst = self.instr_memory.pop()
                    self.instr_addr -= arg_push_inst.size_bytes()
                    
                    if arg_val_inst.opcode != Opcode.MOVE or arg_val_inst.operands[0].mode != AddrMode.IMMEDIATE:
                        raise Exception(f"Only immediate values are supported for {token} arguments in hardware mapping")
                    n_op_list.insert(0, arg_val_inst.operands[0])

                opcode = Opcode.NADD if token == "n+" else Opcode.NMUL
                
                self.add_instruction(opcode, n_op_list)

            elif token == "~":
                self.add_instruction(Opcode.NOT_OP, [Operand(AddrMode.DATA_REG_DIRECT, D0)])

            elif token == "d+":
                # ( al ah bl bh -- rl rh )
                # D0 = bh, (A6) = bl, -(A6) = ah, --(A6) = al
                self.add_instruction(Opcode.MOVE, [Operand(AddrMode.POST_INC, A6), Operand(AddrMode.DATA_REG_DIRECT, D1)]) # D1 = bl
                self.add_instruction(Opcode.MOVE, [Operand(AddrMode.POST_INC, A6), Operand(AddrMode.DATA_REG_DIRECT, D2)]) # D2 = ah
                self.add_instruction(Opcode.MOVE, [Operand(AddrMode.POST_INC, A6), Operand(AddrMode.DATA_REG_DIRECT, D3)]) # D3 = al

                # D0 = bh, D1 = bl
                # +
                # D2 = ah, D3 = al
                # ----------------
                # D0 = rh, (A6) = rl
                self.add_instruction(Opcode.ADD, [Operand(AddrMode.DATA_REG_DIRECT, D1), Operand(AddrMode.DATA_REG_DIRECT, D3)])
                self.add_instruction(Opcode.ADC, [Operand(AddrMode.DATA_REG_DIRECT, D2), Operand(AddrMode.DATA_REG_DIRECT, D0)])

                # TOS = rh
                # NOS <- D3 = rl
                self.add_instruction(Opcode.MOVE, [Operand(AddrMode.DATA_REG_DIRECT, D3), Operand(AddrMode.PRE_DEC, A6)])
            
            # comparison processing
            elif token == "begin":
                # mark loop start
                loop_addr = self.instr_addr
                self.control_flow_stack.append(('begin', loop_addr))
            
            elif token == "until":
                # ( flag -- )
                # if flag == 0, loop back to begin; else exit
                if not self.control_flow_stack or self.control_flow_stack[-1][0] != 'begin':
                    raise Exception("until without matching begin")
                
                _, loop_addr = self.control_flow_stack.pop()
                
                self.add_instruction(Opcode.BEQ, [Operand(AddrMode.IMMEDIATE, loop_addr)])
                self.add_instruction(Opcode.MOVE, [Operand(AddrMode.POST_INC, A6), Operand(AddrMode.DATA_REG_DIRECT, D0)])

            elif token in {'=', '<', '>'}:
                # ( a b -- flag )
                # D0 = b (TOS), (A6) = a (NOS)
                
                self.add_instruction(Opcode.MOVE, [Operand(AddrMode.POST_INC, A6), Operand(AddrMode.DATA_REG_DIRECT, D1)])
                self.add_instruction(Opcode.CMP, [Operand(AddrMode.DATA_REG_DIRECT, D0), Operand(AddrMode.DATA_REG_DIRECT, D1)])
                self.add_instruction(Opcode.CLR, [Operand(AddrMode.DATA_REG_DIRECT, D0)])
                
                jmp_opcode = None
                if token == '=': jmp_opcode = Opcode.BNE    # if a != b, jump (condition false)
                elif token == '>': jmp_opcode = Opcode.BLE  # if a <= b, jump (condition false)  
                elif token == '<': jmp_opcode = Opcode.BGE  # if a >= b, jump (condition false)
                
                jmp_inst = self.add_instruction(jmp_opcode, [Operand(AddrMode.IMMEDIATE, 0)])
                self.add_instruction(Opcode.ADD, [Operand(AddrMode.IMMEDIATE, 1), Operand(AddrMode.DATA_REG_DIRECT, D0)])
                
                jmp_inst.operands[0].value = self.instr_addr

            elif token == "if":
                # ( flag -- )
                # if D0 == 0, jump to else/endif
                jmp_inst = self.add_instruction(Opcode.BEQ, [Operand(AddrMode.IMMEDIATE, 0)])
                self.control_flow_stack.append(('if', jmp_inst))

            elif token == "else":
                if not self.control_flow_stack or self.control_flow_stack[-1][0] != 'if':
                    raise Exception("else without matching if")
                
                _, if_jmp = self.control_flow_stack.pop()
                
                if_jmp.operands[0].value = self.instr_addr
                
                else_jmp = self.add_instruction(Opcode.JMP, [Operand(AddrMode.IMMEDIATE, 0)])
                self.control_flow_stack.append(('else', else_jmp))

            elif token == "endif":
                if not self.control_flow_stack or self.control_flow_stack[-1][0] not in ('if', 'else'):
                    raise Exception("endif without matching if/else")
                
                _, jmp_inst = self.control_flow_stack.pop()
                
                jmp_inst.operands[0].value = self.instr_addr
                
                # drop flag after if/else
                self.add_instruction(Opcode.MOVE, [Operand(AddrMode.POST_INC, A6), Operand(AddrMode.DATA_REG_DIRECT, D0)])

            # variable processing
            elif token in self.variables:
                self.add_instruction(Opcode.MOVE, [Operand(AddrMode.DATA_REG_DIRECT, D0), Operand(AddrMode.PRE_DEC, A6)])
                addr = self.variables[token]
                self.add_instruction(Opcode.MOVE, [Operand(AddrMode.IMMEDIATE, addr), Operand(AddrMode.DATA_REG_DIRECT, D0)])
            
            elif token == "out":
                # D0 = port, (A6) = value

                self.add_instruction(Opcode.MOVE, [Operand(AddrMode.POST_INC, A6), Operand(AddrMode.DATA_REG_DIRECT, D1)]) # D1 = val
                self.add_instruction(Opcode.OUT, [Operand(AddrMode.DATA_REG_DIRECT, D1), Operand(AddrMode.DATA_REG_DIRECT, D0)])

                self.add_instruction(Opcode.MOVE, [Operand(AddrMode.POST_INC, A6), Operand(AddrMode.DATA_REG_DIRECT, D0)])

            elif token == "in":
                # D0 = port_number, D0 <- ports[port_number]
                self.add_instruction(Opcode.IN, [Operand(AddrMode.DATA_REG_DIRECT, D0), Operand(AddrMode.DATA_REG_DIRECT, D0)])
            
            # number processing
            elif token.lstrip('-').isdigit():
                self.add_instruction(Opcode.MOVE, [Operand(AddrMode.DATA_REG_DIRECT, D0), Operand(AddrMode.PRE_DEC, A6)])
                val = int(token)
                self.add_instruction(Opcode.MOVE, [Operand(AddrMode.IMMEDIATE, val), Operand(AddrMode.DATA_REG_DIRECT, D0)])
            
            # procedure processing
            elif token in self.functions:
                func_addr = self.functions[token]
                self.add_instruction(Opcode.JSR, [Operand(AddrMode.IMMEDIATE, func_addr)])
            
            elif token == "'":
                func_name = next(tokens_iter)
                func_addr = self.functions.get(func_name)
                if func_addr is None:
                    raise Exception(f"Unknown subroutine '{func_name}' for execution token")
                self.add_instruction(Opcode.MOVE, [Operand(AddrMode.DATA_REG_DIRECT, D0), Operand(AddrMode.PRE_DEC, A6)])
                self.add_instruction(Opcode.MOVE, [Operand(AddrMode.IMMEDIATE, func_addr), Operand(AddrMode.DATA_REG_DIRECT, D0)])
            
            elif token == "execute":
                self.add_instruction(Opcode.JSR, [Operand(AddrMode.DATA_REG_DIRECT, D0)])
                self.add_instruction(Opcode.MOVE, [Operand(AddrMode.POST_INC, A6), Operand(AddrMode.DATA_REG_DIRECT, D0)])

            # port-mapped i/o control
            elif token == ".":
                # print numeric from TOS to port 0
                self.add_instruction(Opcode.OUT, [Operand(AddrMode.DATA_REG_DIRECT, D0), Operand(AddrMode.IMMEDIATE, 0)])
                self.add_instruction(Opcode.MOVE, [Operand(AddrMode.POST_INC, A6), Operand(AddrMode.DATA_REG_DIRECT, D0)])
            
            elif token == "emit":
                # print char from TOS to port 2
                self.add_instruction(Opcode.OUT, [Operand(AddrMode.DATA_REG_DIRECT, D0), Operand(AddrMode.IMMEDIATE, 2)])
                self.add_instruction(Opcode.MOVE, [Operand(AddrMode.POST_INC, A6), Operand(AddrMode.DATA_REG_DIRECT, D0)])
            
            elif token == "key":
                # read char from port 3 to TOS
                self.add_instruction(Opcode.MOVE, [Operand(AddrMode.DATA_REG_DIRECT, D0), Operand(AddrMode.PRE_DEC, A6)])
                self.add_instruction(Opcode.IN, [Operand(AddrMode.IMMEDIATE, 3), Operand(AddrMode.DATA_REG_DIRECT, D0)])
            
            elif token == "type" or token == "s.":
                # print string from address in TOS to port 2
                # D0 = string address (pstr)
                self.add_instruction(Opcode.MOVE, [Operand(AddrMode.DATA_REG_DIRECT, D0), Operand(AddrMode.ADDR_REG_DIRECT, A0)])
                # D4 = length
                self.add_instruction(Opcode.MOVE, [Operand(AddrMode.POST_INC, A0), Operand(AddrMode.DATA_REG_DIRECT, D4)])
                
                # loop:
                loop_start = self.instr_addr
                self.add_instruction(Opcode.CMP, [Operand(AddrMode.IMMEDIATE, 0), Operand(AddrMode.DATA_REG_DIRECT, D4)])
                exit_jmp = self.add_instruction(Opcode.BEQ, [Operand(AddrMode.IMMEDIATE, 0)])
                
                # read char
                self.add_instruction(Opcode.MOVE, [Operand(AddrMode.POST_INC, A0), Operand(AddrMode.DATA_REG_DIRECT, D1)])
                # output char
                self.add_instruction(Opcode.OUT, [Operand(AddrMode.DATA_REG_DIRECT, D1), Operand(AddrMode.IMMEDIATE, 2)])
                
                # decrement
                self.add_instruction(Opcode.SUB, [Operand(AddrMode.IMMEDIATE, 1), Operand(AddrMode.DATA_REG_DIRECT, D4)])
                # jump back
                self.add_instruction(Opcode.JMP, [Operand(AddrMode.IMMEDIATE, loop_start)])
                
                exit_jmp.operands[0].value = self.instr_addr
                # pop address from data stack
                self.add_instruction(Opcode.MOVE, [Operand(AddrMode.POST_INC, A6), Operand(AddrMode.DATA_REG_DIRECT, D0)])
            
            elif token.startswith('."'):
                # string literal to out; format: ." Hello"

                match = re.search(r'\."\s+(.*)"', token)
                text = match.group(1) if match else ""

                # pstr: length in the first word + chars
                str_addr = self.data_addr
                self.data_memory.extend(len(text).to_bytes(self.WORD_SIZE, 'little', signed=True))
                self.data_addr += self.WORD_SIZE

                for char in text:
                    self.data_memory.extend(ord(char).to_bytes(self.WORD_SIZE, 'little', signed=True))
                    self.data_addr += self.WORD_SIZE

                # A0 = string pointer
                self.add_instruction(Opcode.MOVE, [Operand(AddrMode.IMMEDIATE, str_addr), Operand(AddrMode.ADDR_REG_DIRECT, A0)])
                # D4 = i loop counter
                self.add_instruction(Opcode.MOVE, [Operand(AddrMode.POST_INC, A0), Operand(AddrMode.DATA_REG_DIRECT, D4)])

                # loop:
                loop_start = self.instr_addr

                # check if counter == 0
                self.add_instruction(Opcode.CMP, [Operand(AddrMode.IMMEDIATE, 0), Operand(AddrMode.DATA_REG_DIRECT, D4)])
                exit_jmp = self.add_instruction(Opcode.BEQ, [Operand(AddrMode.IMMEDIATE, 0)]) # will patch later

                # read char into D1
                self.add_instruction(Opcode.MOVE, [Operand(AddrMode.POST_INC, A0), Operand(AddrMode.DATA_REG_DIRECT, D1)])
                # output char
                self.add_instruction(Opcode.OUT, [Operand(AddrMode.DATA_REG_DIRECT, D1), Operand(AddrMode.IMMEDIATE, 2)])

                # decrement counter D4
                self.add_instruction(Opcode.SUB, [Operand(AddrMode.IMMEDIATE, 1), Operand(AddrMode.DATA_REG_DIRECT, D4)])
                # jump back
                self.add_instruction(Opcode.JMP, [Operand(AddrMode.IMMEDIATE, loop_start)])

                exit_jmp.operands[0].value = self.instr_addr

            elif token.startswith('"') and token.endswith('"'):
                # string literal value: "..." -> place pstr in data memory and push its address
                text = token[1:-1]

                str_addr = self.data_addr
                self.data_memory.extend(len(text).to_bytes(self.WORD_SIZE, 'little', signed=True))
                self.data_addr += self.WORD_SIZE

                for char in text:
                    self.data_memory.extend(ord(char).to_bytes(self.WORD_SIZE, 'little', signed=True))
                    self.data_addr += self.WORD_SIZE

                self.add_instruction(Opcode.MOVE, [Operand(AddrMode.DATA_REG_DIRECT, D0), Operand(AddrMode.PRE_DEC, A6)])
                self.add_instruction(Opcode.MOVE, [Operand(AddrMode.IMMEDIATE, str_addr), Operand(AddrMode.DATA_REG_DIRECT, D0)])




prog = """
var a
var b

: my_func
    ." hello"
;

' my_func execute

"""

t = Translator()
t.translate(Parser.tokenize(prog))

print("\n".join([str(i) for i in t.instr_memory]))
print(t.data_memory)
