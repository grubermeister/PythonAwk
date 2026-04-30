from __future__ import annotations

import pytest

from pythonawk.errors import PythonAwkRuntimeError, PythonAwkSyntaxError
from pythonawk.program import Program


def test_syntax_error_has_line_column_and_excerpt() -> None:
    with pytest.raises(PythonAwkSyntaxError) as exc:
        Program("{print @}")
    err = exc.value
    assert err.line == 1
    assert err.column == 8
    assert "^" in err.source_excerpt


def test_runtime_error_includes_row_number() -> None:
    prog = Program("{print 1 / 0}")
    with pytest.raises(PythonAwkRuntimeError) as exc:
        prog.execute(fields=["x"], row_number=99)
    assert exc.value.row_number == 99
