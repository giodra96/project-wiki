"""Exercise the actual CLI entrypoints in disposable repositories."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


class WikiConfigIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="wiki-config-integration-")
        self.addCleanup(temporary.cleanup)
        self.repository = Path(temporary.name) / "project with spaces"
        self.repository.mkdir()
        self.wiki = self.repository / ".project-wiki"

    def run_cli(self, script: str, *arguments: str, expected: int = 0) -> subprocess.CompletedProcess[str]:
        environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        result = subprocess.run(
            [sys.executable, "-B", str(SCRIPTS / script), *arguments],
            cwd=self.repository,
            env=environment,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        return result

    def scaffold(self) -> None:
        result = self.run_cli("wiki_scaffold.py", "create", "--format", "json")
        self.assertTrue(json.loads(result.stdout)["scaffold_created"])

    def config(self, *arguments: str, expected: int = 0) -> subprocess.CompletedProcess[str]:
        return self.run_cli("wiki_config.py", *arguments, expected=expected)

    def snapshot(self) -> dict[str, tuple[str, int, int]]:
        # Include metadata to catch a write that restores identical file content.
        return {
            path.relative_to(self.repository).as_posix(): (
                hashlib.sha256(path.read_bytes()).hexdigest(),
                path.stat().st_mtime_ns,
                path.stat().st_ino,
            )
            for path in self.repository.rglob("*")
            if path.is_file()
        }

    def validate(self, expected: int = 0) -> dict:
        result = self.run_cli("validate_wiki.py", "--wiki-root", str(self.wiki),
                              "--format", "json", expected=expected)
        return json.loads(result.stdout)

    def test_fresh_scaffold_toggle_and_validation_touch_only_configuration(self) -> None:
        self.scaffold()
        self.assertTrue(json.loads(self.config("show").stdout)["config"]["automation"]["auto_sync"])
        initial = self.snapshot()
        for value in ("false", "true"):
            with self.subTest(value=value):
                result = json.loads(self.config("set", "automation.auto_sync", value).stdout)
                self.assertTrue(result["changed"])
                self.assertEqual(result["source"], "file")
                self.assertEqual(result["config"]["automation"]["auto_sync"], value == "true")
                current = self.snapshot()
                self.assertEqual(set(initial), set(current))
                self.assertEqual(
                    {key for key in initial if initial[key] != current[key]},
                    {".project-wiki/config.yml"},
                )
                self.validate()
                self.config("show")
                self.assertEqual(current, self.snapshot())
                initial = current

    def test_legacy_wiki_uses_defaults_without_migration_or_writes(self) -> None:
        self.scaffold()
        (self.wiki / "config.yml").unlink()
        before = self.snapshot()
        result = json.loads(self.config("show").stdout)
        self.assertEqual(result["source"], "defaults")
        self.assertIs(result["config"]["automation"]["auto_sync"], True)
        self.validate()
        self.assertEqual(before, self.snapshot())

    def test_noop_set_preserves_user_comments_and_file_metadata(self) -> None:
        self.scaffold()
        config = self.wiki / "config.yml"
        config.write_text(config.read_text() + "# Preserve my comment.\n", encoding="utf-8")
        before = self.snapshot()
        result = json.loads(self.config("set", "automation.auto_sync", "true").stdout)
        self.assertFalse(result["changed"])
        self.assertEqual(before, self.snapshot())

    def test_invalid_config_reports_errors_and_is_preserved_by_all_entrypoints(self) -> None:
        self.scaffold()
        for content in (
            b"config_version: 1\nautomation: {auto_sync: 'false'}\n",
            b"config_version: 1\nautomation: {auto_sync: false, auto_sync: true}\n",
            b"config_version: 2\nautomation: {auto_sync: false}\n",
            b"config_version: 1\nautomation: [\n",
            b"\xff\xfe\x00",
        ):
            with self.subTest(content=content):
                (self.wiki / "config.yml").write_bytes(content)
                before = self.snapshot()
                for args in (("show",), ("set", "automation.auto_sync", "true")):
                    result = self.config(*args, expected=2)
                    self.assertEqual(result.stdout, "")
                    self.assertIn("automatic wiki writes must be suspended", result.stderr)
                    self.assertEqual(before, self.snapshot())
                report = self.validate(expected=1)
                self.assertIn("wiki-config-invalid", {item["code"] for item in report["findings"]})
                self.assertEqual(before, self.snapshot())

    def test_invalid_command_never_creates_or_changes_a_wiki(self) -> None:
        before = self.snapshot()
        self.config("set", "automation.auto_sync", "false", expected=2)
        self.config("set", "automation.auto_sync", "maybe", expected=2)
        self.config("set", "automation.auto_syncc", "false", expected=2)
        self.assertEqual(before, self.snapshot())
        self.assertFalse(self.wiki.exists())


if __name__ == "__main__":
    unittest.main()
