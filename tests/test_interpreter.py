from __future__ import annotations

import pytest  # type: ignore[import-not-found]  # pyright: ignore[reportMissingImports,reportMissingModuleSource]

from pythonawk.errors import PythonAwkRuntimeError
from pythonawk.program import Program
from tests.cases.parity_cases import PARITY_CASES


@pytest.mark.parametrize("case", PARITY_CASES, ids=lambda c: c.id)
def test_parity_cases(case) -> None:
    prog = Program(case.program)
    outputs = []
    for i, row in enumerate(case.input_rows, start=1):
        outputs.append(prog.execute(fields=list(row), row_number=i))

    normalized: list[tuple[str, ...] | None] = []
    for item in outputs:
        if item is None:
            normalized.append(None)
        else:
            normalized.append(tuple(item))

    assert tuple(normalized) == case.expected


def test_out_of_range_read_returns_empty_string() -> None:
    prog = Program("{print $5}")
    assert prog.execute(fields=["A", "B"], row_number=1) == [""]


def test_out_of_range_write_extends_row() -> None:
    prog = Program('{$4 = "X"; print $1, $2, $3, $4}')
    assert prog.execute(fields=["A"], row_number=1) == ["A", "", "", "X"]


def test_named_field_requires_header() -> None:
    prog = Program('{print $Status}')
    with pytest.raises(PythonAwkRuntimeError):
        prog.execute(fields=["ACTIVE"], header=None, row_number=7)


def test_named_field_with_header_works() -> None:
    prog = Program('{print $Status, $Code}')
    out = prog.execute(
        fields=["ACTIVE", "123"],
        header={"Status": 0, "Code": 1},
        row_number=1,
    )
    assert out == ["ACTIVE", "123"]


def test_division_by_zero_raises_runtime_error() -> None:
    prog = Program("{print 1 / 0}")
    with pytest.raises(PythonAwkRuntimeError):
        prog.execute(fields=["x"], row_number=4)


def test_length_without_arg_uses_row() -> None:
    prog = Program("{print length()}")
    assert prog.execute(fields=["AA", "BBB"], row_number=1) == ["6"]


def test_substr_two_arg_suffix() -> None:
    prog = Program('{print substr($1, 5)}')
    assert prog.execute(fields=["washington"], row_number=1) == ["ington"]


def test_substr_three_arg() -> None:
    prog = Program('{print substr($1, 5, 3)}')
    assert prog.execute(fields=["washington"], row_number=1) == ["ing"]


def test_substr_past_end_returns_empty() -> None:
    prog = Program('{print substr($1, 99, 3)}')
    assert prog.execute(fields=["abc"], row_number=1) == [""]


def test_mktime_utc_epoch() -> None:
    prog = Program('{print mktime("1970 1 1 0 0 0")}')
    assert prog.execute(fields=["x"], row_number=1) == ["0"]


def test_mktime_invalid_returns_minus_one() -> None:
    prog = Program('{print mktime("not a date")}')
    assert prog.execute(fields=["x"], row_number=1) == ["-1"]


def test_strftime_utc_iso() -> None:
    prog = Program('{print strftime("%Y-%m-%d", 0)}')
    assert prog.execute(fields=["x"], row_number=1) == ["1970-01-01"]


def test_julian_to_iso_full_pipeline() -> None:
    src = (
        "{"
        " y = substr($1, 1, 4);"
        " d = substr($1, 5, 3);"
        ' t = mktime(y " 1 1 0 0 0") + (d - 1) * 86400;'
        ' print strftime("%Y-%m-%d", t)'
        "}"
    )
    prog = Program(src)
    assert prog.execute(fields=["2026131"], row_number=1) == ["2026-05-11"]
    assert prog.execute(fields=["2024060"], row_number=2) == ["2024-02-29"]
