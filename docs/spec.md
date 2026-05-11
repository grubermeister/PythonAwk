# PythonAwk — A Python Implementation of an AWK Subset

**Purpose:** A small, self-contained Python library that parses and executes a constrained subset of AWK syntax against tabular data. Usable as an importable module to bring AWK's structural text-processing capabilities into any Python program, or as a command-line utility applied to delimited files and streams.

**Design philosophy:** Same relationship to AWK that PythonSed has to GNU sed. Real AWK syntax — not a Python-flavored reimagining — scoped to a deliberately small grammar that covers the structural transforms most commonly needed when processing delimited data: column selection, reordering, merging, filtering, conditional mutation, and iteration over variable-width rows. Anything outside the supported subset is a parse error, not a silent misinterpretation. If a task requires capabilities beyond this subset, use a full AWK implementation or a general-purpose scripting language.

**Reference:** GNU AWK (gawk) 5.x. The supported subset produces identical output to gawk for any program that falls within the grammar defined below.

---

## 1. Scope and Non-Goals

### In scope

- Column selection and reordering
- Column merging via implicit string concatenation
- Row filtering by field comparison or regex match
- Conditional field assignment (`if`/`else if`/`else`)
- Compound boolean conditions (`&&`, `||`)
- Iteration over variable-width rows (`for` with counter, `++`/`--`/`+=` ergonomics)
- Derived columns via field assignment
- `length()` built-in function
- Named field references via header row (extension to standard AWK)
- Embeddable API: parse once, execute per-row, no I/O side effects
- Command-line interface for standalone use against files and stdin

### Explicitly out of scope

| Feature | Rationale |
|---|---|
| `BEGIN` / `END` blocks | The host application owns initialization and finalization. PythonAwk processes one row at a time; there is no concept of "before first row" or "after last row" at the library level. A future version may add these for command-line mode only. |
| Associative arrays | State accumulation across rows is application logic, not row transformation logic. |
| User-defined functions | If the transform needs functions, it has outgrown a one-line program and belongs in a script. |
| `printf` | `print` with implicit concatenation covers the output-shaping cases this subset targets. |
| `getline` | I/O is controlled by the caller, not by the AWK program. |
| Multiple input files | I/O is controlled by the caller. |
| Output redirection (`>`, `>>`, `\|`) | I/O is controlled by the caller. |
| Pipes and coprocesses | I/O is controlled by the caller. |
| Built-in string functions (`index`, `split`, `gsub`, `sub`, `sprintf`, `match`, `tolower`, `toupper`) | Per-field string manipulation is a separate concern. PythonAwk handles row structure; pair it with PythonSed or Python's own string methods for cell-level transforms. `length()` is included because it is essential for structural decisions (field-length-based filtering and iteration bounds). Other string functions may be added in future versions if demand warrants. |

---

## 2. Formal Grammar

