"""
Command Line Interface (CLI) for rs2zig.

Provides commands to convert Rust files to Zig, view ASTs, and validate outputs.
"""

import sys
import os
import argparse
import logging
from typing import Optional

from rs2zig import __version__
from rs2zig.frontend.ts_parser import RustParser
from rs2zig.frontend.ast_builder import ASTBuilder
from rs2zig.frontend.macro_expand import expand_macros
from rs2zig.lowering.ownership_pass import OwnershipPass
from rs2zig.lowering.trait_lowering import TraitLoweringPass
from rs2zig.lowering.bevy_lowering import BevyLoweringPass
from rs2zig.backend.zig_emitter import ZigEmitter
from rs2zig.validate.zig_fmt_check import ZigValidator

logger = logging.getLogger("rs2zig.cli")


def build_arg_parser() -> argparse.ArgumentParser:
    """Construct CLI argument parser.

    Returns:
        argparse.ArgumentParser instance.
    """
    parser = argparse.ArgumentParser(
        prog="rs2zig",
        description="Native Rust to Zig code converter/transpiler in Python."
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose debug logging")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # Convert subcommand
    convert_parser = subparsers.add_parser("convert", help="Convert Rust source file to Zig")
    convert_parser.add_argument("input", help="Path to input Rust (.rs) file")
    convert_parser.add_argument("-o", "--output", help="Path to output Zig (.zig) file")
    convert_parser.add_argument("--no-format", action="store_true", help="Skip running zig fmt on generated output")
    convert_parser.add_argument("--validate", action="store_true", help="Run zig ast-check / build-obj validation")
    convert_parser.add_argument("--no-expand", action="store_true", help="Skip macro expansion pass")

    # AST subcommand
    ast_parser = subparsers.add_parser("ast", help="Parse Rust source and dump internal IR AST")
    ast_parser.add_argument("input", help="Path to input Rust (.rs) file")

    return parser


def run_transpile(input_path: str, output_path: Optional[str] = None, format_code: bool = True, validate: bool = False, expand: bool = True) -> str:
    """Run full transpilation pipeline on input Rust file.

    Args:
        input_path: Path to input Rust source file.
        output_path: Optional path to write output Zig file.
        format_code: Whether to run `zig fmt` on generated output.
        validate: Whether to run Zig syntax validation.
        expand: Whether to run macro expansion step.

    Returns:
        Generated Zig source code string.
    """
    if not os.path.exists(input_path):
        logger.error("Input file not found: %s", input_path)
        raise FileNotFoundError(f"Input file not found: {input_path}")

    logger.info("Reading input file: %s", input_path)
    if expand:
        rust_code = expand_macros(input_path, is_file_path=True)
    else:
        with open(input_path, "r", encoding="utf-8") as file_handle:
            rust_code = file_handle.read()

    parser = RustParser()
    cst = parser.parse_code(rust_code)

    builder = ASTBuilder(rust_code.encode("utf-8"))
    ir_ast = builder.build_source_file(cst.root_node)

    ownership_pass = OwnershipPass()
    ownership_pass.lower_source_file(ir_ast)

    trait_pass = TraitLoweringPass()
    trait_pass.lower_source_file(ir_ast)

    bevy_pass = BevyLoweringPass()
    requires_bevy = bevy_pass.lower_source_file(ir_ast)

    emitter = ZigEmitter()
    emitter.requires_bevy_runtime = requires_bevy
    zig_code = emitter.emit_source_file(ir_ast)

    validator = ZigValidator()
    if format_code:
        zig_code = validator.format_code(zig_code)

    if validate:
        is_valid, msg = validator.check_syntax(zig_code)
        if is_valid:
            logger.info("Validation successful: %s", msg)
        else:
            logger.warning("Validation failed: %s", msg)

    if output_path:
        with open(output_path, "w", encoding="utf-8") as out_file:
            out_file.write(zig_code)
        logger.info("Wrote generated Zig code to %s", output_path)

    return zig_code


def main() -> None:
    """CLI application main entry point."""
    arg_parser = build_arg_parser()
    args = arg_parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )

    if args.command == "convert":
        try:
            zig_code = run_transpile(
                input_path=args.input,
                output_path=args.output,
                format_code=not args.no_format,
                validate=args.validate,
                expand=not args.no_expand
            )
            if not args.output:
                print(zig_code)
        except Exception as err:
            logger.error("Transpilation failed: %s", err)
            sys.exit(1)
    elif args.command == "ast":
        try:
            with open(args.input, "r", encoding="utf-8") as f:
                code = f.read()
            parser = RustParser()
            cst = parser.parse_code(code)
            builder = ASTBuilder(code.encode("utf-8"))
            ir_ast = builder.build_source_file(cst.root_node)
            print(ir_ast)
        except Exception as err:
            logger.error("AST extraction failed: %s", err)
            sys.exit(1)
    else:
        arg_parser.print_help()


if __name__ == "__main__":
    main()
