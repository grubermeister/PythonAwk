from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ParityCase:
    id: str
    program: str
    input_rows: tuple[tuple[str, ...], ...]
    expected: tuple[tuple[str, ...] | None, ...]


PARITY_CASES: tuple[ParityCase, ...] = (
    ParityCase(
        id="select_reorder",
        program="{print $3, $1, $2}",
        input_rows=(("A", "B", "C"), ("1", "2", "3")),
        expected=(("C", "A", "B"), ("3", "1", "2")),
    ),
    ParityCase(
        id="filter_nonempty",
        program='$3 != "" {print $1, $2, $3}',
        input_rows=(("A", "B", "C"), ("X", "Y")),
        expected=(("A", "B", "C"), None),
    ),
    ParityCase(
        id="compound_condition",
        program='$3 != "" && $4 == "ACTIVE" {print $1, $2, $3}',
        input_rows=(("US", "123", "Widget", "ACTIVE"), ("US", "124", "Widget", "INACTIVE")),
        expected=(("US", "123", "Widget"), None),
    ),
    ParityCase(
        id="regex_filter",
        program='$2 ~ /^NSN/ || $2 ~ /^MIL/ {print $1, $2}',
        input_rows=(("US", "NSN123"), ("UK", "MIL333"), ("CA", "ABC")),
        expected=(("US", "NSN123"), ("UK", "MIL333"), None),
    ),
    ParityCase(
        id="merge_columns",
        program='{print $1 "-" $2, $3, $4}',
        input_rows=(("A", "B", "C", "D"),),
        expected=(("A-B", "C", "D"),),
    ),
    ParityCase(
        id="conditional_mutation",
        program='{if ($4 == "NMCRL") $5 = "AU-" $5; print $1, $2, $3, $4, $5}',
        input_rows=(("A", "B", "C", "NMCRL", "999"), ("D", "E", "F", "OTHER", "123")),
        expected=(("A", "B", "C", "NMCRL", "AU-999"), ("D", "E", "F", "OTHER", "123")),
    ),
    ParityCase(
        id="for_length",
        program='{for (i = 1; i <= NF; i++) if (length($i) > 4) $i = "LONG"; print $0}',
        input_rows=(("ALPHA", "BB", "CCCCCC"), ("AA", "BBB", "CC")),
        expected=(("LONG BB LONG",), ("AA BBB CC",)),
    ),
    ParityCase(
        id="derive_column",
        program='{$6 = $1 $2; print $1, $2, $3, $4, $5, $6}',
        input_rows=(("X", "Y", "1", "2", "3"),),
        expected=(("X", "Y", "1", "2", "3", "XY"),),
    ),
    ParityCase(
        id="substr_two_arg",
        program='{print substr($1, 3)}',
        input_rows=(("washington",), ("ab",)),
        expected=(("shington",), ("",)),
    ),
    ParityCase(
        id="substr_three_arg",
        program='{print substr($1, 5, 3)}',
        input_rows=(("washington",),),
        expected=(("ing",),),
    ),
    ParityCase(
        id="substr_clamp_negative_start",
        program='{print substr($1, -2, 5)}',
        input_rows=(("abcdef",),),
        expected=(("ab",),),
    ),
    ParityCase(
        id="if_else_block_no_semi_before_print",
        program=(
            '{'
            ' if ($1 == "Y") { x = "yes" } else { x = "no" }'
            ' print $1, x'
            '}'
        ),
        input_rows=(("Y",), ("N",)),
        expected=(("Y", "yes"), ("N", "no")),
    ),
)
