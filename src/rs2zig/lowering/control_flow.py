"""
Control Flow Lowering Pass for rs2zig.

Handles Rust control flow constructs (for range loops, println! macros) and formats them into Zig constructs.
"""

import re
from typing import Tuple, List
from rs2zig.ir.nodes import MacroCallExpr, Expr, LiteralExpr


def split_macro_args(args_str: str) -> List[str]:
    """Split macro arguments respecting string literal boundaries.

    Args:
        args_str: Inside of macro call arguments.

    Returns:
        List of argument string tokens.
    """
    args: List[str] = []
    current: List[str] = []
    in_string = False
    escaped = False

    for char in args_str:
        if char == '"' and not escaped:
            in_string = not in_string
            current.append(char)
        elif char == '\\' and in_string:
            escaped = not escaped
            current.append(char)
        elif char == ',' and not in_string:
            args.append("".join(current).strip())
            current = []
        else:
            if escaped:
                escaped = False
            current.append(char)

    if current:
        args.append("".join(current).strip())

    return [a for a in args if a]


def lower_println_macro(macro_expr: MacroCallExpr) -> Tuple[str, List[Expr]]:
    """Lower Rust println! / print! macro call into Zig std.debug.print format and args.

    Args:
        macro_expr: Input MacroCallExpr node.

    Returns:
        Tuple containing Zig format string and list of argument expressions.
    """
    raw_str = macro_expr.raw_args_str.strip()
    match = re.search(r'\((.*)\)', raw_str, re.DOTALL)
    if not match:
        return ("\\n", [])

    inner_content = match.group(1).strip()
    if not inner_content:
        return ("\\n", [])

    parts = split_macro_args(inner_content)
    format_arg = parts[0] if parts else '""'

    # Clean format string quotes
    fmt_str = format_arg.strip('"')
    if macro_expr.macro_name == "println":
        fmt_str += "\\n"

    # Replace Rust format specifiers {} with Zig format specifiers {d}
    fmt_str = fmt_str.replace("{}", "{d}")

    # Build arg list (ignoring the format string argument itself)
    arg_exprs: List[Expr] = [LiteralExpr(value=p, kind="identifier") for p in parts[1:]]

    return (fmt_str, arg_exprs)
