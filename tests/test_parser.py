from __future__ import annotations

import pytest

from pythonawk.ast_nodes import IfStmt
from pythonawk.errors import PythonAwkSyntaxError
from pythonawk.lexer import tokenize
from pythonawk.parser import parse


def _parse_program(source: str):
    return parse(tokens=tokenize(source), source=source)


@pytest.mark.parametrize(
    "source",
    (
        "{print $3, $1, $5}",
        '$3 != "" {print $0}',
        '$3 != "" && $4 == "ACTIVE" {print $1, $2, $3}',
        '$2 ~ /^NSN/ || $2 ~ /^MIL/ {print $1, $2}',
        '{for (i = 1; i <= NF; i++) if ($i == "") $i = "NULL"; print $0}',
    ),
)
def test_parse_spec_examples(source: str) -> None:
    ast = _parse_program(source)
    assert len(ast.rules) >= 1


def test_else_if_chain_is_flattened() -> None:
    source = (
        '{if ($1 == "A") $2 = "x" else if ($1 == "B") $2 = "y" '
        'else if ($1 == "C") $2 = "z" else $2 = "u"; print $0}'
    )
    ast = _parse_program(source)
    stmt = ast.rules[0].block.statements[0]
    assert isinstance(stmt, IfStmt)
    assert len(stmt.branches) == 3
    assert stmt.else_block is not None


def test_increment_in_expression_is_rejected() -> None:
    source = '{print $i++}'
    with pytest.raises(PythonAwkSyntaxError):
        _parse_program(source)


def test_assignment_in_expression_is_rejected() -> None:
    source = '{if (x = 3) print $1}'
    with pytest.raises(PythonAwkSyntaxError):
        _parse_program(source)
