from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.wiki_help import GUIDE_PATH


class WikiHelpTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="wiki-help-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.installation = self.root / "installed skill with spaces"
        (self.installation / "scripts").mkdir(parents=True)
        (self.installation / "assets").mkdir()
        self.script = self.installation / "scripts/wiki_help.py"
        self.guide = self.installation / "assets/user-help.md"
        shutil.copy2(GUIDE_PATH.parent.parent / "scripts/wiki_help.py", self.script)
        shutil.copy2(GUIDE_PATH, self.guide)
        self.project = self.root / "project"
        self.project.mkdir()

    def invoke(self, *arguments: str, cwd: Path | None = None,
               expected: int = 0) -> subprocess.CompletedProcess[str]:
        # Isolated mode with site packages disabled proves no helper dependencies are needed.
        result = subprocess.run(
            [sys.executable, "-I", "-S", "-B", str(self.script), *arguments],
            cwd=cwd or self.project,
            env=dict(os.environ, LANG="C", TERM="dumb"),
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        return result

    def snapshot(self) -> dict[str, tuple[bytes, int]]:
        return {
            path.relative_to(self.root).as_posix(): (path.read_bytes(), path.stat().st_mtime_ns)
            for path in self.root.rglob("*") if path.is_file()
        }

    def test_help_runs_isolated_without_writes(self) -> None:
        before = self.snapshot()
        result = self.invoke()
        self.assertEqual(result.stderr, "")
        self.assertEqual(result.stdout, self.guide.read_text().strip() + "\n")
        self.assertEqual(result.stdout, self.invoke(cwd=self.root).stdout)
        self.assertEqual(before, self.snapshot())

    def test_positional_arguments_are_rejected_without_mutation(self) -> None:
        before = self.snapshot()
        for arguments in (("config",), ("all",), ("unexpected", "argument")):
            with self.subTest(arguments=arguments):
                result = self.invoke(*arguments, expected=2)
                self.assertEqual(result.stdout, "")
                self.assertIn("unrecognized arguments", result.stderr)
        self.assertEqual(before, self.snapshot())

    def test_missing_or_invalid_guide_reports_an_error_without_writes(self) -> None:
        for content in (None, b"", b" \n\t", b"\xff\xfe"):
            with self.subTest(content=content):
                if content is None:
                    self.guide.unlink()
                else:
                    self.guide.write_bytes(content)
                before = self.snapshot()
                result = self.invoke(expected=2)
                self.assertEqual(result.stdout, "")
                self.assertIn("cannot load Project Wiki help", result.stderr)
                self.assertEqual(before, self.snapshot())


if __name__ == "__main__":
    unittest.main()
