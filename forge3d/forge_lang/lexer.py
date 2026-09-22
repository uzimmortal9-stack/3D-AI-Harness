"""ForgeScript lexer."""

T_IDENT, T_NUMBER, T_STRING, T_COLOR, T_LBRACE, T_RBRACE, T_SEMI, T_EOF = \
    "IDENT", "NUMBER", "STRING", "COLOR", "LBRACE", "RBRACE", "SEMI", "EOF"


class Token:
    __slots__ = ("kind", "value", "line")

    def __init__(self, kind, value, line):
        self.kind = kind
        self.value = value
        self.line = line

    def __repr__(self):
        return f"Token({self.kind},{self.value!r},L{self.line})"


class ForgeSyntaxError(Exception):
    def __init__(self, msg, line=0, path=""):
        super().__init__(f"{path}:{line}: {msg}" if path else f"line {line}: {msg}")
        self.line = line


def tokenize(text, path=""):
    tokens = []
    i, n, line = 0, len(text), 1
    last = None
    while i < n:
        c = text[i]
        if c == "\n":
            line += 1
            i += 1
            # newline acts as statement terminator (synthetic ';')
            if last not in (T_SEMI, T_LBRACE, T_EOF, None):
                tokens.append(Token(T_SEMI, "\\n", line - 1))
                last = T_SEMI
            continue
        if c in " \t\r":
            i += 1
            continue
        if text.startswith("//", i):
            while i < n and text[i] != "\n":
                i += 1
            continue
        if c == "#":
            # hex color like #ff2233 vs. '#'-style comment
            j = i + 1
            hexc = "0123456789abcdefABCDEF"
            while j < n and text[j] in hexc:
                j += 1
            if j - (i + 1) in (3, 6):
                tokens.append(Token(T_COLOR, text[i + 1:j], line))
                i = j
                last = T_COLOR
                continue
            while i < n and text[i] != "\n":  # treat as comment
                i += 1
            continue
        if c == "{":
            tokens.append(Token(T_LBRACE, "{", line)); i += 1; last = T_LBRACE; continue
        if c == "}":
            tokens.append(Token(T_RBRACE, "}", line)); i += 1; last = T_RBRACE; continue
        if c == ";" or c == ",":
            tokens.append(Token(T_SEMI, c, line)); i += 1; last = T_SEMI; continue
        if c == '"':
            j = i + 1
            buf = []
            while j < n and text[j] != '"':
                if text[j] == "\\" and j + 1 < n:
                    j += 1
                buf.append(text[j])
                j += 1
            if j >= n:
                raise ForgeSyntaxError("unterminated string", line, path)
            tokens.append(Token(T_STRING, "".join(buf), line))
            i = j + 1
            last = T_STRING
            continue
        if c == "-" or c.isdigit():
            j = i + 1
            while j < n and (text[j].isdigit() or text[j] in ".eE+-"):
                if text[j] in "+-" and text[j - 1] not in "eE":
                    break
                j += 1
            tokens.append(Token(T_NUMBER, float(text[i:j]), line))
            i = j
            last = T_NUMBER
            continue
        if c.isalpha() or c == "_":
            j = i
            while j < n and (text[j].isalnum() or text[j] in "_."):
                j += 1
            tokens.append(Token(T_IDENT, text[i:j], line))
            i = j
            last = T_IDENT
            continue
        raise ForgeSyntaxError(f"unexpected character {c!r}", line, path)
    tokens.append(Token(T_EOF, None, line))
    return tokens
