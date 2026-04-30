from __future__ import annotations

import re
from dataclasses import dataclass

from .errors import PythonAwkSyntaxError, make_source_excerpt


@dataclass(frozen=True, slots=True)
class Token:
    kind: str
    value: str
    line: int
    column: int


KEYWORDS = {"if", "else", "for", "print"}
BUILTINS = {"NF", "NR"}

MULTI_CHAR_TOKENS = {
    "++": "INCR",
    "--": "DECR",
    "+=": "PLUS_ASSIGN",
    "-=": "MINUS_ASSIGN",
    "*=": "MUL_ASSIGN",
    "/=": "DIV_ASSIGN",
    "%=": "MOD_ASSIGN",
    "==": "EQ",
    "!=": "NE",
    "<=": "LE",
    ">=": "GE",
    "&&": "AND",
    "||": "OR",
    "!~": "NMATCH",
}

SINGLE_CHAR_TOKENS = {
    "$": "DOLLAR",
    "+": "PLUS",
    "-": "MINUS",
    "*": "STAR",
    "/": "SLASH",
    "%": "PERCENT",
    "=": "ASSIGN",
    "<": "LT",
    ">": "GT",
    "~": "MATCH",
    "!": "NOT",
    "(": "LPAREN",
    ")": "RPAREN",
    "{": "LBRACE",
    "}": "RBRACE",
    ",": "COMMA",
    ";": "SEMI",
}

NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")
IDENT_RE = re.compile(r"[A-Za-z][A-Za-z0-9_]*")
WS_RE = re.compile(r"[ \t\r\n]+")

REGEX_ALLOWED_PREV = {
    None,
    "LBRACE",
    "LPAREN",
    "COMMA",
    "SEMI",
    "ASSIGN",
    "PLUS_ASSIGN",
    "MINUS_ASSIGN",
    "MUL_ASSIGN",
    "DIV_ASSIGN",
    "MOD_ASSIGN",
    "EQ",
    "NE",
    "LT",
    "GT",
    "LE",
    "GE",
    "MATCH",
    "NMATCH",
    "AND",
    "OR",
    "NOT",
    "PLUS",
    "MINUS",
    "STAR",
    "SLASH",
    "PERCENT",
}


class Lexer:
    def __init__(self, source: str) -> None:
        self.source = source
        self.length = len(source)
        self.index = 0
        self.line = 1
        self.column = 1
        self.prev_token_kind: str | None = None

    def tokenize(self) -> list[Token]:
        tokens: list[Token] = []
        while self.index < self.length:
            self._skip_whitespace()
            if self.index >= self.length:
                break

            line, column = self.line, self.column

            multi = self.source[self.index : self.index + 2]
            if multi in MULTI_CHAR_TOKENS:
                kind = MULTI_CHAR_TOKENS[multi]
                self._advance_count(2)
                token = Token(kind=kind, value=multi, line=line, column=column)
                tokens.append(token)
                self.prev_token_kind = token.kind
                continue

            char = self.source[self.index]

            if char == '"':
                tokens.append(self._read_string())
                self.prev_token_kind = tokens[-1].kind
                continue

            if char == "/" and self.prev_token_kind in REGEX_ALLOWED_PREV:
                tokens.append(self._read_regex())
                self.prev_token_kind = tokens[-1].kind
                continue

            number_match = NUMBER_RE.match(self.source, self.index)
            if number_match is not None:
                text = number_match.group(0)
                self._advance_count(len(text))
                token = Token(kind="NUMBER", value=text, line=line, column=column)
                tokens.append(token)
                self.prev_token_kind = token.kind
                continue

            ident_match = IDENT_RE.match(self.source, self.index)
            if ident_match is not None:
                text = ident_match.group(0)
                self._advance_count(len(text))
                if text in KEYWORDS:
                    kind = text.upper()
                elif text in BUILTINS:
                    kind = "BUILTIN"
                else:
                    kind = "IDENT"
                token = Token(kind=kind, value=text, line=line, column=column)
                tokens.append(token)
                self.prev_token_kind = token.kind
                continue

            if char in SINGLE_CHAR_TOKENS:
                kind = SINGLE_CHAR_TOKENS[char]
                self._advance_count(1)
                token = Token(kind=kind, value=char, line=line, column=column)
                tokens.append(token)
                self.prev_token_kind = token.kind
                continue

            self._syntax_error(f"Unexpected character: {char}", line, column)

        tokens.append(Token(kind="EOF", value="", line=self.line, column=self.column))
        return tokens

    def _skip_whitespace(self) -> None:
        match = WS_RE.match(self.source, self.index)
        if match is None:
            return
        self._advance_count(len(match.group(0)))

    def _read_string(self) -> Token:
        line, column = self.line, self.column
        self._advance_count(1)
        chars: list[str] = []
        while self.index < self.length:
            char = self.source[self.index]
            if char == '"':
                self._advance_count(1)
                return Token(kind="STRING", value="".join(chars), line=line, column=column)
            if char == "\\":
                self._advance_count(1)
                if self.index >= self.length:
                    self._syntax_error("Unterminated string literal", line, column)
                esc = self.source[self.index]
                if esc == "n":
                    chars.append("\n")
                elif esc == "t":
                    chars.append("\t")
                elif esc == "r":
                    chars.append("\r")
                elif esc in {'"', "\\"}:
                    chars.append(esc)
                else:
                    chars.append(esc)
                self._advance_count(1)
                continue
            chars.append(char)
            self._advance_count(1)
        self._syntax_error("Unterminated string literal", line, column)
        raise AssertionError("unreachable")

    def _read_regex(self) -> Token:
        line, column = self.line, self.column
        self._advance_count(1)
        chars: list[str] = []
        while self.index < self.length:
            char = self.source[self.index]
            if char == "/":
                self._advance_count(1)
                return Token(kind="REGEX", value="".join(chars), line=line, column=column)
            if char == "\\":
                chars.append(char)
                self._advance_count(1)
                if self.index >= self.length:
                    self._syntax_error("Unterminated regex literal", line, column)
                chars.append(self.source[self.index])
                self._advance_count(1)
                continue
            if char == "\n":
                self._syntax_error("Unterminated regex literal", line, column)
            chars.append(char)
            self._advance_count(1)
        self._syntax_error("Unterminated regex literal", line, column)
        raise AssertionError("unreachable")

    def _advance_count(self, count: int) -> None:
        for _ in range(count):
            if self.index >= self.length:
                return
            char = self.source[self.index]
            self.index += 1
            if char == "\n":
                self.line += 1
                self.column = 1
            else:
                self.column += 1

    def _syntax_error(self, message: str, line: int, column: int) -> None:
        raise PythonAwkSyntaxError(
            message=message,
            line=line,
            column=column,
            source_excerpt=make_source_excerpt(self.source, line, column),
        )


def tokenize(source: str) -> list[Token]:
    return Lexer(source).tokenize()
