from __future__ import annotations

import subprocess
import sys


def _run_cli(args: list[str], stdin_text: str | None = None) -> subprocess.CompletedProcess[str]:
    cmd = [sys.executable, "-m", "pythonawk.cli", *args]
    return subprocess.run(
        cmd,
        input=stdin_text,
        text=True,
        capture_output=True,
        check=False,
    )


def test_cli_stdin_processing() -> None:
    result = _run_cli(["{print $2, $1}"], "a b\nc d\n")
    assert result.returncode == 0
    assert result.stdout == "b a\nd c\n"


def test_cli_with_separator(tmp_path) -> None:
    path = tmp_path / "input.csv"
    path.write_text("a,b,c\nd,e,f\n", encoding="utf-8")
    result = _run_cli(["-F", ",", "{print $3, $1}", str(path)])
    assert result.returncode == 0
    assert result.stdout == "c a\nf d\n"


def test_cli_with_v_assignment() -> None:
    result = _run_cli(["-v", "prefix=ID", "{print prefix, $1}"], "123\n")
    assert result.returncode == 0
    assert result.stdout == "ID 123\n"


def test_cli_syntax_error_exit_code() -> None:
    result = _run_cli(["{print @}"])
    assert result.returncode == 2
    assert result.stderr.strip() != ""