```ebnf
(* ===== Top-level ===== *)
program         = rule { rule } ;
rule            = [ condition ] action_block ;
condition       = expression ;
action_block    = '{' statement_list '}' ;
statement_list  = statement { ';' statement } [ ';' ] ;

(* ===== Statements ===== *)
statement       = print_stmt
                | assignment_stmt
                | if_stmt
                | for_stmt
                | incr_stmt ;

print_stmt      = 'print' print_args ;
print_args      = print_expr { ',' print_expr } ;
print_expr      = concat_expr ;
concat_expr     = expression { expression } ;       (* adjacent exprs = implicit concatenation *)

assignment_stmt = lvalue '=' expression
                | lvalue '+=' expression
                | lvalue '-=' expression
                | lvalue '*=' expression
                | lvalue '/=' expression
                | lvalue '%=' expression ;
lvalue          = field_ref | variable ;

incr_stmt       = lvalue '++' | lvalue '--'
                | '++' lvalue | '--' lvalue ;

if_stmt         = 'if' '(' expression ')' block
                  { 'else' 'if' '(' expression ')' block }
                  [ 'else' block ] ;
for_stmt        = 'for' '(' for_init ';' expression ';' for_update ')' block ;
for_init        = assignment_stmt ;
for_update      = assignment_stmt | incr_stmt ;
block           = action_block | statement ;

(* ===== Expressions ===== *)
expression      = or_expr ;
or_expr         = and_expr { '||' and_expr } ;
and_expr        = comparison { '&&' comparison } ;
comparison      = addition [ comparison_op addition ] ;
comparison_op   = '==' | '!=' | '<' | '>' | '<=' | '>='
                | '~' | '!~' ;
addition        = multiplication { ( '+' | '-' ) multiplication } ;
multiplication  = unary { ( '*' | '/' | '%' ) unary } ;
unary           = [ '!' | '-' ] atom ;

atom            = field_ref
                | function_call
                | variable
                | string_literal
                | number_literal
                | builtin_var
                | regex_literal
                | '(' expression ')' ;

(* ===== Function calls ===== *)
function_call   = function_name '(' [ expression { ',' expression } ] ')' ;
function_name   = 'length' | 'substr' | 'mktime' | 'strftime' ;

(* ===== Atoms ===== *)
field_ref       = '$' ( INTEGER | IDENTIFIER | variable | '(' expression ')' ) ;
variable        = LOWERCASE_IDENTIFIER ;
string_literal  = '"' { CHAR } '"' ;
number_literal  = INTEGER [ '.' INTEGER ] ;
builtin_var     = 'NF' | 'NR' ;
regex_literal   = '/' { REGEX_CHAR } '/' ;

(* ===== Tokens ===== *)
INTEGER                = DIGIT { DIGIT } ;
IDENTIFIER             = LETTER { LETTER | DIGIT | '_' } ;
LOWERCASE_IDENTIFIER   = LOWERCASE_LETTER { LETTER | DIGIT | '_' } ;
```

### Grammar notes

**`else if` chains.** The `if_stmt` production accepts zero or more `else if` clauses before an optional final `else`. This is syntactic sugar — each `else if` is an additional condition/block pair, not a nested `if` inside an `else`. The parser flattens the chain into a single AST node with a list of (condition, block) pairs and an optional else block.

**Compound assignment operators.** `+=`, `-=`, `*=`, `/=`, `%=` desugar to `lvalue = lvalue op expression` at the AST level. The parser accepts them directly; the interpreter expands them.

**Increment / decrement.** `++` and `--` are supported as both prefix and postfix on lvalues. As statements (not inside expressions), prefix and postfix are equivalent — both increment/decrement by 1. PythonAwk does not support `++`/`--` embedded inside larger expressions (e.g., `$i++` as a print argument); they are statement-level only. This avoids the evaluation-order ambiguities that full AWK inherits from C.

**`length()` function.** `length(expr)` returns the string length of its argument. `length($0)` returns the length of the entire row. `length()` with no argument is equivalent to `length($0)`, matching AWK convention. The `function_call` production is extensible — adding future built-in functions (e.g., `toupper`, `tolower`, `substr`) requires only adding names to `function_name` and implementing the corresponding evaluation.

**Dynamic field reference.** `$(expression)` is supported via the parenthesized form in `field_ref`. This allows computed field access like `$(NF)` (last field) or `$(i + 1)` inside loops.

---

## 3. Implicit Concatenation

Within `print` argument lists and assignment right-hand sides, adjacent atoms with no operator between them are implicitly concatenated as strings. This mirrors standard AWK behavior.

```awk
print $1 "-" $2          # → concatenate($1, "-", $2)
$5 = $3 "/" $4            # → $5 = concatenate($3, "/", $4)
print $1 $2 $3            # → concatenate($1, $2, $3) — no separators
```

Implicit concatenation always produces a string result, even when both operands are numeric. This matches AWK semantics: `print 1 2` outputs `12`, not `3`.

---

## 4. Operator Precedence

Lowest to highest:

| Level | Operators | Associativity | Notes |
|---|---|---|---|
| 1 | `\|\|` | Left | Logical OR; short-circuiting |
| 2 | `&&` | Left | Logical AND; short-circuiting |
| 3 | `~ !~ == != < > <= >=` | None (no chaining) | |
| 4 | `+ -` (binary) | Left | |
| 5 | `* / %` | Left | |
| 6 | `! -` (unary) | Right | |
| 7 | Implicit concatenation | Left | Adjacency of atoms |
| 8 | `$` (field dereference) | Right | |

