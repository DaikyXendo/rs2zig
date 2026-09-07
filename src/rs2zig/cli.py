"""
Command Line Interface (CLI) for rs2zig.

Provides commands to convert Rust files and multi-module projects to Zig, view ASTs, and validate outputs.
"""

import sys
import os
import argparse
import logging
from typing import Optional, List, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

from rs2zig import __version__
from rs2zig.frontend.ts_parser import RustParser
from rs2zig.frontend.ast_builder import ASTBuilder
from rs2zig.frontend.macro_expand import expand_macros
from rs2zig.frontend.mod_resolver import ModuleResolver
from rs2zig.lowering.ownership_pass import OwnershipPass
from rs2zig.lowering.trait_lowering import TraitLoweringPass
from rs2zig.lowering.bevy_lowering import BevyLoweringPass
from rs2zig.frontend.cargo_parser import parse_cargo_toml
from rs2zig.backend.zig_emitter import ZigEmitter
from rs2zig.backend.build_zig_gen import generate_build_zig
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

    # Convert single file subcommand
    convert_parser = subparsers.add_parser("convert", help="Convert single Rust source file to Zig")
    convert_parser.add_argument("input", help="Path to input Rust (.rs) file")
    convert_parser.add_argument("-o", "--output", help="Path to output Zig (.zig) file")
    convert_parser.add_argument("--no-format", action="store_true", help="Skip running zig fmt on generated output")
    convert_parser.add_argument("--validate", action="store_true", help="Run zig ast-check / build-obj validation")
    convert_parser.add_argument("--no-expand", action="store_true", help="Skip macro expansion pass")

    project_parser = subparsers.add_parser("convert-project", help="Convert multi-module Rust project directory to Zig in parallel")
    project_parser.add_argument("project_dir", help="Path to input Rust project directory")
    project_parser.add_argument("-o", "--output-dir", required=True, help="Path to output directory for Zig files & build.zig")
    project_parser.add_argument("-j", "--jobs", type=int, default=os.cpu_count() or 4, help="Number of parallel worker threads (default CPU count)")
    project_parser.add_argument("--wasm", action="store_true", help="Generate build target for WASM32 freestanding")

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
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as out_file:
            out_file.write(zig_code)
        logger.info("Wrote generated Zig code to %s", output_path)

    return zig_code


def _transpile_worker(task_tuple: Tuple[str, str]) -> str:
    """Worker task function for parallel project transpilation."""
    rs_file, target_out = task_tuple
    return run_transpile(input_path=rs_file, output_path=target_out, format_code=True, validate=True, expand=False)


def run_transpile_project(project_dir: str, output_dir: str, jobs: int = 4, target_wasm: bool = False) -> List[str]:
    """Transpile a multi-module Rust project directory concurrently using multithreading.

    Args:
        project_dir: Input Rust project directory path.
        output_dir: Target output directory path.
        jobs: Number of parallel worker threads.
        target_wasm: Whether to target WASM32 freestanding in build.zig.

    Returns:
        List of generated Zig file paths.
    """
    resolver = ModuleResolver()
    rs_files = resolver.discover_project_files(project_dir)
    generated_files: List[str] = []

    os.makedirs(output_dir, exist_ok=True)

    tasks: List[Tuple[str, str]] = []
    for rs_file in rs_files:
        rel_path = os.path.relpath(rs_file, project_dir)
        zig_rel_path = os.path.splitext(rel_path)[0] + ".zig"
        target_out = os.path.join(output_dir, zig_rel_path)
        tasks.append((rs_file, target_out))

    logger.info("Starting multithreaded project transpilation across %d worker threads...", jobs)
    with ThreadPoolExecutor(max_workers=jobs) as executor:
        futures = {executor.submit(_transpile_worker, t): t[1] for t in tasks}
        for future in as_completed(futures):
            target_out = futures[future]
            try:
                future.result()
                generated_files.append(target_out)
            except Exception as err:
                logger.error("Failed to transpile file %s: %s", target_out, err)

    # Parse Cargo.toml if available
    app_name = "app"
    dependencies: List[str] = []
    cargo_file = os.path.join(project_dir, "Cargo.toml")
    manifest = parse_cargo_toml(cargo_file)
    if manifest:
        app_name = manifest.package.name
        dependencies = list(manifest.dependencies.keys())

    # Generate build.zig
    build_zig_content = generate_build_zig(
        executable_name=app_name,
        main_src="main.zig",
        dependencies=dependencies,
        target_wasm=target_wasm
    )
    build_zig_path = os.path.join(output_dir, "build.zig")
    with open(build_zig_path, "w", encoding="utf-8") as f:
        f.write(build_zig_content)
    generated_files.append(build_zig_path)

    logger.info("Multithreaded project transpilation complete. Generated %d files in %s", len(generated_files), output_dir)
    return generated_files


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
    elif args.command == "convert-project":
        try:
            jobs_cnt = getattr(args, "jobs", os.cpu_count() or 4)
            wasm_flag = getattr(args, "wasm", False)
            run_transpile_project(args.project_dir, args.output_dir, jobs=jobs_cnt, target_wasm=wasm_flag)
        except Exception as err:
            logger.error("Project transpilation failed: %s", err)
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
