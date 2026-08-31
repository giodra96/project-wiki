from __future__ import annotations

import builtins
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import date
from pathlib import Path
from typing import Any
from unittest.mock import patch

import yaml  # type: ignore[import-untyped]

from scripts import ingest_document


class IngestDocumentTransactionTests(unittest.TestCase):
    doc_id = "DOCIN-20260820-001"

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.source = self.root / "requirements.txt"
        self.source.write_text("Administrators must export reports as CSV.\n", encoding="utf-8")
        self.wiki_root = self.root / ".project-wiki"

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def invoke(self, *extra_args: str, doc_id: str | None = None) -> tuple[int, str, str]:
        arguments = [
            "ingest_document.py",
            str(self.source),
            "--wiki-root",
            str(self.wiki_root),
            "--doc-id",
            doc_id or self.doc_id,
            *extra_args,
        ]
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch.object(sys, "argv", arguments), redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = ingest_document.main()
        return exit_code, stdout.getvalue(), stderr.getvalue()

    @property
    def documents_root(self) -> Path:
        return self.wiki_root / "intake" / "documents"

    @property
    def document_root(self) -> Path:
        return self.documents_root / self.doc_id

    def assert_no_document_output(self) -> None:
        children = list(self.documents_root.iterdir()) if self.documents_root.exists() else []
        self.assertEqual(children, [])

    def generate_intake_artifacts(self) -> tuple[str, dict[str, Any], dict[str, Any]]:
        source_hash = ingest_document.sha256_file(self.source)
        exit_code, _, stderr = self.invoke(
            "--copy-source",
            "--expected-sha256",
            source_hash,
        )
        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr, "")
        source_info = yaml.safe_load((self.document_root / "source-info.yml").read_text(encoding="utf-8"))
        manifest = json.loads((self.document_root / "chunks.json").read_text(encoding="utf-8"))
        return source_hash, source_info, manifest

    def test_success_publishes_complete_intake_without_staging_files(self) -> None:
        source_hash = ingest_document.sha256_file(self.source)

        exit_code, stdout, stderr = self.invoke(
            "--copy-source",
            "--expected-sha256",
            source_hash,
        )

        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr, "")
        self.assertIn(f"created intake document: {self.doc_id}", stdout)
        self.assertEqual(
            {path.name for path in self.document_root.iterdir()},
            {
                "chunks",
                "chunks.json",
                "extracted.md",
                "intake-report.md",
                "review-progress.yml",
                "source-info.yml",
                "source.txt",
            },
        )
        source_info = (self.document_root / "source-info.yml").read_text(encoding="utf-8")
        self.assertIn('copied_source_path: "source.txt"', source_info)
        self.assertNotIn(f".{self.doc_id}-", source_info)
        self.assertIn(self.doc_id, (self.wiki_root / "intake" / "INDEX.md").read_text(encoding="utf-8"))

    def test_invalid_cli_guards_return_code_2_without_creating_wiki(self) -> None:
        cases = (
            ("unsupported-source", ".csv", (), "unsupported file type '.csv'"),
            ("max-words-too-small", ".txt", ("--max-words", "79"), "--max-words must be at least 80"),
            ("malformed-expected-hash", ".txt", ("--expected-sha256", "not-a-hash"), "--expected-sha256 must be a 64-character hexadecimal SHA-256"),
        )
        for name, suffix, arguments, expected_error in cases:
            with self.subTest(name=name):
                self.source = self.root / f"requirements{suffix}"
                self.source.write_text("Source content.\n", encoding="utf-8")

                exit_code, stdout, stderr = self.invoke(*arguments)

                self.assertEqual(exit_code, 2)
                self.assertEqual(stdout, "")
                self.assertIn(expected_error, stderr)
                self.assertFalse(self.wiki_root.exists())

    def test_empty_source_does_not_create_intake_directories(self) -> None:
        self.source.write_text("", encoding="utf-8")

        exit_code, _, stderr = self.invoke()

        self.assertEqual(exit_code, 4)
        self.assertIn("no extractable text found", stderr)
        self.assertFalse(self.wiki_root.exists())

    def test_preflight_hash_mismatch_does_not_create_intake_directories(self) -> None:
        exit_code, _, stderr = self.invoke("--expected-sha256", "0" * 64)

        self.assertEqual(exit_code, 6)
        self.assertIn("does not match the inbox preflight", stderr)
        self.assertFalse(self.wiki_root.exists())

    def test_snapshot_failure_removes_temporary_directory(self) -> None:
        snapshot_root = self.root / "source-snapshot"

        def create_snapshot_directory(*_: object, **__: object) -> str:
            snapshot_root.mkdir()
            return str(snapshot_root)

        with (
            patch.object(ingest_document.tempfile, "mkdtemp", side_effect=create_snapshot_directory),
            patch.object(ingest_document, "snapshot_source", side_effect=OSError("source unavailable")),
        ):
            exit_code, _, stderr = self.invoke()

        self.assertEqual(exit_code, 5)
        self.assertIn("failed to snapshot source document", stderr)
        self.assertFalse(snapshot_root.exists())
        self.assertFalse(self.wiki_root.exists())

    def test_source_change_during_extraction_does_not_create_intake_directories(self) -> None:
        source_hash = ingest_document.sha256_file(self.source)
        original_extract = ingest_document.extract_blocks

        def extract_and_change_source(snapshot: Path) -> list[ingest_document.TextBlock]:
            blocks = original_extract(snapshot)
            self.source.write_text("Changed while extraction was running.\n", encoding="utf-8")
            return blocks

        with patch.object(ingest_document, "extract_blocks", side_effect=extract_and_change_source):
            exit_code, _, stderr = self.invoke("--expected-sha256", source_hash)

        self.assertEqual(exit_code, 6)
        self.assertIn("source changed after the inbox preflight", stderr)
        self.assert_no_document_output()

    def test_extraction_and_copied_source_use_the_authorized_snapshot(self) -> None:
        source_hash = ingest_document.sha256_file(self.source)
        extracted_paths: list[Path] = []
        original_extract = ingest_document.extract_blocks

        def record_snapshot(snapshot: Path) -> list[ingest_document.TextBlock]:
            extracted_paths.append(snapshot)
            return original_extract(snapshot)

        with patch.object(ingest_document, "extract_blocks", side_effect=record_snapshot):
            exit_code, _, stderr = self.invoke(
                "--copy-source",
                "--expected-sha256",
                source_hash,
            )

        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr, "")
        self.assertEqual(len(extracted_paths), 1)
        self.assertNotEqual(extracted_paths[0], self.source)
        self.assertFalse(extracted_paths[0].exists())
        self.assertEqual(ingest_document.sha256_file(self.document_root / "source.txt"), source_hash)

    def test_generated_source_info_is_parseable_and_consistent(self) -> None:
        source_hash, source_info, manifest = self.generate_intake_artifacts()
        self.assertEqual(source_info["version"], 1)
        self.assertEqual(source_info["id"], self.doc_id)
        self.assertEqual(source_info["status"], "active")
        self.assertIsInstance(source_info["created"], str)
        date.fromisoformat(source_info["created"])
        self.assertEqual(source_info["created"], source_info["updated"])
        self.assertEqual(source_info["source_sha256"], source_hash)
        self.assertEqual(source_info["copied_source_path"], "source.txt")
        self.assertEqual(source_info["chunk_count"], len(manifest["chunks"]))
        self.assertEqual(source_info["word_count"], sum(chunk["word_count"] for chunk in manifest["chunks"]))

    def test_generated_chunk_manifest_is_parseable_and_externalized(self) -> None:
        source_hash, _, manifest = self.generate_intake_artifacts()
        chunk_entry = manifest["chunks"][0]
        chunk_path = self.document_root / chunk_entry["text_path"]

        self.assertEqual(manifest["version"], 1)
        self.assertEqual(manifest["id"], self.doc_id)
        self.assertEqual(manifest["source"]["sha256"], source_hash)
        self.assertEqual(manifest["chunking"]["text_storage"], "external-chunk-files")
        self.assertFalse(manifest["chunking"]["inline_text"])
        self.assertNotIn("text", chunk_entry)
        self.assertTrue(chunk_path.is_file())

    def test_generated_routing_docs_use_compact_inspect_and_view_workflow(self) -> None:
        _, _, manifest = self.generate_intake_artifacts()
        report = (self.document_root / "intake-report.md").read_text(encoding="utf-8")
        extraction_index = (self.document_root / "extracted.md").read_text(encoding="utf-8")
        first_chunk_id = manifest["chunks"][0]["id"]

        for content in (report, extraction_index):
            self.assertIn("review_progress.py inspect", content)
            self.assertIn("review_progress.py view", content)
            self.assertNotIn(first_chunk_id, content)
        self.assertIn("## Extraction Warnings", report)
        self.assertNotIn("- Intake status:", report)
        self.assertIn("review_progress.py audit", report)
        self.assertIn("SHA-256", report)
        self.assertIn("audit --expect-ledger-sha256", report)
        self.assertNotIn("## Candidate Chunks For Agent Review", report)
        self.assertNotIn("## Hint Summary", report)
        self.assertNotIn("## Chunk Files", extraction_index)

    def test_generated_chunk_file_matches_manifest(self) -> None:
        _, _, manifest = self.generate_intake_artifacts()
        chunk_entry = manifest["chunks"][0]
        chunk_path = self.document_root / chunk_entry["text_path"]
        chunk_content = chunk_path.read_text(encoding="utf-8")
        chunk_frontmatter = yaml.safe_load(chunk_content.split("---", 2)[1])

        self.assertEqual(chunk_frontmatter["id"], chunk_entry["id"])
        self.assertEqual(chunk_frontmatter["related"], [self.doc_id])

    def test_generated_review_progress_covers_every_chunk_as_pending(self) -> None:
        _, _, manifest = self.generate_intake_artifacts()
        progress = yaml.safe_load((self.document_root / "review-progress.yml").read_text(encoding="utf-8"))

        self.assertEqual(progress["version"], 1)
        self.assertEqual(progress["intake_id"], self.doc_id)
        self.assertEqual(progress["review_status"], "in-progress")
        self.assertEqual(progress["summary"], {
            "total": len(manifest["chunks"]),
            "pending": len(manifest["chunks"]),
            "reviewed": 0,
            "classified": 0,
            "skipped": 0,
        })
        self.assertEqual(
            [entry["id"] for entry in progress["chunks"]],
            [entry["id"] for entry in manifest["chunks"]],
        )
        self.assertTrue(all(entry["status"] == "pending" for entry in progress["chunks"]))

    def test_artifact_write_failure_removes_staging_directory(self) -> None:
        with patch.object(ingest_document, "write_chunks_json", side_effect=OSError("disk full")):
            exit_code, _, stderr = self.invoke()

        self.assertEqual(exit_code, 5)
        self.assertIn("disk full", stderr)
        self.assert_no_document_output()
        self.assertFalse((self.wiki_root / "intake" / "INDEX.md").exists())

    def test_invalid_staged_manifest_is_not_published(self) -> None:
        def write_invalid_manifest(path: Path, *_: object, **__: object) -> None:
            path.write_text("{}\n", encoding="utf-8")

        with patch.object(ingest_document, "write_chunks_json", side_effect=write_invalid_manifest):
            exit_code, _, stderr = self.invoke()

        self.assertEqual(exit_code, 5)
        self.assertIn("chunks.json does not match the staged intake", stderr)
        self.assert_no_document_output()
        self.assertFalse((self.wiki_root / "intake" / "INDEX.md").exists())

    def test_index_write_failure_rolls_back_published_document(self) -> None:
        index_path = self.wiki_root / "intake" / "INDEX.md"
        index_path.parent.mkdir(parents=True)
        index_path.write_text("# Existing index\n", encoding="utf-8")

        with patch.object(Path, "replace", side_effect=OSError("index unavailable")):
            exit_code, _, stderr = self.invoke()

        self.assertEqual(exit_code, 5)
        self.assertIn("index unavailable", stderr)
        self.assert_no_document_output()
        self.assertEqual(index_path.read_text(encoding="utf-8"), "# Existing index\n")
        self.assertEqual([path.name for path in index_path.parent.iterdir()], ["INDEX.md", "documents"])

    def test_existing_id_returns_clean_error_without_modifying_intake(self) -> None:
        first_exit_code, _, _ = self.invoke()
        index_path = self.wiki_root / "intake" / "INDEX.md"
        original_index = index_path.read_text(encoding="utf-8")

        second_exit_code, _, stderr = self.invoke()

        self.assertEqual(first_exit_code, 0)
        self.assertEqual(second_exit_code, 2)
        self.assertEqual(stderr, f"error: intake document already exists: {self.doc_id}\n")
        self.assertNotIn("Traceback", stderr)
        self.assertEqual(index_path.read_text(encoding="utf-8"), original_index)
        self.assertEqual([path.name for path in self.documents_root.iterdir()], [self.doc_id])

    def test_malformed_explicit_id_is_rejected_without_creating_wiki(self) -> None:
        exit_code, _, stderr = self.invoke(doc_id="DOCIN-invalid")

        self.assertEqual(exit_code, 2)
        self.assertEqual(stderr, "error: --doc-id must match DOCIN-YYYYMMDD-NNN\n")
        self.assertFalse(self.wiki_root.exists())

    def test_missing_pdf_dependency_returns_code_3_without_partial_output(self) -> None:
        self.source = self.root / "requirements.pdf"
        self.source.write_bytes(b"%PDF-placeholder")
        original_import = builtins.__import__

        def import_without_fitz(name: str, *args: object, **kwargs: object) -> object:
            if name == "fitz":
                raise ImportError("fitz unavailable")
            return original_import(name, *args, **kwargs)

        with patch.object(builtins, "__import__", side_effect=import_without_fitz):
            exit_code, _, stderr = self.invoke()

        self.assertEqual(exit_code, 3)
        self.assertIn("PDF extraction requires PyMuPDF", stderr)
        self.assertFalse(self.wiki_root.exists())


if __name__ == "__main__":
    unittest.main()