"""
Unit tests for Cargo.toml parsing and build.zig generation.
"""

import os
import tempfile
import unittest
from rs2zig.frontend.cargo_parser import parse_cargo_toml, CargoManifest
from rs2zig.backend.build_zig_gen import generate_build_zig
from rs2zig.cli import run_transpile_project


class TestCargoParserAndBuildGen(unittest.TestCase):
    """Test suite for Cargo.toml parser and build.zig generator."""

    def test_parse_cargo_toml(self) -> None:
        """Test parsing valid Cargo.toml content."""
        content = """
[package]
name = "my_bevy_game"
version = "0.2.0"
edition = "2021"

[dependencies]
bevy = "0.13"
serde = { version = "1.0", features = ["derive"] }
"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            cargo_path = os.path.join(tmp_dir, "Cargo.toml")
            with open(cargo_path, "w", encoding="utf-8") as f:
                f.write(content)

            manifest = parse_cargo_toml(cargo_path)
            self.assertIsNotNone(manifest)
            assert manifest is not None
            self.assertEqual(manifest.package.name, "my_bevy_game")
            self.assertIn("bevy", manifest.dependencies)
            self.assertIn("serde", manifest.dependencies)

    def test_generate_build_zig_wasm(self) -> None:
        """Test generating build.zig targeting WASM freestanding."""
        build_content = generate_build_zig(
            executable_name="my_bevy_game",
            main_src="main.zig",
            dependencies=["bevy", "serde"],
            target_wasm=True
        )
        self.assertIn('.cpu_arch = .wasm32', build_content)
        self.assertIn('.os_tag = .freestanding', build_content)
        self.assertIn('.name = "my_bevy_game"', build_content)


if __name__ == "__main__":
    unittest.main()
