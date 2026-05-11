from __future__ import annotations

import pytest  # type: ignore[import-not-found]  # pyright: ignore[reportMissingImports,reportMissingModuleSource]

from pythonawk.errors import PythonAwkSyntaxError
from pythonawk.lexer import tokenize

EXAMPLE_PROGRAMS = (
    "{print $3, $1, $5}",
    '$3 != "" {print $0}',
    '$3 != "" && $4 == "ACTIVE" {print $1, $2, $3}',
    '$2 ~ /^NSN/ || $2 ~ /^MIL/ {print $1, $2}',
    '$2 ~ /^[0-9]{4}/ {print $1, $2, $3}',
    '{print $1 "-" $2, $3, $4}',
    '{if ($4 == "NMCRL") $5 = "AU-" $5; print $1, $2, $3, $4, $5}',
    (
        '{ if ($3 == "3") $7 = "high" else if ($3 == "2") $7 = "medium" '
        'else if ($3 == "1") $7 = "low" else $7 = "unknown"; print $0 }'
    ),
    '{for (i = 1; i <= NF; i++) if ($i == "") $i = "NULL"; print $0}',
    '{for (i = 3; i <= NF; i++) if (length($i) > 0) n += 1; print $1, $2, n; n = 0}',
    'length($1) > 4 && length($1) < 20 {print $1, $2}',
    '{$6 = $1 $2; print $1, $2, $3, $4, $5, $6}',
    '$1 != "" {if ($2 ~ /^NSN/) $2 = "MIL-" $2; print $1, $2, $3}',
    '$4 != "DELETED" {print $1, $2, $3}',
    (
        '{for (i = 1; i <= NF; i++) {if (length($i) == 0) $i = "NULL"; '
        'if (length($i) > 100) $i = "TRUNCATED"}; print $0}'
    ),
)


@pytest.mark.parametrize("program", EXAMPLE_PROGRAMS)
def test_tokenize_spec_examples(program: str) -> None:
    tokens = tokenize(program)
    assert tokens
    assert tokens[-1].kind == "EOF"


def test_regex_vs_division_disambiguation() -> None:
    tokens = tokenize('{if ($2 ~ /^NSN/) $2 = $2 "/X"; print 10/2, $2}')
    regex_tokens = [t for t in tokens if t.kind == "REGEX"]
    slash_tokens = [t for t in tokens if t.kind == "SLASH"]
    assert len(regex_tokens) == 1
    assert regex_tokens[0].value == "^NSN"
    assert len(slash_tokens) == 1


def test_unterminated_string_reports_position() -> None:
    with pytest.raises(PythonAwkSyntaxError) as exc:
        tokenize('{print "abc}')
    assert exc.value.line == 1
    assert exc.value.column == 8


def test_unterminated_regex_reports_position() -> None:
    with pytest.raises(PythonAwkSyntaxError) as exc:
        tokenize('{if ($1 ~ /abc) print $1}')
    assert exc.value.line == 1
    assert exc.value.column == 11


def test_unexpected_character_reports_position() -> None:
    with pytest.raises(PythonAwkSyntaxError) as exc:
        tokenize('{print @}')
    assert exc.value.line == 1
    assert exc.value.column == 8
