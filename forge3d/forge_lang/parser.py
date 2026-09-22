"""ForgeScript parser — programs are lists of typed blocks with properties."""
from .lexer import (tokenize, Token, ForgeSyntaxError,
                    T_IDENT, T_NUMBER, T_STRING, T_COLOR, T_LBRACE, T_RBRACE,
                    T_SEMI, T_EOF)


class Prop:
    __slots__ = ("name", "args", "line")

    def __init__(self, name, args, line):
        self.name = name
        self.args = args
        self.line = line

    def __repr__(self):
        return f"Prop({self.name},{self.args},L{self.line})"


class Block:
    __slots__ = ("kind", "name", "items", "line")

    def __init__(self, kind, name, items, line):
        self.kind = kind
        self.name = name
        self.items = items
        self.line = line

    def props(self, name=None):
        for it in self.items:
            if isinstance(it, Prop) and (name is None or it.name == name):
                yield it

    def blocks(self, kind=None):
        for it in self.items:
            if isinstance(it, Block) and (kind is None or it.kind == kind):
                yield it


class Program:
    def __init__(self, blocks, path=""):
        self.blocks = blocks
        self.path = path


def _parse_value(tok):
    return tok.value


def parse(text, path=""):
    tokens = tokenize(text, path)
    p = _Parser(tokens, path)
    return p.parse_program()


class _Parser:
    def __init__(self, tokens, path):
        self.toks = tokens
        self.i = 0
        self.path = path

    def peek(self):
        return self.toks[self.i]

    def next(self):
        t = self.toks[self.i]
        self.i += 1
        return t

    def expect(self, kind):
        t = self.next()
        if t.kind != kind:
            raise ForgeSyntaxError(f"expected {kind} but found {t.kind} ({t.value!r})",
                                   t.line, self.path)
        return t

    def parse_program(self):
        blocks = []
        while self.peek().kind != T_EOF:
            blocks.append(self.parse_top())
        return Program(blocks, self.path)

    def parse_top(self):
        t = self.peek()
        if t.kind == T_IDENT:
            kind = self.next().value
            name = None
            if self.peek().kind == T_IDENT:
                name = self.next().value
            elif self.peek().kind == T_STRING:
                name = self.next().value
            if kind in ("include", "script"):
                if name is None:
                    raise ForgeSyntaxError(f"'{kind}' needs a path string", t.line,
                                           self.path)
                self.expect(T_SEMI) if self.peek().kind == T_SEMI else None
                return Prop(kind, [name], t.line)
            if self.peek().kind != T_LBRACE:
                raise ForgeSyntaxError(
                    f"expected '{{' after '{kind}'" + (f" {name}" if name else ""),
                    self.peek().line, self.path)
            self.next()
            items = self.parse_body()
            return Block(kind, name, items, t.line)
        if t.kind == T_SEMI:
            self.next()
            return None
        raise ForgeSyntaxError(f"unexpected token {t.kind} ({t.value!r})", t.line,
                               self.path)

    def parse_body(self):
        items = []
        while True:
            t = self.peek()
            if t.kind == T_RBRACE:
                self.next()
                return items
            if t.kind == T_SEMI:
                self.next()
                continue
            if t.kind == T_EOF:
                raise ForgeSyntaxError("unexpected end of file (missing '}')",
                                       t.line, self.path)
            if t.kind == T_IDENT:
                name = self.next().value
                args = []
                while self.peek().kind in (T_NUMBER, T_STRING, T_IDENT, T_COLOR):
                    args.append(self.next().value)
                nxt = self.peek()
                if nxt.kind == T_LBRACE:  # nested block: name is a block kind
                    self.next()
                    sub = self.parse_body()
                    items.append(Block(name, args[0] if args else None, sub, t.line))
                else:
                    items.append(Prop(name, args, t.line))
                continue
            raise ForgeSyntaxError(f"unexpected token {t.kind} ({t.value!r}) "
                                   "inside block", t.line, self.path)
