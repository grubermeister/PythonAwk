# PythonAwk -- v1 Implementation Plan

## Context

The repo `PythonAwk` currently contains only [docs/spec.md](spec.md) and a Python-tuned `.gitignore`. The spec defines a small, self-contained library that parses and executes a constrained subset of AWK against pre-split tabular rows, plus a thin CLI for standalone use. The goal of this plan is to take it from specification to an installable Python package -- something we can `pip install pythonawk` (or `pip install -e .` from a checkout) and import in downstream projects.

The spec is the single source of truth. This plan turns it into:

1. A modern, PEP 621 / `pyproject.toml`-driven package using the `src/` layout.
2. A clean module decomposition matching the spec's stated architecture (lexer + parser + AST + tree-walk interpreter).
3. A test suite that includes a gawk-parity harness, which is achievable because both Python 3.14 and `gawk 5.4.0` are present on this machine.
4. A small CLI that exists primarily for testing and standalone use, mirroring the spec's section 8.

No behaviour is invented beyond the spec. Everything outside the spec's grammar is a `PythonAwkSyntaxError`.

---

## 1. Project layout

```
PythonAwk/
+-- .gitignore                    (exists)
+-- docs/
|   +-- spec.md                   (exists -- authoritative)
|   +-- plan.md                   (this file)
+-- pyproject.toml                NEW -- PEP 621, hatchling backend
+-- README.md                     NEW -- short, points at docs/spec.md
+-- LICENSE                       NEW -- placeholder; spec section 10 says license is TBD
+-- src/
|   +-- pythonawk/
|       +-- __init__.py           NEW -- public API: Program, error classes, __version__
|       +-- errors.py             NEW -- PythonAwkError, PythonAwkSyntaxError, PythonAwkRuntimeError
|       +-- lexer.py              NEW -- token types + tokenizer with line/col positions
|       +-- ast_nodes.py          NEW -- @dataclass(frozen=True) node definitions
|       +-- parser.py             NEW -- recursive-descent parser, source -> AST
|       +-- interpreter.py        NEW -- tree-walk evaluator, AST + row -> output row | None
|       +-- program.py            NEW -- Program facade (parse-once, execute-per-row)
|       +-- cli.py                NEW -- argparse-driven CLI; entry point
+-- tests/
|   +-- conftest.py               NEW -- shared fixtures, gawk-availability marker
|   +-- cases/
|   |   +-- __init__.py
|   |   +-- parity_cases.py       NEW -- (program, fields, expected) table reused across tests
|   +-- test_lexer.py             NEW
|   +-- test_parser.py            NEW
|   +-- test_interpreter.py       NEW
|   +-- test_program.py           NEW -- public API contract
|   +-- test_errors.py            NEW -- syntax/runtime error class + position reporting
|   +-- test_cli.py               NEW -- subprocess-driven CLI tests
|   +-- test_gawk_parity.py       NEW -- runs each parity case through both interpreters
+-- .github/
|   +-- workflows/
|       +-- ci.yml                NEW (optional, see section 7)
```

The `src/` layout is chosen deliberately: it forces tests to run against the installed package (via `pip install -e .`), which prevents accidental in-tree imports masking packaging mistakes.

---

## 2. Build configuration: `pyproject.toml`

Single file, no `setup.py`, no `setup.cfg`. Use **hatchling** as the build backend -- it is the current PyPA default for new projects, has zero config for the common case, and reads `__version__` straight out of `src/pythonawk/__init__.py`.

Concrete contents (exact strings to write):

