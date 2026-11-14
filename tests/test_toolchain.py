import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from maintainability_mcp.config import Config
from maintainability_mcp.toolchain import (
    DEFAULT_CLANG_TIDY_CHECKS,
    default_checks,
    detect_clang_version,
    resolve_executable,
    resolve_libclang,
    tool_environment,
)


class ToolchainTests(unittest.TestCase):
    def test_resolve_prefers_versioned(self):
        def which(name):
            return f"/usr/bin/{name}" if name in ("clang-tidy-22", "clang-tidy") else None

        with patch("shutil.which", side_effect=which):
            self.assertEqual(
                resolve_executable("clang-tidy", "22"),
                "/usr/bin/clang-tidy-22",
            )

    def test_resolve_falls_back_to_unversioned(self):
        def which(name):
            return "/usr/bin/cppcheck" if name == "cppcheck" else None

        with patch("shutil.which", side_effect=which):
            self.assertEqual(
                resolve_executable("cppcheck", "22"), "/usr/bin/cppcheck"
            )

    def test_detect_version_from_config(self):
        self.assertEqual(
            detect_clang_version(Config(clang_version="22")), "22"
        )

    def test_detect_version_scans_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name in ("clang-19", "clang-tidy-22"):
                path = Path(tmp) / name
                path.write_text("")
                path.chmod(0o755)
            with patch.dict(os.environ, {"PATH": tmp}, clear=False):
                self.assertEqual(
                    detect_clang_version(Config(clang_version=None)), "22"
                )

    def test_resolve_libclang_explicit(self):
        with tempfile.TemporaryDirectory() as tmp:
            library = Path(tmp) / "libclang.so"
            library.write_text("")
            config = Config(libclang_library=str(library))
            self.assertEqual(resolve_libclang(config), str(library))

    def test_tool_environment_strips_ld_library_path(self):
        with patch.dict(
            os.environ, {"LD_LIBRARY_PATH": "/bad", "KEEP": "yes"}, clear=False
        ):
            env = tool_environment(Config(clean_env=True))
            self.assertNotIn("LD_LIBRARY_PATH", env)
            self.assertEqual(env["KEEP"], "yes")

    def test_tool_environment_keeps_when_disabled(self):
        with patch.dict(os.environ, {"LD_LIBRARY_PATH": "/keep"}, clear=False):
            env = tool_environment(Config(clean_env=False))
            self.assertEqual(env["LD_LIBRARY_PATH"], "/keep")

    def test_default_checks_honors_project_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / ".clang-tidy").write_text("Checks: '*'\n")
            self.assertIsNone(default_checks(Config(), Path(tmp)))

    def test_default_checks_uses_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(
                default_checks(Config(), Path(tmp)), DEFAULT_CLANG_TIDY_CHECKS
            )


if __name__ == "__main__":
    unittest.main()
