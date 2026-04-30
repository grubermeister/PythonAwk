from __future__ import annotations

from .interpreter import Interpreter
from .lexer import tokenize
from .parser import parse


class Program:
    def __init__(self, source: str) -> None:
        self._source = source
        tokens = tokenize(source)
        self._ast = parse(tokens=tokens, source=source)

    def execute(
        self,
        fields: list[str],
        header: dict[str, int] | None = None,
        row_number: int = 1,
    ) -> list[str] | None:
        interpreter = Interpreter(self._ast)
        return interpreter.execute(fields=fields, header=header, row_number=row_number)