**Short-circuit evaluation.** `&&` and `||` follow standard short-circuit semantics. In `A && B`, `B` is not evaluated if `A` is falsy. In `A || B`, `B` is not evaluated if `A` is truthy. This matches AWK and C behavior.

**Assignment operators.** `=`, `+=`, `-=`, `*=`, `/=`, `%=` are statement-level only, not expression-level. They do not appear in the precedence table because they cannot be embedded inside expressions. This eliminates the class of bugs where `if (x = 3)` is written when `if (x == 3)` is intended.

**Increment / decrement.** `++` and `--` are statement-level only. `i++` is a statement, not an expression. This avoids C-inherited evaluation-order ambiguities and keeps the grammar unambiguous.

---

## 5. Built-in Variables

| Variable | Type | Writable | Meaning |
|---|---|---|---|
| `NF` | integer | No | Number of fields in the current row. |
| `NR` | integer | No | Current row number (1-based). |
| `$0` | string | Yes | The entire current row as a single string. |
| `$1` .. `$N` | string | Yes | Positional field reference (1-based, per AWK convention). |
| `$FieldName` | string | Yes | Named field reference. Extension to standard AWK. |
| `$variable` | string | Yes | Dynamic field reference via loop counter or user variable. |

### Field reference semantics

- Reading `$0` returns the full row joined by the output field separator (default: space).
- Assigning to `$0` re-splits the row using the input field separator.
- Assigning to a positional field beyond current `NF` extends the row. Intermediate fields are set to empty strings.
- Reading a positional field beyond current `NF` returns an empty string (not an error). This matches standard AWK behavior.

### Named field references (extension)

`$FieldName`, where `FieldName` is a non-numeric identifier, resolves against a header mapping provided by the caller. This mapping associates field names with 0-based column indices.

If no header mapping is provided and the program contains named field references, `execute()` raises `PythonAwkRuntimeError`. The parser does not reject named references at parse time, because the same compiled program may be used against inputs with or without headers.

### Built-in functions

| Function | Arguments | Returns | Notes |
|---|---|---|---|
| `length()` | 0 or 1 | integer | String length of argument. No argument = `length($0)`. |
| `substr(s, m [, n])` | 2 or 3 | string | 1-based start; n chars (to end if omitted). gawk-compatible clamping. |
| `mktime(datespec)` | 1 | number | UTC seconds since epoch. datespec is "YYYY MM DD HH MM SS" (DST token accepted and ignored). Returns -1 on parse failure. |
| `strftime(fmt, ts)` | 2 | string | UTC. ts is an epoch seconds number. Format directives follow C `strftime`. |

v1 ships `length`, `substr`, `mktime`, and `strftime`.

**UTC divergence from gawk.** `mktime` and `strftime` always operate in UTC. gawk defaults these to local time and accepts an optional `utc-flag` argument; PythonAwk omits the flag and the local-time mode. This is the one documented deviation from the "identical output to gawk" guarantee, chosen because UTC eliminates DST-boundary bugs in date arithmetic (the primary use case). Programs that need local-time formatting must do the conversion outside PythonAwk.

`length()` examples:
```awk
length($1) > 10 {print $1}                    # filter by field length
{if (length($3) == 0) $3 = "MISSING"; print $0}  # check for empty fields
{for (i = 1; i <= NF; i++) if (length($i) > 50) $i = "TRUNCATED"; print $0}
```

---

## 6. Execution Model

PythonAwk operates on one row at a time. The caller provides a pre-split list of field values; PythonAwk returns a transformed list or signals that the row should be dropped.

```
Given an input row (list of field strings):
    1. Set $1..$NF from the input fields. Set NF. Set NR.
    2. For each rule in the program (in source order):
        a. If the rule has no condition, or its condition evaluates truthy:
            Execute the rule's action block.
    3. Return the output row, or None if the row was filtered out.
```

### Print semantics

`print` does not write to stdout (in library mode). It **sets the output row** for the current input row.

