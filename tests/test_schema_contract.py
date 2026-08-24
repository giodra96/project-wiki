from __future__ import annotations

import io
import json
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

import yaml  # type: ignore[import-untyped]

from scripts import check_contracts, check_inbox, ingest_document, validate_wiki
from scripts.schema_contract import SchemaContractError, load_schema_contract
from tests.wiki_fixtures import create_valid_wiki


class SchemaContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.contract = load_schema_contract()

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def copy_contract_surface(self) -> Path:
        repo_root = self.root / "repo"
        relatives = set(self.contract.documentation.version_references)
        for paths in self.contract.documentation.required_path_references.values():
            relatives.update(paths)
        for paths in self.contract.documentation.forbidden_root_paths.values():
            relatives.update(paths)
        relatives.update(
            {
                self.contract.documentation.public_tree_file,
                "assets/document-templates.md",
            }
        )
        relatives.update(self.contract.template_section_inventory)
        source_root = Path(__file__).resolve().parents[1]
        for relative in relatives:
            source = source_root / relative
            target = repo_root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        return repo_root

    def codes(self, repo_root: Path) -> set[str]:
        return {finding.code for finding in check_contracts.check_contracts(repo_root, self.contract).findings}

    def test_repository_contract_surface_matches_manifest(self) -> None:
        report = check_contracts.check_contracts(Path(__file__).resolve().parents[1], self.contract)

        self.assertTrue(report.valid)
        self.assertEqual(report.findings, ())

    def test_ci_runs_contract_checker_and_compiles_contract_modules(self) -> None:
        workflow_path = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "tests.yml"
        workflow = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
        steps = workflow["jobs"]["python-tests"]["steps"]
        runs = "\n".join(step.get("run", "") for step in steps)

        self.assertIn("python scripts/check_contracts.py", runs)
        self.assertIn("scripts/check_contracts.py", runs)
        self.assertIn("scripts/schema_contract.py", runs)
        self.assertIn("tests/test_schema_contract.py", runs)

    def test_version_reference_drift_is_reported(self) -> None:
        repo_root = self.copy_contract_surface()
        skill = repo_root / "SKILL.md"
        skill.write_text(
            skill.read_text(encoding="utf-8").replace(self.contract.schema_version, "9.9.9"),
            encoding="utf-8",
        )

        self.assertIn("schema-version-reference-missing", self.codes(repo_root))

    def test_unrelated_semantic_version_does_not_trigger_schema_drift(self) -> None:
        repo_root = self.copy_contract_surface()
        readme = repo_root / "README.md"
        readme.write_text(readme.read_text(encoding="utf-8") + "\nUnrelated library version: 9.9.9.\n", encoding="utf-8")

        self.assertNotIn("schema-version-reference-missing", self.codes(repo_root))
        self.assertNotIn("schema-version-drift", self.codes(repo_root))

    def test_additional_stale_schema_version_is_reported(self) -> None:
        repo_root = self.copy_contract_surface()
        readme = repo_root / "README.md"
        readme.write_text(readme.read_text(encoding="utf-8") + "\nPrevious schema version: 9.9.9.\n", encoding="utf-8")

        self.assertIn("schema-version-drift", self.codes(repo_root))

    def test_public_root_decisions_path_is_rejected(self) -> None:
        repo_root = self.copy_contract_surface()
        readme = repo_root / "README.md"
        readme.write_text(
            readme.read_text(encoding="utf-8").replace(
                "|   `-- decisions/        # Architectural Decision Records (ADRs)",
                "|-- decisions/            # Architectural Decision Records (ADRs)",
            ),
            encoding="utf-8",
        )

        codes = self.codes(repo_root)
        self.assertIn("public-tree-entry-extra", codes)
        self.assertIn("public-tree-entry-missing", codes)

    def test_forbidden_root_decisions_alias_in_prose_is_rejected(self) -> None:
        repo_root = self.copy_contract_surface()
        contributing = repo_root / "CONTRIBUTING.md"
        contributing.write_text(
            contributing.read_text(encoding="utf-8")
            + "\nStore ADRs in `decisions/`.\n\n```bash\nls .project-wiki/decisions/\n```\n",
            encoding="utf-8",
        )

        findings = check_contracts.check_contracts(repo_root, self.contract).findings
        aliases = [finding for finding in findings if finding.code == "forbidden-root-path-reference"]
        self.assertGreaterEqual(len(aliases), 2)

    def test_template_and_version_drift_are_reported(self) -> None:
        repo_root = self.copy_contract_surface()
        templates = repo_root / "assets" / "core-templates.md"
        templates.write_text(
            templates.read_text(encoding="utf-8").replace(
                f"schema_version: {self.contract.schema_version}",
                "schema_version: 9.9.9",
            ),
            encoding="utf-8",
        )

        codes = self.codes(repo_root)
        self.assertIn("schema-version-reference-missing", codes)
        self.assertIn("template-wiki-version-drift", codes)

    def test_template_status_and_id_domains_are_checked(self) -> None:
        repo_root = self.copy_contract_surface()
        intake_templates = repo_root / "assets" / "intake-source-templates.md"
        intake_templates.write_text(
            intake_templates.read_text(encoding="utf-8")
            .replace("DOCIN-YYYYMMDD-001-REVIEW", "DOCIN-YYYYMMDD-001-BAD", 1),
            encoding="utf-8",
        )
        governance_templates = repo_root / "assets" / "governance-templates.md"
        governance_templates.write_text(
            governance_templates.read_text(encoding="utf-8")
            .replace("type: alert\nstatus: open", "type: alert\nstatus: integrated", 1),
            encoding="utf-8",
        )

        codes = self.codes(repo_root)
        self.assertIn("template-status-drift", codes)
        self.assertIn("template-id-pattern-drift", codes)

    def test_template_frontmatter_fields_and_shapes_are_checked(self) -> None:
        repo_root = self.copy_contract_surface()
        intake_templates = repo_root / "assets" / "intake-source-templates.md"
        intake_templates.write_text(
            intake_templates.read_text(encoding="utf-8").replace(
                "source_paths: []\nconfidence: inferred",
                "confidence: inferred",
                1,
            ),
            encoding="utf-8",
        )
        governance_templates = repo_root / "assets" / "governance-templates.md"
        governance_templates.write_text(
            governance_templates.read_text(encoding="utf-8").replace(
                "created: YYYY-MM-DD",
                "created: 20260820",
                1,
            ),
            encoding="utf-8",
        )

        codes = self.codes(repo_root)
        self.assertIn("template-frontmatter-fields-drift", codes)
        self.assertIn("template-frontmatter-shape-drift", codes)

    def test_registry_template_shape_is_checked(self) -> None:
        repo_root = self.copy_contract_surface()
        core_templates = repo_root / "assets" / "core-templates.md"
        core_templates.write_text(
            core_templates.read_text(encoding="utf-8").replace("documents: []", "documents: {}", 1),
            encoding="utf-8",
        )

        codes = self.codes(repo_root)
        self.assertIn("template-registry-shape-drift", codes)

    def test_template_section_deletion_is_reported(self) -> None:
        repo_root = self.copy_contract_surface()
        governance_templates = repo_root / "assets" / "governance-templates.md"
        governance_text = governance_templates.read_text(encoding="utf-8")
        alert_start = governance_text.index("## Alert\n")
        alert_end = governance_text.index("\n## ", alert_start + 4)
        governance_templates.write_text(
            governance_text[:alert_start] + governance_text[alert_end + 1 :],
            encoding="utf-8",
        )

        findings = check_contracts.check_contracts(repo_root, self.contract).findings

        self.assertTrue(
            any(
                finding.code == "template-section-missing"
                and finding.path == "assets/governance-templates.md"
                for finding in findings
            )
        )
        self.assertTrue(
            any(
                finding.code == "template-inventory-missing"
                and finding.path == "assets/governance-templates.md"
                for finding in findings
            )
        )

    def test_template_frontmatter_fence_language_change_is_reported(self) -> None:
        repo_root = self.copy_contract_surface()
        technical_templates = repo_root / "assets" / "technical-implementation-templates.md"
        technical_text = technical_templates.read_text(encoding="utf-8")
        api_start = technical_text.index("## API Documentation\n")
        api_end = technical_text.index("\n## ", api_start + 4)
        api_section = technical_text[api_start:api_end].replace("```markdown", "```md", 1)
        technical_templates.write_text(
            technical_text[:api_start] + api_section + technical_text[api_end:],
            encoding="utf-8",
        )

        findings = check_contracts.check_contracts(repo_root, self.contract).findings

        self.assertTrue(
            any(
                finding.code == "template-inventory-missing"
                and finding.path == "assets/technical-implementation-templates.md"
                for finding in findings
            )
        )

    def test_alert_template_requires_severity(self) -> None:
        repo_root = self.copy_contract_surface()
        templates = repo_root / "assets" / "governance-templates.md"
        templates.write_text(
            templates.read_text(encoding="utf-8").replace("severity: medium\n", "", 1),
            encoding="utf-8",
        )

        findings = check_contracts.check_contracts(repo_root, self.contract).findings

        self.assertTrue(
            any(
                finding.code == "template-frontmatter-fields-drift"
                and finding.path == "assets/governance-templates.md"
                for finding in findings
            )
        )

    def test_template_section_in_wrong_owner_file_is_reported(self) -> None:
        repo_root = self.copy_contract_surface()
        governance_templates = repo_root / "assets" / "governance-templates.md"
        governance_text = governance_templates.read_text(encoding="utf-8")
        alert_start = governance_text.index("## Alert\n")
        alert_end = governance_text.index("\n## ", alert_start + 4)
        alert_section = governance_text[alert_start:alert_end]
        governance_templates.write_text(
            governance_text[:alert_start] + governance_text[alert_end + 1 :],
            encoding="utf-8",
        )
        core_templates = repo_root / "assets" / "core-templates.md"
        core_templates.write_text(
            core_templates.read_text(encoding="utf-8") + "\n" + alert_section + "\n",
            encoding="utf-8",
        )

        findings = check_contracts.check_contracts(repo_root, self.contract).findings

        self.assertTrue(
            any(
                finding.code == "template-section-missing"
                and finding.path == "assets/governance-templates.md"
                for finding in findings
            )
        )
        self.assertTrue(
            any(
                finding.code == "template-section-extra"
                and finding.path == "assets/core-templates.md"
                for finding in findings
            )
        )

    def test_artifact_filename_change_requires_documentation_updates(self) -> None:
        repo_root = self.copy_contract_surface()
        payload = yaml.safe_load(self.contract.manifest_path.read_text(encoding="utf-8"))
        payload["intake_artifacts"]["source_info"] = "metadata.yml"
        payload["canonical_tree"]["example_files"] = [
            value.replace("source-info.yml", "metadata.yml")
            for value in payload["canonical_tree"]["example_files"]
        ]
        manifest = self.root / "renamed-artifact.yml"
        manifest.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
        contract = load_schema_contract(manifest)

        findings = check_contracts.check_contracts(repo_root, contract).findings

        self.assertTrue(any(finding.code == "intake-artifact-reference-missing" for finding in findings))

    def test_duplicate_manifest_key_is_rejected(self) -> None:
        manifest = self.root / "project-wiki.yml"
        manifest.write_text(
            self.contract.manifest_path.read_text(encoding="utf-8") + "\nmanifest_version: 1\n",
            encoding="utf-8",
        )

        with self.assertRaisesRegex(SchemaContractError, "duplicate key"):
            load_schema_contract(manifest)

    def test_invalid_manifest_mutations_are_rejected(self) -> None:
        original = yaml.safe_load(self.contract.manifest_path.read_text(encoding="utf-8"))
        mutations = [
            ("unsupported manifest", lambda payload: payload.__setitem__("manifest_version", 2), "unsupported manifest_version"),
            ("boolean manifest", lambda payload: payload.__setitem__("manifest_version", True), "must be an integer"),
            ("unknown top level", lambda payload: payload.__setitem__("unknown", {}), "manifest keys mismatch"),
            ("unknown generation", lambda payload: payload["id_generation"].__setitem__("unknown", 1), "id_generation keys mismatch"),
            ("invalid date format", lambda payload: payload["id_generation"].__setitem__("intake_date_format", "%Q"), "generation intake document settings"),
            ("invalid manifest extension", lambda payload: payload["intake_artifacts"].__setitem__("chunks_manifest", "segments.yml"), "chunks_manifest must use"),
            (
                "invalid review completion status",
                lambda payload: payload["review_progress"].__setitem__("complete_entry_statuses", ["unknown"]),
                "non-empty subset",
            ),
            ("missing pattern", lambda payload: payload["id_patterns"].pop("decision"), "unknown ID pattern"),
            ("invalid initial lifecycle", lambda payload: payload["generated_values"].__setitem__("source_initial_status", "ignored"), "source_initial_status must be processable"),
            (
                "duplicate template owner",
                lambda payload: payload["template_section_inventory"]["assets/governance-templates.md"].append("Root INDEX.md"),
                "exactly one owner file",
            ),
            (
                "non-normalized template owner",
                lambda payload: payload["template_section_inventory"].__setitem__(
                    "assets\\core-templates.md",
                    payload["template_section_inventory"].pop("assets/core-templates.md"),
                ),
                "normalized relative path",
            ),
        ]
        for name, mutate, message in mutations:
            with self.subTest(name=name):
                payload = yaml.safe_load(yaml.safe_dump(original))
                mutate(payload)
                manifest = self.root / f"{name.replace(' ', '-')}.yml"
                manifest.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
                with self.assertRaisesRegex(SchemaContractError, message):
                    load_schema_contract(manifest)

    def test_manifest_can_add_a_fully_declared_document_type(self) -> None:
        payload = yaml.safe_load(self.contract.manifest_path.read_text(encoding="utf-8"))
        payload["id_patterns"]["incident"] = r"INC-\d{3}"
        payload["id_examples"]["incident"] = "INC-001"
        payload["document_type_contracts"]["incident"] = {
            "id_pattern": "incident",
            "status_domain": "default",
        }
        manifest = self.root / "extended-type.yml"
        manifest.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

        contract = load_schema_contract(manifest)

        self.assertIn("incident", contract.document_type_contracts)
        self.assertTrue(contract.type_id_patterns["incident"].fullmatch("INC-001"))

    def test_validator_uses_manifest_version_instead_of_internal_constant(self) -> None:
        manifest = self.root / "project-wiki.yml"
        manifest.write_text(
            self.contract.manifest_path.read_text(encoding="utf-8").replace(
                f"version: {self.contract.schema_version}",
                "version: 9.9.9",
                1,
            ),
            encoding="utf-8",
        )
        wiki_root = self.root / ".project-wiki"
        wiki_root.mkdir()
        create_valid_wiki(wiki_root)

        findings = validate_wiki.validate_wiki(wiki_root, manifest).findings

        mismatch = next(finding for finding in findings if finding.code == "wiki-schema-version-mismatch")
        self.assertIn("Expected schema version 9.9.9", mismatch.message)

    def test_ingestion_id_generation_uses_manifest_parameters(self) -> None:
        payload = yaml.safe_load(self.contract.manifest_path.read_text(encoding="utf-8"))
        payload["id_patterns"]["intake-document"] = r"INTAKE-\d{8}-\d{3}"
        payload["id_patterns"]["intake-chunk"] = r"INTAKE-\d{8}-\d{3}-PART-\d{3}"
        payload["id_patterns"]["intake-review"] = r"INTAKE-\d{8}-\d{3}-REVIEW"
        payload["id_patterns"]["intake-extraction-index"] = r"INTAKE-\d{8}-\d{3}-EXTRACTED"
        payload["id_examples"]["intake-document"] = "INTAKE-20260820-001"
        payload["id_examples"]["intake-chunk"] = "INTAKE-20260820-001-PART-001"
        payload["id_examples"]["intake-review"] = "INTAKE-20260820-001-REVIEW"
        payload["id_examples"]["intake-extraction-index"] = "INTAKE-20260820-001-EXTRACTED"
        payload["template_contracts"]["Document Intake Review"]["id"] = "INTAKE-YYYYMMDD-001-REVIEW"
        payload["id_generation"]["intake_document_prefix"] = "INTAKE"
        payload["id_generation"]["intake_chunk_label"] = "PART"
        payload["canonical_tree"]["example_files"] = [
            value.replace("DOCIN-YYYYMMDD-001", "INTAKE-YYYYMMDD-001").replace("chunks/CH-001.md", "chunks/PART-001.md")
            for value in payload["canonical_tree"]["example_files"]
        ]
        manifest = self.root / "alternate-generation.yml"
        manifest.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
        contract = load_schema_contract(manifest)
        documents_root = self.root / "documents"

        doc_id = ingest_document.next_doc_id(documents_root, contract)
        chunks = ingest_document.build_chunks(
            doc_id,
            [ingest_document.TextBlock("content")],
            max_words=80,
            contract=contract,
        )

        self.assertRegex(doc_id, r"^INTAKE-\d{8}-001$")
        self.assertEqual(chunks[0].id, f"{doc_id}-PART-001")

    def test_dashed_intake_date_format_is_accepted_when_contract_is_consistent(self) -> None:
        payload = yaml.safe_load(self.contract.manifest_path.read_text(encoding="utf-8"))
        replacements = {
            "intake-document": r"DOCIN-\d{4}-\d{2}-\d{2}-\d{3}",
            "intake-chunk": r"DOCIN-\d{4}-\d{2}-\d{2}-\d{3}-CH-\d{3}",
            "intake-review": r"DOCIN-\d{4}-\d{2}-\d{2}-\d{3}-REVIEW",
            "intake-extraction-index": r"DOCIN-\d{4}-\d{2}-\d{2}-\d{3}-EXTRACTED",
        }
        payload["id_patterns"].update(replacements)
        payload["id_examples"].update(
            {
                "intake-document": "DOCIN-2026-08-20-001",
                "intake-chunk": "DOCIN-2026-08-20-001-CH-001",
                "intake-review": "DOCIN-2026-08-20-001-REVIEW",
                "intake-extraction-index": "DOCIN-2026-08-20-001-EXTRACTED",
            }
        )
        payload["id_generation"]["intake_date_format"] = "%Y-%m-%d"
        payload["template_contracts"]["Document Intake Review"]["id"] = "DOCIN-YYYY-MM-DD-001-REVIEW"
        payload["canonical_tree"]["example_files"] = [
            value.replace("DOCIN-YYYYMMDD-001", "DOCIN-YYYY-MM-DD-001")
            for value in payload["canonical_tree"]["example_files"]
        ]
        manifest = self.root / "dashed-date.yml"
        manifest.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

        contract = load_schema_contract(manifest)
        doc_id = ingest_document.next_doc_id(self.root / "documents", contract)

        self.assertRegex(doc_id, r"^DOCIN-\d{4}-\d{2}-\d{2}-001$")

    def test_alternate_chunk_contract_round_trips_through_all_helpers(self) -> None:
        payload = yaml.safe_load(self.contract.manifest_path.read_text(encoding="utf-8"))
        payload["id_patterns"]["intake-document"] = r"INTAKE-\d{8}-\d{3}"
        payload["id_patterns"]["intake-chunk"] = r"INTAKE-\d{8}-\d{3}-PART-\d{4}"
        payload["id_patterns"]["intake-review"] = r"INTAKE-\d{8}-\d{3}-REVIEW"
        payload["id_patterns"]["intake-extraction-index"] = r"INTAKE-\d{8}-\d{3}-EXTRACTED"
        payload["id_examples"]["intake-document"] = "INTAKE-20260820-001"
        payload["id_examples"]["intake-chunk"] = "INTAKE-20260820-001-PART-0001"
        payload["id_examples"]["intake-review"] = "INTAKE-20260820-001-REVIEW"
        payload["id_examples"]["intake-extraction-index"] = "INTAKE-20260820-001-EXTRACTED"
        payload["template_contracts"]["Document Intake Review"]["id"] = "INTAKE-YYYYMMDD-001-REVIEW"
        payload["id_generation"]["intake_document_prefix"] = "INTAKE"
        payload["id_generation"]["intake_chunk_label"] = "PART"
        payload["id_generation"]["intake_chunk_sequence_width"] = 4
        payload["intake_artifacts"].update(
            {
                "source_info": "metadata.yml",
                "extraction_index": "extraction-index.md",
                "chunks_manifest": "segments.json",
                "chunk_directory": "segments",
                "intake_report": "report.md",
                "review_progress": "coverage.yml",
                "review": "approval.md",
                "copied_source_stem": "original",
            }
        )
        payload["canonical_tree"]["example_files"] = [
            value.replace("DOCIN-YYYYMMDD-001", "INTAKE-YYYYMMDD-001")
            .replace("source-info.yml", "metadata.yml")
            .replace("extracted.md", "extraction-index.md")
            .replace("chunks.json", "segments.json")
            .replace("chunks/CH-001.md", "segments/PART-0001.md")
            .replace("intake-report.md", "report.md")
            .replace("review-progress.yml", "coverage.yml")
            .replace("review.md", "approval.md")
            for value in payload["canonical_tree"]["example_files"]
        ]
        manifest = self.root / "alternate-round-trip.yml"
        manifest.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
        contract = load_schema_contract(manifest)
        wiki_root = self.root / ".project-wiki"
        wiki_root.mkdir()
        create_valid_wiki(wiki_root)
        source = self.root / "source.md"
        source.write_text("# Source\n\nContent\n", encoding="utf-8")
        arguments = ["ingest_document.py", str(source), "--wiki-root", str(wiki_root)]

        with (
            patch.object(ingest_document, "load_schema_contract", return_value=contract),
            patch.object(sys, "argv", arguments),
            redirect_stdout(io.StringIO()),
            redirect_stderr(io.StringIO()),
        ):
            self.assertEqual(ingest_document.main(), 0)

        documents = list((wiki_root / "intake" / "documents").iterdir())
        self.assertEqual(len(documents), 1)
        document_root = documents[0]
        manifest_payload = json.loads((document_root / "segments.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest_payload["chunks"][0]["text_path"], "segments/PART-0001.md")
        self.assertTrue((document_root / "segments" / "PART-0001.md").is_file())
        self.assertTrue((document_root / "metadata.yml").is_file())
        self.assertTrue((document_root / "report.md").is_file())
        self.assertTrue((document_root / "coverage.yml").is_file())

        validation = validate_wiki.validate_wiki(wiki_root, manifest)
        self.assertFalse(
            any(finding.path.startswith("intake/") for finding in validation.findings),
            validation.findings,
        )
        with patch.object(check_inbox, "load_schema_contract", return_value=contract):
            inbox_report = check_inbox.check_inbox(wiki_root)
        self.assertEqual(inbox_report.decisions, ())

    def test_alternate_semantic_paths_round_trip_through_all_helpers(self) -> None:
        payload = yaml.safe_load(self.contract.manifest_path.read_text(encoding="utf-8"))
        path_map = {
            "WIKI_VERSION.yml": "SCHEMA.yml",
            "REGISTRY.yml": "CATALOG.yml",
            "sources/SOURCE_REGISTRY.yml": "inputs/SOURCES.yml",
            "sources/inbox": "inputs/inbox",
            "sources/processed": "inputs/archive",
            "sources/rejected": "inputs/rejected",
            "sources/ignored": "inputs/ignored",
            "intake/documents": "staging/records",
            "intake/INDEX.md": "staging/INDEX.md",
        }
        payload["semantic_paths"] = {
            "wiki_version_file": "SCHEMA.yml",
            "document_registry_file": "CATALOG.yml",
            "source_registry_file": "inputs/SOURCES.yml",
            "source_inbox_directory": "inputs/inbox",
            "source_processed_directory": "inputs/archive",
            "source_rejected_directory": "inputs/rejected",
            "source_ignored_directory": "inputs/ignored",
            "intake_root_directory": "staging",
            "intake_documents_directory": "staging/records",
            "intake_index_file": "staging/INDEX.md",
        }
        payload["canonical_tree"]["required_directories"] = [
            path_map.get(value, value)
            for value in payload["canonical_tree"]["required_directories"]
        ]
        payload["canonical_tree"]["required_files"] = [
            path_map.get(value, value)
            for value in payload["canonical_tree"]["required_files"]
        ]
        payload["canonical_tree"]["example_files"] = [
            value.replace("intake/documents", "staging/records").replace("sources/processed", "inputs/archive")
            for value in payload["canonical_tree"]["example_files"]
        ]
        manifest = self.root / "alternate-paths.yml"
        manifest.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
        contract = load_schema_contract(manifest)
        wiki_root = self.root / ".project-wiki"
        wiki_root.mkdir()
        create_valid_wiki(wiki_root, contract)
        source = self.root / "source.md"
        source.write_text("# Source\n\nContent\n", encoding="utf-8")
        arguments = ["ingest_document.py", str(source), "--wiki-root", str(wiki_root)]
        with (
            patch.object(ingest_document, "load_schema_contract", return_value=contract),
            patch.object(sys, "argv", arguments),
            redirect_stdout(io.StringIO()),
            redirect_stderr(io.StringIO()),
        ):
            self.assertEqual(ingest_document.main(), 0)

        self.assertEqual(len(list((wiki_root / "staging" / "records").iterdir())), 1)
        self.assertTrue((wiki_root / "staging" / "INDEX.md").is_file())
        validation = validate_wiki.validate_wiki(wiki_root, manifest)
        self.assertTrue(validation.valid, validation.findings)

        inbox_source = wiki_root / "inputs" / "inbox" / "new.md"
        inbox_source.write_text("New source", encoding="utf-8")
        with patch.object(check_inbox, "load_schema_contract", return_value=contract):
            report = check_inbox.check_inbox(wiki_root)
        self.assertEqual(report.decisions[0].reason, "new-unique")

    def test_alternate_source_completion_status_drives_validator_and_inbox(self) -> None:
        payload = yaml.safe_load(self.contract.manifest_path.read_text(encoding="utf-8"))
        payload["generated_values"]["source_processed_status"] = "superseded"
        manifest = self.root / "alternate-source-status.yml"
        manifest.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
        contract = load_schema_contract(manifest)
        wiki_root = self.root / ".project-wiki"
        wiki_root.mkdir()
        create_valid_wiki(wiki_root)
        source = self.root / "source.md"
        source.write_text("# Source\n\nContent\n", encoding="utf-8")
        doc_id = "DOCIN-20260820-001"
        arguments = [
            "ingest_document.py",
            str(source),
            "--wiki-root",
            str(wiki_root),
            "--doc-id",
            doc_id,
        ]
        with (
            patch.object(ingest_document, "load_schema_contract", return_value=contract),
            patch.object(sys, "argv", arguments),
            redirect_stdout(io.StringIO()),
            redirect_stderr(io.StringIO()),
        ):
            self.assertEqual(ingest_document.main(), 0)
        archived = wiki_root / "sources" / "processed" / "2026-08" / "source.md"
        archived.parent.mkdir(parents=True, exist_ok=True)
        archived.write_bytes(source.read_bytes())
        source_hash = ingest_document.sha256_file(archived)
        source_registry = {
            "version": contract.source_registry_version,
            "updated": "2026-08-20",
            "sources": [
                {
                    "id": "SRC-20260820-001",
                    "status": "superseded",
                    "original_path": "sources/inbox/source.md",
                    "current_path": "sources/processed/2026-08/source.md",
                    "filename": "source.md",
                    "sha256": source_hash,
                    "intake_id": doc_id,
                    "processed_at": "2026-08-20",
                    "tags": [],
                    "notes": "Alternate completion status",
                }
            ],
        }
        (wiki_root / "sources" / "SOURCE_REGISTRY.yml").write_text(
            yaml.safe_dump(source_registry, sort_keys=False),
            encoding="utf-8",
        )
        inbox_source = wiki_root / "sources" / "inbox" / "copy.md"
        inbox_source.write_bytes(source.read_bytes())

        validation = validate_wiki.validate_wiki(wiki_root, manifest)
        self.assertFalse(any(finding.path == "sources/SOURCE_REGISTRY.yml" for finding in validation.findings))
        with patch.object(check_inbox, "load_schema_contract", return_value=contract):
            report = check_inbox.check_inbox(wiki_root)
        self.assertEqual(report.decisions[0].reason, "registered-superseded")
        self.assertEqual(report.decisions[0].action, "skip")

        archived.write_text("tampered", encoding="utf-8")
        codes = {finding.code for finding in validate_wiki.validate_wiki(wiki_root, manifest).findings}
        self.assertIn("processed-source-current-hash-mismatch", codes)

    def test_inbox_action_is_driven_by_manifest_reason_mapping(self) -> None:
        payload = yaml.safe_load(self.contract.manifest_path.read_text(encoding="utf-8"))
        payload["source_workflow"]["reason_actions"]["new-unique"] = "review"
        manifest = self.root / "alternate-action.yml"
        manifest.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
        contract = load_schema_contract(manifest)
        wiki_root = self.root / ".project-wiki"
        inbox = wiki_root / "sources" / "inbox"
        inbox.mkdir(parents=True)
        (wiki_root / "sources" / "SOURCE_REGISTRY.yml").write_text(
            f"version: {contract.source_registry_version}\nupdated: 2026-08-20\nsources: []\n",
            encoding="utf-8",
        )
        (inbox / "new.md").write_text("New source", encoding="utf-8")

        with patch.object(check_inbox, "load_schema_contract", return_value=contract):
            report = check_inbox.check_inbox(wiki_root)

        self.assertEqual(report.decisions[0].reason, "new-unique")
        self.assertEqual(report.decisions[0].action, "review")

    def test_generated_intake_confidence_is_manifest_driven(self) -> None:
        payload = yaml.safe_load(self.contract.manifest_path.read_text(encoding="utf-8"))
        payload["confidence_values"] = ["inferred", "unknown"]
        payload["generated_values"]["intake_confidence"] = "inferred"
        manifest = self.root / "alternate-confidence.yml"
        manifest.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
        contract = load_schema_contract(manifest)
        wiki_root = self.root / ".project-wiki"
        wiki_root.mkdir()
        create_valid_wiki(wiki_root, contract)
        source = self.root / "source.md"
        source.write_text("# Source\n\nContent\n", encoding="utf-8")
        arguments = ["ingest_document.py", str(source), "--wiki-root", str(wiki_root)]
        with (
            patch.object(ingest_document, "load_schema_contract", return_value=contract),
            patch.object(sys, "argv", arguments),
            redirect_stdout(io.StringIO()),
            redirect_stderr(io.StringIO()),
        ):
            self.assertEqual(ingest_document.main(), 0)
        document_root = next((wiki_root / contract.semantic_paths.intake_documents_directory).iterdir())
        source_info = yaml.safe_load(
            (document_root / contract.intake_artifacts.source_info).read_text(encoding="utf-8")
        )

        self.assertEqual(source_info["confidence"], "inferred")
        validation = validate_wiki.validate_wiki(wiki_root, manifest)
        self.assertFalse(any(finding.path.startswith(contract.semantic_paths.intake_root_directory) for finding in validation.findings))


if __name__ == "__main__":
    unittest.main()