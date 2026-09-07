"""
Golden Tests Runner for rs2zig.

Discovers and executes golden test cases comparing transpiled output to expected Zig files.
"""

import os
import unittest
from rs2zig.cli import run_transpile
from rs2zig.validate.zig_fmt_check import ZigValidator


class TestGolden(unittest.TestCase):
    """Test suite executing golden tests in tests/golden/."""

    def setUp(self) -> None:
        """Locate golden tests directory."""
        self.golden_dir = os.path.join(os.path.dirname(__file__), "golden")
        self.validator = ZigValidator()

    def test_golden_cases(self) -> None:
        """Run transpilation for each golden test case directory."""
        self.assertTrue(os.path.exists(self.golden_dir), "Golden tests directory missing")

        case_dirs = [
            os.path.join(self.golden_dir, d)
            for d in os.listdir(self.golden_dir)
            if os.path.isdir(os.path.join(self.golden_dir, d))
        ]

        for case_dir in sorted(case_dirs):
            case_name = os.path.basename(case_dir)
            input_file = os.path.join(case_dir, "input.rs")
            expected_file = os.path.join(case_dir, "expected.zig")

            self.assertTrue(os.path.exists(input_file), f"Missing input.rs in {case_name}")

            with self.subTest(case=case_name):
                generated_zig = run_transpile(
                    input_path=input_file,
                    format_code=True,
                    validate=True,
                    expand=False
                )

                # Validate syntax with Zig compiler
                is_valid, msg = self.validator.check_syntax(generated_zig)
                self.assertTrue(is_valid, f"Zig syntax check failed for {case_name}: {msg}")

                if os.path.exists(expected_file):
                    with open(expected_file, "r", encoding="utf-8") as f:
                        expected_zig = f.read()
                    self.assertEqual(
                        generated_zig.strip(),
                        expected_zig.strip(),
                        f"Generated Zig code mismatch in golden test {case_name}"
                    )


if __name__ == "__main__":
    unittest.main()
