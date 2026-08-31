#!/usr/bin/env python3
"""Validate deterministic structural invariants of a project wiki."""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
import unicodedata
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import unquote, urlsplit

try:
    from .schema_contract import (
        SchemaContract,
        SchemaContractDependencyError,
        SchemaContractError,
        load_schema_contract,
        strict_yaml_load,
    )
except ImportError:
    from schema_contract import (  # type: ignore[no-redef]
        SchemaContract,
        SchemaContractDependencyError,
        SchemaContractError,
        load_schema_contract,
        strict_yaml_load,
    )


SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")
INLINE_STATUS_PATTERN = re.compile(r"^\s*Status:\s*([A-Za-z][A-Za-z-]*)\s*$", re.IGNORECASE)
INLINE_EVIDENCE_PREFIX_PATTERN = re.compile(r"^\s*Evidence\s*:", re.IGNORECASE)
INTAKE_CHUNK_REFERENCE_PATTERN = re.compile(
    r"(?:(?:\.project-wiki/)?intake/documents/)?DOCIN-\d{8}-\d{3}(?:/chunks/|-)CH-\d{3}(?:\.md)?\b",
    re.IGNORECASE,
)
INTAKE_REPORT_BODY_STATUS_PATTERN = re.compile(r"^- Intake status: `([^`]+)`\s*$", re.MULTILINE)
HTML_ANCHOR_PATTERN = re.compile(r"<[A-Za-z][^>]*\s(?:id|name)\s*=\s*[\"']([^\"']+)[\"']", re.I)

DETERMINISTIC_CHECKS = (
    "canonical tree and schema version",
    "YAML and JSON parsing",
    "Markdown frontmatter fields and value domains",
    "document ID format, uniqueness, and filename alignment",
    "atomic requirement locations and structured intake evidence",
    "registry shape, uniqueness, paths, anchors, and catalog completeness",
    "source registry shape, hashes, statuses, paths, and intake references",
    "intake review ledger coverage, completion, skip reasons, and integrated target IDs",
    "relative Markdown link targets and anchors",
    "created/updated date ordering and registry update freshness",
)

SEMANTIC_CHECKS_DEFERRED = (
    "contradictions between requirements, decisions, documentation, and code",
    "requirements implied only by implementation behavior",
    "claims made obsolete by later project decisions or source material",
    "missing or weak backlinks whose necessity depends on meaning",
    "traceability quality beyond structural path and ID validity",
    "orphan concepts, risky assumptions, and missing source material",
)

YAML_PARSE_ERROR = object()


class ValidatorDependencyError(RuntimeError):
    pass


@dataclass(frozen=True)
class Finding:
    severity: str
    code: str
    path: str
    message: str
    line: int | None = None

    def sort_key(self) -> tuple[str, int, str, str]:
        return (self.path.casefold(), self.line or 0, self.code, self.message)


@dataclass(frozen=True)
class IdDefinition:
    id: str
    path: str
    line: int | None
    kind: str


@dataclass(frozen=True)
class PendingLink:
    source: Path
    source_relative: str
    destination: str
    line: int