- `print $1, $3` means: the output row consists of field 1 and field 3.
- Comma-separated arguments become separate output fields.
- Adjacent arguments (no comma) are concatenated into a single output field.
- If multiple `print` statements execute for one row, the last one wins.
- If no `print` executes (all rules' conditions were false), the row is dropped — `execute()` returns `None`.

In command-line mode, `print` writes to stdout with fields joined by OFS (default: space) and terminated by ORS (default: newline), matching standard AWK behavior.

### Type coercion

PythonAwk follows AWK's dual string/number type model:

- All field values are strings.
- In arithmetic context (`+`, `-`, `*`, `/`, `%`), strings are coerced to numbers. A string that doesn't look numeric coerces to `0`.
- In comparison context, if both operands look numeric, comparison is numeric; otherwise it's lexicographic. This matches POSIX AWK.
- Concatenation (implicit or via adjacency) always produces a string.

---

## 7. Library API

```python
from pythonawk import Program

# Parse once at startup — validates syntax, builds AST
prog = Program('{print $1, $3}')

# With named fields and conditions
prog = Program('$Status != "INACTIVE" {print $NSN, $Description}')

# Execute against a single row
result = prog.execute(
    fields=["AU", "1234", "Widget", "ACTIVE"],
    header={"Country": 0, "NSN": 1, "Description": 2, "Status": 3},
    row_number=42,
)
# result: ["1234", "Widget"]   — or None if row was filtered out

# Process a whole file
import csv

prog = Program('$3 != "" {if ($2 ~ /^[0-9]/) $2 = "ID-" $2; print $1, $2, $3}')

with open("data.csv") as f:
    reader = csv.reader(f)
    header_row = next(reader)
    header = {name: i for i, name in enumerate(header_row)}

    for row_num, row in enumerate(reader, start=1):
        result = prog.execute(fields=row, header=header, row_number=row_num)
        if result is not None:
            print(",".join(result))
```

### `Program(source: str)`

Parses the AWK subset source string into an internal AST. Raises `PythonAwkSyntaxError` with position information if the source does not conform to the grammar. The compiled program is immutable and safe to reuse across any number of `execute()` calls, including from multiple threads (execution creates no shared mutable state).

### `Program.execute(fields, header=None, row_number=1) -> list[str] | None`

Executes the program against one input row.

**Parameters:**

- `fields` — `list[str]`: The input row, already split into fields by the caller.
- `header` — `dict[str, int] | None`: Maps field names to 0-based indices. Required only if the program uses `$FieldName` references.
- `row_number` — `int`: Sets `NR` for this execution. Default `1`.

**Returns:**

- `list[str]` — the output fields if a `print` statement executed.
- `None` — if no `print` executed (row filtered out by conditions).

**Raises:**

- `PythonAwkRuntimeError` — division by zero, named field reference without header, or other execution error.

### Error Types

```python
class PythonAwkError(Exception):
    """Base class for all PythonAwk errors."""

class PythonAwkSyntaxError(PythonAwkError):
    """Raised when the source program does not conform to the grammar.
    Attributes: message, line, column, source_excerpt."""

class PythonAwkRuntimeError(PythonAwkError):
    """Raised during execution for type errors, missing headers,
    division by zero, etc."""
```

---

## 8. Command-Line Interface

```
pythonawk [-F sep] [-v var=value] 'program' [file ...]
```

When invoked from the command line, PythonAwk reads from the named files (or stdin if none given), splits each line into fields using the field separator (`-F`, default: whitespace), executes the program against each row, and writes output rows to stdout with fields joined by OFS (space) and terminated by ORS (newline).

This mode exists for testing and standalone use. The primary intended interface is the library API.

---

## 9. Example Programs

**Column selection and reorder:**
```awk
{print $3, $1, $5}
```

**Filter rows where a field is empty:**
```awk
$3 != "" {print $0}
```

**Compound condition with `&&`:**
```awk
$3 != "" && $4 == "ACTIVE" {print $1, $2, $3}
```

**Compound condition with `||`:**
```awk
$2 ~ /^NSN/ || $2 ~ /^MIL/ {print $1, $2}
```

**Filter by regex match:**
```awk
$2 ~ /^[0-9]{4}/ {print $1, $2, $3}
```

**Merge columns with literal separator:**
```awk
{print $1 "-" $2, $3, $4}
```

**Conditional field mutation:**
```awk
{if ($4 == "NMCRL") $5 = "AU-" $5; print $1, $2, $3, $4, $5}
```

**`else if` chain for multi-branch logic:**
```awk
{
    if ($3 == "3") $7 = "high"
    else if ($3 == "2") $7 = "medium"
    else if ($3 == "1") $7 = "low"
    else $7 = "unknown";
    print $0
}
```

**Iterate all fields with `++` increment:**
```awk
{for (i = 1; i <= NF; i++) if ($i == "") $i = "NULL"; print $0}
```

**Compound assignment in accumulation:**
```awk
{for (i = 3; i <= NF; i++) if (length($i) > 0) n += 1; print $1, $2, n; n = 0}
```

**Filter by field length:**
```awk
length($1) > 4 && length($1) < 20 {print $1, $2}
```

**Derive a new column from existing ones:**
```awk
{$6 = $1 $2; print $1, $2, $3, $4, $5, $6}
```

**Combined filter and transform:**
```awk
$1 != "" {if ($2 ~ /^NSN/) $2 = "MIL-" $2; print $1, $2, $3}
```

**Drop rows and trim to fixed columns:**
```awk
$4 != "DELETED" {print $1, $2, $3}
```

**Normalize variable-width rows, truncate long fields:**
```awk
{
    for (i = 1; i <= NF; i++) {
        if (length($i) == 0) $i = "NULL";
        if (length($i) > 100) $i = "TRUNCATED"
    };
    print $0
}
```

---

## 10. Implementation Notes

### Parser architecture

Recursive-descent, hand-rolled. No parser generator, no grammar toolkit, no external dependency. The grammar is small enough that a hand-written parser is shorter and more debuggable than generated code. Target size: under 800 lines for lexer, parser, and AST definition combined.

### AST representation

Python dataclasses. Each node type corresponds to one grammar production. The AST is the clean interface between parsing (done once per program string) and execution (done once per input row).

### Interpreter

Tree-walk interpreter over the AST. No compilation to bytecode. For row-at-a-time execution in I/O-bound pipelines, tree-walk overhead is negligible — the bottleneck is never expression evaluation when you're writing rows to a database or disk.

### Testing strategy

Table-driven tests: each case is `(program_string, input_fields, expected_output_or_none)`. Correctness can be validated against gawk for any program in the supported subset — both should produce identical output on identical input. The test suite should include an automated comparison mode that runs each test case through both PythonAwk and gawk and asserts matching results.

### Dependencies

None. Pure Python standard library only. The lexer uses `re` for tokenization. No external packages required at runtime or build time.

### Compatibility

- Python 3.10+
- No OS-specific code. Runs identically on Windows, Linux, and macOS.

### Licensing

To be determined by the project owner. The library is a clean-room implementation — no upstream AWK source code is used or referenced during implementation. Only this specification document guides the build.

---

## 11. Extension Points (Not in v1)

These features are not implemented in v1 but have defined grammar slots or clear integration paths for future versions. Each is gated on a real use case demanding it.

| Feature | Grammar slot | Trigger to implement |
|---|---|---|
| `BEGIN` / `END` blocks | Top-level rule with keyword condition | Command-line mode needs initialization or summary output |
| `OFS` / `ORS` variables | Built-in variable table | Output format needs to differ from defaults |
| `tolower()` / `toupper()` | Add to `function_name` in function-call production | Structural context where calling out to PythonSed for case conversion is awkward |
| `split()` | Function-call producing indexed result | Requires some form of array support; unlikely for PythonAwk |
| Associative arrays | New data type + `in` operator + `for..in` loop | State accumulation across rows; probably belongs in application code, not PythonAwk |
| User-defined functions | `function` keyword at top level | Program has outgrown a config-line expression; strong signal to use a real script instead |
| `printf` | New statement type | Formatted output needed beyond what concatenation provides |
