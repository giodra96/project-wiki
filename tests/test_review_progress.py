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
        self.chunks = ingest_document.build_chunks(
            self.intake_id,
            [ingest_document.TextBlock(" ".join(f"word-{index}" for index in range(120)))],
            max_words=80,
            contract=self.contract,
        )
        manifest = {"chunks": [{"id": chunk.id} for chunk in self.chunks]}
        (self.document_root / self.contract.intake_artifacts.chunks_manifest).write_text(
            json.dumps(manifest),
            encoding="utf-8",
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

    def test_status_returns_limited_next_incomplete_batch(self) -> None:
        exit_code, stdout, stderr = self.invoke("status", "--limit", "1", "--format", "json")

        payload = json.loads(stdout)
        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr, "")
        self.assertEqual(payload["summary"]["pending"], 2)
        self.assertEqual(payload["next"], [{"id": self.chunks[0].id, "status": "pending"}])

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