```toml
[build-system]
requires = ["hatchling>=1.25"]
build-backend = "hatchling.build"

[project]
name = "pythonawk"
description = "A Python implementation of a small, useful subset of AWK."
readme = "README.md"
requires-python = ">=3.10"
license = { text = "TBD" }
authors = [{ name = "Michael Connolly" }]
keywords = ["awk", "gawk", "text-processing", "csv", "tsv", "tabular"]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Intended Audience :: Developers",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: 3.13",
    "Programming Language :: Python :: 3.14",
    "Topic :: Text Processing",
    "Topic :: Software Development :: Interpreters",
    "Operating System :: OS Independent",
]
dependencies = []                 # spec section 10 mandates pure stdlib
dynamic = ["version"]

[project.optional-dependencies]
dev = [
    "pytest>=8",
    "pytest-cov>=5",
    "ruff>=0.6",
]

[project.scripts]
pythonawk = "pythonawk.cli:main"

[project.urls]
Homepage = "https://github.com/<user>/PythonAwk"
Source   = "https://github.com/<user>/PythonAwk"

[tool.hatch.version]
path = "src/pythonawk/__init__.py"

[tool.hatch.build.targets.wheel]
packages = ["src/pythonawk"]

[tool.pytest.ini_options]
addopts = "-ra --strict-markers"
testpaths = ["tests"]
markers = [
    "gawk: tests that shell out to gawk for parity checking",
]

[tool.ruff]
line-length = 100
target-version = "py310"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "SIM"]
```

`__version__ = "0.1.0"` lives in `src/pythonawk/__init__.py` and hatchling reads it.

Install for development:

```bash
# from repo root, with a venv already active
pip install -e ".[dev]"
```

That single command produces a working `pythonawk` console script and an importable `pythonawk` module.

---

## 3. Module-by-module responsibility

Each module corresponds to exactly one concern from the spec. Keep them small; the spec gives us a budget of ~800 lines for lexer + parser + AST combined (section 10) and the interpreter is roughly the same order.

### `errors.py`
Defines the three exception classes from spec section 7. `PythonAwkSyntaxError` carries `message`, `line`, `column`, and a short `source_excerpt` showing the offending region (one line of source plus a caret pointer line). `PythonAwkRuntimeError` carries `message` plus optional `row_number`. Pure data classes; no logic.

### `lexer.py`
Hand-rolled tokenizer using `re` (spec section 10 explicitly authorises this dependency). Produces a flat list of `Token(kind, value, line, column)` records consumed by the parser. Token kinds cover everything in the grammar:

- Keywords: `if`, `else`, `for`, `print`
- Builtins: `NF`, `NR` (recognised lexically because they capitalise differently from user variables)
- Identifiers: lowercase-starting (user variables) vs uppercase-starting (named field references after `$`)
- Field marker: `$`
- Numbers, strings (double-quoted with backslash escapes), regex literals (delimited by `/`)
- Operators: the full set in section 4 -- `+ - * / % ++ --`, `= += -= *= /= %=`, `== != < > <= >= ~ !~`, `&& || !`, `( ) { } [ ] , ;`
- Special handling for the `/regex/` vs `/` (division) ambiguity: a `/` is a regex literal when the previous token is one that cannot legally precede a binary `/` (for example: start-of-input, `,`, `(`, `{`, `~`, `!~`, `&&`, `||`, `=`, `==`, `!=`, `<`, `>`, `<=`, `>=`, `+`, `-`, `*`, `/`, `%`, `;`). This is the same heuristic gawk uses; document it in a one-line comment at the call site.

Output: list of tokens ending in an `EOF` sentinel. Errors raise `PythonAwkSyntaxError` with line/col.

### `ast_nodes.py`
Frozen dataclasses, one per grammar production that produces structure. At minimum:

- `Program(rules: tuple[Rule, ...])`
- `Rule(condition: Expr | None, block: Block)`
- `Block(stmts: tuple[Stmt, ...])`
- Statements: `Print(args: tuple[Concat, ...])`, `Assign(target: LValue, op: str, value: Expr)`, `If(branches: tuple[tuple[Expr, Block], ...], else_block: Block | None)`, `For(init: Stmt, cond: Expr, update: Stmt, body: Block)`, `Incr(target: LValue, delta: int)`
- LValues: `FieldRef(index: Expr | str | int)`, `Variable(name: str)` -- where `index` distinguishes the four field-ref forms from the grammar (`$INTEGER`, `$IDENT`, `$variable`, `$(expr)`)
- Expressions: `BinOp`, `UnaryOp`, `Compare`, `RegexMatch(left, regex, negated: bool)`, `Concat(parts: tuple[Expr, ...])`, `FunctionCall(name: str, args: tuple[Expr, ...])`, `StringLit`, `NumberLit`, `RegexLit(pattern: str)`, `BuiltinVar(name: str)`

