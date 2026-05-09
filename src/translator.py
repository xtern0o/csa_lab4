class Parser:
    RESERVED_WORDS = {
        "var", "!", "@", "dup", "swap", "over", "drop",     # stack/memory
        "@+", "!+",                                         # stack/memory cisc features
        "&", "|", "^", "~",                                 # logical gates
        "+", "-", "*", "/", "mod", "=", ">", "<", "d+",     # arithmetic
        ".", "key", "emit", '."'                            # io console
        "if", "else", "endif", "begin", "until",            # control flow
        ":", ";",                                           # begin/end subroutine
        "(", ")", "\\",                                     # comments
    }