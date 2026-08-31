from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

import yaml  # type: ignore[import-untyped]

from scripts import wiki_scaffold
from scripts.schema_contract import load_schema_contract
from scripts.validate_wiki import validate_wiki


class WikiScaffoldTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.parent = Path(self.temporary_directory.name)
        self.target = self.parent / ".project-wiki"
        self.contract = load_schema_contract()

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def invoke(self, *arguments: str) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        argv = [
            "wiki_scaffold.py",
            "create",
            "--wiki-root",
            str(self.target),
            *arguments,
        ]
        with patch.object(sys, "argv", argv), redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = wiki_scaffold.main()
        return exit_code, stdout.getvalue(), stderr.getvalue()

    def test_dry_run_reports_plan_without_writing(self) -> None:
        exit_code, stdout, stderr = self.invoke("--dry-run", "--format", "json")

        payload = json.loads(stdout)
        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr, "")
        self.assertFalse(os.path.lexists(self.target))
        self.assertEqual(payload["files"], len(self.contract.required_files))
        self.assertEqual(payload["actual_directories"], len(wiki_scaffold.expected_directories(self.contract)))
        self.assertFalse(payload["scaffold_created"])
        self.assertFalse(payload["project_initialization_complete"])
        self.assertFalse(payload["semantic_content_captured"])

    def test_create_publishes_complete_valid_placeholder_wiki(self) -> None:
        exit_code, stdout, stderr = self.invoke("--format", "json")

        payload = json.loads(stdout)
        report = validate_wiki(self.target)
        actual_files = {
            path.relative_to(self.target).as_posix()
            for path in self.target.rglob("*")
            if path.is_file()
        }
        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr, "")
        self.assertTrue(payload["scaffold_created"])
        self.assertEqual(payload["validation"], {"scaffold_contract": "passed", "wiki": "passed"})
        self.assertEqual(actual_files, set(self.contract.required_files))
        self.assertEqual(report.findings, ())
        self.assertTrue((self.target / "requirements" / "functional" / "INDEX.md").is_file())
        self.assertTrue((self.target / "requirements" / "non-functional" / "INDEX.md").is_file())
        self.assertFalse((self.target / "requirements" / "functional-requirements.md").exists())
        self.assertFalse((self.target / "requirements" / "non-functional-requirements.md").exists())

        wiki_version = yaml.safe_load((self.target / "WIKI_VERSION.yml").read_text(encoding="utf-8"))
        self.assertEqual(wiki_version["notes"], "Current schema applied.")
        requirement_evidence = yaml.safe_load(
            (self.target / "traceability" / "requirement-evidence.yml").read_text(encoding="utf-8")
        )
        self.assertEqual(requirement_evidence, {"version": 1, "records": {}})

        registry = yaml.safe_load((self.target / "REGISTRY.yml").read_text(encoding="utf-8"))
        expected_document_ids = {
            recipe.document_id
            for recipe in self.contract.scaffold.files.values()
            if recipe.recipe == "placeholder-document"
        }
        self.assertEqual({entry["id"] for entry in registry["documents"]}, expected_document_ids)
        for relative, recipe in self.contract.scaffold.files.items():
            if recipe.recipe != "placeholder-document":
                continue
            text = (self.target / relative).read_text(encoding="utf-8")
            metadata = yaml.safe_load(text.split("---", 2)[1])
            self.assertEqual(metadata["id"], recipe.document_id)
            self.assertEqual(metadata["type"], recipe.document_type)
            self.assertEqual(metadata["status"], "placeholder")
            self.assertEqual(metadata["confidence"], "unknown")

    def test_existing_target_is_preserved_and_stage_is_cleaned(self) -> None:
        self.target.mkdir()
        sentinel = self.target / "user-content.md"
        sentinel.write_text("keep me", encoding="utf-8")

        exit_code, stdout, stderr = self.invoke()

        self.assertEqual(exit_code, 2)
        self.assertEqual(stdout, "")
        self.assertIn("already exists", stderr)
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep me")
        self.assertEqual(list(self.parent.glob(".project-wiki.stage-*")), [])

    def test_empty_existing_target_is_refused(self) -> None:
        self.target.mkdir()

        exit_code, stdout, stderr = self.invoke()

        self.assertEqual(exit_code, 2)
        self.assertEqual(stdout, "")
        self.assertIn("already exists", stderr)
        self.assertTrue(self.target.is_dir())

    def test_broken_symlink_target_is_refused(self) -> None:
        self.target.symlink_to(self.parent / "missing", target_is_directory=True)

        exit_code, stdout, stderr = self.invoke()

        self.assertEqual(exit_code, 2)
        self.assertEqual(stdout, "")
        self.assertIn("already exists", stderr)
        self.assertTrue(self.target.is_symlink())

    def test_casefold_collision_is_refused(self) -> None:
        collision = self.parent / ".PROJECT-WIKI"
        collision.mkdir()

        exit_code, stdout, stderr = self.invoke()

        self.assertEqual(exit_code, 2)
        self.assertEqual(stdout, "")
        self.assertIn("collides by case", stderr)
        self.assertTrue(collision.is_dir())

    def test_generation_failure_cleans_stage_without_target(self) -> None:
        with patch.object(wiki_scaffold, "write_scaffold", side_effect=OSError("disk full")):
            exit_code, stdout, stderr = self.invoke()

        self.assertEqual(exit_code, 2)
        self.assertEqual(stdout, "")
        self.assertIn("disk full", stderr)
        self.assertFalse(os.path.lexists(self.target))
        self.assertEqual(list(self.parent.glob(".project-wiki.stage-*")), [])

    def test_scaffold_validation_failure_cleans_stage_without_target(self) -> None:
        with patch.object(
            wiki_scaffold,
            "validate_scaffold_stage",
            side_effect=wiki_scaffold.ScaffoldError("recipe mismatch"),
        ):
            exit_code, stdout, stderr = self.invoke()

        self.assertEqual(exit_code, 2)
        self.assertEqual(stdout, "")
        self.assertIn("recipe mismatch", stderr)
        self.assertFalse(os.path.lexists(self.target))
        self.assertEqual(list(self.parent.glob(".project-wiki.stage-*")), [])

    def test_unsupported_exclusive_publish_fails_before_staging(self) -> None:
        with patch.object(wiki_scaffold.platform, "system", return_value="UnsupportedOS"):
            exit_code, stdout, stderr = self.invoke()

        self.assertEqual(exit_code, 2)
        self.assertEqual(stdout, "")
        self.assertIn("refusing unsafe fallback", stderr)
        self.assertFalse(os.path.lexists(self.target))
        self.assertEqual(list(self.parent.glob(".project-wiki.stage-*")), [])

    def test_target_appearing_after_final_precheck_is_not_replaced(self) -> None:
        original = wiki_scaffold.validate_target_absent
        calls = 0

        def inject_race(target: Path) -> None:
            nonlocal calls
            calls += 1
            original(target)
            if calls == 3:
                target.mkdir()
                (target / "sentinel").write_text("external", encoding="utf-8")

        with patch.object(wiki_scaffold, "validate_target_absent", side_effect=inject_race):
            exit_code, stdout, stderr = self.invoke()

        self.assertEqual(exit_code, 2)
        self.assertEqual(stdout, "")
        self.assertIn("appeared during publication", stderr)
        self.assertEqual((self.target / "sentinel").read_text(encoding="utf-8"), "external")
        self.assertEqual(list(self.parent.glob(".project-wiki.stage-*")), [])

if __name__ == "__main__":
    unittest.main()