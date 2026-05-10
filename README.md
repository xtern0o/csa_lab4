# CSA Lab 4
> variant: `forth | cisc | harv | mc | tick | binary | stream | port | pstr | prob1 | cache`

it's META inf (raw info for dev only)

# CISC

## Registers
- machine word: `32 bit = 4 bytes`
- `d0-d7` - 32 bit data registers
- `a0-a7` - 32 bit address registers

### `d0..d7`
- `d0` - **TOS** value - stack optimization
- `d1` - **NOS** value - stack oprimization
- `d2,d3` - 64bit long arithmetics
- `d4` - `I` (loop counter)

### `a0..a7`
- `a6` - **DSP** (Data Stack Pointer)
- `a7` - **RSP** (Return Stack Pointer)
- `a0` - **String pointer** (удобно для печати чтобы не загружать строку целиком)

> стек растет **вниз** (от большего адреса к меньшим)


## Instructions

`[ Opcode : 8bit ] [ Reserve : 8bit ] [ Operand 1 descroptor (src) : 8bit ] [ Operand 2 descriptor (dest) : 8bit ] `

- `Opcode` - код команды размером 1 байт
- `Reserve` - резервное окно для выравнивания по 32-битному слову
- `Operand descriptor` - дескриптор операнда размером 1 байт. Состоит из 2 частей: `[ addrMode : 4bit ] [ value : 4bit ]`
    - `addrmode` - режим адресации. Подробнее о них см. в TODO: режимы адрессации
    - `value` - значение
        - в общем случае - порядковый **номер регистра**
        - в случае **Immediate** адрессации - для первого по счету операнда константа размером 32 бита лежит в **следующем** машинном слове за командой, для второго (если оба операнда - константы) - через одно после команды: `[Instruction : 32bit] [Imm Operand 1 : 32bit] [Imm Operand 2 : 32 bit]`

# 4th

| operation | stack diagram | description |
|-----------|---------------|-------------|
| **Memory & Variables** | | |
| `var <name>` | `( -- )` | выделяет машинное слово (32 бит) в статической памяти |
| `<name>` | `( -- addr )` | кладет на стек адрес объявленной переменной | 
| `!` | `( val addr -- )` | `val -> mem[addr]` |
| `@` | `( addr -- val )` | `mem[addr] -> TOS` |
| `!+` | `( val addr -- addr+1 )` | `val -> mem[addr]; addr+1 -> TOS` | 
| `@+` | `( addr -- addr+1 val)` | `mem[addr] -> TOS; addr+1 -> NOS` |
| **Stack ops** | | |
| `dup` | `( a -- a a )` | TOS -> TOS, NOS |
| `drop` | `( a -- )` | TOS -> /dev/null |
| `swap` | `( a b -- b a )` | TOS, NOS = NOS, TOS |
| `over` | `( a b -- a b a)` | TOS, NOS = NOS, TOS, NOS | 
| **Arithmetics 32bit** | | set NZVC for every op |
| `+` | `( a b -- res )` | NOS + TOS -> TOS |
| `-` | `( a b -- res )` | NOS - TOS -> TOS |
| `*` | `( a b -- res )` | NOS * TOS -> TOS |
| `/` | `( a b -- res )` | NOS / TOS -> TOS |
| `mod` | `( a b -- res )` | NOS % TOS -> TOS |
| `=`, `>`, `<` | `( a b -- flag )` | Сравнение `a <condition> b`. Возвращает `1` (true) или `0` (ложь) |
| **Long arithmetics 64bit** | | set NZVC |
| `d+` | `( al ah bl bh -- rl rh )` | сложение 2 64-битных чисел. Каждое занимает 2 ячейки стека (младшая и старшая части)
| **Bitwise logic** | | |
| `&` | `( a b -- res )` | TOS -> NOS & TOS |
| `\|` | `( a b -- res )` | TOS -> NOS or TOS |
| `^` | `( a b -- res )` | TOS -> NOS ^ TOS | 
| `~` | `( a -- res )` | TOS -> ~TOS (not) |
| **I/O** | | |
| `.` | `( a -- )` | Вывод числа с вершины стека в терминал
| `key` | `( -- char)` | читает 1 символ из порта ввода и кладет его ASCII-код на стек
| `emit` | `( char -- )` | снимает со стека ASCII-код и выводит соответствующий символ в порт вывода
| **Control Flow** | | |
| `if` | `( flag -- )` | `flag == 0` => переход на соответствующий адрес `else` или `endif` |
| `else` | `( -- ) ` | ветка выполнения, если основное условие в `if` оказалось ложным | 
| `endif` | `( -- )` | маркер завершения `if` |
| `begin` | `( -- )` | маркер начала цикла | 
| `until` | `( flag -- )` | завершает цикл, если `flag == 1`. Иначе прыгает обратно на `begin` |
| **Subroutines** | | |
| `: <func_name>` | `( -- )` | определеление новой подпрограммы (далее функции) с именем `<func_name>` |
| `;` | `( -- )` | завершение определение подпрограммы (генерирует инструкцию возврата) |
| **Comments** | | |
| `( ... )` | `( -- )` | многострочный комментарий. Транслятор игнорирует все между скобками. Если не закрыть скобку - транслятор игнорирует все после последней скобки. Если закрыть скобку лишний раз - это вызовет ошибку |
| `\` | `( -- )` | однострочный коммент. Транслятор игнорирует все символы в строке после `\`.
