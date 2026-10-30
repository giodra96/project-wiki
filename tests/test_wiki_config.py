from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from scripts import wiki_config
from scripts.validate_wiki import validate_wiki
from tests.wiki_fixtures import create_valid_wiki


class WikiConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / ".project-wiki"
        self.root.mkdir()
        self.path = self.root / "config.yml"

    def invoke(self, *arguments: str) -> tuple[int, str, str]:
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.object(sys, "argv", ["wiki_config.py", "--wiki-root", str(self.root), *arguments]), \
                redirect_stdout(stdout), redirect_stderr(stderr):
            status = wiki_config.main()
        return status, stdout.getvalue(), stderr.getvalue()

    def test_missing_config_uses_defaults_without_writing(self) -> None:
        status, stdout, stderr = self.invoke("show")
        self.assertEqual((status, stderr), (0, ""))
        self.assertEqual(json.loads(stdout), {"config": wiki_config.default_config(), "source": "defaults"})
        self.assertEqual(list(self.root.iterdir()), [])

    def test_toggle_changes_only_config_and_same_value_preserves_comments(self) -> None:
        sentinel = self.root / "STATUS.md"
        sentinel.write_text("unchanged", encoding="utf-8")
        for enabled in (False, True):
            status, stdout, stderr = self.invoke("set", "automation.auto_sync", str(enabled).lower())
            self.assertEqual((status, stderr), (0, ""))
            self.assertTrue(json.loads(stdout)["changed"])
            self.assertEqual(wiki_config.read_config(self.root)["automation"]["auto_sync"], enabled)
        content = self.path.read_text() + "# user comment\n"
        self.path.write_text(content)
        status, stdout, stderr = self.invoke("set", "automation.auto_sync", "true")
        self.assertEqual((status, stderr), (0, ""))
        self.assertFalse(json.loads(stdout)["changed"])
        self.assertEqual(self.path.read_text(), content)
        self.assertEqual(sentinel.read_text(), "unchanged")
        self.assertEqual({path.name for path in self.root.iterdir()}, {"config.yml", "STATUS.md"})

    def test_invalid_config_is_never_overwritten_or_silently_enabled(self) -> None:
        invalid = (
            "",
            "[]",
            "config_version: 2\nautomation: {auto_sync: false}",
            "config_version: true\nautomation: {auto_sync: false}",
            "config_version: 1\nautomation: {auto_sync: 'false'}",
            "config_version: 1\nautomation: {auto_sync: 0}",
            "config_version: 1\nautomation: {auto_sync: null}",
            "config_version: 1\nautomation: {auto_syncc: false}",
            "config_version: 1\nautomation: {auto_sync: false}\nextra: true",
            "config_version: 1\nautomation: {auto_sync: false, auto_sync: true}",
            "config_version: 1\nautomation: [",
        )
        for content in invalid:
            with self.subTest(content=content):
                self.path.write_text(content)
                for arguments in (("show",), ("set", "automation.auto_sync", "true")):
                    status, stdout, stderr = self.invoke(*arguments)
                    self.assertEqual(status, 2)
                    self.assertEqual(stdout, "")
                    self.assertIn("automatic wiki writes must be suspended", stderr)
                    self.assertEqual(self.path.read_text(), content)

    def test_symlink_and_directory_are_rejected(self) -> None:
        target = self.root.parent / "external.yml"
        target.write_text(wiki_config.render_config(wiki_config.default_config()))
        self.path.symlink_to(target)
        status, _, _ = self.invoke("set", "automation.auto_sync", "false")
        self.assertEqual(status, 2)
        self.assertTrue(self.path.is_symlink())
        self.assertTrue(wiki_config.read_config(self.root.parent)["automation"]["auto_sync"])
        self.assertEqual(target.read_text(), wiki_config.render_config(wiki_config.default_config()))
        self.path.unlink()
        self.path.mkdir()
        self.assertEqual(self.invoke("show")[0], 2)

    def test_failed_atomic_write_preserves_existing_config_and_cleans_temp(self) -> None:
        original = wiki_config.render_config(wiki_config.default_config())
        self.path.write_text(original)
        with patch.object(wiki_config.os, "replace", side_effect=OSError("test write failure")):
            self.assertEqual(self.invoke("set", "automation.auto_sync", "false")[0], 2)
        self.assertEqual(self.path.read_text(), original)
        self.assertEqual(list(self.root.glob(".config-*")), [])

    def test_set_refuses_absent_wiki(self) -> None:
        self.root.rmdir()
        self.assertEqual(self.invoke("set", "automation.auto_sync", "false")[0], 2)
        self.assertFalse(self.root.exists())

    def test_validation_accepts_legacy_and_disabled_config_but_reports_invalid(self) -> None:
        create_valid_wiki(self.root)
        self.assertTrue(validate_wiki(self.root).valid)
        wiki_config.set_auto_sync(self.root, False)
        self.assertTrue(validate_wiki(self.root).valid)
        self.path.write_text("config_version: 1\nautomation: {auto_sync: 'false'}")
        self.assertIn("wiki-config-invalid", {item.code for item in validate_wiki(self.root).findings})


if __name__ == "__main__":
    unittest.main()
