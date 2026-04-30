# PythonAwk

A Python implementation of a constrained AWK subset, focused on row-level
transforms for tabular data. Use it as an importable library in Python
programs, or as a small CLI against delimited files and stdin.

The full language reference lives in [docs/spec.md](docs/spec.md). The
implementation plan that this repo was built from lives in
[docs/plan.md](docs/plan.md).

## What it is (and isn't)

PythonAwk implements the structural-transform parts of AWK: column
selection and reordering, regex-driven row filtering, conditional field
mutation, iteration over variable-width rows, and derived columns via
field assignment. Programs that fall inside the supported subset produce
identical output to `gawk 5.x`.

Things explicitly **not** supported in v1: `BEGIN` / `END` blocks,
associative arrays, user-defined functions, `printf`, `getline`, output
redirection, and most string functions (`substr`, `gsub`, `split`,
`tolower`, etc.). `length()` is the only built-in function. See spec
section 1 for the full out-of-scope list and the rationale.

If your program needs anything in that list, reach for real `gawk` or a
plain Python script. If it fits the subset, PythonAwk gives you AWK
syntax with no subprocess, no extra runtime dependency, and a clean
parse-once / execute-per-row API.

## Install

```bash
pip install -e ".[dev]"
```

This is editable-install + dev extras (`pytest`, `pytest-cov`, `ruff`).
For a production install once the project is published:

```bash
pip install pythonawk
```

Requires Python 3.10 or newer. Pure standard library at runtime --
no third-party dependencies.

## Quick start

### As a library

```python
from pythonawk import Program

# Parse once at startup
prog = Program('$3 != "" {print $1, $3}')

# Execute against pre-split rows
result = prog.execute(fields=["AU", "1234", "Widget", "ACTIVE"])
# result == ["AU", "Widget"]

# Filtered rows return None
result = prog.execute(fields=["AU", "1234", "", "ACTIVE"])
# result is None
```

Named-field references work when you pass a `header` mapping:

```python
prog = Program('$Status == "ACTIVE" {print $NSN, $Description}')
prog.execute(
    fields=["AU", "1234", "Widget", "ACTIVE"],
    header={"Country": 0, "NSN": 1, "Description": 2, "Status": 3},
    row_number=42,
)
# -> ["1234", "Widget"]
```

### As a CLI

```bash
# Reorder columns
printf 'a b c\nd e f\n' | pythonawk '{print $2, $1}'
# b a
# e d

# Filter by regex on field 2, against a file
pythonawk '$2 ~ /^[0-9]+/ {print $1, $2}' data.tsv

# Tab-separated input
pythonawk -F $'\t' '{print $3, $1}' data.tsv

# Inject an initial variable
pythonawk -v prefix=ID- '{print prefix $1}' data.tsv
```

## Directory layout

```
PythonAwk/
+-- docs/
|   +-- spec.md             Language spec (authoritative)
|   +-- plan.md             Implementation plan this repo was built from
+-- src/
|   +-- pythonawk/
|       +-- __init__.py     Public API: Program, error classes, __version__
|       +-- program.py      Program facade -- parse-once, execute-per-row
|       +-- lexer.py        Hand-rolled tokenizer with line/col positions
|       +-- parser.py       Recursive-descent parser, tokens -> AST
|       +-- ast_nodes.py    Frozen-dataclass AST node definitions
|       +-- interpreter.py  Tree-walk evaluator, AST + row -> output | None
|       +-- cli.py          argparse-driven command-line entry point
|       +-- errors.py       PythonAwkError and subclasses
|       +-- py.typed        PEP 561 marker -- exposes type hints to consumers
+-- tests/
|   +-- cases/
|   |   +-- parity_cases.py   Shared (program, rows, expected) test corpus
|   +-- conftest.py           Shared fixtures (gawk-path detection)
|   +-- test_lexer.py
|   +-- test_parser.py
|   +-- test_interpreter.py
|   +-- test_program.py       Public API contract
|   +-- test_errors.py        Error class shape and position reporting
|   +-- test_cli.py           Subprocess-driven CLI tests
|   +-- test_gawk_parity.py   Runs the parity corpus through real gawk too
+-- pyproject.toml          PEP 621, hatchling backend
+-- README.md               This file
+-- LICENSE                 LGPLv3 License Terms
```

## Library API

```python
from pythonawk import Program, PythonAwkError, PythonAwkSyntaxError, PythonAwkRuntimeError
```

### `Program(source: str)`

Parses an AWK subset program. Raises `PythonAwkSyntaxError` (with
`line`, `column`, and `source_excerpt` attributes) if the source does
not conform to the grammar. Compiled programs are immutable and safe
to reuse across any number of `execute()` calls and threads --
execution creates no shared mutable state.

### `Program.execute(fields, header=None, row_number=1) -> list[str] | None`

Run the program against one input row.

- `fields` -- `list[str]`. The row, already split into fields by the caller.
- `header` -- `dict[str, int] | None`. Maps named-field references
  (`$FieldName`) to 0-based column indices. Required only if the
  program actually uses named fields; using one without supplying
  `header` raises `PythonAwkRuntimeError`.
