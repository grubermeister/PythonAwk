from __future__ import annotations

import subprocess

import pytest

from pythonawk.program import Program
from tests.cases.parity_cases import PARITY_CASES


@pytest.mark.gawk
@pytest.mark.parametrize("case", PARITY_CASES, ids=lambda c: c.id)
def test_gawk_parity(case, gawk_path: str | None) -> None:
    if gawk_path is None:
        pytest.skip("gawk not available on PATH")

    prog = Program(case.program)
    py_lines: list[str] = []
    for i, row in enumerate(case.input_rows, start=1):
        out = prog.execute(fields=list(row), row_number=i)
        if out is not None:
            py_lines.append(" ".join(out))

    input_text = "\n".join(" ".join(row) for row in case.input_rows) + "\n"
    result = subprocess.run(
        [gawk_path, case.program],
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr

    gawk_lines = result.stdout.splitlines()
    assert py_lines == gawk_lines