@dataclass(frozen=True)
class ValidationReport:
    wiki_root: str
    findings: tuple[Finding, ...]

    @property
    def valid(self) -> bool:
        return not any(finding.severity == "error" for finding in self.findings)

    def as_dict(self) -> dict[str, Any]:
        errors = sum(finding.severity == "error" for finding in self.findings)
        warnings = sum(finding.severity == "warning" for finding in self.findings)
        return {
            "version": 1,
            "wiki_root": self.wiki_root,
            "valid": self.valid,
            "summary": {
                "errors": errors,
                "warnings": warnings,
                "findings": len(self.findings),
            },
            "deterministic_checks": list(DETERMINISTIC_CHECKS),
            "semantic_checks_deferred": list(SEMANTIC_CHECKS_DEFERRED),
            "findings": [asdict(finding) for finding in self.findings],
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate deterministic structural invariants in .project-wiki/."
    )
    parser.add_argument(
        "--wiki-root",
        default=".project-wiki",
        help="Project wiki root. Defaults to .project-wiki in the current directory.",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format. Defaults to text.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    wiki_root = Path(args.wiki_root).expanduser().resolve()
    try:
        report = validate_wiki(wiki_root)
    except SchemaContractDependencyError as error:
        print_fatal_error(args.format, wiki_root, "validator-dependency-error", str(error))
        return 2
    except SchemaContractError as error:
        print_fatal_error(args.format, wiki_root, "schema-contract-invalid", str(error))
        return 2
    except ValidatorDependencyError as error:
        print_fatal_error(args.format, wiki_root, "validator-dependency-error", str(error))
        return 2
    except (OSError, RuntimeError, TypeError, ValueError) as error:
        print_fatal_error(args.format, wiki_root, "validator-io-error", f"Failed to validate project wiki: {error}")
        return 2

    if args.format == "json":
        print(json.dumps(report.as_dict(), indent=2, sort_keys=True))
    else:
        print_text_report(report)
    return 0 if report.valid else 1


def validate_wiki(wiki_root: Path, manifest_path: Path | None = None) -> ValidationReport:
    validator = WikiValidator(wiki_root.resolve(), load_schema_contract(manifest_path))
    return validator.run()


class WikiValidator:
    def __init__(self, wiki_root: Path, contract: SchemaContract | None = None) -> None:
        self.wiki_root = wiki_root
        self.contract = contract or load_schema_contract()
        self.findings: list[Finding] = []
        self.yaml_documents: dict[str, Any] = {}
        self.json_documents: dict[str, Any] = {}
        self.frontmatter: dict[str, dict[str, Any]] = {}
        self.definitions: list[IdDefinition] = []
        self.definitions_by_path: dict[str, set[str]] = {}
        self.definition_anchors_by_path: dict[str, dict[str, set[str]]] = {}
        self.embedded_status_by_path: dict[str, dict[str, str]] = {}
        self.embedded_title_by_path: dict[str, dict[str, str]] = {}
        self.requirement_evidence_by_id: dict[str, tuple[str, ...]] = {}
        self.intake_chunk_ids: set[str] = set()
        self.updated_by_path: dict[str, date] = {}
        self.anchor_cache: dict[str, set[str]] = {}
        self.pending_links: list[PendingLink] = []
        self.registry_ids: set[str] = set()
        self.source_registry_ids: set[str] = set()
        self.registry_target_paths: set[str] = set()
        self.reported_symlinks: set[str] = set()

    def run(self) -> ValidationReport:
        if not self.wiki_root.is_dir():
            self.add("error", "wiki-root-missing", ".", "Project wiki root does not exist or is not a directory.")
            return self.report()

        self.check_symlinks()
        self.check_required_tree()
        self.parse_structured_files()
        self.scan_markdown_files()
        self.check_intake_source_info()
        self.check_intake_manifests()
        self.check_links()
        self.check_duplicate_definitions()
        self.check_requirement_evidence()
        self.check_embedded_record_contracts()
        self.check_wiki_version()
        self.check_source_registry()
        self.check_registry()
        self.check_intake_review_progress()
        self.check_registry_completeness()
        return self.report()

    def report(self) -> ValidationReport:
        findings = tuple(sorted(self.findings, key=Finding.sort_key))
        return ValidationReport(wiki_root=self.wiki_root.as_posix(), findings=findings)

    def add(self, severity: str, code: str, path: str, message: str, line: int | None = None) -> None:
        self.findings.append(Finding(severity=severity, code=code, path=path, message=message, line=line))

    def check_required_tree(self) -> None:
        for relative in self.contract.required_directories:
            path = self.wiki_root / relative
            if path.is_symlink():
                continue
            if not path.is_dir():
                self.add("error", "required-directory-missing", relative, "Required wiki directory is missing.")
        for relative in self.contract.required_files:
            path = self.wiki_root / relative
            if path.is_symlink():
                continue
            if not path.is_file():
                self.add("error", "required-file-missing", relative, "Required wiki file is missing.")

    def check_symlinks(self) -> None:
        for path in sorted(self.wiki_root.rglob("*")):
            if not path.is_symlink():
                continue
            relative = self.relative(path)
            self.reported_symlinks.add(relative)
            self.add("error", "symlink-not-allowed", relative, "Symlinks are not allowed inside .project-wiki/.")

    def parse_structured_files(self) -> None:
        for path in sorted(self.wiki_root.rglob("*")):
            if path.is_symlink() or not path.is_file() or self.is_raw_source(path) or self.is_template(path):
                continue
            relative = self.relative(path)
            if path.suffix.lower() in {".yml", ".yaml"}:
                self.yaml_documents[relative] = self.load_yaml(path, relative)
            elif path.suffix.lower() == ".json":
                try:
                    self.json_documents[relative] = json.loads(path.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, UnicodeError) as error:
                    self.add("error", "json-invalid", relative, f"Invalid JSON: {error}")

    def load_yaml(self, path: Path, relative: str) -> Any:
        try:
            payload = strict_yaml_load(path.read_text(encoding="utf-8"), relative)
        except UnicodeError as error:
            self.add("error", "yaml-invalid", relative, f"Invalid YAML encoding: {error}")
            return None
        except SchemaContractDependencyError as error:
            raise ValidatorDependencyError(
                "wiki validation requires PyYAML; install scripts/requirements.txt"
            ) from error
        except SchemaContractError as error:
            self.add("error", "yaml-invalid", relative, str(error))
            return None
        if payload is None:
            self.add("error", "yaml-empty", relative, "YAML document is empty.")
        return payload

    def check_intake_manifests(self) -> None:
        artifacts = self.contract.intake_artifacts
        intake_parts = PurePosixPath(self.contract.semantic_paths.intake_documents_directory).parts
        for relative, payload in sorted(self.json_documents.items()):
            parts = PurePosixPath(relative).parts
            if (
                len(parts) != len(intake_parts) + 2
                or parts[: len(intake_parts)] != intake_parts
                or parts[-1] != artifacts.chunks_manifest
            ):
                continue
            intake_id = parts[len(intake_parts)]
            if not isinstance(payload, dict):
                self.add("error", "intake-manifest-invalid", relative, "Intake chunk manifest must be a JSON object.")
                continue
            if payload.get("version") != self.contract.intake_chunks_manifest_version:
                self.add(
                    "error",
                    "intake-manifest-version-invalid",
                    relative,
                    f"Intake manifest version must be {self.contract.intake_chunks_manifest_version}.",
                )
            if payload.get("id") != intake_id:
                self.add("error", "intake-manifest-id-mismatch", relative, f"Manifest ID must match directory '{intake_id}'.")
            chunks = payload.get("chunks")
            if not isinstance(chunks, list) or not chunks:
                self.add("error", "intake-manifest-chunks-invalid", relative, "Intake manifest must contain a non-empty chunks list.")
                continue
            seen_ids: set[str] = set()
            seen_paths: set[str] = set()
            chunk_pattern = self.contract.type_id_patterns["intake-chunk"]
            generation = self.contract.id_generation
            text_path_pattern = re.compile(
                rf"{re.escape(artifacts.chunk_directory)}/"
                rf"{re.escape(generation.intake_chunk_label)}-"
                rf"\d{{{generation.intake_chunk_sequence_width}}}\.md"
            )
            for index, chunk in enumerate(chunks, start=1):
                if not isinstance(chunk, dict):
                    self.add("error", "intake-manifest-chunk-invalid", relative, f"Chunk {index} must be an object.")
                    continue
                chunk_id = chunk.get("id")
                text_path = chunk.get("text_path")
                if not isinstance(chunk_id, str) or chunk_pattern.fullmatch(chunk_id) is None or not chunk_id.startswith(f"{intake_id}-"):
                    self.add("error", "intake-manifest-chunk-id-invalid", relative, f"Chunk {index} has an invalid ID.")
                elif chunk_id in seen_ids:
                    self.add("error", "intake-manifest-chunk-id-duplicate", relative, f"Chunk ID '{chunk_id}' appears more than once.")
                else:
                    seen_ids.add(chunk_id)
                    self.intake_chunk_ids.add(chunk_id)
                if not isinstance(text_path, str):
                    self.add("error", "intake-manifest-text-path-invalid", relative, f"Chunk {index} has no valid text_path.")
                    continue
                if text_path_pattern.fullmatch(text_path) is None:
                    self.add("error", "intake-manifest-text-path-invalid", relative, f"Chunk {index} text_path does not match the schema contract.")
                if text_path in seen_paths:
                    self.add("error", "intake-manifest-text-path-duplicate", relative, f"Chunk text_path '{text_path}' appears more than once.")
                seen_paths.add(text_path)
                document_root = self.intake_document_root(intake_id)
                normalized = self.normalized_relative_path(text_path)
                if normalized is None:
                    self.add("error", "intake-manifest-text-path-invalid", relative, f"Chunk {index} text_path escapes its intake directory.")
                    continue
                target = self.resolve_contained_path(
                    document_root / normalized,
                    document_root,
                    relative,
                    "intake-manifest-text-path-invalid",
                    f"Chunk {index} text_path",
                    reject_symlinks=True,
                )
                if target is not None:
                    if not target.is_file():
                        self.add("error", "intake-manifest-text-path-missing", relative, f"Chunk {index} text_path does not exist: {text_path}.")
                    else:
                        target_relative = self.relative(target)
                        metadata = self.frontmatter.get(target_relative)
                        if not isinstance(metadata, dict) or metadata.get("id") != chunk_id:
                            self.add("error", "intake-manifest-chunk-target-id-mismatch", relative, f"Chunk {index} ID does not match {text_path} frontmatter.")
                        if isinstance(metadata, dict) and metadata.get("type") != "intake-chunk":
                            self.add("error", "intake-manifest-chunk-target-type-invalid", relative, f"Chunk {index} target type must be 'intake-chunk'.")
                        related = metadata.get("related") if isinstance(metadata, dict) else None
                        if isinstance(related, list) and intake_id not in related:
                            self.add("error", "intake-manifest-chunk-parent-mismatch", relative, f"Chunk {index} target does not relate to {intake_id}.")

            chunks_root = self.intake_document_root(intake_id) / artifacts.chunk_directory
            actual_paths = {
                path.relative_to(self.intake_document_root(intake_id)).as_posix()
                for path in chunks_root.glob("*.md")
                if path.is_file()
                and not path.is_symlink()
                and text_path_pattern.fullmatch(f"{artifacts.chunk_directory}/{path.name}") is not None
            }
            if seen_paths != actual_paths:
                missing_from_manifest = sorted(actual_paths - seen_paths)
                missing_on_disk = sorted(seen_paths - actual_paths)
                if missing_from_manifest:
                    self.add("error", "intake-manifest-orphan-chunk", relative, f"Chunk files are not listed in the manifest: {', '.join(missing_from_manifest)}.")
                if missing_on_disk:
                    self.add("error", "intake-manifest-text-path-missing", relative, f"Manifest paths are absent on disk: {', '.join(missing_on_disk)}.")

    def check_intake_review_progress(self) -> None:
        artifacts = self.contract.intake_artifacts
        progress_contract = self.contract.review_progress
        intake_parts = PurePosixPath(self.contract.semantic_paths.intake_documents_directory).parts
        for manifest_relative, manifest in sorted(self.json_documents.items()):
            parts = PurePosixPath(manifest_relative).parts
            if (
                len(parts) != len(intake_parts) + 2
                or parts[: len(intake_parts)] != intake_parts
                or parts[-1] != artifacts.chunks_manifest
                or not isinstance(manifest, dict)
            ):
                continue
            intake_id = parts[len(intake_parts)]
            progress_relative = self.intake_document_relative(intake_id, artifacts.review_progress)
            progress = self.yaml_documents.get(progress_relative)
            if progress is None:
                self.add("error", "intake-review-progress-missing", progress_relative, "Review progress ledger is required for every intake document.")
                continue
            if not isinstance(progress, dict):
                self.add("error", "intake-review-progress-invalid", progress_relative, "Review progress ledger must be a YAML mapping.")
                continue
            expected_top_level = {"version", "intake_id", "updated", "review_status", "summary", "chunks"}
            if set(progress) != expected_top_level:
                self.add("error", "intake-review-progress-shape-invalid", progress_relative, "Review progress ledger fields do not match the schema contract.")
            if progress.get("version") != self.contract.intake_review_progress_version:
                self.add("error", "intake-review-progress-version-invalid", progress_relative, f"Review progress version must be {self.contract.intake_review_progress_version}.")
            if progress.get("intake_id") != intake_id:
                self.add("error", "intake-review-progress-id-mismatch", progress_relative, f"Review progress intake_id must match directory '{intake_id}'.")
            self.validate_date(progress.get("updated"), progress_relative, "updated")
            review_status = progress.get("review_status")
            if review_status not in progress_contract.workflow_statuses:
                self.add("error", "intake-review-progress-status-invalid", progress_relative, f"Unsupported review_status: {review_status!r}.")

            manifest_chunks = manifest.get("chunks")
            manifest_ids = [
                chunk.get("id")
                for chunk in manifest_chunks
                if isinstance(chunk, dict) and isinstance(chunk.get("id"), str)
            ] if isinstance(manifest_chunks, list) else []
            entries = progress.get("chunks")
            if not isinstance(entries, list):
                self.add("error", "intake-review-progress-chunks-invalid", progress_relative, "Review progress chunks must be a list.")
                continue

            ledger_ids: list[str] = []
            status_counts = {status: 0 for status in progress_contract.entry_statuses}
            valid_entries: list[dict[str, Any]] = []
            for index, entry in enumerate(entries, start=1):
                location = f"chunks[{index}]"
                if not isinstance(entry, dict):
                    self.add("error", "intake-review-progress-entry-invalid", progress_relative, f"{location} must be a mapping.")
                    continue
                valid_entries.append(entry)
                if set(entry) != {"id", "status", "classifications", "target_ids", "notes"}:
                    self.add("error", "intake-review-progress-entry-shape-invalid", progress_relative, f"{location} fields do not match the schema contract.")
                chunk_id = entry.get("id")
                if not isinstance(chunk_id, str):
                    self.add("error", "intake-review-progress-entry-id-invalid", progress_relative, f"{location}.id must be a chunk ID.")
                else:
                    ledger_ids.append(chunk_id)
                entry_status = entry.get("status")
                if entry_status not in progress_contract.entry_statuses:
                    self.add("error", "intake-review-progress-entry-status-invalid", progress_relative, f"{location} has unsupported status {entry_status!r}.")
                else:
                    status_counts[entry_status] += 1
                classifications = entry.get("classifications")
                if (
                    not isinstance(classifications, list)
                    or any(not isinstance(value, str) or value not in progress_contract.classifications for value in classifications)
                    or len(classifications) != len(set(classifications))
                ):
                    self.add("error", "intake-review-progress-classifications-invalid", progress_relative, f"{location}.classifications is invalid.")
                    classifications = []
                target_ids = entry.get("target_ids")
                if (
                    not isinstance(target_ids, list)
                    or any(not isinstance(value, str) or self.contract.generic_id_pattern.fullmatch(value) is None for value in target_ids)
                    or len(target_ids) != len(set(target_ids))
                ):
                    self.add("error", "intake-review-progress-target-ids-invalid", progress_relative, f"{location}.target_ids is invalid.")
                    target_ids = []
                notes = entry.get("notes")
                if notes is not None and (not isinstance(notes, str) or not notes.strip()):
                    self.add("error", "intake-review-progress-notes-invalid", progress_relative, f"{location}.notes must be null or a non-empty string.")
                if entry_status == "classified" and not classifications:
                    self.add("error", "intake-review-progress-classification-required", progress_relative, f"{location} must declare at least one classification.")
                if entry_status == "skipped":
                    if classifications or target_ids:
                        self.add("error", "intake-review-progress-skipped-content-invalid", progress_relative, f"{location} skipped entries cannot declare classifications or target IDs.")
                    if not isinstance(notes, str) or not notes.strip():
                        self.add("error", "intake-review-progress-skip-reason-required", progress_relative, f"{location} skipped entries require a reason in notes.")

            if ledger_ids != manifest_ids or len(ledger_ids) != len(set(ledger_ids)):
                self.add("error", "intake-review-progress-coverage-mismatch", progress_relative, "Review progress must cover every manifest chunk exactly once and in manifest order.")

            summary = progress.get("summary")
            expected_summary = {"total": len(entries), **status_counts}
            if not isinstance(summary, dict) or summary != expected_summary:
                self.add("error", "intake-review-progress-summary-mismatch", progress_relative, f"Review progress summary must equal {expected_summary}.")

            all_complete = bool(entries) and all(
                entry.get("status") in progress_contract.complete_entry_statuses
                for entry in valid_entries
            ) and len(valid_entries) == len(entries)
            expected_review_status = "complete" if all_complete else "in-progress"
            if review_status in progress_contract.workflow_statuses and review_status != expected_review_status:
                self.add("error", "intake-review-progress-completion-mismatch", progress_relative, f"review_status must be '{expected_review_status}' for the current chunk dispositions.")

            source_info = self.yaml_documents.get(self.intake_document_relative(intake_id, artifacts.source_info))
            intake_status = source_info.get("status") if isinstance(source_info, dict) else None
            if intake_status in {"reviewed", "integrated"} and not all_complete:
                self.add("error", "intake-review-progress-incomplete", progress_relative, f"Intake status '{intake_status}' requires complete chunk review coverage.")
            if intake_status == "integrated":
                ledger_atomic_edges: set[tuple[str, str]] = set()
                for index, entry in enumerate(valid_entries, start=1):
                    if entry.get("status") != "classified":
                        continue
                    chunk_id = entry.get("id")
                    classifications = entry.get("classifications")
                    target_ids = entry.get("target_ids")
                    if not isinstance(target_ids, list) or not target_ids:
                        self.add("error", "intake-review-progress-target-required", progress_relative, f"chunks[{index}] classified entries require target IDs after integration.")
                        continue
                    atomic_targets = [
                        target_id
                        for target_id in target_ids
                        if isinstance(target_id, str) and self.is_atomic_requirement_id(target_id)
                    ]
                    if (
                        isinstance(classifications, list)
                        and {"requirement", "requirement-refinement"}.intersection(classifications)
                        and not atomic_targets
                    ):
                        self.add(
                            "error",
                            "intake-review-progress-atomic-target-required",
                            progress_relative,
                            f"chunks[{index}] requirement classifications require at least one atomic REQ, NFR, or CON target.",
                        )
                    for target_id in target_ids:
                        if isinstance(target_id, str) and target_id not in self.registry_ids:
                            self.add("error", "intake-review-progress-target-missing", progress_relative, f"chunks[{index}] target ID '{target_id}' is not registered.")
                    if isinstance(chunk_id, str):
                        for target_id in atomic_targets:
                            ledger_atomic_edges.add((chunk_id, target_id))
                            if chunk_id not in self.requirement_evidence_by_id.get(target_id, ()):
                                self.add(
                                    "error",
                                    "intake-review-progress-evidence-mismatch",
                                    progress_relative,
                                    f"chunks[{index}] targets '{target_id}', but that record does not list '{chunk_id}' in Evidence.",
                                )
                evidence_atomic_edges = {
                    (chunk_id, document_id)
                    for document_id, evidence in self.requirement_evidence_by_id.items()
                    for chunk_id in evidence
                    if chunk_id.startswith(f"{intake_id}-")
                }
                for chunk_id, document_id in sorted(evidence_atomic_edges - ledger_atomic_edges):
                    self.add(
                        "error",
                        "intake-review-progress-evidence-mismatch",
                        progress_relative,
                        f"Evidence links '{document_id}' to '{chunk_id}', but the integrated ledger does not contain the reciprocal target.",
                    )

    def check_intake_source_info(self) -> None:
        artifacts = self.contract.intake_artifacts
        intake_parts = PurePosixPath(self.contract.semantic_paths.intake_documents_directory).parts
        for relative, payload in sorted(self.yaml_documents.items()):
            parts = PurePosixPath(relative).parts
            if (
                len(parts) != len(intake_parts) + 2
                or parts[: len(intake_parts)] != intake_parts
                or parts[-1] != artifacts.source_info
            ):
                continue
            intake_id = parts[len(intake_parts)]
            if not isinstance(payload, dict):
                self.add("error", "intake-source-info-invalid", relative, "Intake source info must be a YAML mapping.")
                continue
            required = (
                "version",
                "id",
                "type",
                "status",
                "title",
                "created",
                "updated",
                "source_path",
                "source_filename",
                "source_sha256",
                "immutable_source",
                "file_type",
                "copied_source_path",
                "word_count",
                "chunk_count",
                "confidence",
            )
            for field in required:
                if field not in payload:
                    self.add("error", "intake-source-info-field-missing", relative, f"Intake source info is missing '{field}'.")
            if payload.get("version") != self.contract.intake_source_info_version:
                self.add(
                    "error",
                    "intake-source-info-version-invalid",
                    relative,
                    f"Intake source info version must be {self.contract.intake_source_info_version}.",
                )
            if payload.get("id") != intake_id:
                self.add("error", "intake-source-info-id-mismatch", relative, f"Intake source ID must match directory '{intake_id}'.")
            if payload.get("type") != "intake-document":
                self.add("error", "intake-source-info-type-invalid", relative, "Intake source type must be 'intake-document'.")
            intake_status = payload.get("status")
            if not isinstance(intake_status, str) or intake_status not in self.contract.statuses["intake"]:
                self.add("error", "intake-source-info-status-invalid", relative, f"Unsupported intake status: {payload.get('status')!r}.")
            source_hash = payload.get("source_sha256")
            if not isinstance(source_hash, str) or SHA256_PATTERN.fullmatch(source_hash.lower()) is None:
                self.add("error", "intake-source-info-hash-invalid", relative, "Intake source SHA-256 is invalid.")
            if payload.get("immutable_source") is not True:
                self.add("error", "intake-source-info-immutable-invalid", relative, "immutable_source must be true.")
            for field in ("word_count", "chunk_count"):
                if not isinstance(payload.get(field), int) or payload[field] < 0:
                    self.add("error", "intake-source-info-count-invalid", relative, f"{field} must be a non-negative integer.")
            for field in ("title", "source_path", "source_filename", "file_type"):
                if not isinstance(payload.get(field), str) or not payload[field].strip():
                    self.add("error", "intake-source-info-field-invalid", relative, f"{field} must be a non-empty string.")
            created = self.validate_date(payload.get("created"), relative, "created")
            updated = self.validate_date(payload.get("updated"), relative, "updated")
            if created is not None and updated is not None and updated < created:
                self.add("error", "updated-before-created", relative, "Intake source updated date precedes created date.")
            if not isinstance(payload.get("confidence"), str) or payload.get("confidence") not in self.contract.confidence_values:
                self.add("error", "intake-source-info-confidence-invalid", relative, "Intake confidence is invalid.")

            manifest_relative = self.intake_document_relative(intake_id, artifacts.chunks_manifest)
            manifest = self.json_documents.get(manifest_relative)
            if isinstance(manifest, dict):
                manifest_source = manifest.get("source")
                manifest_hash = manifest_source.get("sha256") if isinstance(manifest_source, dict) else None
                if isinstance(source_hash, str) and manifest_hash != source_hash:
                    self.add("error", "intake-source-hash-mismatch", relative, f"{artifacts.source_info} and {artifacts.chunks_manifest} source hashes differ.")
                chunks = manifest.get("chunks")
                if isinstance(chunks, list) and payload.get("chunk_count") != len(chunks):
                    self.add("error", "intake-source-chunk-count-mismatch", relative, f"{artifacts.source_info} chunk_count differs from {artifacts.chunks_manifest}.")
                if isinstance(chunks, list) and all(isinstance(chunk, dict) and isinstance(chunk.get("word_count"), int) for chunk in chunks):
                    manifest_word_count = sum(chunk["word_count"] for chunk in chunks)
                    if payload.get("word_count") != manifest_word_count:
                        self.add("error", "intake-source-word-count-mismatch", relative, f"{artifacts.source_info} word_count differs from {artifacts.chunks_manifest}.")
                if manifest.get("title") != payload.get("title"):
                    self.add("error", "intake-source-title-mismatch", relative, f"{artifacts.source_info} and {artifacts.chunks_manifest} titles differ.")
                if manifest.get("created") != payload.get("created"):
                    self.add("error", "intake-source-created-mismatch", relative, f"{artifacts.source_info} and {artifacts.chunks_manifest} created dates differ.")
                if isinstance(manifest_source, dict):
                    if manifest_source.get("path") != payload.get("source_path") or manifest_source.get("filename") != payload.get("source_filename"):
                        self.add("error", "intake-source-identity-mismatch", relative, f"{artifacts.source_info} and {artifacts.chunks_manifest} source identity differ.")

            report_relative = self.intake_document_relative(intake_id, artifacts.intake_report)
            report_metadata = self.frontmatter.get(report_relative)
            if isinstance(report_metadata, dict):
                for field in ("id", "status", "title", "created", "updated"):
                    if report_metadata.get(field) != payload.get(field):
                        self.add(
                            "error",
                            "intake-report-metadata-mismatch",
                            relative,
                            f"{artifacts.intake_report} {field} differs from {artifacts.source_info}.",
                        )
            report_path = self.wiki_root / report_relative
            if report_path.is_file():
                report_text = self.read_text(report_path, report_relative)
                body_statuses = (
                    INTAKE_REPORT_BODY_STATUS_PATTERN.findall(report_text)
                    if report_text is not None
                    else []
                )
                if any(body_status != intake_status for body_status in body_statuses):
                    self.add(
                        "error",
                        "intake-report-body-status-mismatch",
                        report_relative,
                        f"Body intake status must match {artifacts.source_info} status '{intake_status}'.",
                    )

            copied_source = payload.get("copied_source_path")
            if copied_source is not None:
                if not isinstance(copied_source, str) or not copied_source.strip():
                    self.add("error", "intake-copied-source-path-invalid", relative, "copied_source_path must be a path or null.")
                else:
                    candidate = self.intake_document_root(intake_id) / Path(copied_source).name
                    resolved_copy = self.resolve_contained_path(
                        candidate,
                        self.intake_document_root(intake_id),
                        relative,
                        "intake-copied-source-path-invalid",
                        "copied_source_path",
                        reject_symlinks=True,
                    )
                    if resolved_copy is None:
                        continue
                    if not resolved_copy.is_file():
                        self.add("error", "intake-copied-source-missing", relative, "Declared copied source file does not exist.")
                    elif isinstance(source_hash, str) and sha256_file(resolved_copy) != source_hash:
                        self.add("error", "intake-copied-source-hash-mismatch", relative, "Copied source bytes do not match source_sha256.")

    def scan_markdown_files(self) -> None:
        for path in sorted(self.wiki_root.rglob("*.md")):
            if (
                path.is_symlink()
                or not path.is_file()
                or self.is_raw_source(path)
                or self.is_template(path)
                or self.is_copied_intake_source(path)
            ):
                continue
            relative = self.relative(path)
            text = self.read_text(path, relative)
            if text is None:
                continue
            body, body_start_line, metadata = self.parse_frontmatter(path, relative, text)
            if metadata is not None:
                self.frontmatter[relative] = metadata
                self.validate_frontmatter(relative, metadata)
            if not self.is_intake_chunk(path):
                self.scan_markdown_body(
                    path,
                    relative,
                    body,
                    body_start_line,
                    metadata,
                    interpret_definitions=not self.is_intake_document(path),
                )

    def read_text(self, path: Path, relative: str) -> str | None:
        try:
            return path.read_text(encoding="utf-8")
        except UnicodeError as error:
            self.add("error", "markdown-encoding-invalid", relative, f"Markdown is not valid UTF-8: {error}")
            return None

    def parse_frontmatter(
        self,
        path: Path,
        relative: str,
        text: str,
    ) -> tuple[str, int, dict[str, Any] | None]:
        lines = text.splitlines()
        if not lines or lines[0].strip() != "---":
            if self.requires_frontmatter(path):
                self.add("error", "frontmatter-missing", relative, "Non-index wiki document has no YAML frontmatter.", 1)
            return text, 1, None

        end_index = next((index for index, line in enumerate(lines[1:], start=1) if line.strip() == "---"), None)
        if end_index is None:
            self.add("error", "frontmatter-unclosed", relative, "YAML frontmatter has no closing delimiter.", 1)
            return "", len(lines) + 1, None

        yaml_text = "\n".join(lines[1:end_index])
        metadata = self.load_yaml_text(yaml_text, relative)
        body = "\n".join(lines[end_index + 1 :])
        if metadata is YAML_PARSE_ERROR:
            return body, end_index + 2, None
        if metadata is None:
            code = "frontmatter-empty" if not yaml_text.strip() else "frontmatter-not-mapping"
            message = "YAML frontmatter is empty." if not yaml_text.strip() else "Frontmatter must be a YAML mapping, not null."
            self.add("error", code, relative, message, 1)
            return body, end_index + 2, None
        if not isinstance(metadata, dict):
            self.add("error", "frontmatter-not-mapping", relative, "Frontmatter must be a YAML mapping.", 1)
            return body, end_index + 2, None
        return body, end_index + 2, metadata

    def load_yaml_text(self, text: str, relative: str) -> Any:
        try:
            return strict_yaml_load(text, f"frontmatter in {relative}")
        except SchemaContractDependencyError as error:
            raise ValidatorDependencyError(
                "wiki validation requires PyYAML; install scripts/requirements.txt"
            ) from error
        except SchemaContractError as error:
            self.add("error", "frontmatter-yaml-invalid", relative, str(error), 1)
            return YAML_PARSE_ERROR

    def requires_frontmatter(self, path: Path) -> bool:
        relative = self.relative(path)
        if path.name == "INDEX.md" or relative in self.contract.frontmatter_exempt_paths:
            return False
        if relative.startswith("logs/wiki-log-"):
            return False
        return True

    def validate_frontmatter(self, relative: str, metadata: dict[str, Any]) -> None:
        for field in self.contract.frontmatter_fields:
            if field not in metadata:
                self.add("error", "frontmatter-field-missing", relative, f"Frontmatter field '{field}' is required.", 1)

        document_id = metadata.get("id")
        document_type = metadata.get("type")
        status = metadata.get("status")
        confidence = metadata.get("confidence")

        type_contract = (
            self.contract.document_type_contracts.get(document_type)
            if isinstance(document_type, str)
            else None
        )
        for field in type_contract.required_fields if type_contract else ():
            if field not in metadata:
                self.add(
                    "error",
                    "frontmatter-field-missing",
                    relative,
                    f"Frontmatter field '{field}' is required for type '{document_type}'.",
                    1,
                )

        if not isinstance(document_id, str) or not self.contract.generic_id_pattern.fullmatch(document_id):
            self.add("error", "id-invalid", relative, "Frontmatter id must be a stable uppercase identifier.", 1)
        else:
            self.definitions.append(IdDefinition(document_id, relative, 2, "frontmatter"))
            self.definitions_by_path.setdefault(relative, set()).add(document_id)
            expected_pattern = self.contract.type_id_patterns.get(document_type) if isinstance(document_type, str) else None
            if expected_pattern is not None and expected_pattern.fullmatch(document_id) is None:
                self.add(
                    "error",
                    "id-type-mismatch",
                    relative,
                    f"ID '{document_id}' does not match type '{document_type}'.",
                    2,
                )
            self.validate_filename_id(relative, document_id)

        for field in ("type", "title"):
            value = metadata.get(field)
            if not isinstance(value, str) or not value.strip():
                self.add("error", "frontmatter-field-invalid", relative, f"Frontmatter field '{field}' must be a non-empty string.", 1)
        if not isinstance(document_type, str) or document_type not in self.contract.document_type_contracts:
            self.add("error", "document-type-invalid", relative, f"Unsupported document type: {document_type!r}.", 1)

        allowed_statuses = self.contract.statuses_for_type(document_type)
        if not isinstance(status, str) or status not in allowed_statuses:
            self.add(
                "error",
                "status-invalid",
                relative,
                f"Unsupported status {status!r} for document type {document_type!r}.",
                1,
            )
        if not isinstance(confidence, str) or confidence not in self.contract.confidence_values:
            self.add("error", "confidence-invalid", relative, f"Unsupported confidence value: {confidence!r}.", 1)

        for field in ("tags", "related", "source_paths"):
            self.validate_string_list(metadata.get(field), relative, field, "frontmatter-field-invalid")

        created = self.validate_date(metadata.get("created"), relative, "created")
        updated = self.validate_date(metadata.get("updated"), relative, "updated")
        if created is not None and updated is not None and updated < created:
            self.add("error", "updated-before-created", relative, "Frontmatter updated date precedes created date.", 1)
        if updated is not None:
            self.updated_by_path[relative] = updated

        if document_type == "alert":
            severity = metadata.get("severity")
            if not isinstance(severity, str) or severity not in self.contract.alert_severities:
                self.add("error", "alert-severity-invalid", relative, f"Unsupported alert severity: {severity!r}.", 1)

    def validate_filename_id(self, relative: str, document_id: str) -> None:
        path = PurePosixPath(relative)
        parent = path.parent.as_posix()
        if parent not in self.contract.standalone_record_directories:
            return
        stem = path.stem.upper()
        if stem != document_id and not stem.startswith(f"{document_id}-"):
            self.add(
                "error",
                "id-filename-mismatch",
                relative,
                f"Filename does not start with frontmatter ID '{document_id}'.",
                2,
            )

    def scan_markdown_body(
        self,
        path: Path,
        relative: str,
        body: str,
        body_start_line: int,
        metadata: dict[str, Any] | None,
        *,
        interpret_definitions: bool,
    ) -> None:
        parser = self.markdown_parser()
        tokens = parser.parse(body)
        frontmatter_id = metadata.get("id") if metadata else None
        heading_definitions: dict[str, list[int]] = {}
        anchors: set[str] = set()
        explicit_anchors: set[str] = set()
        slug_counts: dict[str, int] = {}
        current_record_id: str | None = None
        current_record_level: int | None = None

        for index, token in enumerate(tokens):
            line_number = body_start_line + (token.map[0] if token.map else 0)
            if token.type == "heading_open" and index + 1 < len(tokens):
                inline = tokens[index + 1]
                heading = inline.content
                base_slug = github_slug(heading)
                count = slug_counts.get(base_slug, 0)
                slug_counts[base_slug] = count + 1
                anchor = base_slug if count == 0 else f"{base_slug}-{count}"
                anchors.add(anchor)
                document_id = self.heading_id(heading) if interpret_definitions else None
                if document_id is not None:
                    current_record_id = document_id
                    current_record_level = int(token.tag[1:]) if token.tag.startswith("h") else None
                    heading_definitions.setdefault(document_id, []).append(line_number)
                    self.definitions_by_path.setdefault(relative, set()).add(document_id)
                    self.definition_anchors_by_path.setdefault(relative, {}).setdefault(document_id, set()).add(anchor)
                    title = self.heading_title(heading, document_id)
                    if title:
                        self.embedded_title_by_path.setdefault(relative, {})[document_id] = title
                elif current_record_id is not None and token.tag.startswith("h"):
                    heading_level = int(token.tag[1:])
                    if current_record_level is not None and heading_level <= current_record_level:
                        current_record_id = None
                        current_record_level = None

            if token.type == "html_block":
                explicit_anchors.update(self.extract_html_anchors(token.content))

            if token.type != "inline":
                continue
            if interpret_definitions:
                for offset, line in enumerate(token.content.splitlines()):
                    status_match = INLINE_STATUS_PATTERN.match(line)
                    if status_match and current_record_id is not None:
                        status = status_match.group(1).lower()
                        if status not in self.contract.statuses_for_embedded_id(current_record_id):
                            self.add(
                                "error",
                                "status-invalid",
                                relative,
                                f"Unsupported status {status!r} for embedded record '{current_record_id}'.",
                                line_number + offset,
                            )
                        previous_status = self.embedded_status_by_path.setdefault(relative, {}).get(current_record_id)
                        if previous_status is not None and previous_status != status:
                            self.add(
                                "error",
                                "embedded-status-conflict",
                                relative,
                                f"Embedded record '{current_record_id}' declares conflicting statuses.",
                                line_number + offset,
                            )
                        self.embedded_status_by_path[relative][current_record_id] = status
                    if INLINE_EVIDENCE_PREFIX_PATTERN.match(line) and current_record_id is not None:
                        self.add(
                            "error",
                            "embedded-inline-evidence-invalid",
                            relative,
                            f"Embedded record '{current_record_id}' must store intake evidence in "
                            f"{self.contract.semantic_paths.requirement_evidence_file}, not inline.",
                            line_number + offset,
                        )
                    if (
                        current_record_id is not None
                        and self.is_atomic_requirement_id(current_record_id)
                        and INTAKE_CHUNK_REFERENCE_PATTERN.search(line)
                    ):
                        self.add(
                            "error",
                            "embedded-intake-chunk-reference-invalid",
                            relative,
                            f"Atomic record '{current_record_id}' must store intake chunk references in "
                            f"{self.contract.semantic_paths.requirement_evidence_file}, not in its readable body.",
                            line_number + offset,
                        )
            for child in token.children or []:
                if child.type == "link_open":
                    destination = child.attrGet("href")
                    if destination:
                        self.pending_links.append(PendingLink(path, relative, destination, line_number))
                elif child.type == "image":
                    destination = child.attrGet("src")
                    if destination:
                        self.pending_links.append(PendingLink(path, relative, destination, line_number))
                elif child.type == "html_inline":
                    explicit_anchors.update(self.extract_html_anchors(child.content))

        anchors.update(explicit_anchors)
        self.anchor_cache[relative] = {anchor.casefold() for anchor in anchors}
        for anchor in explicit_anchors:
            candidate_id = anchor.upper()
            if self.contract.generic_id_pattern.fullmatch(candidate_id):
                self.definition_anchors_by_path.setdefault(relative, {}).setdefault(candidate_id, set()).add(anchor.casefold())

        for document_id, lines in heading_definitions.items():
            locations = lines[1:] if document_id == frontmatter_id else lines
            for line_number in locations:
                self.definitions.append(IdDefinition(document_id, relative, line_number, "heading"))

    def markdown_parser(self) -> Any:
        try:
            from markdown_it import MarkdownIt  # type: ignore[import-untyped]
        except ImportError as error:
            raise ValidatorDependencyError(
                "wiki validation requires markdown-it-py; install scripts/requirements.txt"
            ) from error
        return MarkdownIt("commonmark", {"html": True})

    def extract_html_anchors(self, content: str) -> set[str]:
        return {match.group(1).casefold() for match in HTML_ANCHOR_PATTERN.finditer(content)}

    def heading_id(self, heading: str) -> str | None:
        direct = self.contract.canonical_id_pattern.match(heading)
        if direct:
            return direct.group(0)
        match = re.search(self.contract.id_pattern_strings["wiki-log"], heading)
        return match.group(0) if match else None

    def is_atomic_requirement_id(self, document_id: str) -> bool:
        return any(
            self.contract.type_id_patterns[document_type].fullmatch(document_id) is not None
            for document_type in ("requirement", "non-functional-requirement", "constraint")
        )

    @staticmethod
    def heading_title(heading: str, document_id: str) -> str:
        position = heading.find(document_id)
        if position < 0:
            return ""
        return heading[position + len(document_id) :].lstrip(" | -–—:").strip()

    def check_duplicate_definitions(self) -> None:
        by_id: dict[str, list[IdDefinition]] = {}
        for definition in self.definitions:
            by_id.setdefault(definition.id, []).append(definition)
        for document_id, definitions in sorted(by_id.items()):
            if len(definitions) < 2:
                continue
            locations = ", ".join(
                f"{definition.path}:{definition.line or 1}" for definition in definitions
            )
            for definition in definitions:
                self.add(
                    "error",
                    "id-duplicate",
                    definition.path,
                    f"ID '{document_id}' is defined more than once: {locations}.",
                    definition.line,
                )

    def check_embedded_record_contracts(self) -> None:
        atomic_patterns = {
            "requirement": self.contract.type_id_patterns["requirement"],
            "non-functional-requirement": self.contract.type_id_patterns["non-functional-requirement"],
            "constraint": self.contract.type_id_patterns["constraint"],
        }
        for definition in self.definitions:
            if definition.kind != "heading":
                continue
            relative = definition.path
            document_id = definition.id
            if PurePosixPath(relative).name == "INDEX.md":
                self.add(
                    "error",
                    "index-embedded-record-invalid",
                    relative,
                    f"Index files are routing-only and cannot define embedded record '{document_id}'.",
                    definition.line,
                )
            expected_location: str | None = None
            if atomic_patterns["requirement"].fullmatch(document_id):
                expected_location = "requirements/functional/*.md"
                valid_location = (
                    PurePosixPath(relative).parent.as_posix() == "requirements/functional"
                    and PurePosixPath(relative).name != "INDEX.md"
                )
            elif atomic_patterns["non-functional-requirement"].fullmatch(document_id):
                expected_location = "requirements/non-functional/*.md"
                valid_location = (
                    PurePosixPath(relative).parent.as_posix() == "requirements/non-functional"
                    and PurePosixPath(relative).name != "INDEX.md"
                )
            elif atomic_patterns["constraint"].fullmatch(document_id):
                expected_location = "requirements/constraints.md"
                valid_location = relative == expected_location
            else:
                continue
            if not valid_location:
                self.add(
                    "error",
                    "atomic-record-location-invalid",
                    relative,
                    f"Atomic record '{document_id}' must be stored in {expected_location}.",
                    definition.line,
                )

    def check_requirement_evidence(self) -> None:
        relative = self.contract.semantic_paths.requirement_evidence_file
        payload = self.yaml_documents.get(relative)
        if not isinstance(payload, dict):
            if (self.wiki_root / relative).is_file() and payload is not None:
                self.add("error", "requirement-evidence-invalid", relative, "Requirement evidence must be a YAML mapping.")
            return
        if set(payload) != {"version", "records"} or payload.get("version") != 1:
            self.add(
                "error",
                "requirement-evidence-invalid",
                relative,
                "Requirement evidence must contain version: 1 and a records mapping.",
            )
        records = payload.get("records")
        if not isinstance(records, dict):
            self.add("error", "requirement-evidence-invalid", relative, "Requirement evidence records must be a mapping.")
            return
        atomic_definition_ids = {
            definition.id
            for definition in self.definitions
            if definition.kind == "heading" and self.is_atomic_requirement_id(definition.id)
        }
        for document_id, raw_evidence in records.items():
            if not isinstance(document_id, str) or not self.is_atomic_requirement_id(document_id):
                self.add(
                    "error",
                    "requirement-evidence-record-id-invalid",
                    relative,
                    f"Requirement evidence key {document_id!r} is not an atomic REQ, NFR, or CON ID.",
                )
                continue
            if document_id not in atomic_definition_ids:
                self.add(
                    "error",
                    "requirement-evidence-record-missing",
                    relative,
                    f"Requirement evidence references undefined atomic record '{document_id}'.",
                )
            if (
                not isinstance(raw_evidence, list)
                or not raw_evidence
                or any(not isinstance(chunk_id, str) for chunk_id in raw_evidence)
                or len(raw_evidence) != len(set(raw_evidence))
            ):
                self.add(
                    "error",
                    "requirement-evidence-chunks-invalid",
                    relative,
                    f"Evidence for '{document_id}' must be a non-empty unique list of chunk IDs.",
                )
                continue
            evidence = tuple(raw_evidence)
            self.requirement_evidence_by_id[document_id] = evidence
            for chunk_id in evidence:
                if self.contract.type_id_patterns["intake-chunk"].fullmatch(chunk_id) is None:
                    self.add(
                        "error",
                        "requirement-evidence-chunk-id-invalid",
                        relative,
                        f"Evidence for '{document_id}' contains invalid chunk ID '{chunk_id}'.",
                    )
                elif chunk_id not in self.intake_chunk_ids:
                    self.add(
                        "error",
                        "requirement-evidence-chunk-missing",
                        relative,
                        f"Evidence chunk '{chunk_id}' for '{document_id}' does not exist.",
                    )
    def check_wiki_version(self) -> None:
        relative = self.contract.semantic_paths.wiki_version_file
        payload = self.yaml_documents.get(relative)
        if not isinstance(payload, dict):
            if (self.wiki_root / relative).is_file() and payload is not None:
                self.add("error", "wiki-version-invalid", relative, "WIKI_VERSION.yml must be a YAML mapping.")
            return
        if payload.get("schema") != self.contract.schema_name:
            self.add("error", "wiki-schema-invalid", relative, f"schema must be {self.contract.schema_name!r}.")
        if str(payload.get("schema_version")) != self.contract.schema_version:
            self.add(
                "error",
                "wiki-schema-version-mismatch",
                relative,
                f"Expected schema version {self.contract.schema_version}, found {payload.get('schema_version')!r}.",
            )
        schema_updated = self.validate_date(payload.get("schema_updated"), relative, "schema_updated")
        if schema_updated is not None and schema_updated.isoformat() != self.contract.schema_updated:
            self.add(
                "error",
                "wiki-schema-updated-mismatch",
                relative,
                f"schema_updated must be {self.contract.schema_updated}.",
            )
        self.validate_date(payload.get("last_migrated"), relative, "last_migrated")

    def check_registry(self) -> None:
        relative = self.contract.semantic_paths.document_registry_file
        payload = self.yaml_documents.get(relative)
        if not isinstance(payload, dict):
            if (self.wiki_root / relative).is_file() and payload is not None:
                self.add("error", "registry-invalid", relative, "REGISTRY.yml must be a YAML mapping.")
            return
        if payload.get("version") != self.contract.document_registry_version:
            self.add("error", "registry-version-invalid", relative, f"Registry version must be {self.contract.document_registry_version}.")
        registry_updated = self.validate_date(payload.get("updated"), relative, "updated")
        documents = payload.get("documents")
        if not isinstance(documents, list):
            self.add("error", "registry-documents-invalid", relative, "Registry documents must be a list.")
            return

        seen: set[str] = set()
        entries_by_id: dict[str, dict[str, Any]] = {}
        for index, entry in enumerate(documents, start=1):
            location = f"REGISTRY.yml#documents[{index}]"
            if not isinstance(entry, dict):
                self.add("error", "registry-entry-invalid", relative, f"Registry entry {index} must be a mapping.")
                continue
            for field in ("id", "type", "title", "path", "status", "tags", "related", "source_paths", "confidence"):
                if field not in entry:
                    self.add("error", "registry-field-missing", relative, f"{location} is missing '{field}'.")

            document_id = entry.get("id")
            if not isinstance(document_id, str) or not self.contract.generic_id_pattern.fullmatch(document_id):
                self.add("error", "registry-id-invalid", relative, f"{location} has an invalid ID.")
                continue
            if document_id in seen:
                self.add("error", "registry-id-duplicate", relative, f"Registry ID '{document_id}' appears more than once.")
            seen.add(document_id)
            self.registry_ids.add(document_id)
            entries_by_id[document_id] = entry

            registry_status = entry.get("status")
            registry_type = entry.get("type")
            if not isinstance(registry_type, str) or registry_type not in self.contract.document_type_contracts:
                self.add("error", "registry-type-invalid", relative, f"{location} has unsupported type {registry_type!r}.")
            expected_pattern = self.contract.type_id_patterns.get(registry_type) if isinstance(registry_type, str) else None
            if expected_pattern is not None and expected_pattern.fullmatch(document_id) is None:
                self.add(
                    "error",
                    "registry-id-type-mismatch",
                    relative,
                    f"{location} ID '{document_id}' does not match type {registry_type!r}.",
                )
            if not isinstance(registry_status, str) or registry_status not in self.contract.document_statuses:
                self.add("error", "registry-status-invalid", relative, f"{location} has unsupported status {entry.get('status')!r}.")
            elif registry_status not in self.contract.statuses_for_type(entry.get("type")):
                self.add(
                    "error",
                    "registry-status-invalid",
                    relative,
                    f"{location} status {entry.get('status')!r} is invalid for type {entry.get('type')!r}.",
                )
            if not isinstance(entry.get("confidence"), str) or entry.get("confidence") not in self.contract.confidence_values:
                self.add("error", "registry-confidence-invalid", relative, f"{location} has unsupported confidence {entry.get('confidence')!r}.")
            for field in ("type", "title"):
                if not isinstance(entry.get(field), str) or not entry[field].strip():
                    self.add("error", "registry-field-invalid", relative, f"{location}.{field} must be a non-empty string.")
            for field in ("tags", "related", "source_paths"):
                self.validate_string_list(entry.get(field), relative, f"{location}.{field}", "registry-field-invalid")
            target_relative = self.validate_registry_path(document_id, entry.get("path"), relative, location)
            if target_relative is not None:
                self.registry_target_paths.add(target_relative)
                self.reconcile_registry_frontmatter(document_id, entry, target_relative, relative, location)
            self.validate_registry_source_paths(entry.get("source_paths"), relative, location)

        known_ids = {definition.id for definition in self.definitions} | self.registry_ids | self.source_registry_ids
        for document_id, entry in entries_by_id.items():
            related = entry.get("related")
            if not isinstance(related, list):
                continue
            for related_id in related:
                if isinstance(related_id, str) and related_id not in known_ids:
                    self.add(
                        "error",
                        "registry-related-id-missing",
                        relative,
                        f"Registry ID '{document_id}' relates to unknown ID '{related_id}'.",
                    )

        catalogued_dates = [
            self.updated_by_path[path]
            for path in self.registry_target_paths
            if path in self.updated_by_path
        ]
        max_catalogued_updated = max(catalogued_dates, default=None)
        if registry_updated is not None and max_catalogued_updated is not None and registry_updated < max_catalogued_updated:
            self.add(
                "error",
                "registry-updated-stale",
                relative,
                f"Registry updated date {registry_updated} precedes catalogued document update {max_catalogued_updated}.",
            )

    def validate_registry_path(self, document_id: str, value: object, registry_path: str, location: str) -> str | None:
        if not isinstance(value, str) or not value.strip():
            self.add("error", "registry-path-invalid", registry_path, f"{location}.path must be a non-empty relative path.")
            return None
        path_text, separator, fragment = value.partition("#")
        normalized = self.safe_wiki_path(path_text, registry_path, "registry-path-invalid", location)
        if normalized is None:
            return None
        target = self.wiki_root / normalized
        resolved = self.resolve_contained_path(
            target,
            self.wiki_root,
            registry_path,
            "registry-path-outside-wiki",
            f"{location}.path",
            reject_symlinks=True,
        )
        if resolved is None:
            return None
        if not resolved.is_file():
            self.add("error", "registry-path-missing", registry_path, f"{location}.path target does not exist: {path_text}.")
            return None
        target_relative = self.relative(target)
        if separator and fragment:
            normalized_fragment = unquote(fragment).casefold()
            if not self.anchor_exists(target, normalized_fragment):
                self.add("error", "registry-anchor-missing", registry_path, f"{location}.path anchor does not exist: #{fragment}.")
            elif normalized_fragment not in self.definition_anchors_by_path.get(target_relative, {}).get(document_id, set()):
                self.add(
                    "error",
                    "registry-anchor-id-mismatch",
                    registry_path,
                    f"{location}.path anchor does not identify '{document_id}'.",
                )
        if document_id not in self.definitions_by_path.get(target_relative, set()):
            self.add(
                "error",
                "registry-id-target-mismatch",
                registry_path,
                f"{location} points to {target_relative}, which does not define '{document_id}'.",
            )
        return target_relative

    def reconcile_registry_frontmatter(
        self,
        document_id: str,
        entry: dict[str, Any],
        target_relative: str,
        registry_path: str,
        location: str,
    ) -> None:
        metadata = self.frontmatter.get(target_relative)
        if metadata is not None and metadata.get("id") == document_id:
            for field in ("type", "title", "status", "tags", "related", "source_paths", "confidence"):
                if field in entry and entry.get(field) != metadata.get(field):
                    self.add(
                        "error",
                        "registry-frontmatter-mismatch",
                        registry_path,
                        f"{location}.{field} does not match {target_relative} frontmatter.",
                    )
            return

        embedded_status = self.embedded_status_by_path.get(target_relative, {}).get(document_id)
        if embedded_status is not None and entry.get("status") != embedded_status:
            self.add(
                "error",
                "registry-embedded-status-mismatch",
                registry_path,
                f"{location}.status does not match embedded record '{document_id}'.",
            )
        embedded_title = self.embedded_title_by_path.get(target_relative, {}).get(document_id)
        if embedded_title is not None and entry.get("title") != embedded_title:
            self.add(
                "error",
                "registry-embedded-title-mismatch",
                registry_path,
                f"{location}.title does not match embedded record '{document_id}'.",
            )

    def validate_registry_source_paths(self, value: object, relative: str, location: str) -> None:
        if not isinstance(value, list):
            return
        repository_root = self.wiki_root.parent
        for source_path in value:
            if not isinstance(source_path, str) or not source_path.strip():
                continue
            pure = PurePosixPath(source_path.replace("\\", "/"))
            if pure.is_absolute() or ".." in pure.parts:
                self.add("error", "source-path-invalid", relative, f"{location} has unsafe source path '{source_path}'.")
                continue
            candidate = repository_root / pure
            if not candidate.exists():
                self.add("error", "source-path-missing", relative, f"{location} source path does not exist: {source_path}.")
            else:
                self.resolve_contained_path(
                    candidate,
                    repository_root,
                    relative,
                    "source-path-outside-repository",
                    f"{location} source path",
                    reject_symlinks=False,
                )

    def check_registry_completeness(self) -> None:
        for definition in self.definitions:
            if not self.requires_registry_entry(definition):
                continue
            if definition.id not in self.registry_ids:
                self.add(
                    "error",
                    "registry-entry-missing",
                    definition.path,
                    f"Defined ID '{definition.id}' is not catalogued in REGISTRY.yml.",
                    definition.line,
                )

    def requires_registry_entry(self, definition: IdDefinition) -> bool:
        if re.fullmatch(self.contract.id_pattern_strings["wiki-log"], definition.id):
            return False
        parts = PurePosixPath(definition.path).parts
        if not parts:
            return False
        non_registry_prefixes = {
            self.contract.semantic_paths.intake_root_directory,
            self.contract.semantic_paths.source_inbox_directory,
            self.contract.semantic_paths.source_processed_directory,
            self.contract.semantic_paths.source_rejected_directory,
            self.contract.semantic_paths.source_ignored_directory,
            "logs",
            "templates",
        }
        if any(
            parts[: len(prefix_parts)] == prefix_parts
            for prefix_parts in (PurePosixPath(value).parts for value in non_registry_prefixes)
        ):
            return False
        return True

    def check_source_registry(self) -> None:
        relative = self.contract.semantic_paths.source_registry_file
        payload = self.yaml_documents.get(relative)
        if not isinstance(payload, dict):
            if (self.wiki_root / relative).is_file() and payload is not None:
                self.add("error", "source-registry-invalid", relative, "Source registry must be a YAML mapping.")
            return
        if payload.get("version") != self.contract.source_registry_version:
            self.add("error", "source-registry-version-invalid", relative, f"Source registry version must be {self.contract.source_registry_version}.")
        self.validate_date(payload.get("updated"), relative, "updated")
        sources = payload.get("sources")
        if not isinstance(sources, list):
            self.add("error", "source-registry-sources-invalid", relative, "Source registry sources must be a list.")
            return

        seen: set[str] = set()
        for index, entry in enumerate(sources, start=1):
            location = f"sources[{index}]"
            if not isinstance(entry, dict):
                self.add("error", "source-registry-entry-invalid", relative, f"{location} must be a mapping.")
                continue
            for field in ("id", "status", "original_path", "current_path", "filename", "sha256", "intake_id", "processed_at", "tags", "notes"):
                if field not in entry:
                    self.add("error", "source-registry-field-missing", relative, f"{location} is missing '{field}'.")
            source_id = entry.get("id")
            if not isinstance(source_id, str) or re.fullmatch(self.contract.id_pattern_strings["source-record"], source_id) is None:
                self.add("error", "source-registry-id-invalid", relative, f"{location} has an invalid source ID.")
            elif source_id in seen:
                self.add("error", "source-registry-id-duplicate", relative, f"Source ID '{source_id}' appears more than once.")
            else:
                seen.add(source_id)
                self.source_registry_ids.add(source_id)
            source_status = entry.get("status")
            if not isinstance(source_status, str) or source_status not in self.contract.statuses["source"]:
                self.add("error", "source-registry-status-invalid", relative, f"{location} has unsupported status {entry.get('status')!r}.")
            source_hash = entry.get("sha256")
            if not isinstance(source_hash, str) or SHA256_PATTERN.fullmatch(source_hash.lower()) is None:
                self.add("error", "source-registry-hash-invalid", relative, f"{location} has an invalid SHA-256.")
            self.validate_string_list(entry.get("tags"), relative, f"{location}.tags", "source-registry-field-invalid")
            for field in ("original_path", "current_path"):
                value = entry.get(field)
                if value is not None:
                    self.safe_wiki_path(value, relative, "source-registry-path-invalid", f"{location}.{field}")
            current_path = entry.get("current_path")
            if isinstance(current_path, str):
                normalized = self.normalized_relative_path(current_path)
                if normalized is not None:
                    target = self.wiki_root / normalized
                    resolved_target = self.resolve_contained_path(
                        target,
                        self.wiki_root,
                        relative,
                        "source-registry-path-outside-wiki",
                        f"{location}.current_path",
                        reject_symlinks=True,
                    )
                    if resolved_target is not None and not resolved_target.is_file():
                        self.add("error", "source-registry-current-path-missing", relative, f"{location}.current_path does not exist: {current_path}.")
            intake_id = entry.get("intake_id")
            if intake_id is not None:
                if not isinstance(intake_id, str) or re.fullmatch(self.contract.id_pattern_strings["intake-document"], intake_id) is None:
                    self.add("error", "source-registry-intake-id-invalid", relative, f"{location}.intake_id is invalid.")
                elif not self.intake_document_root(intake_id).is_dir():
                    self.add("error", "source-registry-intake-missing", relative, f"{location}.intake_id directory does not exist: {intake_id}.")
            if entry.get("processed_at") is not None:
                self.validate_date(entry.get("processed_at"), relative, f"{location}.processed_at")
            if entry.get("status") == self.contract.generated_values["source_processed_status"]:
                self.validate_processed_source_entry(entry, relative, location)

    def validate_processed_source_entry(self, entry: dict[str, Any], relative: str, location: str) -> None:
        source_hash = entry.get("sha256")
        intake_id = entry.get("intake_id")
        processed_at = entry.get("processed_at")
        current_path = entry.get("current_path")
        valid_intake_id = (
            isinstance(intake_id, str)
            and re.fullmatch(self.contract.id_pattern_strings["intake-document"], intake_id) is not None
        )
        if not valid_intake_id:
            self.add("error", "processed-source-intake-required", relative, f"{location} processed source requires a valid intake_id.")
        if self.validate_date(processed_at, relative, f"{location}.processed_at") is None:
            self.add("error", "processed-source-date-required", relative, f"{location} processed source requires processed_at.")
        if not isinstance(current_path, str):
            self.add("error", "processed-source-current-path-required", relative, f"{location} processed source requires current_path.")
        else:
            normalized = self.normalized_relative_path(current_path)
            if normalized is not None:
                target = self.wiki_root / normalized
                resolved_target = self.resolve_contained_path(
                    target,
                    self.wiki_root,
                    relative,
                    "source-registry-path-outside-wiki",
                    f"{location}.current_path",
                    reject_symlinks=True,
                )
                if resolved_target is not None and resolved_target.is_file() and isinstance(source_hash, str) and SHA256_PATTERN.fullmatch(source_hash.lower()):
                    if sha256_file(resolved_target) != source_hash.lower():
                        self.add("error", "processed-source-current-hash-mismatch", relative, f"{location} sha256 does not match current_path bytes.")

        if not valid_intake_id:
            return
        artifacts = self.contract.intake_artifacts
        source_info_relative = self.intake_document_relative(intake_id, artifacts.source_info)
        manifest_relative = self.intake_document_relative(intake_id, artifacts.chunks_manifest)
        source_info = self.yaml_documents.get(source_info_relative)
        manifest = self.json_documents.get(manifest_relative)
        if not isinstance(source_info, dict) or not isinstance(manifest, dict):
            self.add("error", "processed-source-intake-missing", relative, f"{location} intake provenance is incomplete.")
            return
        manifest_source = manifest.get("source")
        manifest_hash = manifest_source.get("sha256") if isinstance(manifest_source, dict) else None
        if source_info.get("source_sha256") != source_hash or manifest_hash != source_hash:
            self.add("error", "processed-source-intake-hash-mismatch", relative, f"{location} sha256 does not match intake provenance.")

    def check_links(self) -> None:
        for link in self.pending_links:
            self.validate_link(link.source, link.source_relative, link.destination, link.line)

    def validate_link(self, source: Path, relative: str, destination: str, line_number: int) -> None:
        destination = html.unescape(destination).strip()
        parsed = urlsplit(destination)
        if parsed.scheme or destination.startswith("//"):
            return
        path_text = unquote(parsed.path)
        fragment = unquote(parsed.fragment)
        if not path_text:
            target = source
        else:
            candidate = self.resolve_contained_path(
                source.parent / path_text,
                self.wiki_root,
                relative,
                "link-outside-wiki",
                f"Link target '{destination}'",
                reject_symlinks=True,
                line=line_number,
            )
            if candidate is None:
                return
            target = candidate
        if not target.exists():
            self.add("error", "link-target-missing", relative, f"Link target does not exist: {destination}.", line_number)
            return
        if fragment and (not target.is_file() or not self.anchor_exists(target, fragment)):
            self.add("error", "link-anchor-missing", relative, f"Link anchor does not exist: {destination}.", line_number)

    def anchor_exists(self, path: Path, fragment: str) -> bool:
        relative = self.relative(path)
        if relative not in self.anchor_cache:
            self.anchor_cache[relative] = self.collect_anchors(path)
        return fragment.casefold() in self.anchor_cache[relative]

    def collect_anchors(self, path: Path) -> set[str]:
        if path.suffix.lower() != ".md":
            return set()
        text = self.read_text(path, self.relative(path))
        if text is None:
            return set()
        body = strip_frontmatter(text)
        tokens = self.markdown_parser().parse(body)
        anchors: set[str] = set()
        slug_counts: dict[str, int] = {}
        for index, token in enumerate(tokens):
            if token.type == "heading_open" and index + 1 < len(tokens):
                heading = tokens[index + 1].content
                base_slug = github_slug(heading)
                count = slug_counts.get(base_slug, 0)
                slug_counts[base_slug] = count + 1
                anchors.add(base_slug if count == 0 else f"{base_slug}-{count}")
            if token.type == "html_block":
                anchors.update(self.extract_html_anchors(token.content))
            if token.type == "inline":
                for child in token.children or []:
                    if child.type == "html_inline":
                        anchors.update(self.extract_html_anchors(child.content))
        return anchors

    def validate_string_list(self, value: object, relative: str, field: str, code: str) -> None:
        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            self.add("error", code, relative, f"{field} must be a list of strings.")

    def validate_date(self, value: object, relative: str, field: str) -> date | None:
        parsed: date | None = None
        if type(value) is date:
            parsed = value
        elif isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            try:
                parsed = date.fromisoformat(value)
            except ValueError:
                parsed = None
        if parsed is None:
            self.add("error", "date-invalid", relative, f"{field} must be an ISO date (YYYY-MM-DD).")
        return parsed

    def safe_wiki_path(self, value: object, relative: str, code: str, field: str) -> str | None:
        if not isinstance(value, str) or not value.strip():
            self.add("error", code, relative, f"{field} must be a non-empty relative path.")
            return None
        normalized = self.normalized_relative_path(value)
        if normalized is None:
            self.add("error", code, relative, f"{field} must stay inside .project-wiki/: {value!r}.")
        return normalized

    def normalized_relative_path(self, value: str) -> str | None:
        text = value.strip().replace("\\", "/")
        while text.startswith("./"):
            text = text[2:]
        if text.startswith(".project-wiki/"):
            text = text[len(".project-wiki/") :]
        pure = PurePosixPath(text)
        if pure.is_absolute() or ".." in pure.parts or not pure.parts:
            return None
        return pure.as_posix()

    def resolve_contained_path(
        self,
        candidate: Path,
        root: Path,
        finding_path: str,
        code: str,
        label: str,
        *,
        reject_symlinks: bool,
        line: int | None = None,
    ) -> Path | None:
        root_resolved = root.resolve()
        lexical = Path(os.path.abspath(candidate))
        try:
            relative = lexical.relative_to(root_resolved)
        except ValueError:
            self.add("error", code, finding_path, f"{label} escapes {root_resolved}.", line)
            return None
        if reject_symlinks:
            current = root_resolved
            for part in relative.parts:
                current = current / part
                if current.is_symlink():
                    self.add("error", "symlink-target-not-allowed", finding_path, f"{label} traverses symlink {current}.", line)
                    return None
        try:
            resolved = lexical.resolve(strict=False)
        except (OSError, RuntimeError) as error:
            self.add("error", "path-resolution-failed", finding_path, f"{label} cannot be resolved: {error}.", line)
            return None
        if not resolved.is_relative_to(root_resolved):
            self.add("error", code, finding_path, f"{label} resolves outside {root_resolved}.", line)
            return None
        return resolved

    def is_raw_source(self, path: Path) -> bool:
        relative = PurePosixPath(self.relative(path))
        raw_directories = (
            self.contract.semantic_paths.source_inbox_directory,
            self.contract.semantic_paths.source_processed_directory,
            self.contract.semantic_paths.source_rejected_directory,
            self.contract.semantic_paths.source_ignored_directory,
        )
        return any(relative.parts[: len(prefix)] == prefix for prefix in (PurePosixPath(value).parts for value in raw_directories))

    def is_template(self, path: Path) -> bool:
        relative = PurePosixPath(self.relative(path))
        return bool(relative.parts and relative.parts[0] == "templates")

    def is_intake_chunk(self, path: Path) -> bool:
        parts = PurePosixPath(self.relative(path)).parts
        intake_parts = PurePosixPath(self.contract.semantic_paths.intake_documents_directory).parts
        return (
            len(parts) >= len(intake_parts) + 3
            and parts[: len(intake_parts)] == intake_parts
            and parts[len(intake_parts) + 1] == self.contract.intake_artifacts.chunk_directory
        )

    def is_intake_document(self, path: Path) -> bool:
        parts = PurePosixPath(self.relative(path)).parts
        intake_parts = PurePosixPath(self.contract.semantic_paths.intake_documents_directory).parts
        return len(parts) >= len(intake_parts) + 1 and parts[: len(intake_parts)] == intake_parts

    def is_copied_intake_source(self, path: Path) -> bool:
        parts = PurePosixPath(self.relative(path)).parts
        intake_parts = PurePosixPath(self.contract.semantic_paths.intake_documents_directory).parts
        return (
            len(parts) == len(intake_parts) + 2
            and parts[: len(intake_parts)] == intake_parts
            and re.fullmatch(
                self.contract.id_pattern_strings["intake-document"],
                parts[len(intake_parts)],
            ) is not None
            and parts[-1].startswith(f"{self.contract.intake_artifacts.copied_source_stem}.")
        )

    def intake_document_root(self, intake_id: str) -> Path:
        return self.wiki_root / self.contract.semantic_paths.intake_documents_directory / intake_id

    def intake_document_relative(self, intake_id: str, artifact_name: str) -> str:
        return (
            PurePosixPath(self.contract.semantic_paths.intake_documents_directory)
            / intake_id
            / artifact_name
        ).as_posix()

    def relative(self, path: Path) -> str:
        return path.relative_to(self.wiki_root).as_posix()


def print_fatal_error(output_format: str, wiki_root: Path, code: str, message: str) -> None:
    finding = Finding(severity="error", code=code, path=".", message=message)
    report = ValidationReport(wiki_root=wiki_root.as_posix(), findings=(finding,))
    if output_format == "json":
        print(json.dumps(report.as_dict(), indent=2, sort_keys=True))
    else:
        print(f"error: {message}", file=sys.stderr)


def github_slug(value: str) -> str:
    value = re.sub(r"!?\[([^\]]+)\]\([^)]*\)", r"\1", value)
    value = re.sub(r"<[^>]+>", "", value)
    value = html.unescape(value).strip().casefold()
    characters = [
        character
        for character in value
        if character in {" ", "-", "_"} or not unicodedata.category(character).startswith(("P", "S"))
    ]
    return re.sub(r"\s+", "-", "".join(characters))


def strip_frontmatter(text: str) -> str:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return text
    end_index = next((index for index, line in enumerate(lines[1:], start=1) if line.strip() == "---"), None)
    if end_index is None:
        return ""
    return "\n".join(lines[end_index + 1 :])


def sha256_file(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as file_obj:
        for chunk in iter(lambda: file_obj.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def print_text_report(report: ValidationReport) -> None:
    payload = report.as_dict()
    summary = payload["summary"]
    status = "passed" if report.valid else "failed"
    print(f"Project wiki structural validation {status}")
    print(f"errors={summary['errors']} warnings={summary['warnings']}")
    for finding in report.findings:
        location = f"{finding.path}:{finding.line}" if finding.line else finding.path
        print(f"{finding.severity.upper()} {finding.code} {location} - {finding.message}")
    print("Semantic checks deferred to the agent:")
    for check in SEMANTIC_CHECKS_DEFERRED:
        print(f"- {check}")


if __name__ == "__main__":
    raise SystemExit(main())