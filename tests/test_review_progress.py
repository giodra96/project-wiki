from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

import yaml  # type: ignore[import-untyped]

from scripts import ingest_document, review_progress
from scripts.schema_contract import load_schema_contract


class ReviewProgressCliTests(unittest.TestCase):
    intake_id = "DOCIN-20260824-001"

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.wiki_root = self.root / ".project-wiki"
        self.contract = load_schema_contract()
        self.document_root = (
            self.wiki_root
            / self.contract.semantic_paths.intake_documents_directory
            / self.intake_id
        )
        self.document_root.mkdir(parents=True)
        self.source = self.root / "requirements.md"
        self.source.write_text("Test source", encoding="utf-8")
        self.write_artifacts(
            [ingest_document.TextBlock(" ".join(f"word-{index}" for index in range(120)))],
            file_type="md",
        )

    def write_artifacts(
        self,
        blocks: list[ingest_document.TextBlock],
        *,
        file_type: str,
        max_words: int = 80,
        warnings: list[str] | None = None,
    ) -> None:
        self.chunks = ingest_document.build_chunks(
            self.intake_id,
            blocks,
            max_words=max_words,
            contract=self.contract,
        )
        ingest_document.write_chunk_files(
            self.document_root / self.contract.intake_artifacts.chunk_directory,
            self.intake_id,
            "Requirements",
            self.source,
            "2026-08-24",
            self.chunks,
            "active",
            "confirmed",
        )
        ingest_document.write_chunks_json(
            self.document_root / self.contract.intake_artifacts.chunks_manifest,
            self.intake_id,
            "Requirements",
            self.source,
            "0" * 64,
            "2026-08-24",
            max_words,
            self.chunks,
            self.contract.intake_chunks_manifest_version,
            self.contract.intake_artifacts,
        )
        ingest_document.write_source_info(
            self.document_root / self.contract.intake_artifacts.source_info,
            self.intake_id,
            "Requirements",
            self.source,
            "0" * 64,
            None,
            "2026-08-24",
            file_type,
            sum(chunk.word_count for chunk in self.chunks),
            len(self.chunks),
            "active",
            self.contract.intake_source_info_version,
            "confirmed",
        )
        ingest_document.write_intake_report(
            self.document_root / self.contract.intake_artifacts.intake_report,
            self.intake_id,
            "Requirements",
            self.source,
            "2026-08-24",
            self.chunks,
            "active",
            self.contract.intake_artifacts,
            "confirmed",
            warnings,
        )
        ingest_document.write_review_progress(
            self.document_root / self.contract.intake_artifacts.review_progress,
            self.intake_id,
            "2026-08-24",
            self.chunks,
            self.contract.intake_review_progress_version,
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    @property
    def ledger_path(self) -> Path:
        return self.document_root / self.contract.intake_artifacts.review_progress

    def invoke(self, *arguments: str) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        argv = [
            "review_progress.py",
            *arguments,
            "--wiki-root",
            str(self.wiki_root),
            "--intake-id",
            self.intake_id,
        ]
        with patch.object(sys, "argv", argv), redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = review_progress.main()
        return exit_code, stdout.getvalue(), stderr.getvalue()

    def snapshot_files(self) -> dict[str, bytes]:
        return {
            path.relative_to(self.wiki_root).as_posix(): path.read_bytes()
            for path in self.wiki_root.rglob("*")
            if path.is_file()
        }

    def test_status_returns_limited_next_incomplete_batch(self) -> None:
        exit_code, stdout, stderr = self.invoke("status", "--limit", "1", "--format", "json")

        payload = json.loads(stdout)
        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr, "")
        self.assertEqual(payload["summary"]["pending"], 2)
        self.assertEqual(payload["next"], [{"id": self.chunks[0].id, "status": "pending"}])

    def test_inspect_reports_unstructured_document_without_text_or_previews(self) -> None:
        ledger_before = self.ledger_path.read_bytes()

        exit_code, stdout, stderr = self.invoke("inspect", "--format", "json")

        payload = json.loads(stdout)
        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr, "")
        self.assertEqual(payload["intake_id"], self.intake_id)
        self.assertEqual(payload["extraction"]["chunk_count"], 2)
        self.assertEqual(payload["extraction"]["warnings"], {"available": True, "items": []})
        self.assertEqual(payload["structure"], {
            "guidance": "use-all",
            "kind": "unstructured",
            "reliable": False,
            "sections": [],
        })
        self.assertNotIn("preview", stdout)
        self.assertNotIn("word-0", stdout)
        self.assertEqual(self.ledger_path.read_bytes(), ledger_before)

    def test_inspect_reports_recorded_extraction_warnings(self) -> None:
        self.write_artifacts(
            [ingest_document.TextBlock("Extracted content.")],
            file_type="pdf",
            warnings=["Layout order may be incomplete on page 2."],
        )

        exit_code, stdout, stderr = self.invoke("inspect", "--format", "json")

        payload = json.loads(stdout)
        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr, "")
        self.assertEqual(payload["extraction"]["warnings"], {
            "available": True,
            "items": ["Layout order may be incomplete on page 2."],
        })

    def test_audit_reports_ledger_snapshot_without_semantic_candidates(self) -> None:
        ledger = yaml.safe_load(self.ledger_path.read_text(encoding="utf-8"))
        ledger["chunks"][0].update({
            "status": "skipped",
            "notes": "No canonical content selected.",
        })
        ledger["chunks"][1].update({
            "status": "classified",
            "classifications": ["technical-documentation"],
            "target_ids": ["PROJECT"],
        })
        ledger["review_status"] = "complete"
        ledger["summary"].update({"pending": 0, "classified": 1, "skipped": 1})
        self.ledger_path.write_text(yaml.safe_dump(ledger, sort_keys=False), encoding="utf-8")
        before = self.snapshot_files()

        exit_code, stdout, stderr = self.invoke("audit", "--format", "json")

        payload = json.loads(stdout)
        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr, "")
        self.assertEqual(payload["audit_status"], "review-complete")
        self.assertEqual(payload["ledger_snapshot"]["review_status"], "complete")
        self.assertEqual(payload["ledger_snapshot"]["summary"], ledger["summary"])
        self.assertRegex(payload["ledger_snapshot"]["sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(
            set(payload),
            {"version", "intake_id", "audit_status", "ledger_snapshot"},
        )
        self.assertEqual(self.snapshot_files(), before)

        first_digest = payload["ledger_snapshot"]["sha256"]
        ledger["chunks"][0]["notes"] = "Reviewed again; no canonical target selected."
        self.ledger_path.write_text(yaml.safe_dump(ledger, sort_keys=False), encoding="utf-8")
        stale_exit_code, stale_stdout, stale_stderr = self.invoke(
            "audit",
            "--expect-ledger-sha256",
            first_digest,
            "--format",
            "json",
        )
        second_exit_code, second_stdout, second_stderr = self.invoke("audit", "--format", "json")
        second_payload = json.loads(second_stdout)

        self.assertEqual(stale_exit_code, 2)
        self.assertEqual(stale_stdout, "")
        self.assertIn("ledger changed since the reviewed audit snapshot", stale_stderr)
        self.assertEqual(second_exit_code, 0)
        self.assertEqual(second_stderr, "")
        self.assertNotEqual(second_payload["ledger_snapshot"]["sha256"], first_digest)

        current_digest = second_payload["ledger_snapshot"]["sha256"]
        current_exit_code, _, current_stderr = self.invoke(
            "audit",
            "--expect-ledger-sha256",
            current_digest,
        )
        self.assertEqual(current_exit_code, 0)
        self.assertEqual(current_stderr, "")

    def test_audit_skips_reports_optional_signals_without_modifying_files(self) -> None:
        self.write_artifacts(
            [ingest_document.TextBlock("The system shall " + " ".join(f"word-{index}" for index in range(117)))],
            file_type="md",
        )
        ledger = yaml.safe_load(self.ledger_path.read_text(encoding="utf-8"))
        ledger["chunks"][0].update({
            "status": "skipped",
            "notes": "Requirement summarized but not modeled in this pass.",
        })
        ledger["chunks"][1].update({
            "status": "classified",
            "classifications": ["technical-documentation"],
            "target_ids": ["PROJECT"],
        })
        ledger["review_status"] = "complete"
        ledger["summary"].update({"pending": 0, "classified": 1, "skipped": 1})
        self.ledger_path.write_text(yaml.safe_dump(ledger, sort_keys=False), encoding="utf-8")
        before = self.snapshot_files()

        exit_code, stdout, stderr = self.invoke("audit-skips", "--format", "json")

        payload = json.loads(stdout)
        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr, "")
        self.assertEqual(payload["skip_count"], 1)
        self.assertEqual(payload["contiguous_skip_runs"], [])
        self.assertEqual(payload["skipped_chunks"][0]["id"], self.chunks[0].id)
        self.assertEqual(
            payload["skipped_chunks"][0]["signals"],
            ["normative-language", "deferred-or-unmodeled-note"],
        )
        self.assertEqual(self.snapshot_files(), before)

    def test_audit_reports_incomplete_review(self) -> None:
        exit_code, stdout, stderr = self.invoke("audit", "--format", "json")

        payload = json.loads(stdout)
        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr, "")
        self.assertEqual(payload["audit_status"], "review-incomplete")
        self.assertEqual(payload["ledger_snapshot"]["review_status"], "in-progress")
        self.assertNotIn("review_candidates", payload)

    def test_inspect_assigns_distinct_ids_to_repeated_source_headings(self) -> None:
        self.write_artifacts(
            [
                ingest_document.TextBlock("# Authentication", heading="Authentication", starts_section=True),
                ingest_document.TextBlock("First requirement.", heading="Authentication"),
                ingest_document.TextBlock("# Authentication", heading="Authentication", starts_section=True),
                ingest_document.TextBlock("Second requirement.", heading="Authentication"),
            ],
            file_type="md",
        )

        exit_code, stdout, stderr = self.invoke("inspect", "--format", "json")

        payload = json.loads(stdout)
        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr, "")
        self.assertTrue(payload["structure"]["reliable"])
        self.assertEqual(payload["structure"]["kind"], "source-sections-flat")
        self.assertEqual(
            [(section["id"], section["title"]) for section in payload["structure"]["sections"]],
            [("SEC-001", "Authentication"), ("SEC-002", "Authentication")],
        )

    def test_inspect_text_uses_compact_chunk_sequence_ranges(self) -> None:
        self.write_artifacts(
            [
                ingest_document.TextBlock("# Authentication", heading="Authentication", starts_section=True),
                ingest_document.TextBlock("Requirement text.", heading="Authentication"),
            ],
            file_type="md",
        )

        exit_code, stdout, stderr = self.invoke("inspect")

        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr, "")
        self.assertIn("SEC-001 | source-section | Authentication | chunks 1-1", stdout)
        self.assertNotIn(f"{self.intake_id}-CH-", stdout)

    def test_inspect_recognizes_docx_heading_sections(self) -> None:
        self.write_artifacts(
            [
                ingest_document.TextBlock("Authentication", heading="Authentication", starts_section=True),
                ingest_document.TextBlock("Administrators must sign in.", heading="Authentication"),
            ],
            file_type="docx",
        )

        exit_code, stdout, stderr = self.invoke("inspect", "--format", "json")

        payload = json.loads(stdout)
        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr, "")
        self.assertEqual(payload["structure"]["guidance"], "use-section-or-all")
        self.assertEqual(payload["structure"]["sections"][0]["title"], "Authentication")

    def test_unsectioned_preamble_is_exposed_as_sec_000(self) -> None:
        self.write_artifacts(
            [
                ingest_document.TextBlock("Document preamble."),
                ingest_document.TextBlock("# Authentication", heading="Authentication", starts_section=True),
                ingest_document.TextBlock("Requirement text.", heading="Authentication"),
            ],
            file_type="md",
        )

        inspect_exit, inspect_stdout, inspect_stderr = self.invoke("inspect", "--format", "json")
        view_exit, view_stdout, view_stderr = self.invoke("view", "--section", "SEC-000")

        payload = json.loads(inspect_stdout)
        self.assertEqual((inspect_exit, inspect_stderr), (0, ""))
        self.assertEqual(
            [(section["id"], section["kind"]) for section in payload["structure"]["sections"]],
            [("SEC-000", "unsectioned"), ("SEC-001", "source-section")],
        )
        self.assertEqual((view_exit, view_stderr), (0, ""))
        self.assertIn("Document preamble.", view_stdout)
        self.assertNotIn("Requirement text.", view_stdout)

    def test_inspect_requires_full_view_for_page_only_pdf(self) -> None:
        self.write_artifacts(
            [
                ingest_document.TextBlock("First page text.", heading="Page 1", page=1),
                ingest_document.TextBlock("Second page text.", heading="Page 2", page=2),
            ],
            file_type="pdf",
        )

        exit_code, stdout, stderr = self.invoke("inspect", "--format", "json")

        payload = json.loads(stdout)
        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr, "")
        self.assertEqual(payload["structure"], {
            "guidance": "use-all",
            "kind": "page-only",
            "reliable": False,
            "sections": [],
        })

    def test_view_requires_an_explicit_selector(self) -> None:
        exit_code, stdout, stderr = self.invoke("view")

        self.assertEqual(exit_code, 2)
        self.assertEqual(stdout, "")
        self.assertIn("choose exactly one of --all, --section, or --chunks", stderr)

    def test_view_all_returns_every_chunk_without_generated_wrappers(self) -> None:
        ledger_before = self.ledger_path.read_bytes()

        exit_code, stdout, stderr = self.invoke("view", "--all")

        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr, "")
        self.assertIn("Scope: all", stdout)
        self.assertIn("word-0", stdout)
        self.assertIn("word-119", stdout)
        self.assertEqual(stdout.count(f"--- {self.intake_id}-CH-"), len(self.chunks))
        self.assertEqual(stdout.count("| pending ---"), len(self.chunks))
        self.assertNotIn("Parent intake", stdout)
        self.assertNotIn("Word count", stdout)
        self.assertNotIn("Hints", stdout)
        self.assertEqual(self.ledger_path.read_bytes(), ledger_before)

    def test_view_chunks_accepts_short_ids_and_preserves_source_order(self) -> None:
        ledger_before = self.ledger_path.read_bytes()

        exit_code, stdout, stderr = self.invoke(
            "view",
            "--chunks",
            "CH-002",
            "CH-001",
            "--format",
            "json",
        )

        payload = json.loads(stdout)
        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr, "")
        self.assertEqual(payload["scope"], {
            "kind": "chunks",
            "ids": [self.chunks[0].id, self.chunks[1].id],
        })
        self.assertEqual(
            [chunk["id"] for chunk in payload["chunks"]],
            [self.chunks[0].id, self.chunks[1].id],
        )
        self.assertEqual(self.ledger_path.read_bytes(), ledger_before)

    def test_view_chunks_rejects_unknown_or_duplicate_ids(self) -> None:
        for requested_ids, expected in (
            (("CH-999",), "unknown chunk ID for this intake"),
            (("CH-001", "CH-001"), "duplicate chunk ID"),
            (("DOCIN-20260824-999-CH-001",), "unknown chunk ID for this intake"),
        ):
            with self.subTest(requested_ids=requested_ids):
                exit_code, stdout, stderr = self.invoke("view", "--chunks", *requested_ids)

                self.assertEqual(exit_code, 2)
                self.assertEqual(stdout, "")
                self.assertIn(expected, stderr)

    def test_view_section_selects_one_repeated_heading_occurrence(self) -> None:
        self.write_artifacts(
            [
                ingest_document.TextBlock("# Authentication", heading="Authentication", starts_section=True),
                ingest_document.TextBlock("First requirement.", heading="Authentication"),
                ingest_document.TextBlock("# Authentication", heading="Authentication", starts_section=True),
                ingest_document.TextBlock("Second requirement.", heading="Authentication"),
            ],
            file_type="md",
        )

        exit_code, stdout, stderr = self.invoke("view", "--section", "SEC-001")

        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr, "")
        self.assertIn("Scope: SEC-001 | source-section | Authentication", stdout)
        self.assertIn("First requirement.", stdout)
        self.assertNotIn("Second requirement.", stdout)

    def test_view_section_keeps_all_chunks_of_a_long_source_section(self) -> None:
        self.write_artifacts(
            [
                ingest_document.TextBlock("# Large Section", heading="Large Section", starts_section=True),
                ingest_document.TextBlock(
                    " ".join(f"requirement-{index}" for index in range(120)),
                    heading="Large Section",
                ),
            ],
            file_type="md",
            max_words=40,
        )

        exit_code, stdout, stderr = self.invoke("view", "--section", "SEC-001")

        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr, "")
        self.assertIn("requirement-0", stdout)
        self.assertIn("requirement-119", stdout)
        self.assertEqual(stdout.count(f"--- {self.intake_id}-CH-"), len(self.chunks))

    def test_view_section_rejects_page_only_pdf(self) -> None:
        self.write_artifacts(
            [ingest_document.TextBlock("Page text.", heading="Page 1", page=1)],
            file_type="pdf",
        )

        exit_code, stdout, stderr = self.invoke("view", "--section", "SEC-001")

        self.assertEqual(exit_code, 2)
        self.assertEqual(stdout, "")
        self.assertIn("section view is unavailable for this document; use --all", stderr)

    def test_inspect_rejects_chunk_path_outside_intake(self) -> None:
        manifest_path = self.document_root / self.contract.intake_artifacts.chunks_manifest
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["chunks"][0]["text_path"] = "../outside.md"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        exit_code, stdout, stderr = self.invoke("inspect", "--format", "json")

        self.assertEqual(exit_code, 2)
        self.assertEqual(stdout, "")
        self.assertIn("unsafe text_path", stderr)

    def test_apply_updates_recalculates_summary_and_completion(self) -> None:
        updates_path = self.root / "updates.json"
        updates_path.write_text(
            json.dumps(
                [
                    {
                        "id": self.chunks[0].id,
                        "status": "classified",
                        "classifications": ["requirement", "open-question"],
                        "target_ids": ["REQ-001", "OQ-001"],
                        "notes": "Two items captured.",
                    },
                    {
                        "id": self.chunks[1].id,
                        "status": "skipped",
                        "notes": "Glossary-only content.",
                    },
                ]
            ),
            encoding="utf-8",
        )

        exit_code, _, stderr = self.invoke("apply", "--updates", str(updates_path))
        ledger = yaml.safe_load(self.ledger_path.read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr, "")
        self.assertEqual(ledger["review_status"], "complete")
        self.assertEqual(ledger["summary"], {
            "total": 2,
            "pending": 0,
            "reviewed": 0,
            "classified": 1,
            "skipped": 1,
        })
        status_exit_code, status_stdout, _ = self.invoke("status", "--format", "json")
        status_payload = json.loads(status_stdout)
        self.assertEqual(status_exit_code, 0)
        self.assertEqual(status_payload["classification_counts"], {"open-question": 1, "requirement": 1})
        self.assertEqual(status_payload["registered_target_count"], 2)

    def test_invalid_update_does_not_modify_ledger(self) -> None:
        original = self.ledger_path.read_bytes()
        updates_path = self.root / "invalid-updates.json"
        updates_path.write_text(
            json.dumps([{"id": self.chunks[0].id, "status": "skipped"}]),
            encoding="utf-8",
        )

        exit_code, stdout, stderr = self.invoke("apply", "--updates", str(updates_path))

        self.assertEqual(exit_code, 2)
        self.assertEqual(stdout, "")
        self.assertIn("requires notes", stderr)
        self.assertEqual(self.ledger_path.read_bytes(), original)