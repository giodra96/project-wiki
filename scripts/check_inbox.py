#!/usr/bin/env python3
"""Classify project-wiki source inbox files before document ingestion."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from dataclasses import asdict, dataclass, replace
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Any

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


SUPPORTED_SUFFIXES = {".pdf", ".docx", ".txt", ".md", ".markdown"}
IGNORED_NAMES = {"readme.md", ".gitkeep", ".ds_store"}
TEMPORARY_SUFFIXES = (".tmp", ".part", ".download")
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")


class InboxCheckError(RuntimeError):
    pass


@dataclass(frozen=True)
class RegistrySource:
    id: str
    status: str
    sha256: str
    paths: tuple[str, ...]
    current_path: str | None
    intake_id: str | None
    processed_at: str | None


@dataclass(frozen=True)
class IntakeSource:
    id: str
    sha256: str
    paths: tuple[str, ...]


@dataclass(frozen=True)
class InboxFile:
    path: str
    absolute_path: Path
    sha256: str
    size_bytes: int


@dataclass(frozen=True)
class InboxDecision:
    path: str
    sha256: str
    size_bytes: int
    action: str
    reason: str
    registry_ids: tuple[str, ...] = ()
    registry_statuses: tuple[str, ...] = ()
    intake_ids: tuple[str, ...] = ()
    selected_registry_id: str | None = None
    duplicate_of: str | None = None
    quarantined_to: str | None = None


@dataclass(frozen=True)
class IgnoredFile:
    path: str
    reason: str


@dataclass(frozen=True)
class InboxReport:
    wiki_root: str
    registry_path: str
    decisions: tuple[InboxDecision, ...]
    ignored: tuple[IgnoredFile, ...]

    def as_dict(self) -> dict[str, Any]:
        reason_counts: dict[str, int] = {}
        for decision in self.decisions:
            reason_counts[decision.reason] = reason_counts.get(decision.reason, 0) + 1
        return {
            "version": 1,
            "wiki_root": self.wiki_root,
            "registry_path": self.registry_path,
            "summary": {
                "supported_files": len(self.decisions),
                "process": sum(decision.action == "process" for decision in self.decisions),
                "skip": sum(decision.action == "skip" for decision in self.decisions),
                "review": sum(decision.action == "review" for decision in self.decisions),
                "ignored": len(self.ignored),
                "by_reason": dict(sorted(reason_counts.items())),
            },
            "files": [asdict(decision) for decision in self.decisions],
            "ignored": [asdict(ignored) for ignored in self.ignored],
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check .project-wiki/sources/inbox for historical and in-inbox duplicates."
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
    parser.add_argument(
        "--quarantine-skips",
        action="store_true",
        help="After rechecking hashes, move files classified skip to sources/ignored/.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    wiki_root = Path(args.wiki_root).expanduser().resolve()
    try:
        report = check_inbox(wiki_root)
        if args.quarantine_skips:
            report = quarantine_skipped_files(wiki_root, report)
    except InboxCheckError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    except OSError as error:
        print(f"error: failed to inspect source inbox: {error}", file=sys.stderr)
        return 3

    if args.format == "json":
        print(json.dumps(report.as_dict(), indent=2, sort_keys=True))
    else:
        print_text_report(report)
    return 0


def check_inbox(wiki_root: Path) -> InboxReport:
    try:
        contract = load_schema_contract()
    except SchemaContractError as error:
        raise InboxCheckError(f"invalid schema contract: {error}") from error
    inbox_root = wiki_root / contract.semantic_paths.source_inbox_directory
    registry_path = wiki_root / contract.semantic_paths.source_registry_file
    registry_sources = load_source_registry(registry_path, contract)
    intake_sources = load_intake_history(
        wiki_root / contract.semantic_paths.intake_documents_directory,
        contract,
    )
    validate_processed_registry_sources(wiki_root, registry_sources, intake_sources, contract)
    source_paths, ignored = discover_source_files(wiki_root, inbox_root)
    inbox_files = tuple(inspect_inbox_file(wiki_root, path) for path in source_paths)
    decisions = classify_inbox_files(wiki_root, inbox_files, registry_sources, intake_sources, contract)
    validate_decision_contract(decisions, contract)
    return InboxReport(
        wiki_root=wiki_root.as_posix(),
        registry_path=registry_path.as_posix(),
        decisions=decisions,
        ignored=ignored,
    )


def validate_decision_contract(
    decisions: tuple[InboxDecision, ...],
    contract: SchemaContract,
) -> None:
    for decision in decisions:
        expected_action = contract.source_reason_actions.get(decision.reason)
        if expected_action is None:
            raise InboxCheckError(f"schema contract has no action for inbox reason {decision.reason!r}")
        if decision.action != expected_action:
            raise InboxCheckError(
                f"inbox reason {decision.reason!r} emitted action {decision.action!r}; "
                f"schema contract requires {expected_action!r}"
            )


def load_source_registry(path: Path, contract: SchemaContract) -> tuple[RegistrySource, ...]:
    if not path.exists():
        raise InboxCheckError(f"source registry not found: {path}")
    if not path.is_file():
        raise InboxCheckError(f"source registry is not a file: {path}")

    payload = load_yaml_mapping(path, "source registry")
    if payload.get("version") != contract.source_registry_version:
        raise InboxCheckError(f"source registry must be a version {contract.source_registry_version} YAML mapping")
    raw_sources = payload.get("sources")
    if not isinstance(raw_sources, list):
        raise InboxCheckError("source registry field 'sources' must be a list")

    sources: list[RegistrySource] = []
    seen_ids: set[str] = set()
    for index, raw_source in enumerate(raw_sources, start=1):
        if not isinstance(raw_source, dict):
            raise InboxCheckError(f"source registry entry {index} must be a mapping")

        source_id = raw_source.get("id")
        status = raw_source.get("status")
        source_hash = raw_source.get("sha256")
        source_pattern = re.compile(contract.id_pattern_strings["source-record"])
        if not isinstance(source_id, str) or source_pattern.fullmatch(source_id) is None:
            raise InboxCheckError(f"source registry entry {index} has no valid id")
        if source_id in seen_ids:
            raise InboxCheckError(f"source registry contains duplicate id: {source_id}")
        if not isinstance(status, str) or status not in contract.statuses["source"]:
            raise InboxCheckError(f"source registry entry {source_id} has invalid status: {status}")
        if not isinstance(source_hash, str) or not SHA256_PATTERN.fullmatch(source_hash.lower()):
            raise InboxCheckError(f"source registry entry {source_id} has no valid sha256")

        current_path = normalize_source_path(raw_source.get("current_path"))
        paths = tuple(
            normalized
            for field in ("original_path", "current_path")
            if (normalized := normalize_source_path(raw_source.get(field))) is not None
        )
        intake_id = raw_source.get("intake_id")
        processed_at = raw_source.get("processed_at")
        sources.append(
            RegistrySource(
                id=source_id,
                status=status,
                sha256=source_hash.lower(),
                paths=paths,
                current_path=current_path,
                intake_id=intake_id if isinstance(intake_id, str) else None,
                processed_at=processed_at.isoformat() if isinstance(processed_at, date) else processed_at if isinstance(processed_at, str) else None,
            )
        )
        seen_ids.add(source_id)
    return tuple(sources)


def validate_processed_registry_sources(
    wiki_root: Path,
    registry_sources: tuple[RegistrySource, ...],
    intake_sources: tuple[IntakeSource, ...],
    contract: SchemaContract,
) -> None:
    intake_by_id = {source.id: source for source in intake_sources}
    for source in registry_sources:
        if source.status != contract.generated_values["source_processed_status"]:
            continue
        intake_pattern = re.compile(contract.id_pattern_strings["intake-document"])
        if source.intake_id is None or intake_pattern.fullmatch(source.intake_id) is None:
            raise InboxCheckError(f"processed source {source.id} has no valid intake_id")
        if source.processed_at is None or re.fullmatch(r"\d{4}-\d{2}-\d{2}", source.processed_at) is None:
            raise InboxCheckError(f"processed source {source.id} has no valid processed_at date")
        try:
            date.fromisoformat(source.processed_at)
        except ValueError as error:
            raise InboxCheckError(f"processed source {source.id} has no valid processed_at date") from error
        intake = intake_by_id.get(source.intake_id)
        if intake is None:
            raise InboxCheckError(f"processed source {source.id} references missing intake {source.intake_id}")
        if intake.sha256 != source.sha256:
            raise InboxCheckError(f"processed source {source.id} hash does not match intake {source.intake_id}")
        if source.current_path is None:
            raise InboxCheckError(f"processed source {source.id} has no current_path")
        current_path = wiki_root / source.current_path
        if not current_path.is_file():
            raise InboxCheckError(f"processed source {source.id} current_path does not exist")
        if sha256_file(current_path) != source.sha256:
            raise InboxCheckError(f"processed source {source.id} hash does not match current_path")


def load_intake_history(documents_root: Path, contract: SchemaContract) -> tuple[IntakeSource, ...]:
    if not documents_root.exists():
        return ()
    if not documents_root.is_dir():
        raise InboxCheckError(f"intake documents path is not a directory: {documents_root}")

    sources: list[IntakeSource] = []
    seen_ids: set[str] = set()
    intake_pattern = re.compile(contract.id_pattern_strings["intake-document"])
    for document_root in sorted(documents_root.iterdir()):
        if not document_root.is_dir():
            raise InboxCheckError(f"intake history entry is not a directory: {document_root}")
        if intake_pattern.fullmatch(document_root.name) is None:
            raise InboxCheckError(f"intake history directory has invalid ID: {document_root.name}")
        path = document_root / contract.intake_artifacts.source_info
        manifest = validate_historical_intake(document_root, contract)
        payload = load_yaml_mapping(path, f"intake source info {path.parent.name}")
        intake_id = payload.get("id")
        source_hash = payload.get("source_sha256")
        if payload.get("version") != contract.intake_source_info_version:
            raise InboxCheckError(
                f"intake source info {intake_id or document_root.name} has unsupported version"
            )
        if not isinstance(intake_id, str) or intake_pattern.fullmatch(intake_id) is None:
            raise InboxCheckError(f"intake source info has no valid id: {path}")
        if intake_id != document_root.name:
            raise InboxCheckError(f"intake source info id does not match its directory: {document_root}")
        if intake_id in seen_ids:
            raise InboxCheckError(f"intake history contains duplicate id: {intake_id}")
        if not isinstance(source_hash, str) or not SHA256_PATTERN.fullmatch(source_hash.lower()):
            raise InboxCheckError(f"intake source info {intake_id} has no valid source_sha256")
        intake_status = payload.get("status")
        if not isinstance(intake_status, str) or intake_status not in contract.statuses["intake"]:
            raise InboxCheckError(f"intake source info {intake_id} has an invalid status")
        manifest_source = manifest.get("source")
        manifest_hash = manifest_source.get("sha256") if isinstance(manifest_source, dict) else None
        if not isinstance(manifest_hash, str) or not SHA256_PATTERN.fullmatch(manifest_hash.lower()):
            raise InboxCheckError(f"intake manifest {intake_id} has no valid source sha256")
        if manifest_hash.lower() != source_hash.lower():
            raise InboxCheckError(f"intake history {intake_id} has conflicting source hashes")

        copied_source_path = resolve_copied_source_path(
            document_root,
            payload.get("copied_source_path"),
            contract.intake_artifacts.copied_source_stem,
        )
        if copied_source_path is not None and sha256_file(copied_source_path) != source_hash.lower():
            raise InboxCheckError(f"intake history {intake_id} copied source hash does not match metadata")

        paths = tuple(
            normalized
            for field in ("source_path", "copied_source_path")
            if (normalized := normalize_source_path(payload.get(field))) is not None
        )
        sources.append(IntakeSource(id=intake_id, sha256=source_hash.lower(), paths=paths))
        seen_ids.add(intake_id)
    return tuple(sources)


def validate_historical_intake(document_root: Path, contract: SchemaContract) -> dict[str, Any]:
    artifacts = contract.intake_artifacts
    required_files = (
        document_root / artifacts.source_info,
        document_root / artifacts.extraction_index,
        document_root / artifacts.chunks_manifest,
        document_root / artifacts.intake_report,
    )
    missing = [path.name for path in required_files if not path.is_file()]
    if missing:
        raise InboxCheckError(
            f"incomplete intake history {document_root.name}; missing: {', '.join(missing)}"
        )
    empty = [path.name for path in required_files if path.stat().st_size == 0]
    if empty:
        raise InboxCheckError(
            f"incomplete intake history {document_root.name}; empty: {', '.join(empty)}"
        )

    try:
        manifest = json.loads((document_root / artifacts.chunks_manifest).read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeError) as error:
        raise InboxCheckError(f"invalid intake manifest {document_root.name}: {error}") from error
    if not isinstance(manifest, dict) or manifest.get("id") != document_root.name:
        raise InboxCheckError(f"intake manifest does not match its directory: {document_root.name}")
    if manifest.get("version") != contract.intake_chunks_manifest_version:
        raise InboxCheckError(f"intake manifest has unsupported version: {document_root.name}")

    entries = manifest.get("chunks")
    if not isinstance(entries, list) or not entries:
        raise InboxCheckError(f"intake manifest has no chunks: {document_root.name}")
    for index, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            raise InboxCheckError(f"intake manifest chunk {index} is not a mapping: {document_root.name}")
        chunk_id = entry.get("id")
        text_path = entry.get("text_path")
        chunk_pattern = re.compile(contract.id_pattern_strings["intake-chunk"])
        if not isinstance(chunk_id, str) or chunk_pattern.fullmatch(chunk_id) is None:
            raise InboxCheckError(f"intake manifest chunk {index} has an invalid id: {document_root.name}")
        generation = contract.id_generation
        text_path_pattern = re.compile(
            rf"{re.escape(artifacts.chunk_directory)}/"
            rf"{re.escape(generation.intake_chunk_label)}-"
            rf"\d{{{generation.intake_chunk_sequence_width}}}\.md"
        )
        if not isinstance(text_path, str) or text_path_pattern.fullmatch(text_path) is None:
            raise InboxCheckError(f"intake manifest chunk {index} has an invalid text_path: {document_root.name}")
        chunk_path = (document_root / text_path).resolve()
        if not chunk_path.is_relative_to(document_root.resolve()) or not chunk_path.is_file():
            raise InboxCheckError(f"intake manifest chunk {index} is missing: {document_root.name}")
        if chunk_path.stat().st_size == 0:
            raise InboxCheckError(f"intake manifest chunk {index} is empty: {document_root.name}")
    return manifest


def resolve_copied_source_path(
    document_root: Path,
    value: object,
    copied_source_stem: str,
) -> Path | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise InboxCheckError(f"intake history {document_root.name} has invalid copied_source_path")

    declared = Path(value).expanduser()
    if declared.is_absolute() and declared.parent == document_root:
        candidate = declared
    else:
        candidate = document_root / declared.name
    if not candidate.is_file() or not candidate.resolve().is_relative_to(document_root.resolve()):
        raise InboxCheckError(f"intake history {document_root.name} copied source is missing")
    if candidate.stem != copied_source_stem:
        raise InboxCheckError(f"intake history {document_root.name} copied source name does not match schema contract")
    return candidate


def load_yaml_mapping(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = strict_yaml_load(path.read_text(encoding="utf-8"), label)
    except UnicodeError as error:
        raise InboxCheckError(f"invalid {label} YAML encoding: {error}") from error
    except SchemaContractDependencyError as error:
        raise InboxCheckError(f"{label} checks require PyYAML; install scripts/requirements.txt") from error
    except SchemaContractError as error:
        raise InboxCheckError(str(error)) from error
    if not isinstance(payload, dict):
        raise InboxCheckError(f"{label} must be a YAML mapping: {path}")
    return payload


def discover_source_files(
    wiki_root: Path,
    inbox_root: Path,
) -> tuple[tuple[Path, ...], tuple[IgnoredFile, ...]]:
    if not inbox_root.exists():
        return (), ()
    if not inbox_root.is_dir():
        raise InboxCheckError(f"source inbox is not a directory: {inbox_root}")

    sources: list[Path] = []
    ignored: list[IgnoredFile] = []
    paths = sorted(
        (path for path in inbox_root.rglob("*") if not path.is_dir()),
        key=lambda path: (path.relative_to(inbox_root).as_posix().casefold(), path.as_posix()),
    )
    for path in paths:
        relative_path = path.relative_to(wiki_root).as_posix()
        reason = ignored_reason(path, inbox_root)
        if reason is not None:
            ignored.append(IgnoredFile(path=relative_path, reason=reason))
        else:
            sources.append(path)
    return tuple(sources), tuple(ignored)


def ignored_reason(path: Path, inbox_root: Path) -> str | None:
    relative_parts = path.relative_to(inbox_root).parts
    lower_name = path.name.lower()
    if path.is_symlink():
        return "symlink"
    if lower_name in IGNORED_NAMES or any(part.startswith(".") for part in relative_parts):
        return "housekeeping-or-hidden"
    if any(part.startswith("_") for part in relative_parts):
        return "underscore-prefixed"
    if lower_name.endswith(TEMPORARY_SUFFIXES):
        return "temporary-or-partial"
    if path.suffix.lower() not in SUPPORTED_SUFFIXES:
        return "unsupported-extension"
    return None


def classify_inbox_files(
    wiki_root: Path,
    inbox_files: tuple[InboxFile, ...],
    registry_sources: tuple[RegistrySource, ...],
    intake_sources: tuple[IntakeSource, ...],
    contract: SchemaContract,
) -> tuple[InboxDecision, ...]:
    status_priority = {
        status: index
        for index, status in enumerate(contract.source_status_priority)
    }
    registry_by_hash: dict[str, list[RegistrySource]] = {}
    registry_by_path: dict[str, list[RegistrySource]] = {}
    for source in registry_sources:
        registry_by_hash.setdefault(source.sha256, []).append(source)
        for path in source.paths:
            registry_by_path.setdefault(path, []).append(source)

    intake_by_hash: dict[str, list[IntakeSource]] = {}
    intake_by_path: dict[str, list[IntakeSource]] = {}
    for source in intake_sources:
        intake_by_hash.setdefault(source.sha256, []).append(source)
        for path in source.paths:
            intake_by_path.setdefault(path, []).append(source)

    inbox_by_hash: dict[str, list[InboxFile]] = {}
    for inbox_file in inbox_files:
        inbox_by_hash.setdefault(inbox_file.sha256, []).append(inbox_file)

    decisions: list[InboxDecision] = []
    for source_hash in sorted(inbox_by_hash):
        duplicates = sorted(inbox_by_hash[source_hash], key=lambda item: (item.path.casefold(), item.path))
        hash_matches = sorted(
            registry_by_hash.get(source_hash, []),
            key=lambda source: (status_priority[source.status], source.id),
        )
        intake_matches = sorted(intake_by_hash.get(source_hash, []), key=lambda source: source.id)
        canonical = select_canonical_file(
            wiki_root,
            duplicates,
            has_hash_history=bool(hash_matches or intake_matches),
            registry_by_path=registry_by_path,
            intake_by_path=intake_by_path,
        )
        decisions.append(
            classify_canonical_file(
                wiki_root,
                canonical,
                hash_matches,
                intake_matches,
                registry_by_path,
                intake_by_path,
                contract,
            )
        )
        for duplicate in (item for item in duplicates if item != canonical):
            decisions.append(
                decision_for_reason(
                    contract,
                    path=duplicate.path,
                    sha256=duplicate.sha256,
                    size_bytes=duplicate.size_bytes,
                    reason="inbox-duplicate",
                    registry_ids=tuple(source.id for source in hash_matches),
                    registry_statuses=tuple(source.status for source in hash_matches),
                    intake_ids=tuple(source.id for source in intake_matches),
                    duplicate_of=canonical.path,
                )
            )
    return tuple(sorted(decisions, key=lambda decision: (decision.path.casefold(), decision.path)))


def classify_canonical_file(
    wiki_root: Path,
    inbox_file: InboxFile,
    hash_matches: list[RegistrySource],
    intake_matches: list[IntakeSource],
    registry_by_path: dict[str, list[RegistrySource]],
    intake_by_path: dict[str, list[IntakeSource]],
    contract: SchemaContract,
) -> InboxDecision:
    terminal_hash_matches = [source for source in hash_matches if source.status in contract.source_terminal_statuses]
    if terminal_hash_matches:
        selected_match = terminal_hash_matches[0]
        return decision_for_reason(
            contract,
            path=inbox_file.path,
            sha256=inbox_file.sha256,
            size_bytes=inbox_file.size_bytes,
            reason=f"registered-{selected_match.status}",
            registry_ids=tuple(source.id for source in hash_matches),
            registry_statuses=tuple(source.status for source in hash_matches),
            intake_ids=tuple(source.id for source in intake_matches),
        )

    if intake_matches:
        return decision_for_reason(
            contract,
            path=inbox_file.path,
            sha256=inbox_file.sha256,
            size_bytes=inbox_file.size_bytes,
            reason="intake-history-match",
            registry_ids=tuple(source.id for source in hash_matches),
            registry_statuses=tuple(source.status for source in hash_matches),
            intake_ids=tuple(source.id for source in intake_matches),
        )

    if hash_matches:
        processable_matches = [source for source in hash_matches if source.status in contract.source_processable_statuses]
        if len(processable_matches) != 1:
            return decision_for_reason(
                contract,
                path=inbox_file.path,
                sha256=inbox_file.sha256,
                size_bytes=inbox_file.size_bytes,
                reason="ambiguous-processable-history",
                registry_ids=tuple(source.id for source in hash_matches),
                registry_statuses=tuple(source.status for source in hash_matches),
            )
        selected_match = processable_matches[0]
        return decision_for_reason(
            contract,
            path=inbox_file.path,
            sha256=inbox_file.sha256,
            size_bytes=inbox_file.size_bytes,
            reason=f"registered-{selected_match.status}",
            registry_ids=tuple(source.id for source in hash_matches),
            registry_statuses=tuple(source.status for source in hash_matches),
            selected_registry_id=selected_match.id,
        )

    path_matches: dict[str, RegistrySource] = {}
    intake_path_matches: dict[str, IntakeSource] = {}
    for path_key in candidate_path_keys(wiki_root, inbox_file):
        for source in registry_by_path.get(path_key, []):
            path_matches[source.id] = source
        for source in intake_by_path.get(path_key, []):
            intake_path_matches[source.id] = source
    if path_matches or intake_path_matches:
        status_priority = {
            status: index
            for index, status in enumerate(contract.source_status_priority)
        }
        matches = sorted(path_matches.values(), key=lambda source: (status_priority[source.status], source.id))
        intake_history = sorted(intake_path_matches.values(), key=lambda source: source.id)
        return decision_for_reason(
            contract,
            path=inbox_file.path,
            sha256=inbox_file.sha256,
            size_bytes=inbox_file.size_bytes,
            reason="historical-path-with-new-content",
            registry_ids=tuple(source.id for source in matches),
            registry_statuses=tuple(source.status for source in matches),
            intake_ids=tuple(source.id for source in intake_history),
        )

    return decision_for_reason(
        contract,
        path=inbox_file.path,
        sha256=inbox_file.sha256,
        size_bytes=inbox_file.size_bytes,
        reason="new-unique",
    )


def decision_for_reason(
    contract: SchemaContract,
    *,
    reason: str,
    path: str,
    sha256: str,
    size_bytes: int,
    registry_ids: tuple[str, ...] = (),
    registry_statuses: tuple[str, ...] = (),
    intake_ids: tuple[str, ...] = (),
    selected_registry_id: str | None = None,
    duplicate_of: str | None = None,
    quarantined_to: str | None = None,
) -> InboxDecision:
    action = contract.source_reason_actions.get(reason)
    if action is None:
        raise InboxCheckError(f"schema contract has no action for inbox reason {reason!r}")
    return InboxDecision(
        path=path,
        sha256=sha256,
        size_bytes=size_bytes,
        action=action,
        reason=reason,
        registry_ids=registry_ids,
        registry_statuses=registry_statuses,
        intake_ids=intake_ids,
        selected_registry_id=selected_registry_id,
        duplicate_of=duplicate_of,
        quarantined_to=quarantined_to,
    )


def select_canonical_file(
    wiki_root: Path,
    duplicates: list[InboxFile],
    *,
    has_hash_history: bool,
    registry_by_path: dict[str, list[RegistrySource]],
    intake_by_path: dict[str, list[IntakeSource]],
) -> InboxFile:
    if not has_hash_history:
        historical_paths = [
            inbox_file
            for inbox_file in duplicates
            if any(
                path_key in registry_by_path or path_key in intake_by_path
                for path_key in candidate_path_keys(wiki_root, inbox_file)
            )
        ]
        if historical_paths:
            return historical_paths[0]
    return duplicates[0]


def candidate_path_keys(wiki_root: Path, inbox_file: InboxFile) -> set[str]:
    keys = {inbox_file.path, inbox_file.absolute_path.resolve().as_posix()}
    relative_to_parent = inbox_file.absolute_path.relative_to(wiki_root.parent).as_posix()
    keys.add(relative_to_parent)
    return {normalized for key in keys if (normalized := normalize_source_path(key)) is not None}


def normalize_source_path(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip().replace("\\", "/")
    while text.startswith("./"):
        text = text[2:]
    parts = PurePosixPath(text).parts
    if ".project-wiki" in parts:
        project_wiki_index = len(parts) - 1 - tuple(reversed(parts)).index(".project-wiki")
        parts = parts[project_wiki_index + 1 :]
    return PurePosixPath(*parts).as_posix()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file_obj:
        for chunk in iter(lambda: file_obj.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_inbox_file(wiki_root: Path, path: Path) -> InboxFile:
    try:
        before = path.stat()
        source_hash = sha256_file(path)
        after = path.stat()
    except OSError as error:
        raise InboxCheckError(f"cannot hash inbox file {path}: {error}") from error
    if file_fingerprint(before) != file_fingerprint(after):
        raise InboxCheckError(f"inbox file changed during preflight; rerun check: {path}")
    return InboxFile(
        path=path.relative_to(wiki_root).as_posix(),
        absolute_path=path,
        sha256=source_hash,
        size_bytes=after.st_size,
    )


def quarantine_skipped_files(wiki_root: Path, report: InboxReport) -> InboxReport:
    contract = load_schema_contract()
    inbox_root = (wiki_root / contract.semantic_paths.source_inbox_directory).resolve()
    ignored_root = wiki_root / contract.semantic_paths.source_ignored_directory
    plans: list[tuple[InboxDecision, Path, Path]] = []
    reserved_destinations: set[Path] = set()

    for decision in report.decisions:
        if decision.action != "skip":
            continue
        source = (wiki_root / decision.path).resolve()
        if not source.is_relative_to(inbox_root):
            raise InboxCheckError(f"skip source is outside the inbox: {decision.path}")
        verify_decision_hash(source, decision.sha256)
        relative_path = source.relative_to(inbox_root)
        destination = unique_quarantine_path(
            ignored_root / relative_path,
            decision.sha256,
            reserved_destinations,
        )
        reserved_destinations.add(destination)
        plans.append((decision, source, destination))

    moved: list[tuple[Path, Path]] = []
    try:
        for decision, source, destination in plans:
            verify_decision_hash(source, decision.sha256)
            destination.parent.mkdir(parents=True, exist_ok=True)
            source.rename(destination)
            moved.append((source, destination))
    except (OSError, InboxCheckError) as error:
        rollback_errors: list[str] = []
        for source, destination in reversed(moved):
            try:
                source.parent.mkdir(parents=True, exist_ok=True)
                destination.rename(source)
            except OSError as rollback_error:
                rollback_errors.append(str(rollback_error))
        suffix = f"; rollback errors: {'; '.join(rollback_errors)}" if rollback_errors else ""
        raise InboxCheckError(f"failed to quarantine skipped inbox files: {error}{suffix}") from error

    destinations = {
        decision.path: destination.relative_to(wiki_root).as_posix()
        for decision, _, destination in plans
    }
    return replace(
        report,
        decisions=tuple(
            replace(decision, quarantined_to=destinations.get(decision.path))
            for decision in report.decisions
        ),
    )


def verify_decision_hash(path: Path, expected_hash: str) -> None:
    try:
        before = path.stat()
        actual_hash = sha256_file(path)
        after = path.stat()
    except OSError as error:
        raise InboxCheckError(f"cannot recheck skipped file {path}: {error}") from error
    if file_fingerprint(before) != file_fingerprint(after) or actual_hash != expected_hash:
        raise InboxCheckError(f"inbox file changed after preflight; rerun check: {path}")


def file_fingerprint(stat_result: os.stat_result) -> tuple[int, int, int, int]:
    return (
        stat_result.st_dev,
        stat_result.st_ino,
        stat_result.st_size,
        stat_result.st_mtime_ns,
    )


def unique_quarantine_path(destination: Path, source_hash: str, reserved: set[Path]) -> Path:
    if not destination.exists() and destination not in reserved:
        return destination
    for sequence in range(1, 10_000):
        candidate = destination.with_name(
            f"{destination.stem}-{source_hash[:12]}-{sequence}{destination.suffix}"
        )
        if not candidate.exists() and candidate not in reserved:
            return candidate
    raise InboxCheckError(f"could not allocate quarantine path for: {destination}")


def print_text_report(report: InboxReport) -> None:
    payload = report.as_dict()
    summary = payload["summary"]
    print("Source inbox preflight complete")
    print(
        f"process={summary['process']} skip={summary['skip']} review={summary['review']} "
        f"ignored={summary['ignored']}"
    )
    for decision in report.decisions:
        details = f"reason={decision.reason} sha256={decision.sha256}"
        if decision.duplicate_of:
            details += f" duplicate_of={decision.duplicate_of}"
        if decision.registry_ids:
            details += f" registry_ids={','.join(decision.registry_ids)}"
        if decision.intake_ids:
            details += f" intake_ids={','.join(decision.intake_ids)}"
        if decision.selected_registry_id:
            details += f" selected_registry_id={decision.selected_registry_id}"
        if decision.quarantined_to:
            details += f" quarantined_to={decision.quarantined_to}"
        print(f"{decision.action.upper()} {decision.path} {details}")


if __name__ == "__main__":
    raise SystemExit(main())