from __future__ import annotations

import builtins
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from scripts import check_inbox


class SourceInboxCheckTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.wiki_root = self.root / ".project-wiki"
        self.inbox_root = self.wiki_root / "sources" / "inbox"
        self.inbox_root.mkdir(parents=True)
        self.write_empty_registry()

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def write_source(self, relative_path: str, content: str) -> Path:
        path = self.inbox_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def write_empty_registry(self) -> None:
        registry_path = self.wiki_root / "sources" / "SOURCE_REGISTRY.yml"
        registry_path.write_text(
            "version: 1\nupdated: 2026-08-20\nsources: []\n",
            encoding="utf-8",
        )

    def write_registry(
        self,
        *,
        source_id: str,
        status: str,
        source_hash: str,
        original_path: str,
        current_path: str,
        intake_id: str | None = None,
        processed_at: str | None = None,
    ) -> None:
        registry_path = self.wiki_root / "sources" / "SOURCE_REGISTRY.yml"
        registry_path.write_text(
            "\n".join(
                [
                    "version: 1",
                    "updated: 2026-08-20",
                    "sources:",
                    f"  - id: {source_id}",
                    f"    status: {status}",
                    f"    original_path: {original_path}",
                    f"    current_path: {current_path}",
                    "    filename: source.md",
                    f'    sha256: "{source_hash}"',
                    f"    intake_id: {intake_id or 'null'}",
                    f"    processed_at: {processed_at or 'null'}",
                    "    tags: []",
                    '    notes: "Test source."',
                    "",
                ]
            ),
            encoding="utf-8",
        )

    def write_processed_history(
        self,
        *,
        source_id: str,
        content: str,
        original_path: str,
        current_path: str,
        intake_id: str = "DOCIN-20260801-001",
    ) -> str:
        archived = self.wiki_root / current_path
        archived.parent.mkdir(parents=True, exist_ok=True)
        archived.write_text(content, encoding="utf-8")
        source_hash = check_inbox.sha256_file(archived)
        self.write_intake_history(
            intake_id=intake_id,
            source_hash=source_hash,
            source_path=(self.wiki_root / original_path).as_posix(),
        )
        self.write_registry(
            source_id=source_id,
            status="processed",
            source_hash=source_hash,
            original_path=original_path,
            current_path=current_path,
            intake_id=intake_id,
            processed_at="2026-08-01",
        )
        return source_hash

    def write_intake_history(
        self,
        *,
        intake_id: str,
        source_hash: str,
        source_path: str,
        complete: bool = True,
        copied_source_content: str | None = None,
    ) -> None:
        intake_root = self.wiki_root / "intake" / "documents" / intake_id
        intake_root.mkdir(parents=True)
        copied_source_path = intake_root / "source.md" if copied_source_content is not None else None
        if copied_source_path is not None:
            copied_source_path.write_text(copied_source_content, encoding="utf-8")
        copied_source_value = f'"{copied_source_path.as_posix()}"' if copied_source_path else "null"
        (intake_root / "source-info.yml").write_text(
            "\n".join(
                [
                    "version: 1",
                    f'id: "{intake_id}"',
                    "type: intake-document",
                    "status: active",
                    'title: "Test intake"',
                    "created: 2026-08-20",
                    "updated: 2026-08-20",
                    f'source_path: "{source_path}"',
                    'source_filename: "source.md"',
                    f'source_sha256: "{source_hash}"',
                    "immutable_source: true",
                    'file_type: "md"',
                    f"copied_source_path: {copied_source_value}",
                    "word_count: 3",
                    "chunk_count: 1",
                    "confidence: confirmed",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        if complete:
            (intake_root / "extracted.md").write_text("# Extraction Index\n", encoding="utf-8")
            (intake_root / "intake-report.md").write_text("# Intake Report\n", encoding="utf-8")
            chunks_root = intake_root / "chunks"
            chunks_root.mkdir()
            (chunks_root / "CH-001.md").write_text("# Chunk\n\nSource content\n", encoding="utf-8")
            (intake_root / "chunks.json").write_text(
                json.dumps(
                    {
                        "version": 1,
                        "id": intake_id,
                        "source": {
                            "path": source_path,
                            "filename": "source.md",
                            "sha256": source_hash,
                        },
                        "chunks": [
                            {
                                "id": f"{intake_id}-CH-001",
                                "text_path": "chunks/CH-001.md",
                            }
                        ],
                    }
                )
                + "\n",
                encoding="utf-8",
            )

    def decisions_by_name(self, report: check_inbox.InboxReport) -> dict[str, check_inbox.InboxDecision]:
        return {Path(decision.path).name: decision for decision in report.decisions}

    def test_new_supported_file_is_processed_and_housekeeping_is_ignored(self) -> None:
        self.write_source("requirements.md", "The user must sign in.")
        self.write_source("README.md", "Inbox instructions")
        self.write_source("draft.md.part", "partial download")
        self.write_source("image.png", "not supported")

        report = check_inbox.check_inbox(self.wiki_root)

        self.assertEqual(len(report.decisions), 1)
        self.assertEqual(report.decisions[0].action, "process")
        self.assertEqual(report.decisions[0].reason, "new-unique")
        self.assertEqual(
            {ignored.reason for ignored in report.ignored},
            {"housekeeping-or-hidden", "temporary-or-partial", "unsupported-extension"},
        )

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks are not supported")
    def test_symlink_and_underscore_prefixed_paths_are_ignored(self) -> None:
        self.write_source("requirements.md", "Process this source.")
        self.write_source("_draft.md", "Ignore this draft.")
        self.write_source("_private/nested.md", "Ignore this private source.")
        symlink_target = self.root / "linked-source.md"
        symlink_target.write_text("Ignore linked content.\n", encoding="utf-8")
        (self.inbox_root / "linked.md").symlink_to(symlink_target)

        report = check_inbox.check_inbox(self.wiki_root)

        self.assertEqual([Path(decision.path).name for decision in report.decisions], ["requirements.md"])
        ignored = {item.path: item.reason for item in report.ignored}
        self.assertEqual(ignored["sources/inbox/_draft.md"], "underscore-prefixed")
        self.assertEqual(ignored["sources/inbox/_private/nested.md"], "underscore-prefixed")
        self.assertEqual(ignored["sources/inbox/linked.md"], "symlink")

    def test_duplicate_files_in_inbox_use_lexicographically_first_canonical_path(self) -> None:
        self.write_source("z-copy.md", "Identical requirements")
        self.write_source("a-original.md", "Identical requirements")

        report = check_inbox.check_inbox(self.wiki_root)
        decisions = self.decisions_by_name(report)

        self.assertEqual(decisions["a-original.md"].action, "process")
        self.assertEqual(decisions["a-original.md"].reason, "new-unique")
        self.assertEqual(decisions["z-copy.md"].action, "skip")
        self.assertEqual(decisions["z-copy.md"].reason, "inbox-duplicate")
        self.assertEqual(decisions["z-copy.md"].duplicate_of, decisions["a-original.md"].path)

    def test_processed_hash_is_skipped_even_when_inbox_filename_changed(self) -> None:
        source = self.write_source("renamed.md", "Previously processed content")
        source_hash = self.write_processed_history(
            source_id="SRC-20260801-001",
            content="Previously processed content",
            original_path="sources/inbox/original.md",
            current_path="sources/processed/2026-08/original.md",
        )
        self.assertEqual(check_inbox.sha256_file(source), source_hash)

        report = check_inbox.check_inbox(self.wiki_root)
        decision = report.decisions[0]

        self.assertEqual(decision.action, "skip")
        self.assertEqual(decision.reason, "registered-processed")
        self.assertEqual(decision.registry_ids, ("SRC-20260801-001",))

    def test_pending_or_failed_hash_remains_processable_without_new_registration(self) -> None:
        for status in ("pending", "failed"):
            with self.subTest(status=status):
                source = self.write_source("source.md", "Pending content")
                self.write_registry(
                    source_id="SRC-20260820-001",
                    status=status,
                    source_hash=check_inbox.sha256_file(source),
                    original_path="sources/inbox/source.md",
                    current_path="sources/inbox/source.md",
                )

                report = check_inbox.check_inbox(self.wiki_root)
                decision = report.decisions[0]

                self.assertEqual(decision.action, "process")
                self.assertEqual(decision.reason, f"registered-{status}")
                self.assertEqual(decision.selected_registry_id, "SRC-20260820-001")

    def test_reused_registered_path_with_changed_content_requires_review(self) -> None:
        self.write_source("source.md", "A new version of the source")
        self.write_processed_history(
            source_id="SRC-20260801-001",
            content="Old version of the source",
            original_path="sources/inbox/source.md",
            current_path="sources/processed/2026-08/source.md",
        )

        report = check_inbox.check_inbox(self.wiki_root)
        decision = report.decisions[0]

        self.assertEqual(decision.action, "review")
        self.assertEqual(decision.reason, "historical-path-with-new-content")
        self.assertEqual(decision.registry_ids, ("SRC-20260801-001",))

    def test_intake_history_skips_content_missing_from_registry(self) -> None:
        source = self.write_source("renamed.md", "Previously ingested content")
        self.write_intake_history(
            intake_id="DOCIN-20260801-001",
            source_hash=check_inbox.sha256_file(source),
            source_path="/original/location/source.md",
        )

        report = check_inbox.check_inbox(self.wiki_root)
        decision = report.decisions[0]

        self.assertEqual(decision.action, "skip")
        self.assertEqual(decision.reason, "intake-history-match")
        self.assertEqual(decision.intake_ids, ("DOCIN-20260801-001",))

    def test_intake_history_overrides_stale_pending_registry_status(self) -> None:
        source = self.write_source("source.md", "Already ingested content")
        source_hash = check_inbox.sha256_file(source)
        self.write_registry(
            source_id="SRC-20260801-001",
            status="pending",
            source_hash=source_hash,
            original_path="sources/inbox/source.md",
            current_path="sources/inbox/source.md",
        )
        self.write_intake_history(
            intake_id="DOCIN-20260801-001",
            source_hash=source_hash,
            source_path=source.resolve().as_posix(),
        )

        report = check_inbox.check_inbox(self.wiki_root)
        decision = report.decisions[0]

        self.assertEqual(decision.action, "skip")
        self.assertEqual(decision.reason, "intake-history-match")
        self.assertEqual(decision.registry_statuses, ("pending",))
        self.assertEqual(decision.intake_ids, ("DOCIN-20260801-001",))

    def test_incomplete_intake_history_fails_closed(self) -> None:
        source = self.write_source("source.md", "Potentially ingested content")
        self.write_intake_history(
            intake_id="DOCIN-20260801-001",
            source_hash=check_inbox.sha256_file(source),
            source_path=source.resolve().as_posix(),
            complete=False,
        )

        with self.assertRaisesRegex(check_inbox.InboxCheckError, "incomplete intake history"):
            check_inbox.check_inbox(self.wiki_root)

    def test_conflicting_intake_hashes_fail_closed(self) -> None:
        source = self.write_source("source.md", "Historically ingested content")
        source_hash = check_inbox.sha256_file(source)
        self.write_intake_history(
            intake_id="DOCIN-20260801-001",
            source_hash=source_hash,
            source_path=source.resolve().as_posix(),
        )
        source_info = self.wiki_root / "intake" / "documents" / "DOCIN-20260801-001" / "source-info.yml"
        source_info.write_text(
            source_info.read_text(encoding="utf-8").replace(source_hash, "0" * 64),
            encoding="utf-8",
        )

        with self.assertRaisesRegex(check_inbox.InboxCheckError, "conflicting source hashes"):
            check_inbox.check_inbox(self.wiki_root)

    def test_copied_intake_source_hash_mismatch_fails_closed(self) -> None:
        source = self.write_source("source.md", "Historically ingested content")
        source_hash = check_inbox.sha256_file(source)
        self.write_intake_history(
            intake_id="DOCIN-20260801-001",
            source_hash=source_hash,
            source_path=source.resolve().as_posix(),
            copied_source_content="Different copied bytes",
        )

        with self.assertRaisesRegex(check_inbox.InboxCheckError, "copied source hash does not match"):
            check_inbox.check_inbox(self.wiki_root)

    def test_historical_path_is_canonical_when_identical_inbox_copy_exists(self) -> None:
        self.write_source("a-copy.md", "A changed version")
        historical_path = self.write_source("z-original.md", "A changed version")
        self.write_processed_history(
            source_id="SRC-20260801-001",
            content="Old version",
            original_path="sources/inbox/z-original.md",
            current_path="sources/processed/2026-08/z-original.md",
        )

        report = check_inbox.check_inbox(self.wiki_root)
        decisions = self.decisions_by_name(report)

        self.assertEqual(decisions[historical_path.name].action, "review")
        self.assertEqual(decisions[historical_path.name].reason, "historical-path-with-new-content")
        self.assertEqual(decisions["a-copy.md"].action, "skip")
        self.assertEqual(decisions["a-copy.md"].duplicate_of, decisions[historical_path.name].path)

    def test_missing_or_non_scalar_registry_status_fails_closed(self) -> None:
        registry_path = self.wiki_root / "sources" / "SOURCE_REGISTRY.yml"
        status_lines = {
            "missing": [],
            "non-scalar": ["    status: []"],
        }
        for name, status_line in status_lines.items():
            with self.subTest(name=name):
                registry_path.write_text(
                    "\n".join(
                        [
                            "version: 1",
                            "updated: 2026-08-20",
                            "sources:",
                            "  - id: SRC-20260820-001",
                            *status_line,
                            f'    sha256: "{"0" * 64}"',
                            "",
                        ]
                    ),
                    encoding="utf-8",
                )

                with self.assertRaisesRegex(check_inbox.InboxCheckError, "invalid status"):
                    check_inbox.check_inbox(self.wiki_root)

    def test_duplicate_registry_yaml_key_fails_closed(self) -> None:
        registry_path = self.wiki_root / "sources" / "SOURCE_REGISTRY.yml"
        registry_path.write_text(
            "version: 1\nupdated: 2026-08-20\nsources: []\nsources: []\n",
            encoding="utf-8",
        )

        with self.assertRaisesRegex(check_inbox.InboxCheckError, "duplicate key"):
            check_inbox.check_inbox(self.wiki_root)

    def test_non_utf8_registry_returns_controlled_error(self) -> None:
        self.write_source("source.md", "Source content")
        registry_path = self.wiki_root / "sources" / "SOURCE_REGISTRY.yml"
        registry_path.write_bytes(b"version: 1\nsources: []\n\xff")

        with self.assertRaisesRegex(check_inbox.InboxCheckError, "invalid source registry YAML"):
            check_inbox.check_inbox(self.wiki_root)

    def test_missing_registry_fails_closed(self) -> None:
        self.write_source("source.md", "Source content")
        (self.wiki_root / "sources" / "SOURCE_REGISTRY.yml").unlink()

        with self.assertRaisesRegex(check_inbox.InboxCheckError, "source registry not found"):
            check_inbox.check_inbox(self.wiki_root)

    def test_missing_pyyaml_returns_controlled_dependency_error(self) -> None:
        self.write_source("source.md", "Source content")
        original_import = builtins.__import__

        def import_without_yaml(name: str, *args: object, **kwargs: object) -> object:
            if name == "yaml":
                raise ImportError("yaml unavailable")
            return original_import(name, *args, **kwargs)

        with patch.object(builtins, "__import__", side_effect=import_without_yaml):
            with self.assertRaisesRegex(check_inbox.InboxCheckError, "requires? PyYAML"):
                check_inbox.check_inbox(self.wiki_root)

    def test_multiple_processable_registry_matches_require_review(self) -> None:
        source = self.write_source("source.md", "Pending content")
        source_hash = check_inbox.sha256_file(source)
        registry_path = self.wiki_root / "sources" / "SOURCE_REGISTRY.yml"
        registry_path.write_text(
            "\n".join(
                [
                    "version: 1",
                    "updated: 2026-08-20",
                    "sources:",
                    "  - id: SRC-20260820-001",
                    "    status: pending",
                    f'    sha256: "{source_hash}"',
                    "  - id: SRC-20260820-002",
                    "    status: failed",
                    f'    sha256: "{source_hash}"',
                    "",
                ]
            ),
            encoding="utf-8",
        )

        report = check_inbox.check_inbox(self.wiki_root)
        decision = report.decisions[0]

        self.assertEqual(decision.action, "review")
        self.assertEqual(decision.reason, "ambiguous-processable-history")
        self.assertIsNone(decision.selected_registry_id)

    def test_quarantine_skips_rechecks_hash_and_moves_only_duplicates(self) -> None:
        canonical = self.write_source("a-original.md", "Identical content")
        duplicate = self.write_source("z-copy.md", "Identical content")
        report = check_inbox.check_inbox(self.wiki_root)

        applied = check_inbox.quarantine_skipped_files(self.wiki_root, report)
        decisions = self.decisions_by_name(applied)

        self.assertTrue(canonical.exists())
        self.assertFalse(duplicate.exists())
        destination = self.wiki_root / decisions["z-copy.md"].quarantined_to
        self.assertTrue(destination.is_file())
        self.assertEqual(check_inbox.sha256_file(destination), decisions["z-copy.md"].sha256)
        self.assertIsNone(decisions["a-original.md"].quarantined_to)

    def test_quarantine_aborts_when_skipped_file_changed_after_preflight(self) -> None:
        self.write_source("a-original.md", "Identical content")
        duplicate = self.write_source("z-copy.md", "Identical content")
        report = check_inbox.check_inbox(self.wiki_root)
        duplicate.write_text("Changed after preflight", encoding="utf-8")

        with self.assertRaisesRegex(check_inbox.InboxCheckError, "changed after preflight"):
            check_inbox.quarantine_skipped_files(self.wiki_root, report)

        self.assertTrue(duplicate.exists())
        self.assertFalse((self.wiki_root / "sources" / "ignored").exists())

    def test_quarantine_rolls_back_when_later_skip_fails_revalidation(self) -> None:
        self.write_source("a-original.md", "Identical content")
        first_duplicate = self.write_source("m-copy.md", "Identical content")
        second_duplicate = self.write_source("z-copy.md", "Identical content")
        report = check_inbox.check_inbox(self.wiki_root)
        original_verify = check_inbox.verify_decision_hash
        call_count = 0

        def fail_second_move(path: Path, expected_hash: str) -> None:
            nonlocal call_count
            call_count += 1
            if call_count == 4:
                raise check_inbox.InboxCheckError("changed after preflight")
            original_verify(path, expected_hash)

        with patch.object(check_inbox, "verify_decision_hash", side_effect=fail_second_move):
            with self.assertRaisesRegex(check_inbox.InboxCheckError, "changed after preflight"):
                check_inbox.quarantine_skipped_files(self.wiki_root, report)

        self.assertTrue(first_duplicate.exists())
        self.assertTrue(second_duplicate.exists())
        quarantined_files = list((self.wiki_root / "sources" / "ignored").rglob("*"))
        self.assertFalse(any(path.is_file() for path in quarantined_files))

    def test_paths_from_moved_repository_match_current_logical_inbox_path(self) -> None:
        self.write_source("source.md", "New version")
        archived = self.wiki_root / "sources/processed/2026-08/source.md"
        archived.parent.mkdir(parents=True)
        archived.write_text("Old version", encoding="utf-8")
        source_hash = check_inbox.sha256_file(archived)
        self.write_intake_history(
            intake_id="DOCIN-20260801-001",
            source_hash=source_hash,
            source_path="/old/checkout/.project-wiki/sources/inbox/source.md",
        )
        self.write_registry(
            source_id="SRC-20260801-001",
            status="processed",
            source_hash=source_hash,
            original_path="/old/checkout/.project-wiki/sources/inbox/source.md",
            current_path="/old/checkout/.project-wiki/sources/processed/2026-08/source.md",
            intake_id="DOCIN-20260801-001",
            processed_at="2026-08-01",
        )

        decision = check_inbox.check_inbox(self.wiki_root).decisions[0]

        self.assertEqual(decision.action, "review")
        self.assertEqual(decision.reason, "historical-path-with-new-content")

    def test_processed_registry_without_provenance_fails_closed(self) -> None:
        source = self.write_source("source.md", "Unverified content")
        self.write_registry(
            source_id="SRC-20260801-001",
            status="processed",
            source_hash=check_inbox.sha256_file(source),
            original_path="sources/inbox/source.md",
            current_path="sources/inbox/source.md",
        )

        with self.assertRaisesRegex(check_inbox.InboxCheckError, "no valid intake_id"):
            check_inbox.check_inbox(self.wiki_root)

    def test_json_cli_exposes_actions_and_quarantine_results(self) -> None:
        canonical = self.write_source("a-original.md", "Identical content")
        duplicate = self.write_source("z-copy.md", "Identical content")
        arguments = [
            "check_inbox.py",
            "--wiki-root",
            str(self.wiki_root),
            "--format",
            "json",
            "--quarantine-skips",
        ]
        stdout = io.StringIO()
        stderr = io.StringIO()

        with patch.object(sys, "argv", arguments), redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = check_inbox.main()

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr.getvalue(), "")
        self.assertEqual(payload["summary"]["process"], 1)
        self.assertEqual(payload["summary"]["skip"], 1)
        self.assertEqual([entry["action"] for entry in payload["files"]], ["process", "skip"])
        self.assertTrue(canonical.exists())
        self.assertFalse(duplicate.exists())
        quarantined = next(entry for entry in payload["files"] if entry["action"] == "skip")
        self.assertTrue((self.wiki_root / quarantined["quarantined_to"]).is_file())


if __name__ == "__main__":
    unittest.main()