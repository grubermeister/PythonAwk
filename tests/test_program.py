from __future__ import annotations

import pytest

from pythonawk.errors import PythonAwkSyntaxError
from pythonawk.program import Program


def test_program_execute_multiple_rows() -> None:
    prog = Program('{print $2, $1}')
    assert prog.execute(fields=["a", "b"], row_number=1) == ["b", "a"]
    assert prog.execute(fields=["c", "d"], row_number=2) == ["d", "c"]


def test_program_does_not_persist_user_variables_across_rows() -> None:
    prog = Program('{n += 1; print n}')
    assert prog.execute(fields=["x"], row_number=1) == ["1"]
    assert prog.execute(fields=["y"], row_number=2) == ["1"]


def test_program_syntax_error_on_invalid_source() -> None:
    with pytest.raises(PythonAwkSyntaxError):
        Program('{print "unterminated}')
