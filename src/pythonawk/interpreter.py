from __future__ import annotations

import math
import re

from .ast_nodes import (
	AssignStmt,
	BinaryExpr,
	BlockNode,
	BuiltinVar,
	ConcatExpr,
	FieldRef,
	ForStmt,
	FunctionCall,
	IfStmt,
	IncrStmt,
	NumberLiteral,
	PrintStmt,
	ProgramNode,
	RegexLiteral,
	StringLiteral,
	UnaryExpr,
	VariableRef,
)
from .errors import PythonAwkRuntimeError

NUMERIC_RE = re.compile(r"^[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?$")


class Interpreter:
	def __init__(self, program: ProgramNode) -> None:
		self.program = program
		self._fields: list[str] = []
		self._header: dict[str, int] | None = None
		self._nr: int = 1
		self._output_row: list[str] | None = None
		self._user_vars: dict[str, str | float] = {}

	def execute(
		self,
		fields: list[str],
		header: dict[str, int] | None,
		row_number: int,
	) -> list[str] | None:
		self._fields = [str(v) for v in fields]
		self._header = header
		self._nr = row_number
		self._output_row = None
		self._user_vars = {}

		for rule in self.program.rules:
			if rule.condition is None or self._truthy(self._eval_expr(rule.condition)):
				self._execute_block(rule.block)

		return self._output_row

	def _execute_block(self, block: BlockNode) -> None:
		for stmt in block.statements:
			self._execute_statement(stmt)

	def _execute_statement(self, stmt) -> None:
		if isinstance(stmt, PrintStmt):
			out: list[str] = []
			for arg in stmt.args:
				out.append(self._to_string(self._eval_expr(arg)))
			self._output_row = out
			return

		if isinstance(stmt, AssignStmt):
			value = self._eval_expr(stmt.value)
			if stmt.op != "=":
				current = self._get_lvalue(stmt.target)
				left_num = self._to_number(current)
				right_num = self._to_number(value)
				if stmt.op == "+=":
					value = left_num + right_num
				elif stmt.op == "-=":
					value = left_num - right_num
				elif stmt.op == "*=":
					value = left_num * right_num
				elif stmt.op == "/=":
					if right_num == 0:
						self._runtime_error("Division by zero")
					value = left_num / right_num
				elif stmt.op == "%=":
					if right_num == 0:
						self._runtime_error("Division by zero")
					value = math.fmod(left_num, right_num)
			self._set_lvalue(stmt.target, value)
			return

		if isinstance(stmt, IncrStmt):
			current = self._to_number(self._get_lvalue(stmt.target))
			self._set_lvalue(stmt.target, current + stmt.delta)
			return

		if isinstance(stmt, IfStmt):
			for cond, block in stmt.branches:
				if self._truthy(self._eval_expr(cond)):
					self._execute_block(block)
					return
			if stmt.else_block is not None:
				self._execute_block(stmt.else_block)
			return

		if isinstance(stmt, ForStmt):
			self._execute_statement(stmt.init)
			while self._truthy(self._eval_expr(stmt.condition)):
				self._execute_block(stmt.body)
				self._execute_statement(stmt.update)
			return

		if isinstance(stmt, BlockNode):
			self._execute_block(stmt)
			return

		self._runtime_error("Unsupported statement type")

	def _eval_expr(self, expr):
		if isinstance(expr, StringLiteral):
			return expr.value
		if isinstance(expr, NumberLiteral):
			return expr.value
		if isinstance(expr, RegexLiteral):
			return expr.pattern
		if isinstance(expr, VariableRef):
			return self._user_vars.get(expr.name, "")
		if isinstance(expr, BuiltinVar):
			if expr.name == "NF":
				return float(len(self._fields))
			if expr.name == "NR":
				return float(self._nr)
			self._runtime_error(f"Unknown builtin variable: {expr.name}")
		if isinstance(expr, FieldRef):
			return self._get_field(expr)
		if isinstance(expr, ConcatExpr):
			return "".join(self._to_string(self._eval_expr(part)) for part in expr.parts)
		if isinstance(expr, UnaryExpr):
			value = self._eval_expr(expr.operand)
			if expr.op == "!":
				return 0.0 if self._truthy(value) else 1.0
			if expr.op == "-":
				return -self._to_number(value)
			self._runtime_error(f"Unsupported unary operator: {expr.op}")
		if isinstance(expr, BinaryExpr):
			return self._eval_binary(expr)
		if isinstance(expr, FunctionCall):
			return self._eval_function(expr)
		self._runtime_error("Unsupported expression type")

	def _eval_binary(self, expr: BinaryExpr):
		if expr.op == "||":
			left = self._eval_expr(expr.left)
			if self._truthy(left):
				return 1.0
			return 1.0 if self._truthy(self._eval_expr(expr.right)) else 0.0

		if expr.op == "&&":
			left = self._eval_expr(expr.left)
			if not self._truthy(left):
				return 0.0
			return 1.0 if self._truthy(self._eval_expr(expr.right)) else 0.0

		left = self._eval_expr(expr.left)
		right = self._eval_expr(expr.right)

		if expr.op in {"==", "!=", "<", ">", "<=", ">="}:
			result = self._compare(left, right, expr.op)
			return 1.0 if result else 0.0

		if expr.op in {"~", "!~"}:
			pattern = self._to_string(right)
			hay = self._to_string(left)
			matched = re.search(pattern, hay) is not None
			return 1.0 if (matched if expr.op == "~" else not matched) else 0.0

		left_num = self._to_number(left)
		right_num = self._to_number(right)

		if expr.op == "+":
			return left_num + right_num
		if expr.op == "-":
			return left_num - right_num
		if expr.op == "*":
			return left_num * right_num
		if expr.op == "/":
			if right_num == 0:
				self._runtime_error("Division by zero")
			return left_num / right_num
		if expr.op == "%":
			if right_num == 0:
				self._runtime_error("Division by zero")
			return math.fmod(left_num, right_num)

		self._runtime_error(f"Unsupported binary operator: {expr.op}")

	def _eval_function(self, call: FunctionCall):
		if call.name != "length":
			self._runtime_error(f"Unsupported function: {call.name}")
		if len(call.args) == 0:
			return float(len(self._to_string(self._read_field_by_number(0))))
		if len(call.args) == 1:
			return float(len(self._to_string(self._eval_expr(call.args[0]))))
		self._runtime_error("length() accepts 0 or 1 argument")

	def _compare(self, left, right, op: str) -> bool:
		if self._looks_numeric(left) and self._looks_numeric(right):
			a_num = self._to_number(left)
			b_num = self._to_number(right)
			if op == "==":
				return a_num == b_num
			if op == "!=":
				return a_num != b_num
			if op == "<":
				return a_num < b_num
			if op == ">":
				return a_num > b_num
			if op == "<=":
				return a_num <= b_num
			if op == ">=":
				return a_num >= b_num
		else:
			a_str = self._to_string(left)
			b_str = self._to_string(right)
			if op == "==":
				return a_str == b_str
			if op == "!=":
				return a_str != b_str
			if op == "<":
				return a_str < b_str
			if op == ">":
				return a_str > b_str
			if op == "<=":
				return a_str <= b_str
			if op == ">=":
				return a_str >= b_str
		self._runtime_error(f"Unsupported comparison operator: {op}")
		raise AssertionError("unreachable")

	def _get_lvalue(self, target):
		if isinstance(target, VariableRef):
			return self._user_vars.get(target.name, "")
		if isinstance(target, FieldRef):
			return self._get_field(target)
		self._runtime_error("Invalid lvalue")

	def _set_lvalue(self, target, value) -> None:
		if isinstance(target, VariableRef):
			if isinstance(value, str):
				self._user_vars[target.name] = value
			else:
				self._user_vars[target.name] = float(value)
			return
		if isinstance(target, FieldRef):
			self._set_field(target, value)
			return
		self._runtime_error("Invalid lvalue")

	def _resolve_field_number(self, ref: FieldRef) -> int:
		idx = ref.index
		if isinstance(idx, int):
			return idx
		if isinstance(idx, str):
			if self._header is None:
				self._runtime_error(f"Named field '{idx}' used without header mapping")
			header = self._header
			assert header is not None
			if idx not in header:
				self._runtime_error(f"Named field '{idx}' not found in header mapping")
			return header[idx] + 1
		if isinstance(idx, BuiltinVar):
			value = self._eval_expr(idx)
			return int(self._to_number(value))
		value = self._eval_expr(idx)
		return int(self._to_number(value))

	def _get_field(self, ref: FieldRef) -> str:
		number = self._resolve_field_number(ref)
		return self._read_field_by_number(number)

	def _read_field_by_number(self, number: int) -> str:
		if number == 0:
			return " ".join(self._fields)
		if number < 0:
			self._runtime_error("Negative field index is invalid")
		index = number - 1
		if index >= len(self._fields):
			return ""
		return self._fields[index]

	def _set_field(self, ref: FieldRef, value) -> None:
		text = self._to_string(value)
		number = self._resolve_field_number(ref)
		if number == 0:
			self._fields = self._split_fields_from_zero(text)
			return
		if number < 0:
			self._runtime_error("Negative field index is invalid")
		index = number - 1
		if index >= len(self._fields):
			self._fields.extend([""] * (index + 1 - len(self._fields)))
		self._fields[index] = text

	def _split_fields_from_zero(self, text: str) -> list[str]:
		stripped = text.strip()
		if stripped == "":
			return []
		return re.findall(r"\S+", stripped)

	def _looks_numeric(self, value) -> bool:
		if isinstance(value, (int, float)):
			return True
		if not isinstance(value, str):
			return False
		return NUMERIC_RE.fullmatch(value.strip()) is not None

	def _to_number(self, value) -> float:
		if isinstance(value, (int, float)):
			return float(value)
		if isinstance(value, str):
			text = value.strip()
			if NUMERIC_RE.fullmatch(text):
				try:
					return float(text)
				except ValueError:
					return 0.0
		return 0.0

	def _to_string(self, value) -> str:
		if isinstance(value, str):
			return value
		if isinstance(value, int):
			return str(value)
		if isinstance(value, float):
			if value.is_integer():
				return str(int(value))
			return format(value, ".15g")
		return str(value)

	def _truthy(self, value) -> bool:
		if isinstance(value, str):
			if self._looks_numeric(value):
				return self._to_number(value) != 0.0
			return value != ""
		return self._to_number(value) != 0.0

	def _runtime_error(self, message: str) -> None:
		raise PythonAwkRuntimeError(message=message, row_number=self._nr)
