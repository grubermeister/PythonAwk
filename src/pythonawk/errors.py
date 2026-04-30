from __future__ import annotations

from dataclasses import dataclass


class PythonAwkError(Exception):
    """Base class for all PythonAwk errors."""


@dataclass(slots=True)
class PythonAwkSyntaxError(PythonAwkError):
    """Raised when source does not conform to the supported grammar."""

    message: str
    line: int
    column: int
    source_excerpt: str = ""

    def __str__(self) -> str:
        loc = f"line {self.line}, column {self.column}"
        if self.source_excerpt:
            return f"{self.message} at {loc}\n{self.source_excerpt}"
        return f"{self.message} at {loc}"


@dataclass(slots=True)
class PythonAwkRuntimeError(PythonAwkError):
    """Raised for runtime failures while executing a row."""

    message: str
    row_number: int | None = None

    def __str__(self) -> str:
        if self.row_number is None:
            return self.message
        return f"{self.message} (row {self.row_number})"


def make_source_excerpt(source: str, line: int, column: int) -> str:
    """Create a one-line excerpt with a caret under the failing column."""

    lines = source.splitlines()
    if line < 1 or line > len(lines):
        return ""
    text = lines[line - 1]
    pointer_col = max(column, 1)
    return f"{text}\n{' ' * (pointer_col - 1)}^"
