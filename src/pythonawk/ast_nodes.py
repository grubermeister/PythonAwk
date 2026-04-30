from __future__ import annotations

from dataclasses import dataclass

Position = tuple[int, int]


@dataclass(frozen=True, slots=True)
class ProgramNode:
	rules: tuple[RuleNode, ...]
	pos: Position


@dataclass(frozen=True, slots=True)
class RuleNode:
	condition: ExprNode | None
	block: BlockNode
	pos: Position


@dataclass(frozen=True, slots=True)
class BlockNode:
	statements: tuple[StmtNode, ...]
	pos: Position


@dataclass(frozen=True, slots=True)
class PrintStmt:
	args: tuple[ExprNode, ...]
	pos: Position


@dataclass(frozen=True, slots=True)
class AssignStmt:
	target: LValueNode
	op: str
	value: ExprNode
	pos: Position


@dataclass(frozen=True, slots=True)
class IfStmt:
	branches: tuple[tuple[ExprNode, BlockNode], ...]
	else_block: BlockNode | None
	pos: Position


@dataclass(frozen=True, slots=True)
class ForStmt:
	init: AssignStmt | IncrStmt
	condition: ExprNode
	update: AssignStmt | IncrStmt
	body: BlockNode
	pos: Position


@dataclass(frozen=True, slots=True)
class IncrStmt:
	target: LValueNode
	delta: int
	pos: Position


@dataclass(frozen=True, slots=True)
class FieldRef:
	index: int | str | ExprNode
	pos: Position


@dataclass(frozen=True, slots=True)
class VariableRef:
	name: str
	pos: Position


@dataclass(frozen=True, slots=True)
class BinaryExpr:
	left: ExprNode
	op: str
	right: ExprNode
	pos: Position


@dataclass(frozen=True, slots=True)
class UnaryExpr:
	op: str
	operand: ExprNode
	pos: Position


@dataclass(frozen=True, slots=True)
class ConcatExpr:
	parts: tuple[ExprNode, ...]
	pos: Position


@dataclass(frozen=True, slots=True)
class FunctionCall:
	name: str
	args: tuple[ExprNode, ...]
	pos: Position


@dataclass(frozen=True, slots=True)
class StringLiteral:
	value: str
	pos: Position


@dataclass(frozen=True, slots=True)
class NumberLiteral:
	value: float
	text: str
	pos: Position


@dataclass(frozen=True, slots=True)
class RegexLiteral:
	pattern: str
	pos: Position


@dataclass(frozen=True, slots=True)
class BuiltinVar:
	name: str
	pos: Position


StmtNode = PrintStmt | AssignStmt | IfStmt | ForStmt | IncrStmt | BlockNode
LValueNode = FieldRef | VariableRef
ExprNode = (
	FieldRef
	| VariableRef
	| BinaryExpr
	| UnaryExpr
	| ConcatExpr
	| FunctionCall
	| StringLiteral
	| NumberLiteral
	| RegexLiteral
	| BuiltinVar
)