Each node carries a `pos: tuple[int, int]` (line, col) for error reporting at runtime.

The `if`/`else if` chain is flattened into a single `If` node per the spec note in section 2 (Grammar notes). Compound assignments are kept as-is at the AST level (op kept on the node) and expanded by the interpreter, which matches the spec's note that they "desugar... at the AST level. The parser accepts them directly; the interpreter expands them."

### `parser.py`
Recursive-descent. One method per grammar production, using the precedence table from spec section 4. Methods follow the standard Pratt-ish layering: `parse_program -> parse_rule -> parse_block -> parse_statement -> parse_expression -> parse_or -> parse_and -> parse_comparison -> parse_addition -> parse_multiplication -> parse_unary -> parse_concat -> parse_atom`.

Two non-obvious things to get right (both already nailed down in the spec, just calling them out for the implementer):

1. **Implicit concatenation** sits between unary and atom in precedence, but it is *not* a unary operator -- it kicks in when two atoms appear adjacent with no operator between them. In the parser, `parse_concat` collects atoms in a loop until it sees a token that cannot start a new atom.
2. **`++`/`--` are statement-level only** (spec section 4). The parser must reject `$i++` inside an expression context with a clear error message.

Errors raise `PythonAwkSyntaxError` with the position of the offending token and a one-line excerpt with caret.

### `interpreter.py`
Tree-walk evaluator. Owns the per-row execution state:

```
class Interpreter:
    def __init__(self, program: Program): ...
    def execute(
        self,
        fields: list[str],
        header: dict[str, int] | None,
        row_number: int,
    ) -> list[str] | None: ...
```

Internal state per call: `self._fields` (mutable copy), `self._nf` (derived from `len(self._fields)`), `self._nr`, `self._header`, `self._user_vars: dict[str, str | float]`, `self._output_row: list[str] | None`.

Key behaviours from spec:

- Fields are 1-indexed externally (`$1` is `self._fields[0]`). Out-of-range read returns `""`. Out-of-range write extends the list, padding with `""` (section 5, Field reference semantics).
- `$0` read joins fields with space (default OFS); `$0` write re-splits on input field separator (default whitespace). The library API takes pre-split `fields`, so `$0` write only matters if a program writes `$0` directly during execution.
- Type coercion follows POSIX AWK (section 6, Type coercion): a value is "numeric-looking" if `_looks_numeric(s)` matches `^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$`. Comparisons compare numerically iff both operands are numeric-looking; otherwise lexicographic. Arithmetic always coerces; non-numeric strings become `0`.
- Implicit concatenation always returns a string, even when both operands are numeric (`print 1 2` -> `"12"`).
- Division by zero raises `PythonAwkRuntimeError`. So does using `$Name` without a `header` mapping.
- `length()` with no args = `length($0)`. With one arg, returns string length of the coerced string form of the argument.
- Multiple `print` statements: last one wins. If no `print` runs, `execute` returns `None`.

### `program.py`
The public facade. Single class, two methods (constructor + `execute`). Roughly:

```
class Program:
    def __init__(self, source: str) -> None:
        tokens = tokenize(source)
        self._ast = Parser(tokens).parse_program()

    def execute(
        self,
        fields: list[str],
        header: dict[str, int] | None = None,
        row_number: int = 1,
    ) -> list[str] | None:
        return Interpreter(self._ast).execute(fields, header, row_number)
```

`Interpreter` is constructed per call (or lazily cached -- pick one and document) so the spec's promise that "the compiled program is immutable and safe to reuse... including from multiple threads" holds. Per-call construction is simpler and cheap; do that unless profiling says otherwise.

### `cli.py`
Argparse-driven, matching the spec's section 8 invocation:

```
pythonawk [-F sep] [-v var=value] 'program' [file ...]
```

