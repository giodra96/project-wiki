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
from typing import Any
from unittest.mock import patch

import yaml  # type: ignore[import-untyped]

from scripts import validate_wiki
from scripts import ingest_document
from tests.wiki_fixtures import create_valid_wiki


class WikiValidatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name) / ".project-wiki"
        self.root.mkdir()
        self.ids = create_valid_wiki(self.root)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def codes(self) -> set[str]:
        return {finding.code for finding in validate_wiki.validate_wiki(self.root).findings}

    def ingest_source(
        self,
        content: str,
        *,
        doc_id: str = "DOCIN-20260820-001",
        max_words: int | None = None,
    ) -> Path:
        source = Path(self.temporary_directory.name) / f"source-{doc_id}.md"
        source.write_text(content, encoding="utf-8")
        arguments = [
            "ingest_document.py",
            str(source),
            "--wiki-root",
            str(self.root),
            "--doc-id",
            doc_id,
        ]
        if max_words is not None:
            arguments.extend(("--max-words", str(max_words)))
        with patch.object(sys, "argv", arguments), redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(ingest_document.main(), 0)
        return self.root / "intake" / "documents" / doc_id

    def create_processed_source_fixture(self) -> tuple[Path, Path, dict[str, Any]]:
        source = Path(self.temporary_directory.name) / "processed-source.md"
        source.write_text("# Processed source\n\nContent\n", encoding="utf-8")
        intake_id = "DOCIN-20260820-001"
        arguments = [
            "ingest_document.py",
            str(source),
            "--wiki-root",
            str(self.root),
            "--doc-id",
            intake_id,
        ]
        with patch.object(sys, "argv", arguments), redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(ingest_document.main(), 0)
        archived = self.root / "sources" / "processed" / "2026-08" / "processed-source.md"
        archived.parent.mkdir(parents=True, exist_ok=True)
        archived.write_bytes(source.read_bytes())
        source_registry = {
            "version": 1,
            "updated": "2026-08-20",
            "sources": [
                {
                    "id": "SRC-20260820-001",
                    "status": "processed",
                    "original_path": "sources/inbox/processed-source.md",
                    "current_path": "sources/processed/2026-08/processed-source.md",
                    "filename": "processed-source.md",
                    "sha256": ingest_document.sha256_file(archived),
                    "intake_id": intake_id,
                    "processed_at": "2026-08-20",
                    "tags": [],
                    "notes": "Processed fixture",
                }
            ],
        }
        registry_path = self.root / "sources" / "SOURCE_REGISTRY.yml"
        registry_path.write_text(yaml.safe_dump(source_registry, sort_keys=False), encoding="utf-8")
        return archived, registry_path, source_registry

    def add_atomic_requirement(self, chunk_id: str, *, evidence_chunk_id: str | None = None) -> None:
        topic_path = self.root / "requirements" / "functional" / "authentication.md"
        evidence = evidence_chunk_id or chunk_id
        topic_path.write_text(
            "\n".join(
                [
                    "---",
                    "id: REQ-TOPIC-20260820-001",
                    "type: requirements-topic",
                    "status: active",
                    "title: Authentication",
                    "created: 2026-08-20",
                    "updated: 2026-08-20",
                    "tags: [requirements, functional]",
                    "related: []",
                    "source_paths: []",
                    "confidence: confirmed",
                    "---",
                    "",
                    "# Authentication",
                    "",
                    '<a id="req-001"></a>',
                    "",
                    "## REQ-001 - User Authentication",
                    "",
                    "Status: active",
                    "Tags: [authentication]",
                    "Related: []",
                    "Confidence: confirmed",
                    "",
                    "### Statement",
                    "",
                    "The product shall authenticate users.",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        registry_path = self.root / "REGISTRY.yml"
        registry = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
        registry["documents"].extend(
            [
                {
                    "id": "REQ-TOPIC-20260820-001",
                    "type": "requirements-topic",
                    "title": "Authentication",
                    "path": "requirements/functional/authentication.md",
                    "status": "active",
                    "tags": ["requirements", "functional"],
                    "related": [],
                    "source_paths": [],
                    "confidence": "confirmed",
                },
                {
                    "id": "REQ-001",
                    "type": "requirement",
                    "title": "User Authentication",
                    "path": "requirements/functional/authentication.md#req-001",
                    "status": "active",
                    "tags": ["authentication"],
                    "related": [],
                    "source_paths": [],
                    "confidence": "confirmed",
                },
            ]
        )
        registry_path.write_text(yaml.safe_dump(registry, sort_keys=False), encoding="utf-8")
        evidence_path = self.root / "traceability" / "requirement-evidence.yml"
        evidence_payload = yaml.safe_load(evidence_path.read_text(encoding="utf-8"))
        evidence_payload["records"]["REQ-001"] = [evidence]
        evidence_path.write_text(yaml.safe_dump(evidence_payload, sort_keys=False), encoding="utf-8")

    def test_complete_canonical_wiki_passes_without_findings(self) -> None:
        report = validate_wiki.validate_wiki(self.root)

        self.assertTrue(report.valid)
        self.assertEqual(report.findings, ())

    def test_json_cli_returns_zero_for_valid_wiki(self) -> None:
        arguments = ["validate_wiki.py", "--wiki-root", str(self.root), "--format", "json"]
        stdout = io.StringIO()
        stderr = io.StringIO()

        with patch.object(sys, "argv", arguments), redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = validate_wiki.main()

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr.getvalue(), "")
        self.assertTrue(payload["valid"])
        self.assertEqual(payload["summary"]["findings"], 0)

    def test_missing_required_file_and_frontmatter_are_reported(self) -> None:
        (self.root / "technical/security.md").unlink()
        project_path = self.root / "PROJECT.md"
        project_path.write_text("# Project without frontmatter\n", encoding="utf-8")

        codes = self.codes()

        self.assertIn("required-file-missing", codes)
        self.assertIn("frontmatter-missing", codes)

    def test_invalid_yaml_status_and_confidence_are_reported(self) -> None:
        (self.root / "WIKI_VERSION.yml").write_text("schema: [unterminated\n", encoding="utf-8")
        security = self.root / "technical/security.md"
        content = security.read_text(encoding="utf-8")
        content = content.replace("status: placeholder", "status: impossible")
        content = content.replace("confidence: unknown", "confidence: certain")
        security.write_text(content, encoding="utf-8")

        codes = self.codes()

        self.assertIn("yaml-invalid", codes)
        self.assertIn("status-invalid", codes)
        self.assertIn("confidence-invalid", codes)

    def test_unknown_frontmatter_and_registry_types_are_reported(self) -> None:
        security = self.root / "technical" / "security.md"
        security.write_text(
            security.read_text(encoding="utf-8").replace("type: note", "type: typo-type"),
            encoding="utf-8",
        )
        registry_path = self.root / "REGISTRY.yml"
        registry = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
        registry["documents"][0]["type"] = "typo-type"
        registry_path.write_text(yaml.safe_dump(registry, sort_keys=False), encoding="utf-8")

        codes = self.codes()

        self.assertIn("document-type-invalid", codes)
        self.assertIn("registry-type-invalid", codes)

    def test_duplicate_yaml_keys_and_non_scalar_domains_return_json_findings(self) -> None:
        project = self.root / "PROJECT.md"
        project.write_text(
            project.read_text(encoding="utf-8").replace(
                "status: placeholder",
                "status: impossible\nstatus: placeholder",
            ),
            encoding="utf-8",
        )
        security = self.root / "technical" / "security.md"
        security.write_text(
            security.read_text(encoding="utf-8")
            .replace("status: placeholder", "status: []")
            .replace("confidence: unknown", "confidence: {}"),
            encoding="utf-8",
        )
        registry_path = self.root / "REGISTRY.yml"
        registry = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
        registry["documents"][0]["status"] = []
        registry_path.write_text(yaml.safe_dump(registry, sort_keys=False), encoding="utf-8")
        arguments = ["validate_wiki.py", "--wiki-root", str(self.root), "--format", "json"]
        stdout = io.StringIO()

        with patch.object(sys, "argv", arguments), redirect_stdout(stdout), redirect_stderr(io.StringIO()):
            exit_code = validate_wiki.main()

        payload = json.loads(stdout.getvalue())
        codes = {finding["code"] for finding in payload["findings"]}
        self.assertEqual(exit_code, 1)
        self.assertIn("frontmatter-yaml-invalid", codes)
        self.assertIn("status-invalid", codes)
        self.assertIn("confidence-invalid", codes)
        self.assertIn("registry-status-invalid", codes)

    def test_duplicate_id_and_filename_mismatch_are_reported(self) -> None:
        project_id = self.ids["PROJECT.md"]
        glossary = self.root / "GLOSSARY.md"
        glossary.write_text(
            glossary.read_text(encoding="utf-8").replace(self.ids["GLOSSARY.md"], project_id),
            encoding="utf-8",
        )
        request = self.root / "changes" / "requests" / "wrong-name.md"
        request.write_text(
            "\n".join(
                [
                    "---",
                    "id: CR-20260820-001",
                    "type: change-request",
                    "status: active",
                    "title: Change",
                    "created: 2026-08-20",
                    "updated: 2026-08-20",
                    "tags: []",
                    "related: []",
                    "source_paths: []",
                    "confidence: confirmed",
                    "---",
                    "",
                    "# CR-20260820-001 - Change",
                    "",
                ]
            ),
            encoding="utf-8",
        )

        codes = self.codes()

        self.assertIn("id-duplicate", codes)
        self.assertIn("id-filename-mismatch", codes)

    def test_registry_duplicate_missing_path_and_uncatalogued_id_are_reported(self) -> None:
        registry_path = self.root / "REGISTRY.yml"
        registry = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
        registry["documents"][0]["path"] = "missing/document.md"
        registry["documents"].append(dict(registry["documents"][1]))
        registry_path.write_text(yaml.safe_dump(registry, sort_keys=False), encoding="utf-8")
        extra = self.root / "technical" / "modules" / "extra.md"
        extra.write_text(
            "\n".join(
                [
                    "---",
                    "id: MOD-001",
                    "type: module",
                    "status: active",
                    "title: Extra module",
                    "created: 2026-08-20",
                    "updated: 2026-08-20",
                    "tags: []",
                    "related: []",
                    "source_paths: []",
                    "confidence: confirmed",
                    "---",
                    "",
                    "# Extra module",
                    "",
                ]
            ),
            encoding="utf-8",
        )

        codes = self.codes()

        self.assertIn("registry-id-duplicate", codes)
        self.assertIn("registry-path-missing", codes)
        self.assertIn("registry-entry-missing", codes)

    def test_registry_related_id_must_exist(self) -> None:
        registry_path = self.root / "REGISTRY.yml"
        registry = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
        registry["documents"][0]["related"] = ["MISSING-001"]
        registry_path.write_text(yaml.safe_dump(registry, sort_keys=False), encoding="utf-8")

        self.assertIn("registry-related-id-missing", self.codes())

    def test_broken_link_and_anchor_are_reported_but_valid_anchor_passes(self) -> None:
        index = self.root / "INDEX.md"
        index.write_text(
            "\n".join(
                [
                    "# Project Wiki",
                    "",
                    "- [Valid project heading](./PROJECT.md#project)",
                    "- [Missing document](./missing.md)",
                    "- [Missing anchor](./PROJECT.md#not-there)",
                    "",
                ]
            ),
            encoding="utf-8",
        )

        findings = validate_wiki.validate_wiki(self.root).findings
        codes = [finding.code for finding in findings]

        self.assertEqual(codes.count("link-target-missing"), 1)
        self.assertEqual(codes.count("link-anchor-missing"), 1)

    def test_commonmark_links_setext_headings_and_code_fences_are_parsed_structurally(self) -> None:
        docs_root = self.root / "docs"
        docs_root.mkdir()
        nested_target = docs_root / "a(b).md"
        nested_target.write_text("Section\n=======\n", encoding="utf-8")
        reference_target = docs_root / "target.md"
        reference_target.write_text("# Section\n", encoding="utf-8")
        index = self.root / "INDEX.md"
        index.write_text(
            "\n".join(
                [
                    "# Project Wiki",
                    "",
                    "- [Nested parentheses](./docs/a(b).md#section)",
                    "- [Reference link][target]",
                    "",
                    "[target]: ./docs/target.md#section",
                    "",
                    "````markdown",
                    "[Ignored broken link](./missing-from-code.md)",
                    "Status: impossible",
                    "````",
                    "",
                ]
            ),
            encoding="utf-8",
        )

        findings = validate_wiki.validate_wiki(self.root).findings

        self.assertFalse(any(finding.path == "INDEX.md" for finding in findings))

    def test_registry_fragment_must_identify_the_matching_embedded_record(self) -> None:
        requirements = self.root / "requirements" / "functional" / "authentication.md"
        requirements.write_text(
            "\n".join(
                [
                    "---",
                    "id: REQ-TOPIC-20260820-001",
                    "type: requirements-topic",
                    "status: active",
                    "title: Requirements",
                    "created: 2026-08-20",
                    "updated: 2026-08-20",
                    "tags: []",
                    "related: []",
                    "source_paths: []",
                    "confidence: confirmed",
                    "---",
                    "",
                    '<a id="req-001"></a>',
                    "",
                    "## REQ-001 - First",
                    "",
                    "Status: draft",
                    "",
                    '<a id="req-002"></a>',
                    "",
                    "## REQ-002 - Second",
                    "",
                    "Status: active",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        registry_path = self.root / "REGISTRY.yml"
        registry = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
        registry["documents"].append(
            {
                "id": "REQ-TOPIC-20260820-001",
                "type": "requirements-topic",
                "title": "Requirements",
                "path": "requirements/functional/authentication.md",
                "status": "active",
                "tags": [],
                "related": [],
                "source_paths": [],
                "confidence": "confirmed",
            }
        )
        registry["documents"].append(
            {
                "id": "REQ-001",
                "type": "api",
                "title": "First",
                "path": "requirements/functional/authentication.md#req-002",
                "status": "active",
                "tags": [],
                "related": [],
                "source_paths": [],
                "confidence": "confirmed",
            }
        )
        registry["documents"].append(
            {
                "id": "REQ-002",
                "type": "requirement",
                "title": "Second",
                "path": "requirements/functional/authentication.md#req-002",
                "status": "active",
                "tags": [],
                "related": [],
                "source_paths": [],
                "confidence": "confirmed",
            }
        )
        registry_path.write_text(yaml.safe_dump(registry, sort_keys=False), encoding="utf-8")

        findings = validate_wiki.validate_wiki(self.root).findings

        self.assertTrue(any(finding.code == "registry-anchor-id-mismatch" and "REQ-001" in finding.message for finding in findings))
        self.assertFalse(any(finding.code == "registry-anchor-id-mismatch" and "REQ-002" in finding.message for finding in findings))
        self.assertTrue(any(finding.code == "registry-id-type-mismatch" and "REQ-001" in finding.message for finding in findings))
        self.assertTrue(any(finding.code == "registry-embedded-status-mismatch" and "REQ-001" in finding.message for finding in findings))

    def test_data_id_attribute_does_not_create_an_anchor(self) -> None:
        requirements = self.root / "requirements" / "functional" / "authentication.md"
        requirements.write_text(
            "\n".join(
                [
                    "---",
                    "id: REQ-TOPIC-20260820-001",
                    "type: requirements-topic",
                    "status: active",
                    "title: Authentication",
                    "created: 2026-08-20",
                    "updated: 2026-08-20",
                    "tags: []",
                    "related: []",
                    "source_paths: []",
                    "confidence: confirmed",
                    "---",
                    "",
                    "# Authentication",
                    "",
                    '<a data-id="req-001"></a>',
                    "",
                    "## REQ-001 - Requirement",
                    "",
                    "Status: active",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        registry_path = self.root / "REGISTRY.yml"
        registry = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
        registry["documents"].append(
            {
                "id": "REQ-TOPIC-20260820-001",
                "type": "requirements-topic",
                "title": "Authentication",
                "path": "requirements/functional/authentication.md",
                "status": "active",
                "tags": [],
                "related": [],
                "source_paths": [],
                "confidence": "confirmed",
            }
        )
        registry["documents"].append(
            {
                "id": "REQ-001",
                "type": "requirement",
                "title": "Requirement",
                "path": "requirements/functional/authentication.md#req-001",
                "status": "active",
                "tags": [],
                "related": [],
                "source_paths": [],
                "confidence": "confirmed",
            }
        )
        registry_path.write_text(yaml.safe_dump(registry, sort_keys=False), encoding="utf-8")

        codes = self.codes()

        self.assertIn("registry-anchor-missing", codes)

    def test_embedded_id_prefix_is_not_truncated(self) -> None:
        validator = validate_wiki.WikiValidator(self.root)

        self.assertIsNone(validator.heading_id("REQ-0010 - Not a valid REQ-001 token"))
        self.assertEqual(validator.heading_id("REQ-001 - Valid"), "REQ-001")

    def test_embedded_title_is_extracted_after_actual_id_position(self) -> None:
        validator = validate_wiki.WikiValidator(self.root)

        self.assertEqual(
            validator.heading_title("REQ-001 - User authentication", "REQ-001"),
            "User authentication",
        )
        self.assertEqual(
            validator.heading_title(
                "[2026-08-25] scan | WLOG-20260825-001 | Initial Repository Scan",
                "WLOG-20260825-001",
            ),
            "Initial Repository Scan",
        )

    def test_wiki_log_registry_title_uses_text_after_embedded_id(self) -> None:
        log_path = self.root / "logs" / "wiki-log-2026-08.md"
        log_path.write_text(
            "\n".join(
                [
                    "# Wiki Log 2026-08",
                    "",
                    '<a id="wlog-20260825-001"></a>',
                    "",
                    "## [2026-08-25] scan | WLOG-20260825-001 | Initial Repository Scan",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        registry_path = self.root / "REGISTRY.yml"
        registry = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
        registry["documents"].append(
            {
                "id": "WLOG-20260825-001",
                "type": "note",
                "title": "Initial Repository Scan",
                "path": "logs/wiki-log-2026-08.md#wlog-20260825-001",
                "status": "active",
                "tags": ["log", "scan"],
                "related": [],
                "source_paths": [],
                "confidence": "confirmed",
            }
        )
        registry_path.write_text(yaml.safe_dump(registry, sort_keys=False), encoding="utf-8")

        valid_codes = self.codes()
        registry["documents"][-1]["title"] = "| WLOG-20260825-001 | Initial Repository Scan"
        registry_path.write_text(yaml.safe_dump(registry, sort_keys=False), encoding="utf-8")
        invalid_codes = self.codes()

        self.assertNotIn("registry-embedded-title-mismatch", valid_codes)
        self.assertIn("registry-embedded-title-mismatch", invalid_codes)

    def test_real_intake_source_text_is_not_interpreted_as_canonical_structure(self) -> None:
        source = Path(self.temporary_directory.name) / "source.md"
        source.write_text(
            "# Imported Source\n\n## REQ-999 - Source-only heading\n\nStatus: proposed\n",
            encoding="utf-8",
        )
        doc_id = "DOCIN-20260820-001"
        arguments = [
            "ingest_document.py",
            str(source),
            "--wiki-root",
            str(self.root),
            "--doc-id",
            doc_id,
            "--copy-source",
        ]
        with patch.object(sys, "argv", arguments), redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            exit_code = ingest_document.main()
        self.assertEqual(exit_code, 0)

        findings = validate_wiki.validate_wiki(self.root).findings

        self.assertFalse(any(finding.code == "status-invalid" and "chunks/" in finding.path for finding in findings))
        self.assertFalse(any("REQ-999" in finding.message for finding in findings))
        self.assertFalse(any(finding.code == "registry-updated-stale" for finding in findings))
        self.assertFalse(any(finding.path.startswith(f"intake/documents/{doc_id}/") for finding in findings))

    def test_inconsistent_intake_metadata_and_manifest_are_reported(self) -> None:
        source = Path(self.temporary_directory.name) / "source.md"
        source.write_text("# Imported Source\n\nContent\n", encoding="utf-8")
        doc_id = "DOCIN-20260820-001"
        arguments = [
            "ingest_document.py",
            str(source),
            "--wiki-root",
            str(self.root),
            "--doc-id",
            doc_id,
            "--copy-source",
        ]
        with patch.object(sys, "argv", arguments), redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(ingest_document.main(), 0)

        document_root = self.root / "intake" / "documents" / doc_id
        source_info_path = document_root / "source-info.yml"
        source_info = yaml.safe_load(source_info_path.read_text(encoding="utf-8"))
        source_info["source_sha256"] = "0" * 64
        source_info["chunk_count"] = 99
        source_info_path.write_text(yaml.safe_dump(source_info, sort_keys=False), encoding="utf-8")
        manifest_path = document_root / "chunks.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["chunks"][0]["text_path"] = "chunks/missing.md"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        codes = self.codes()

        self.assertIn("intake-source-hash-mismatch", codes)
        self.assertIn("intake-source-chunk-count-mismatch", codes)
        self.assertIn("intake-copied-source-hash-mismatch", codes)
        self.assertIn("intake-manifest-text-path-missing", codes)

    def test_swapped_intake_chunk_paths_are_reported(self) -> None:
        source = Path(self.temporary_directory.name) / "large-source.md"
        source.write_text(" ".join(f"word-{index}" for index in range(180)), encoding="utf-8")
        doc_id = "DOCIN-20260820-001"
        arguments = [
            "ingest_document.py",
            str(source),
            "--wiki-root",
            str(self.root),
            "--doc-id",
            doc_id,
            "--max-words",
            "80",
        ]
        with patch.object(sys, "argv", arguments), redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(ingest_document.main(), 0)
        manifest_path = self.root / "intake" / "documents" / doc_id / "chunks.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(manifest["chunks"]), 2)
        manifest["chunks"][0]["text_path"], manifest["chunks"][1]["text_path"] = (
            manifest["chunks"][1]["text_path"],
            manifest["chunks"][0]["text_path"],
        )
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        findings = validate_wiki.validate_wiki(self.root).findings

        mismatches = [finding for finding in findings if finding.code == "intake-manifest-chunk-target-id-mismatch"]
        self.assertGreaterEqual(len(mismatches), 2)

    def test_duplicate_intake_chunk_text_path_is_reported(self) -> None:
        document_root = self.ingest_source(
            " ".join(f"word-{index}" for index in range(180)),
            max_words=80,
        )
        manifest_path = document_root / "chunks.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(manifest["chunks"]), 2)
        manifest["chunks"][1]["text_path"] = manifest["chunks"][0]["text_path"]
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        self.assertIn("intake-manifest-text-path-duplicate", self.codes())

    def test_orphan_intake_chunk_file_is_reported(self) -> None:
        document_root = self.ingest_source("# Source\n\nContent\n")
        manifest = json.loads((document_root / "chunks.json").read_text(encoding="utf-8"))
        chunk = manifest["chunks"][0]
        chunk_path = document_root / chunk["text_path"]
        orphan_id = "DOCIN-20260820-001-CH-999"
        orphan_path = chunk_path.with_name("CH-999.md")
        orphan_path.write_text(
            chunk_path.read_text(encoding="utf-8").replace(chunk["id"], orphan_id),
            encoding="utf-8",
        )

        self.assertIn("intake-manifest-orphan-chunk", self.codes())

    def test_review_progress_must_cover_every_manifest_chunk(self) -> None:
        document_root = self.ingest_source(
            " ".join(f"word-{index}" for index in range(180)),
            max_words=80,
        )
        progress_path = document_root / "review-progress.yml"
        progress = yaml.safe_load(progress_path.read_text(encoding="utf-8"))
        progress["chunks"].pop()
        progress_path.write_text(yaml.safe_dump(progress, sort_keys=False), encoding="utf-8")

        codes = self.codes()

        self.assertIn("intake-review-progress-coverage-mismatch", codes)
        self.assertIn("intake-review-progress-summary-mismatch", codes)

    def test_reviewed_intake_requires_complete_chunk_dispositions(self) -> None:
        document_root = self.ingest_source("# Source\n\nContent\n")
        source_info_path = document_root / "source-info.yml"
        source_info = yaml.safe_load(source_info_path.read_text(encoding="utf-8"))
        source_info["status"] = "reviewed"
        source_info_path.write_text(yaml.safe_dump(source_info, sort_keys=False), encoding="utf-8")
        report_path = document_root / "intake-report.md"
        report_path.write_text(
            report_path.read_text(encoding="utf-8").replace("status: active", "status: reviewed", 1),
            encoding="utf-8",
        )

        self.assertIn("intake-review-progress-incomplete", self.codes())

    def test_legacy_intake_report_body_status_must_match_source_info(self) -> None:
        document_root = self.ingest_source("# Source\n\nContent\n")
        report_path = document_root / "intake-report.md"
        report = report_path.read_text(encoding="utf-8")
        report_path.write_text(
            report.replace("## Extraction Summary", "- Intake status: `active`\n\n## Extraction Summary"),
            encoding="utf-8",
        )

        self.assertNotIn("intake-report-body-status-mismatch", self.codes())

        report_path.write_text(
            report_path.read_text(encoding="utf-8").replace(
                "- Intake status: `active`",
                "- Intake status: `integrated`",
            ),
            encoding="utf-8",
        )

        self.assertIn("intake-report-body-status-mismatch", self.codes())

    def test_skipped_review_progress_entry_requires_reason(self) -> None:
        document_root = self.ingest_source("# Source\n\nContent\n")
        progress_path = document_root / "review-progress.yml"
        progress = yaml.safe_load(progress_path.read_text(encoding="utf-8"))
        progress["review_status"] = "complete"
        progress["summary"].update({"pending": 0, "skipped": 1})
        progress["chunks"][0]["status"] = "skipped"
        progress_path.write_text(yaml.safe_dump(progress, sort_keys=False), encoding="utf-8")

        self.assertIn("intake-review-progress-skip-reason-required", self.codes())

    def test_integrated_classified_chunk_requires_registered_target(self) -> None:
        document_root = self.ingest_source("# Source\n\nContent\n")
        progress_path = document_root / "review-progress.yml"
        progress = yaml.safe_load(progress_path.read_text(encoding="utf-8"))
        progress["review_status"] = "complete"
        progress["summary"].update({"pending": 0, "classified": 1})
        progress["chunks"][0].update({
            "status": "classified",
            "classifications": ["requirement"],
            "target_ids": [],
        })
        progress_path.write_text(yaml.safe_dump(progress, sort_keys=False), encoding="utf-8")
        source_info_path = document_root / "source-info.yml"
        source_info = yaml.safe_load(source_info_path.read_text(encoding="utf-8"))
        source_info["status"] = "integrated"
        source_info_path.write_text(yaml.safe_dump(source_info, sort_keys=False), encoding="utf-8")
        report_path = document_root / "intake-report.md"
        report_path.write_text(
            report_path.read_text(encoding="utf-8").replace("status: active", "status: integrated", 1),
            encoding="utf-8",
        )

        self.assertIn("intake-review-progress-target-required", self.codes())

        progress["chunks"][0]["target_ids"] = ["REQ-999"]
        progress_path.write_text(yaml.safe_dump(progress, sort_keys=False), encoding="utf-8")
        self.assertIn("intake-review-progress-target-missing", self.codes())

        progress["chunks"][0].update({
            "classifications": ["technical-documentation"],
            "target_ids": [self.ids["PROJECT.md"]],
        })
        progress_path.write_text(yaml.safe_dump(progress, sort_keys=False), encoding="utf-8")
        ledger_findings = [
            finding
            for finding in validate_wiki.validate_wiki(self.root).findings
            if finding.path.endswith("review-progress.yml")
        ]
        self.assertEqual(ledger_findings, [])

    def test_integrated_requirement_requires_atomic_target_and_matching_evidence(self) -> None:
        document_root = self.ingest_source("# Source\n\nThe product shall authenticate users.\n")
        manifest = json.loads((document_root / "chunks.json").read_text(encoding="utf-8"))
        chunk_id = manifest["chunks"][0]["id"]
        progress_path = document_root / "review-progress.yml"
        progress = yaml.safe_load(progress_path.read_text(encoding="utf-8"))
        progress["review_status"] = "complete"
        progress["summary"].update({"pending": 0, "classified": 1})
        progress["chunks"][0].update({
            "status": "classified",
            "classifications": ["requirement"],
            "target_ids": [self.ids["PROJECT.md"]],
        })
        progress_path.write_text(yaml.safe_dump(progress, sort_keys=False), encoding="utf-8")
        source_info_path = document_root / "source-info.yml"
        source_info = yaml.safe_load(source_info_path.read_text(encoding="utf-8"))
        source_info["status"] = "integrated"
        source_info_path.write_text(yaml.safe_dump(source_info, sort_keys=False), encoding="utf-8")

        self.assertIn("intake-review-progress-atomic-target-required", self.codes())

        self.add_atomic_requirement(chunk_id)
        progress["chunks"][0]["target_ids"] = ["REQ-001", "REQ-TOPIC-20260820-001"]
        progress_path.write_text(yaml.safe_dump(progress, sort_keys=False), encoding="utf-8")
        relevant = {
            finding.code
            for finding in validate_wiki.validate_wiki(self.root).findings
            if finding.path.endswith("review-progress.yml")
        }
        self.assertNotIn("intake-review-progress-atomic-target-required", relevant)
        self.assertNotIn("intake-review-progress-evidence-mismatch", relevant)

    def test_integrated_requirement_rejects_evidence_ledger_mismatch(self) -> None:
        document_root = self.ingest_source("# Source\n\nThe product shall authenticate users.\n")
        manifest = json.loads((document_root / "chunks.json").read_text(encoding="utf-8"))
        chunk_id = manifest["chunks"][0]["id"]
        self.add_atomic_requirement(chunk_id, evidence_chunk_id="DOCIN-20260820-999-CH-001")
        progress_path = document_root / "review-progress.yml"
        progress = yaml.safe_load(progress_path.read_text(encoding="utf-8"))
        progress["review_status"] = "complete"
        progress["summary"].update({"pending": 0, "classified": 1})
        progress["chunks"][0].update({
            "status": "classified",
            "classifications": ["requirement"],
            "target_ids": ["REQ-001"],
        })
        progress_path.write_text(yaml.safe_dump(progress, sort_keys=False), encoding="utf-8")
        source_info_path = document_root / "source-info.yml"
        source_info = yaml.safe_load(source_info_path.read_text(encoding="utf-8"))
        source_info["status"] = "integrated"
        source_info_path.write_text(yaml.safe_dump(source_info, sort_keys=False), encoding="utf-8")

        codes = self.codes()

        self.assertIn("requirement-evidence-chunk-missing", codes)
        self.assertIn("intake-review-progress-evidence-mismatch", codes)

    def test_uniform_overview_only_requirement_integration_is_rejected(self) -> None:
        document_root = self.ingest_source(
            "## One\n\nFirst requirement.\n\n"
            "## Two\n\nSecond requirement.\n\n"
            "## Three\n\nThird requirement.\n",
            max_words=80,
        )
        progress_path = document_root / "review-progress.yml"
        progress = yaml.safe_load(progress_path.read_text(encoding="utf-8"))
        progress["review_status"] = "complete"
        progress["summary"].update({"pending": 0, "classified": 3})
        for entry in progress["chunks"]:
            entry.update({
                "status": "classified",
                "classifications": ["requirement"],
                "target_ids": [self.ids["PROJECT.md"]],
                "notes": "Requirement candidate reviewed.",
            })
        progress_path.write_text(yaml.safe_dump(progress, sort_keys=False), encoding="utf-8")
        source_info_path = document_root / "source-info.yml"
        source_info = yaml.safe_load(source_info_path.read_text(encoding="utf-8"))
        source_info["status"] = "integrated"
        source_info_path.write_text(yaml.safe_dump(source_info, sort_keys=False), encoding="utf-8")

        findings = [
            finding
            for finding in validate_wiki.validate_wiki(self.root).findings
            if finding.code == "intake-review-progress-atomic-target-required"
        ]

        self.assertEqual(len(findings), 3)

    def test_indexes_cannot_contain_atomic_records(self) -> None:
        index_path = self.root / "requirements" / "functional" / "INDEX.md"
        index_path.write_text(
            index_path.read_text(encoding="utf-8")
            + "\n<a id=\"req-001\"></a>\n\n## REQ-001 - Invalid Index Record\n\nStatus: active\n",
            encoding="utf-8",
        )

        codes = self.codes()

        self.assertIn("index-embedded-record-invalid", codes)
        self.assertIn("atomic-record-location-invalid", codes)

    def test_atomic_evidence_rejects_ranges_and_duplicates(self) -> None:
        self.add_atomic_requirement("DOCIN-20260820-001-CH-001")
        evidence_path = self.root / "traceability" / "requirement-evidence.yml"
        payload = yaml.safe_load(evidence_path.read_text(encoding="utf-8"))
        payload["records"]["REQ-001"] = [
            "DOCIN-20260820-001-CH-001",
            "DOCIN-20260820-001-CH-001",
        ]
        evidence_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
        self.assertIn("requirement-evidence-chunks-invalid", self.codes())

        payload["records"]["REQ-001"] = [
            "DOCIN-20260820-001-CH-001 through DOCIN-20260820-001-CH-003"
        ]
        evidence_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
        self.assertIn("requirement-evidence-chunk-id-invalid", self.codes())

    def test_inline_atomic_evidence_is_rejected(self) -> None:
        self.add_atomic_requirement("DOCIN-20260820-001-CH-001")
        topic_path = self.root / "requirements" / "functional" / "authentication.md"
        content = topic_path.read_text(encoding="utf-8")
        topic_path.write_text(
            content.replace("Confidence: confirmed", "Evidence: [DOCIN-20260820-001-CH-001]\nConfidence: confirmed", 1),
            encoding="utf-8",
        )

        self.assertIn("embedded-inline-evidence-invalid", self.codes())

    def test_atomic_intake_chunk_reference_is_rejected_but_code_path_is_allowed(self) -> None:
        document_root = self.ingest_source("# Source\n\nThe product shall authenticate users.\n")
        manifest = json.loads((document_root / "chunks.json").read_text(encoding="utf-8"))
        chunk_id = manifest["chunks"][0]["id"]
        self.add_atomic_requirement(chunk_id)
        topic_path = self.root / "requirements" / "functional" / "authentication.md"
        content = topic_path.read_text(encoding="utf-8")
        intake_id, chunk_sequence = chunk_id.rsplit("-CH-", 1)
        intake_path = f".project-wiki/intake/documents/{intake_id}/chunks/CH-{chunk_sequence}.md"
        topic_path.write_text(
            content.replace("Related: []\nConfidence: confirmed", f"Related: []\nSource paths: [{intake_path}]\nConfidence: confirmed"),
            encoding="utf-8",
        )

        self.assertIn("embedded-intake-chunk-reference-invalid", self.codes())

        topic_path.write_text(
            topic_path.read_text(encoding="utf-8").replace(intake_path, "src/authentication.py"),
            encoding="utf-8",
        )

        self.assertNotIn("embedded-intake-chunk-reference-invalid", self.codes())

    def test_source_registry_invalid_status_hash_and_current_path_are_reported(self) -> None:
        source_registry = {
            "version": 1,
            "updated": "2026-08-20",
            "sources": [
                {
                    "id": "SRC-20260820-001",
                    "status": "unknown",
                    "original_path": "sources/inbox/source.md",
                    "current_path": "sources/processed/2026-08/source.md",
                    "filename": "source.md",
                    "sha256": "bad-hash",
                    "intake_id": None,
                    "processed_at": None,
                    "tags": [],
                    "notes": "Invalid fixture",
                }
            ],
        }
        (self.root / "sources" / "SOURCE_REGISTRY.yml").write_text(
            yaml.safe_dump(source_registry, sort_keys=False),
            encoding="utf-8",
        )

        codes = self.codes()

        self.assertIn("source-registry-status-invalid", codes)
        self.assertIn("source-registry-hash-invalid", codes)
        self.assertIn("source-registry-current-path-missing", codes)

    def test_processed_source_archive_must_match_intake_provenance(self) -> None:
        archived, _, _ = self.create_processed_source_fixture()

        valid_findings = validate_wiki.validate_wiki(self.root).findings
        self.assertFalse(any(finding.path == "sources/SOURCE_REGISTRY.yml" for finding in valid_findings))

        archived.write_text("Tampered bytes", encoding="utf-8")
        self.assertIn("processed-source-current-hash-mismatch", self.codes())

    def test_processed_source_requires_intake_id_and_processed_date(self) -> None:
        _, registry_path, source_registry = self.create_processed_source_fixture()
        source_registry["sources"][0]["intake_id"] = None
        source_registry["sources"][0]["processed_at"] = None
        registry_path.write_text(yaml.safe_dump(source_registry, sort_keys=False), encoding="utf-8")
        codes = self.codes()
        self.assertIn("processed-source-intake-required", codes)
        self.assertIn("processed-source-date-required", codes)

    def test_non_iso_frontmatter_date_is_reported(self) -> None:
        project = self.root / "PROJECT.md"
        project.write_text(
            project.read_text(encoding="utf-8").replace("created: 2026-08-20", "created: '2026-W34-4'"),
            encoding="utf-8",
        )

        self.assertIn("date-invalid", self.codes())

    def test_registry_frontmatter_drift_is_reported(self) -> None:
        registry_path = self.root / "REGISTRY.yml"
        registry = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
        registry["documents"][0]["title"] = "Drifted title"
        registry_path.write_text(yaml.safe_dump(registry, sort_keys=False), encoding="utf-8")

        self.assertIn("registry-frontmatter-mismatch", self.codes())

    def test_invalid_alert_status_is_reported(self) -> None:
        alert = self.root / "alerts" / "ALERT-20260820-001-invalid-status.md"
        alert.write_text(
            "\n".join(
                [
                    "---",
                    "id: ALERT-20260820-001",
                    "type: alert",
                    "status: integrated",
                    "severity: high",
                    "title: Invalid alert",
                    "created: 2026-08-20",
                    "updated: 2026-08-20",
                    "tags: []",
                    "related: []",
                    "source_paths: []",
                    "confidence: confirmed",
                    "---",
                    "",
                    "# Invalid alert",
                    "",
                ]
            ),
            encoding="utf-8",
        )

        self.assertIn("status-invalid", self.codes())

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks are not supported")
    def test_external_broken_and_directory_symlinks_are_reported_without_crashing_json(self) -> None:
        outside_file = Path(self.temporary_directory.name) / "outside.md"
        outside_file.write_text("# Outside\n", encoding="utf-8")
        project = self.root / "PROJECT.md"
        project.unlink()
        project.symlink_to(outside_file)

        security = self.root / "technical" / "security.md"
        security.unlink()
        security.symlink_to(Path(self.temporary_directory.name) / "missing.md")

        outside_directory = Path(self.temporary_directory.name) / "outside-directory"
        outside_directory.mkdir()
        (self.root / "technical" / "modules" / "external").symlink_to(outside_directory, target_is_directory=True)

        arguments = ["validate_wiki.py", "--wiki-root", str(self.root), "--format", "json"]
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch.object(sys, "argv", arguments), redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = validate_wiki.main()

        payload = json.loads(stdout.getvalue())
        symlink_findings = [finding for finding in payload["findings"] if finding["code"] == "symlink-not-allowed"]
        self.assertEqual(exit_code, 1)
        self.assertEqual(stderr.getvalue(), "")
        self.assertEqual(len(symlink_findings), 3)

    def test_link_outside_wiki_is_reported(self) -> None:
        outside = self.root.parent / "outside.md"
        outside.write_text("# Outside\n", encoding="utf-8")
        (self.root / "INDEX.md").write_text("# Index\n\n[Outside](../outside.md)\n", encoding="utf-8")

        self.assertIn("link-outside-wiki", self.codes())

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks are not supported")
    def test_registry_source_path_resolving_outside_repository_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as external_directory:
            external = Path(external_directory) / "source.py"
            external.write_text("print('outside')\n", encoding="utf-8")
            (self.root.parent / "external-source.py").symlink_to(external)
            registry_path = self.root / "REGISTRY.yml"
            registry = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
            registry["documents"][0]["source_paths"] = ["external-source.py"]
            registry_path.write_text(yaml.safe_dump(registry, sort_keys=False), encoding="utf-8")

            self.assertIn("source-path-outside-repository", self.codes())

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks are not supported")
    def test_linked_symlink_loop_is_a_json_finding_not_a_crash(self) -> None:
        loop = self.root / "loop.md"
        loop.symlink_to("loop.md")
        (self.root / "INDEX.md").write_text("# Index\n\n[Loop](./loop.md)\n", encoding="utf-8")
        arguments = ["validate_wiki.py", "--wiki-root", str(self.root), "--format", "json"]
        stdout = io.StringIO()
        stderr = io.StringIO()

        with patch.object(sys, "argv", arguments), redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = validate_wiki.main()

        payload = json.loads(stdout.getvalue())
        codes = {finding["code"] for finding in payload["findings"]}
        self.assertEqual(exit_code, 1)
        self.assertEqual(stderr.getvalue(), "")
        self.assertIn("symlink-not-allowed", codes)
        self.assertIn("symlink-target-not-allowed", codes)

    def test_missing_dependencies_use_json_error_contract(self) -> None:
        original_import = builtins.__import__
        arguments = ["validate_wiki.py", "--wiki-root", str(self.root), "--format", "json"]
        for dependency in ("yaml", "markdown_it"):
            with self.subTest(dependency=dependency):
                stdout = io.StringIO()
                stderr = io.StringIO()

                def import_without_dependency(name: str, *args: object, **kwargs: object) -> object:
                    if name == dependency:
                        raise ImportError(f"{dependency} unavailable")
                    return original_import(name, *args, **kwargs)

                with (
                    patch.object(builtins, "__import__", side_effect=import_without_dependency),
                    patch.object(sys, "argv", arguments),
                    redirect_stdout(stdout),
                    redirect_stderr(stderr),
                ):
                    exit_code = validate_wiki.main()

                payload = json.loads(stdout.getvalue())
                self.assertEqual(exit_code, 2)
                self.assertEqual(stderr.getvalue(), "")
                self.assertEqual(payload["findings"][0]["code"], "validator-dependency-error")

    def test_json_cli_returns_one_and_separates_semantic_checks(self) -> None:
        (self.root / "technical/security.md").unlink()
        arguments = ["validate_wiki.py", "--wiki-root", str(self.root), "--format", "json"]
        stdout = io.StringIO()
        stderr = io.StringIO()

        with patch.object(sys, "argv", arguments), redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = validate_wiki.main()

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 1)
        self.assertEqual(stderr.getvalue(), "")
        self.assertFalse(payload["valid"])
        self.assertGreater(payload["summary"]["errors"], 0)
        self.assertIn("Markdown frontmatter fields and value domains", payload["deterministic_checks"])
        self.assertIn(
            "contradictions between requirements, decisions, documentation, and code",
            payload["semantic_checks_deferred"],
        )


if __name__ == "__main__":
    unittest.main()