import re

from isa import *


class Parser:
    RESERVED_WORDS = {
        "var", "!", "@", "dup", "swap", "over", "drop",     # stack/memory
        "@+", "!+",                                         # stack/memory cisc features
        "&", "|", "^", "~",                                 # logical gates
        "+", "-", "*", "/", "mod", "=", ">", "<", "d+",     # arithmetic
        ".", "key", "emit", '."',                           # io console
        "if", "else", "endif", "begin", "until",            # control flow
        ":", ";",                                           # begin/end subroutine
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
        # паттерн для поиска '."..."': \."\s+.*?"
        tokens = re.findall(r'\."\s+.*?"|\S+', src_code)
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
        """

        tokens_iter = iter(tokens)

        for token in tokens_iter:

            if token == "var":
                var_name = next(tokens_iter)
                self.variables[var_name] = self.data_addr
                self.data_addr += self.WORD_SIZE
            
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

            elif token == "~":
                self.add_instruction(Opcode.NOT_OP, [Operand(AddrMode.DATA_REG_DIRECT, D0)])

                
            elif token in self.variables:
                self.add_instruction(Opcode.MOVE, [Operand(AddrMode.DATA_REG_DIRECT, D0), Operand(AddrMode.PRE_DEC, A6)])
                addr = self.variables[token]
                self.add_instruction(Opcode.MOVE, [Operand(AddrMode.IMMEDIATE, addr), Operand(AddrMode.DATA_REG_DIRECT, D0)])




