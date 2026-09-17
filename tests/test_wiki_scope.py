from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

import yaml

from scripts import check_inbox, ingest_document, wiki_scaffold, wiki_scope
from scripts.validate_wiki import validate_wiki
from tests.wiki_fixtures import create_valid_wiki


class WikiScopeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.repo = Path(self.temporary.name)
        self.wiki = self.repo / ".project-wiki"
        self.wiki.mkdir()

    def scope(self, rules: str) -> wiki_scope.WikiScope:
        (self.wiki / ".wikiignore").write_text(rules, encoding="utf-8")
        return wiki_scope.WikiScope(self.wiki)

    def invoke(self, *arguments: str) -> tuple[int, str, str]:
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.object(sys, "argv", ["wiki_scope.py", *arguments, "--wiki-root", str(self.wiki)]), \
             redirect_stdout(stdout), redirect_stderr(stderr):
            code = wiki_scope.main()
        return code, stdout.getvalue(), stderr.getvalue()

    def git(self, *arguments: str) -> None:
        subprocess.run(["git", *arguments], cwd=self.repo, check=True, capture_output=True)

    def test_matcher_is_initialized_once_for_multiple_batches(self) -> None:
        with self.scope("private/\n") as scope, patch.object(wiki_scope.subprocess, "run", wraps=subprocess.run) as run:
            self.assertTrue(scope.ignored("private/a.py"))
            self.assertFalse(scope.ignored("public/b.py"))
            self.assertTrue(scope.ignored("private/a.py"))
            self.assertEqual(sum("init" in call.args[0] for call in run.call_args_list), 1)
        self.assertIsNone(scope._matcher)

    def test_read_omits_excluded_sources_before_content_access(self) -> None:
        self.scope("private/\n")
        (self.repo / "private").mkdir()
        secret = self.repo / "private/a.py"
        secret.write_text("secret content")
        public = self.repo / "public.py"
        public.write_text("first\nsecond\nthird\n")
        original = Path.read_text

        def guarded(path, *arguments, **options):
            self.assertNotEqual(path.resolve(), secret.resolve())
            return original(path, *arguments, **options)

        with patch.object(Path, "read_text", guarded):
            code, output, error = self.invoke("read", "private/a.py", "public.py", "--start-line", "2", "--end-line", "2", "--format", "json")
        self.assertEqual((code, error), (0, ""))
        self.assertEqual(json.loads(output), {"documents": [{"path": "public.py", "content": "second\n"}]})
        self.assertNotIn("private", output)

    def test_read_cannot_bypass_exclusions_through_symlinks(self) -> None:
        secret = self.repo / "secret.py"
        secret.write_text("secret")
        (self.repo / "alias.py").symlink_to(secret)
        with self.scope("/secret.py\n") as scope:
            self.assertIsNone(scope.read_source("alias.py"))

    def test_search_prunes_excluded_sources_and_limits_output(self) -> None:
        self.scope("private/\n")
        (self.repo / "private").mkdir()
        (self.repo / "private/a.py").write_text("needle SECRET")
        (self.repo / "public.py").write_text("needle first\nneedle second\n")
        code, output, error = self.invoke("search", "--pattern", "needle", "--limit", "1", "--format", "json")
        self.assertEqual((code, error), (0, ""))
        self.assertEqual(json.loads(output), {"matches": [{"path": "public.py", "line": 1, "text": "needle first"}]})
        self.assertNotIn("SECRET", output)

    def test_list_can_be_narrowed_to_relevant_sources(self) -> None:
        self.scope("")
        (self.repo / "src").mkdir()
        (self.repo / "src/main.py").write_text("")
        (self.repo / "unrelated.py").write_text("")
        code, output, error = self.invoke("list", "src", "--format", "json")
        self.assertEqual((code, error), (0, ""))
        self.assertEqual(json.loads(output), {"paths": ["src/main.py"]})

    def test_diff_omits_ignored_changes_and_deletions(self) -> None:
        self.git("init", "--quiet")
        (self.repo / "private.py").write_text("secret before\n")
        (self.repo / "public.py").write_text("before\n")
        self.git("add", "private.py", "public.py")
        self.git("-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "--quiet", "-m", "fixture")
        (self.repo / "private.py").unlink()
        (self.repo / "public.py").write_text("after\n")
        self.scope("/private.py\n")
        code, output, error = self.invoke("diff", "--base", "HEAD")
        self.assertEqual((code, error), (0, ""))
        self.assertIn("+after", output)
        self.assertNotIn("private.py", output)
        self.assertNotIn("secret", output)

    def test_diff_filters_paths_before_invoking_diff(self) -> None:
        self.git("init", "--quiet")
        (self.repo / "private.py").write_text("secret")
        (self.repo / "public.py").write_text("public")
        self.git("add", "private.py", "public.py")
        (self.repo / "private.py").write_text("new secret")
        (self.repo / "public.py").write_text("new public")
        original = subprocess.run

        def guarded(command, *arguments, **options):
            if "diff" in command:
                self.assertIn("--", command)
                self.assertEqual(command[command.index("--") + 1:], ["public.py"])
            return original(command, *arguments, **options)

        with self.scope("/private.py\n") as scope, patch.object(wiki_scope.subprocess, "run", side_effect=guarded):
            self.assertIn("new public", scope.source_diff([]))

    def test_staged_diff_supports_unborn_repository(self) -> None:
        self.git("init", "--quiet")
        (self.repo / "public.py").write_text("new public")
        self.git("add", "public.py")
        with self.scope("") as scope:
            self.assertIn("+new public", scope.source_diff([], cached=True))

    def test_binary_reads_emit_no_content(self) -> None:
        (self.repo / "binary.dat").write_bytes(b"text\0binary")
        with self.scope("") as scope:
            self.assertIsNone(scope.read_source("binary.dat"))

    def test_diff_does_not_expose_ignored_side_of_rename(self) -> None:
        self.git("init", "--quiet")
        (self.repo / "old.py").write_text("secret before\n")
        self.git("add", "old.py")
        self.git("-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "--quiet", "-m", "fixture")
        self.git("mv", "old.py", "new.py")
        (self.repo / "new.py").write_text("public after\n")
        self.git("add", "new.py")
        self.scope("/old.py\n")
        code, output, error = self.invoke("diff", "--cached")
        self.assertEqual((code, error), (0, ""))
        self.assertIn("+public after", output)
        self.assertNotIn("old.py", output)
        self.assertNotIn("secret before", output)

    def test_source_commands_do_not_fall_back_after_scope_failure(self) -> None:
        self.scope("private/\n")
        (self.repo / "public.py").write_text("content")
        with patch.object(wiki_scope.subprocess, "run", side_effect=FileNotFoundError):
            code, output, _ = self.invoke("read", "public.py")
        self.assertEqual(code, 2)
        self.assertEqual(output, "")

    def test_missing_rules_need_no_git_and_include_all_paths(self) -> None:
        with patch.object(wiki_scope.subprocess, "run", side_effect=AssertionError("unexpected Git call")):
            self.assertEqual(wiki_scope.WikiScope(self.wiki).ignored_many(["src/main.py", "gone.py"]), [False, False])

    def test_comments_only_configuration_needs_no_git(self) -> None:
        scope = self.scope("# /vendor/\n\n   \n")
        with patch.object(wiki_scope.subprocess, "run", side_effect=AssertionError("unexpected Git call")):
            self.assertFalse(scope.ignored("vendor/main.py"))

    def test_anchoring_directory_rules_and_wildcards(self) -> None:
        scope = self.scope("/vendor/\n*.min.js\ncache/\nsrc/**/generated?.[ch]\n")
        paths = ["vendor/a.py", "src/vendor/a.py", "app/a.min.js", "src/cache/a", "src/deep/generated1.c", "src/main.c"]
        self.assertEqual(scope.ignored_many(paths), [True, False, True, True, True, False])

    def test_git_negations_and_parent_directory_semantics(self) -> None:
        scope = self.scope("/legacy/*\n!/legacy/README.md\n/hidden/\n!/hidden/keep.md\n")
        self.assertEqual(scope.ignored_many(["legacy/a.py", "legacy/README.md", "hidden/keep.md"]), [True, False, True])

    def test_escapes_spaces_and_case_sensitive_paths(self) -> None:
        scope = self.scope("# comment\n\\#secret\n\\!secret\nspace\\ \nCase.txt\n")
        self.assertEqual(scope.ignored_many(["#secret", "!secret", "space ", "Case.txt", "case.txt"]), [True, True, True, True, False])

    def test_later_rules_override_and_deleted_paths_are_filtered(self) -> None:
        scope = self.scope("*.log\n!keep.log\nkeep.log\n")
        self.assertEqual(scope.ignored_many(["deleted.log", "keep.log", "src/main.py"]), [True, True, False])

    def test_source_discovery_prunes_before_entering_excluded_directory(self) -> None:
        excluded = self.repo / "private"
        excluded.mkdir()
        (excluded / "secret.txt").write_text("secret")
        (self.repo / "keep.py").write_text("public")
        scope = self.scope("/private/\n")
        original = os.scandir

        def guarded(path):
            if not isinstance(path, int):
                self.assertNotEqual(Path(path), excluded)
            return original(path)

        with patch.object(wiki_scope.os, "scandir", side_effect=guarded):
            self.assertEqual(list(scope.source_files()), [self.repo / "keep.py"])

    def test_gitignore_and_nested_wikiignore_do_not_change_scope(self) -> None:
        (self.repo / ".gitignore").write_text("keep.py\n")
        (self.repo / "src").mkdir()
        (self.repo / "src" / ".wikiignore").write_text("main.py\n")
        scope = self.scope("/vendor/\n")
        self.assertEqual(scope.ignored_many(["keep.py", "src/main.py"]), [False, False])

    def test_exclusions_apply_to_git_tracked_files(self) -> None:
        subprocess.run(["git", "init", "--quiet", str(self.repo)], check=True)
        (self.repo / "tracked.py").write_text("tracked content")
        subprocess.run(["git", "add", "tracked.py"], cwd=self.repo, check=True)
        scope = self.scope("/tracked.py\n")
        self.assertTrue(scope.ignored("tracked.py"))

    def test_nonempty_rules_fail_closed_when_git_is_unavailable(self) -> None:
        scope = self.scope("private/\n")
        with patch.object(wiki_scope.subprocess, "run", side_effect=FileNotFoundError):
            with self.assertRaises(wiki_scope.WikiScopeError):
                scope.ignored("private/a.py")

    def test_unsafe_paths_are_rejected(self) -> None:
        scope = self.scope("")
        for path in ["../outside", "a/../outside", "a\0b", "/outside"]:
            with self.subTest(path=path), self.assertRaises(wiki_scope.WikiScopeError):
                scope.ignored(path)

    def test_new_scaffold_has_comments_only_configuration(self) -> None:
        contents = wiki_scaffold.build_scaffold_contents(wiki_scaffold.load_schema_contract(), "2026-09-17")
        rules = contents[".wikiignore"]
        self.assertTrue(rules)
        self.assertTrue(all(not line or line.startswith("#") for line in rules.splitlines()))

    def test_missing_historical_source_is_preserved_without_warning(self) -> None:
        ids = create_valid_wiki(self.wiki)
        owner = next(iter(ids))
        source_paths = ["legacy/deleted.py"]
        path = self.wiki / owner
        path.write_text(path.read_text().replace("source_paths: []", "source_paths: [legacy/deleted.py]"))
        registry_path = self.wiki / "REGISTRY.yml"
        registry = yaml.safe_load(registry_path.read_text())
        next(entry for entry in registry["documents"] if entry["path"] == owner)["source_paths"] = source_paths
        registry_path.write_text(yaml.safe_dump(registry))
        self.scope("/legacy/\n")
        previous = path.read_bytes()
        self.assertEqual(validate_wiki(self.wiki).findings, ())
        self.assertEqual(path.read_bytes(), previous)
        self.scope("")
        self.assertIn("source-path-missing", {finding.code for finding in validate_wiki(self.wiki).findings})

    def test_ignored_patterns_do_not_disable_canonical_validation(self) -> None:
        create_valid_wiki(self.wiki)
        self.scope("*\n")
        (self.wiki / "PROJECT.md").write_text("Missing required frontmatter")
        self.assertIn("frontmatter-missing", {finding.code for finding in validate_wiki(self.wiki).findings})

    def test_excluded_inbox_sources_are_not_hashed_reported_or_quarantined(self) -> None:
        create_valid_wiki(self.wiki)
        source = self.wiki / "sources/inbox/secret.md"
        source.write_text("secret")
        self.scope("/.project-wiki/sources/inbox/secret.md\n")
        with patch.object(check_inbox, "inspect_inbox_file", side_effect=AssertionError("excluded source read")):
            report = check_inbox.check_inbox(self.wiki)
            report = check_inbox.quarantine_skipped_files(self.wiki, report)
        self.assertEqual(report.decisions, ())
        self.assertEqual(report.ignored, ())
        self.assertTrue(source.exists())

    def test_ingestion_refuses_ignored_source_before_reading(self) -> None:
        source = self.repo / "private.md"
        source.write_text("secret")
        self.scope("/private.md\n")
        with patch.object(sys, "argv", ["ingest_document.py", str(source), "--wiki-root", str(self.wiki)]), \
             patch.object(ingest_document, "snapshot_source", side_effect=AssertionError("excluded source read")), \
             redirect_stderr(io.StringIO()), redirect_stdout(io.StringIO()):
            self.assertEqual(ingest_document.main(), 2)
        self.assertFalse((self.wiki / "intake").exists())

    def test_filter_cli_preserves_unusual_filenames_and_omits_excluded_names(self) -> None:
        self.scope("*.log\n")
        data = io.TextIOWrapper(io.BytesIO(b"keep\nname.py\0secret.log\0"))
        stdout = io.StringIO()
        with patch.object(sys, "argv", ["wiki_scope.py", "filter", "--wiki-root", str(self.wiki), "--null"]), \
             patch.object(sys, "stdin", data), redirect_stdout(stdout):
            self.assertEqual(wiki_scope.main(), 0)
        self.assertEqual(stdout.getvalue(), "keep\nname.py\0")