Behaviour:
- Read stdin if no files; otherwise iterate the listed files in order.
- Split each line by `-F` (default: any-whitespace, collapse runs, like AWK's default).
- Set `NR` to the cumulative row count across files (matching gawk).
- Build a `Program` once, call `execute` per row.
- If `execute` returns a list, write `OFS.join(result) + ORS` to stdout. Default OFS = `" "`, ORS = `"\n"`.
- `-v var=value` populates initial user-variable values. (Spec section 8 lists this flag; section 11 marks `OFS`/`ORS` as not-in-v1, so we expose `-v` for user vars only and hardcode separators for now.)

`main()` returns an int exit code; the entry point in `pyproject.toml` calls it.

---

## 4. Implementation phases

Implement in this order. Each phase ends with passing tests for that phase before the next starts.

1. **Scaffolding.** Write `pyproject.toml`, `README.md` (10 lines pointing at the spec), `LICENSE` placeholder, empty package skeleton. `pip install -e ".[dev]"` should succeed and `python -c "import pythonawk"` should work.
2. **Errors + lexer.** Implement `errors.py`, `lexer.py`. Tests in `test_lexer.py`: token sequences for every example program in spec section 9, plus the regex-vs-division disambiguation cases, plus a handful of malformed-input cases that should raise `PythonAwkSyntaxError` with correct line/col.
3. **AST + parser.** Implement `ast_nodes.py`, `parser.py`. Tests in `test_parser.py`: parse every example in spec section 9 and assert AST shape; assert flattened `If` chains; assert `++`/`--` rejected inside expressions; assert assignment rejected inside expressions (per spec section 4 note about `if (x = 3)`).
4. **Interpreter + Program facade.** Implement `interpreter.py`, `program.py`, wire them through `__init__.py`. Tests in `test_interpreter.py` and `test_program.py`: per-row execution against the parity table; type-coercion edge cases; field extension; named-field references with and without header; runtime errors.
5. **CLI.** Implement `cli.py`. Tests in `test_cli.py`: subprocess `pythonawk` against fixture files; stdin handling; `-F`; `-v`; exit codes.
6. **gawk parity harness.** Implement `test_gawk_parity.py`: for each row in `parity_cases.py`, build an equivalent gawk invocation, compare outputs byte-for-byte. Skip with `pytest.mark.skip` if `gawk` is not on PATH (use `shutil.which("gawk")` in `conftest.py`).
7. **(Optional) CI.** GitHub Actions workflow running `pytest` and `ruff check` on Linux + Windows + macOS, Python 3.10 through 3.14. Install gawk on Linux/macOS for the parity tests; skip parity on Windows runners (gawk install there is messy and the local dev box already covers it).

Each phase is a separate commit (or PR if you want review gates).

---

## 5. Testing strategy

The spec section 10 calls for "table-driven tests... with an automated comparison mode that runs each test case through both PythonAwk and gawk and asserts matching results." Concrete shape:

`tests/cases/parity_cases.py`:

```python
# Each case is reused by:
#   - test_interpreter.py   (asserts our execute() output)
#   - test_gawk_parity.py   (asserts gawk produces the same output)
#
# Shape:
#   ParityCase(
#       id="...",
#       program="...",          # AWK source
#       input_rows=[[...], ...],# pre-split fields per row
#       header={"...": 0, ...} | None,
#       expected=[[...], None, [...]],  # per-row output, None means filtered
#   )
PARITY_CASES: tuple[ParityCase, ...] = (
    ParityCase(id="select_reorder",   program="{print $3, $1, $5}",            ...),
    ParityCase(id="filter_nonempty",  program='$3 != "" {print $0}',          ...),
    # ... one entry per example in spec section 9, plus boundary cases
)
```

Both `test_interpreter.py` and `test_gawk_parity.py` parametrise over `PARITY_CASES`. The interpreter test calls `Program(case.program).execute(...)`; the parity test pipes the input through `gawk -F ' ' case.program` and compares output line-by-line.

Coverage targets:
- Every example in spec section 9 (12 programs).
- Boundary cases: empty fields, missing fields, `NF == 0` rows, very long fields for `length()`, regex with special characters, numeric vs lexicographic comparison flips, division by zero, named field with and without header.
- Negative cases (parse errors): `if (x = 3)`, `print $i++`, unterminated string, unterminated regex, mismatched braces. These do not go through gawk -- they assert our `PythonAwkSyntaxError` line/col is correct.

Run locally:

```bash
# from repo root, with venv active and "pip install -e .[dev]" already done
pytest                              # all tests
pytest -m "not gawk"                # skip parity if gawk missing
pytest tests/test_gawk_parity.py -v # parity only
ruff check .
```

Expected: all tests pass; `ruff check` clean.

---

## 6. Distribution and installation

After phase 1, the package is installable via `pip install -e .` from the checkout. After implementation completes:

```bash
pip install build
python -m build                      # produces dist/pythonawk-0.1.0-py3-none-any.whl
pip install dist/pythonawk-0.1.0-py3-none-any.whl
```

Downstream projects depend on it via:

```toml
# in their pyproject.toml
dependencies = ["pythonawk @ git+https://github.com/<user>/PythonAwk@v0.1.0"]
```

Or, after publishing to a private/public index:

```toml
dependencies = ["pythonawk>=0.1,<0.2"]
```

Tag releases as `v0.1.0`, `v0.1.1`, etc. Bump `__version__` in `src/pythonawk/__init__.py` -- hatchling reads it directly, so there is exactly one place to change.

---

## 7. Tooling and quality gates

- **Linting/formatting**: `ruff` (one tool, configured in `pyproject.toml` above). No black, no isort, no flake8 -- ruff covers all three.
- **Type checking**: not required for v1 per the spec ("pure Python standard library only"), but adding `from __future__ import annotations` at the top of every module and writing type hints on public functions costs nothing and makes the code IDE-friendly.
- **Pre-commit**: optional. If used, configure `pre-commit-config.yaml` with `ruff` and `ruff-format` hooks.

---

## 8. Critical files (where to look during implementation)

For implementers picking this up cold:

- [docs/spec.md](spec.md) -- authoritative spec. Section 2 (grammar), section 4 (precedence), section 5 (built-ins / field semantics), section 6 (execution model / type coercion), section 7 (API contract), section 9 (worked examples).
- `pyproject.toml` -- all packaging config in one place; hatchling reads the version from `src/pythonawk/__init__.py`.
- `src/pythonawk/lexer.py` -- the tokenizer's regex-vs-division disambiguation logic is the easiest place to introduce subtle bugs; review it carefully.
- `src/pythonawk/parser.py` -- the precedence climbing must match section 4 exactly.
- `src/pythonawk/interpreter.py` -- the type coercion rules in section 6 are the second-easiest place to introduce subtle bugs.
- `tests/cases/parity_cases.py` -- the canonical test corpus.

---

## 9. Verification (end-to-end)

After all phases land, the following sequence must succeed on a fresh clone, with `gawk` on PATH:

```bash
# from repo root
python -m venv .venv
. .venv/bin/activate                                  # Linux/macOS
# .venv\Scripts\activate                              # Windows
pip install -e ".[dev]"

# Library import works
python -c "from pythonawk import Program; print(Program('{print $1}').execute(['hello','world']))"
# Expected exit code: 0
# Expected stdout:    ['hello']

# CLI works on stdin
printf 'a b c\nd e f\n' | pythonawk '{print $2, $1}'
# Expected exit code: 0
# Expected stdout:
# b a
# e d

# Test suite passes (including gawk parity)
pytest
# Expected: all tests pass, exit code 0

# Linting clean
ruff check .
# Expected: exit code 0

# Wheel builds
pip install build && python -m build
# Expected: dist/pythonawk-0.1.0-py3-none-any.whl exists
```

If every line above behaves as commented, v1 is done.

---

## 10. Out of scope for this plan

Spec section 11 lists future extensions (`BEGIN`/`END`, `OFS`/`ORS`, `tolower`/`toupper`, `substr`, associative arrays, user-defined functions, `printf`). None are part of v1. The grammar and `function_call` production are designed so that adding any of them is additive -- no v1 module needs to be restructured to accommodate them later.
