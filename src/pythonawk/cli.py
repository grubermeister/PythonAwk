from __future__ import annotations

import argparse
import re
import sys

from .errors import PythonAwkError
from .program import Program

VAR_NAME_RE = re.compile(r"^[a-z][A-Za-z0-9_]*$")


def _escape_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _build_program_source(raw_source: str, assignments: list[str]) -> str:
    if not assignments:
        return raw_source

    parts: list[str] = []
    for item in assignments:
        if "=" not in item:
            raise ValueError(f"Invalid -v value '{item}'. Expected var=value")
        name, value = item.split("=", 1)
        if not VAR_NAME_RE.fullmatch(name):
            raise ValueError(f"Invalid variable name '{name}' for -v")
        parts.append(f'{name}="{_escape_string(value)}"')

    init_rule = "{" + "; ".join(parts) + ";}"
    return init_rule + " " + raw_source


def _split_fields(line: str, separator: str | None) -> list[str]:
    if separator is None:
        stripped = line.strip()
        if stripped == "":
            return []
        return re.findall(r"\S+", stripped)
    return line.split(separator)


def _iter_lines(files: list[str]):
    if not files:
        for line in sys.stdin:
            yield line
        return

    for path in files:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                yield line


def main() -> int:
    parser = argparse.ArgumentParser(prog="pythonawk")
    parser.add_argument("-F", dest="separator", default=None, help="input field separator")
    parser.add_argument("-v", dest="variables", action="append", default=[], help="var=value")
    parser.add_argument("program", help="AWK subset program source")
    parser.add_argument("files", nargs="*", help="input files (default: stdin)")
    args = parser.parse_args()

    try:
        source = _build_program_source(args.program, args.variables)
        program = Program(source)
    except (ValueError, PythonAwkError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    row_number = 0
    try:
        for line in _iter_lines(args.files):
            row_number += 1
            text = line.rstrip("\r\n")
            fields = _split_fields(text, args.separator)
            result = program.execute(fields=fields, header=None, row_number=row_number)
            if result is not None:
                sys.stdout.write(" ".join(result) + "\n")
    except PythonAwkError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