- `row_number` -- `int`. Sets `NR` for this call. Defaults to 1.

Returns the output row as `list[str]` if a `print` ran, or `None` if
the row was filtered out (no matching rule, or no `print` inside the
matched block). If multiple `print` statements run, the last one wins.

Raises `PythonAwkRuntimeError` on division by zero, missing header for
a named field, or other runtime failures. The error carries the
`row_number` of the failing row.

## Built-in variables and functions

Built-in variables (read-only unless noted):

| Variable    | Meaning                                                          |
|-------------|------------------------------------------------------------------|
| `NF`        | Number of fields in the current row                              |
| `NR`        | Current row number (1-based; matches the `row_number` argument)  |
| `$0`        | The whole row. Reading joins fields with a space.                |
| `$1`..`$N`  | Positional field reference (1-based)                             |
| `$FieldName`| Named-field reference -- resolved via `header`. Extension to AWK.|
| `$variable` | Dynamic field reference, e.g. `$i` inside a `for` loop           |
| `$(expr)`   | Computed field reference, e.g. `$(NF)` for the last field        |

Out-of-range field reads return `""`; out-of-range writes extend the
row, padding with `""`. Writing to `$0` re-splits the row on whitespace.

Built-in functions:

| Function    | Returns                                                          |
|-------------|------------------------------------------------------------------|
| `length()`  | Length of `$0`                                                   |
| `length(x)` | Length of the string form of `x`                                 |

`length()` is the only built-in function in v1. It is enough for
length-based filtering and loop bounds, which is what the structural
transforms need it for. Other string functions (`substr`, `tolower`,
`gsub`, ...) are listed as future extensions in spec section 11.

User variables are just lowercase identifiers (`i`, `prefix`, `n`).
There is no declaration syntax -- first assignment creates them.

## Command-line interface

```
pythonawk [-F sep] [-v var=value] 'program' [file ...]
```

- `-F sep` -- input field separator. Default is whitespace (any run of
  whitespace, leading/trailing stripped, like AWK's default). Pass any
  literal string -- a comma, a tab (use `$'\t'` in bash), a pipe, etc.
- `-v var=value` -- inject an initial value for a user variable. The
  variable name must start with a lowercase letter and contain only
  letters, digits, and underscores. Repeat the flag for multiple
  variables. Values are always set as strings; let the program coerce
  if it wants a number.
- `program` -- the AWK source as a single positional argument.
- `file ...` -- zero or more input files. With no files, reads stdin.
  `NR` is the cumulative row count across all inputs, matching gawk.

Output: rows that produced a `print` are written to stdout, fields
joined by a single space, terminated by `\n`. The `OFS` / `ORS`
variables are not configurable in v1 (see spec section 11).

Exit codes: `0` on success, `2` on parse or runtime error (the error
message is written to stderr).

The CLI is intentionally thin -- the library API is the primary
interface. The CLI exists for testing, ad-hoc use, and scripting.

## Errors

Three exception classes, all importable from `pythonawk`:

- `PythonAwkError` -- base class.
- `PythonAwkSyntaxError` -- raised by `Program(source)` when the
  source does not conform to the grammar. Carries `message`, `line`,
  `column`, and a `source_excerpt` (the offending line plus a caret
  pointer) for human-readable error reporting.
- `PythonAwkRuntimeError` -- raised by `Program.execute(...)` for
  division by zero, named-field reference without `header`, etc.
  Carries the `row_number` of the failing row.

## Development

From the repo root, with a virtualenv active:

```bash
pip install -e ".[dev]"

pytest                                # full suite, including gawk parity
pytest -m "not gawk"                  # skip parity tests if gawk is missing
pytest tests/test_gawk_parity.py -v   # parity tests only

ruff check .                          # lint
ruff format .                         # format
```

The gawk-parity tests in [tests/test_gawk_parity.py](tests/test_gawk_parity.py)
shell out to real `gawk` and assert byte-for-byte matching output for
every entry in `tests/cases/parity_cases.py`. They auto-skip when
`gawk` is not on `PATH`, so the rest of the suite stays runnable on
machines without it. Adding a new test case to `parity_cases.py`
exercises both the local interpreter and gawk in one shot -- prefer
that over writing standalone unit tests for new language behaviour.

To build a wheel:

```bash
pip install build
python -m build
# -> dist/pythonawk-0.1.0-py3-none-any.whl
```

To pin a version, bump `__version__` in `src/pythonawk/__init__.py`.
Hatchling reads it from there; no other file needs to change.

## License

PythonAwk is licensed under the **GNU Lesser General Public License
version 3 or later** (LGPLv3+). The full text lives in
[LICENSE](LICENSE). LGPLv3 incorporates the terms of GPLv3 by
reference, so the GPLv3 text is shipped alongside in
[LICENSE.GPL](LICENSE.GPL).

The implementation is clean-room: no upstream AWK source was consulted;
only the spec in [docs/spec.md](docs/spec.md) guided the build.
