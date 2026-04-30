from __future__ import annotations

from .ast_nodes import (
	AssignStmt,
	BinaryExpr,
	BlockNode,
	BuiltinVar,
	ConcatExpr,
	ExprNode,
	FieldRef,
	ForStmt,
	FunctionCall,
	IfStmt,
	IncrStmt,
	NumberLiteral,
	PrintStmt,
	ProgramNode,
	RegexLiteral,
	RuleNode,
	StmtNode,
	StringLiteral,
	UnaryExpr,
	VariableRef,
)
from .errors import PythonAwkSyntaxError, make_source_excerpt
from .lexer import Token

COMPARISON_KINDS = {"EQ", "NE", "LT", "GT", "LE", "GE", "MATCH", "NMATCH"}
ASSIGNMENT_KINDS = {
	"ASSIGN": "=",
	"PLUS_ASSIGN": "+=",
	"MINUS_ASSIGN": "-=",
	"MUL_ASSIGN": "*=",
	"DIV_ASSIGN": "/=",
	"MOD_ASSIGN": "%=",
}


class Parser:
	def __init__(self, tokens: list[Token], source: str) -> None:
		self.tokens = tokens
		self.source = source
		self.index = 0

	def parse_program(self) -> ProgramNode:
		rules: list[RuleNode] = []
		start = self.current()
		while not self._is("EOF"):
			rules.append(self.parse_rule())
		return ProgramNode(rules=tuple(rules), pos=(start.line, start.column))

	def parse_rule(self) -> RuleNode:
		start = self.current()
		condition = None if self._is("LBRACE") else self.parse_expression()
		block = self.parse_action_block()
		return RuleNode(condition=condition, block=block, pos=(start.line, start.column))

	def parse_action_block(self) -> BlockNode:
		lbrace = self._expect("LBRACE")
		statements: list[StmtNode] = []
		if not self._is("RBRACE"):
			statements.append(self.parse_statement())
			while self._match("SEMI"):
				if self._is("RBRACE"):
					break
				statements.append(self.parse_statement())
		self._expect("RBRACE")
		return BlockNode(statements=tuple(statements), pos=(lbrace.line, lbrace.column))

	def parse_statement(self):
		if self._is("PRINT"):
			return self.parse_print_statement()
		if self._is("IF"):
			return self.parse_if_statement()
		if self._is("FOR"):
			return self.parse_for_statement()
		if self._is("LBRACE"):
			return self.parse_action_block()
		if self._is("INCR", "DECR"):
			return self.parse_prefix_increment_statement()
		return self.parse_assignment_or_postfix_increment_statement()

	def parse_print_statement(self) -> PrintStmt:
		kw = self._expect("PRINT")
		args: list[ExprNode] = [self.parse_expression()]
		while self._match("COMMA"):
			args.append(self.parse_expression())
		return PrintStmt(args=tuple(args), pos=(kw.line, kw.column))

	def parse_if_statement(self) -> IfStmt:
		start = self._expect("IF")
		self._expect("LPAREN")
		first_cond = self.parse_expression()
		self._expect("RPAREN")
		first_block = self.parse_statement_as_block()
		branches: list[tuple[ExprNode, BlockNode]] = [(first_cond, first_block)]
		else_block: BlockNode | None = None

		while self._match("ELSE"):
			if self._match("IF"):
				self._expect("LPAREN")
				cond = self.parse_expression()
				self._expect("RPAREN")
				block = self.parse_statement_as_block()
				branches.append((cond, block))
				continue
			else_block = self.parse_statement_as_block()
			break

		return IfStmt(
			branches=tuple(branches),
			else_block=else_block,
			pos=(start.line, start.column),
		)

	def parse_for_statement(self) -> ForStmt:
		start = self._expect("FOR")
		self._expect("LPAREN")
		init = self.parse_assignment_statement()
		self._expect("SEMI")
		condition = self.parse_expression()
		self._expect("SEMI")
		update = self.parse_for_update_statement()
		self._expect("RPAREN")
		body = self.parse_statement_as_block()
		return ForStmt(
			init=init,
			condition=condition,
			update=update,
			body=body,
			pos=(start.line, start.column),
		)

	def parse_statement_as_block(self) -> BlockNode:
		if self._is("LBRACE"):
			return self.parse_action_block()
		stmt = self.parse_statement()
		return BlockNode(statements=(stmt,), pos=getattr(stmt, "pos", (1, 1)))

	def parse_prefix_increment_statement(self) -> IncrStmt:
		op = self._advance()
		target = self.parse_lvalue()
		delta = 1 if op.kind == "INCR" else -1
		return IncrStmt(target=target, delta=delta, pos=(op.line, op.column))

	def parse_assignment_or_postfix_increment_statement(self):
		target = self.parse_lvalue()
		tok = self.current()
		if tok.kind in ASSIGNMENT_KINDS:
			self._advance()
			value = self.parse_expression()
			return AssignStmt(
				target=target,
				op=ASSIGNMENT_KINDS[tok.kind],
				value=value,
				pos=(tok.line, tok.column),
			)
		if tok.kind in {"INCR", "DECR"}:
			self._advance()
			delta = 1 if tok.kind == "INCR" else -1
			return IncrStmt(target=target, delta=delta, pos=(tok.line, tok.column))
		self._error(tok, "Expected assignment or increment/decrement statement")

	def parse_assignment_statement(self) -> AssignStmt:
		target = self.parse_lvalue()
		op = self.current()
		if op.kind not in ASSIGNMENT_KINDS:
			self._error(op, "Expected assignment in for-init")
		self._advance()
		value = self.parse_expression()
		return AssignStmt(
			target=target,
			op=ASSIGNMENT_KINDS[op.kind],
			value=value,
			pos=(op.line, op.column),
		)

	def parse_for_update_statement(self):
		target = self.parse_lvalue()
		tok = self.current()
		if tok.kind in ASSIGNMENT_KINDS:
			self._advance()
			value = self.parse_expression()
			return AssignStmt(
				target=target,
				op=ASSIGNMENT_KINDS[tok.kind],
				value=value,
				pos=(tok.line, tok.column),
			)
		if tok.kind in {"INCR", "DECR"}:
			self._advance()
			delta = 1 if tok.kind == "INCR" else -1
			return IncrStmt(target=target, delta=delta, pos=(tok.line, tok.column))
		self._error(tok, "Expected assignment or increment/decrement in for-update")

	def parse_lvalue(self):
		tok = self.current()
		if tok.kind == "DOLLAR":
			return self.parse_field_ref()
		if tok.kind == "IDENT" and tok.value and tok.value[0].islower():
			ident = self._advance()
			return VariableRef(name=ident.value, pos=(ident.line, ident.column))
		self._error(tok, "Expected lvalue")

	def parse_expression(self):
		return self.parse_or()

	def parse_or(self):
		expr = self.parse_and()
		while self._match("OR"):
			op = self.tokens[self.index - 1]
			right = self.parse_and()
			expr = BinaryExpr(left=expr, op="||", right=right, pos=(op.line, op.column))
		return expr

	def parse_and(self):
		expr = self.parse_comparison()
		while self._match("AND"):
			op = self.tokens[self.index - 1]
			right = self.parse_comparison()
			expr = BinaryExpr(left=expr, op="&&", right=right, pos=(op.line, op.column))
		return expr

	def parse_comparison(self):
		expr = self.parse_addition()
		tok = self.current()
		if tok.kind in COMPARISON_KINDS:
			self._advance()
			right = self.parse_addition()
			if self.current().kind in COMPARISON_KINDS:
				self._error(self.current(), "Comparison chaining is not supported")
			expr = BinaryExpr(left=expr, op=tok.value, right=right, pos=(tok.line, tok.column))
		return expr

	def parse_addition(self):
		expr = self.parse_multiplication()
		while self._is("PLUS", "MINUS"):
			op = self._advance()
			right = self.parse_multiplication()
			expr = BinaryExpr(left=expr, op=op.value, right=right, pos=(op.line, op.column))
		return expr

	def parse_multiplication(self):
		expr = self.parse_unary()
		while self._is("STAR", "SLASH", "PERCENT"):
			op = self._advance()
			right = self.parse_unary()
			expr = BinaryExpr(left=expr, op=op.value, right=right, pos=(op.line, op.column))
		return expr

	def parse_unary(self):
		if self._is("NOT", "MINUS"):
			op = self._advance()
			operand = self.parse_unary()
			return UnaryExpr(op=op.value, operand=operand, pos=(op.line, op.column))
		return self.parse_concat()

	def parse_concat(self):
		first = self.parse_atom()
		parts = [first]
		while self._can_start_atom(self.current()):
			parts.append(self.parse_atom())
		if self._is("INCR", "DECR"):
			self._error(
				self.current(),
				"Increment/decrement are statement-level only, not expression-level",
			)
		if len(parts) == 1:
			return first
		return ConcatExpr(parts=tuple(parts), pos=first.pos)

	def parse_atom(self):
		tok = self.current()

		if tok.kind == "DOLLAR":
			return self.parse_field_ref()

		if tok.kind == "IDENT":
			ident = self._advance()
			if self._match("LPAREN"):
				if ident.value != "length":
					self._error(ident, f"Unsupported function: {ident.value}")
				args = []
				if not self._is("RPAREN"):
					args.append(self.parse_expression())
					while self._match("COMMA"):
						args.append(self.parse_expression())
				self._expect("RPAREN")
				return FunctionCall(
					name=ident.value,
					args=tuple(args),
					pos=(ident.line, ident.column),
				)
			if not ident.value[0].islower():
				msg = f"Identifier '{ident.value}' must be referenced as ${ident.value}"
				self._error(ident, msg)
			return VariableRef(name=ident.value, pos=(ident.line, ident.column))

		if tok.kind == "BUILTIN":
			built = self._advance()
			return BuiltinVar(name=built.value, pos=(built.line, built.column))

		if tok.kind == "STRING":
			lit = self._advance()
			return StringLiteral(value=lit.value, pos=(lit.line, lit.column))

		if tok.kind == "NUMBER":
			lit = self._advance()
			return NumberLiteral(value=float(lit.value), text=lit.value, pos=(lit.line, lit.column))

		if tok.kind == "REGEX":
			lit = self._advance()
			return RegexLiteral(pattern=lit.value, pos=(lit.line, lit.column))

		if tok.kind == "LPAREN":
			self._advance()
			expr = self.parse_expression()
			self._expect("RPAREN")
			return expr

		self._error(tok, f"Unexpected token in expression: {tok.kind}")

	def parse_field_ref(self) -> FieldRef:
		start = self._expect("DOLLAR")
		tok = self.current()
		if tok.kind == "NUMBER":
			num = self._advance()
			return FieldRef(index=int(num.value), pos=(start.line, start.column))
		if tok.kind == "IDENT":
			ident = self._advance()
			if ident.value[0].islower():
				return FieldRef(
					index=VariableRef(name=ident.value, pos=(ident.line, ident.column)),
					pos=(start.line, start.column),
				)
			return FieldRef(index=ident.value, pos=(start.line, start.column))
		if tok.kind == "BUILTIN":
			built = self._advance()
			return FieldRef(
				index=BuiltinVar(name=built.value, pos=(built.line, built.column)),
				pos=(start.line, start.column),
			)
		if tok.kind == "LPAREN":
			self._advance()
			expr = self.parse_expression()
			self._expect("RPAREN")
			return FieldRef(index=expr, pos=(start.line, start.column))
		self._error(tok, "Expected field reference after '$'")
		raise AssertionError("unreachable")

	def current(self) -> Token:
		return self.tokens[self.index]

	def _advance(self) -> Token:
		tok = self.tokens[self.index]
		self.index += 1
		return tok

	def _is(self, *kinds: str) -> bool:
		return self.current().kind in kinds

	def _match(self, *kinds: str) -> bool:
		if self._is(*kinds):
			self._advance()
			return True
		return False

	def _expect(self, kind: str) -> Token:
		tok = self.current()
		if tok.kind != kind:
			self._error(tok, f"Expected {kind}, found {tok.kind}")
		return self._advance()

	def _can_start_atom(self, tok: Token) -> bool:
		return tok.kind in {"DOLLAR", "IDENT", "BUILTIN", "STRING", "NUMBER", "REGEX", "LPAREN"}

	def _error(self, tok: Token, message: str) -> None:
		raise PythonAwkSyntaxError(
			message=message,
			line=tok.line,
			column=tok.column,
			source_excerpt=make_source_excerpt(self.source, tok.line, tok.column),
		)


def parse(tokens: list[Token], source: str) -> ProgramNode:
	return Parser(tokens=tokens, source=source).parse_program()
