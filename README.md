# CSA Lab 4
> variant: `forth | cisc | harv | mc | tick | binary | stream | port | pstr | prob1 | cache`

## META inf (raw info for dev)

- machine word: `32 bit = 4 bytes`

## Instructions

`[ Opcode : 8bit ] [ Reserve : 8bit ] [ Operand 1 descroptor (src) : 8bit ] [ Operand 2 descriptor (dest) : 8bit ] `

- `Opcode` - код команды размером 1 байт
- `Reserve` - резервное окно для выравнивания по 32-битному слову
- `Operand descriptor` - дескриптор операнда размером 1 байт. Состоит из 2 частей: `[ addrMode : 4bit ] [ value : 4bit ]`
    - `addrmode` - режим адресации. Подробнее о них см. в TODO: режимы адрессации
    - `value` - значение
        - в общем случае - порядковый **номер регистра**
        - в случае **Immediate** адрессации - для первого по счету операнда константа размером 32 бита лежит в **следующем** машинном слове за командой, для второго (если оба операнда - константы) - через одно после команды: `[Instruction : 32bit] [Imm Operand 1 : 32bit] [Imm Operand 2 : 32 bit]`
