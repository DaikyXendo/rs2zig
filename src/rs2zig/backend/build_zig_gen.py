"""
build.zig File Generator for rs2zig.

Generates Zig build scripts for converted projects targeting Zig 0.16.0.
"""

import logging
from typing import List, Optional

logger = logging.getLogger("rs2zig.backend.build_zig_gen")


def generate_build_zig(
    executable_name: str = "app",
    main_src: str = "main.zig",
    dependencies: Optional[List[str]] = None,
    target_wasm: bool = False
) -> str:
    """Generate content for a build.zig script targeting Zig 0.16.0.

    Args:
        executable_name: Name of target binary executable.
        main_src: Path to main Zig source file.
        dependencies: Optional list of external dependency module names.
        target_wasm: If True, generate build target for WASM32 freestanding.

    Returns:
        Generated build.zig file contents.
    """
    deps_list = dependencies or []

    if target_wasm:
        target_clause = """const target = b.resolveTargetQuery(.{
        .cpu_arch = .wasm32,
        .os_tag = .freestanding,
    });"""
    else:
        target_clause = "const target = b.standardTargetOptions(.{});"

    deps_code = ""
    if deps_list:
        deps_code = "\n" + "\n".join(
            f'    // Add dependency: {dep}\n    // exe.root_module.addImport("{dep}", b.dependency("{dep}", .{{}}).module("{dep}"));'
            for dep in deps_list
        )

    return f'''const std = @import("std");

pub fn build(b: *std.Build) void {{
    {target_clause}
    const optimize = b.standardOptimizeOption(.{{}});

    const exe = b.addExecutable(.{{
        .name = "{executable_name}",
        .root_module = b.createModule(.{{
            .root_source_file = b.path("{main_src}"),
            .target = target,
            .optimize = optimize,
        }}),
    }});{deps_code}

    b.installArtifact(exe);

    const run_cmd = b.addRunArtifact(exe);
    run_cmd.step.dependOn(b.getInstallStep());

    const run_step = b.step("run", "Run the application");
    run_step.dependOn(&run_cmd.step);
}}
'''
