"""
build.zig File Generator for rs2zig.

Generates Zig build scripts for converted projects.
"""

import logging

logger = logging.getLogger("rs2zig.backend.build_zig_gen")


def generate_build_zig(executable_name: str = "app", main_src: str = "src/main.zig") -> str:
    """Generate content for a build.zig script targeting Zig 0.13/0.14/0.16.

    Args:
        executable_name: Name of target binary executable.
        main_src: Path to main Zig source file.

    Returns:
        Generated build.zig file contents.
    """
    return f'''const std = @import("std");

pub fn build(b: *std.Build) void {{
    const target = b.standardTargetOptions(.{{}});
    const optimize = b.standardOptimizeOption(.{{}});

    const exe = b.addExecutable(.{{
        .name = "{executable_name}",
        .root_source_file = b.path("{main_src}"),
        .target = target,
        .optimize = optimize,
    }});

    b.installArtifact(exe);

    const run_cmd = b.addRunArtifact(exe);
    run_cmd.step.dependOn(b.getInstallStep());

    const run_step = b.step("run", "Run the application");
    run_step.dependOn(&run_cmd.step);
}}
'''
