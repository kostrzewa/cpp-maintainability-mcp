import tempfile
import unittest
from pathlib import Path

from cpp_maintainability_mcp.analyzers.duplication import DuplicationAnalyzer


class DuplicationTests(unittest.TestCase):
    def test_duplicate_block_across_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = Path(tmp) / "a.cpp"
            second = Path(tmp) / "b.cpp"
            block = "\n".join(f"int value{i} = {i};" for i in range(8))
            first.write_text(block + "\nint unique_a = 1;\n")
            second.write_text(block + "\nint unique_b = 2;\n")
            results, findings = DuplicationAnalyzer().analyze_files(
                [first, second]
            )
            self.assertTrue(findings)
            self.assertGreater(results[str(first)].metrics["duplication"], 0.0)
            self.assertGreater(results[str(second)].metrics["duplication"], 0.0)

    def test_unique_files_have_no_duplication(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = Path(tmp) / "a.cpp"
            second = Path(tmp) / "b.cpp"
            first.write_text("\n".join(f"int a{i} = {i};" for i in range(8)))
            second.write_text("\n".join(f"int b{i} = {i};" for i in range(8)))
            results, findings = DuplicationAnalyzer().analyze_files(
                [first, second]
            )
            self.assertFalse(findings)
            self.assertEqual(results[str(first)].metrics["duplication"], 0.0)

    def test_adjacent_windows_merge_into_one_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = Path(tmp) / "a.cpp"
            second = Path(tmp) / "b.cpp"
            block = "\n".join(f"int value{i} = {i};" for i in range(20))
            first.write_text(block + "\n")
            second.write_text(block + "\n")
            _, findings = DuplicationAnalyzer().analyze_files([first, second])
            self.assertEqual(len(findings), 2)
            self.assertTrue(
                all(
                    finding.end_line - finding.start_line + 1 >= 20
                    for finding in findings
                )
            )

    def test_duplicate_comment_blocks_are_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = Path(tmp) / "a.cpp"
            second = Path(tmp) / "b.cpp"
            comment = """/**
 * @brief Shared documentation
 * @param value The value
 * @return The result
 * @details More details
 */"""
            first.write_text(comment + "\nint a() { return 1; }\n")
            second.write_text(comment + "\nint b() { return 2; }\n")
            _, findings = DuplicationAnalyzer().analyze_files([first, second])
            self.assertFalse(findings)


if __name__ == "__main__":
    unittest.main()
