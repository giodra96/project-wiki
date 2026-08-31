#!/usr/bin/env python3
"""Inspect, audit, view, and update project-wiki document review progress ledgers."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
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


class ReviewProgressError(RuntimeError):
    pass


AUDIT_NORMATIVE_TERM_PATTERN = re.compile(r"\b(?:shall|must|required|requires|SLA|KPI)\b", re.IGNORECASE)
AUDIT_DEFERRED_NOTE_PATTERN = re.compile(
    r"\b(?:not model(?:ed|led)|without (?:atomic )?decomposition|summari[sz]ed|deferred|outside (?:this |the )?.*scope)\b",
    re.IGNORECASE,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect or update an intake review progress ledger.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("status", "apply", "inspect", "audit", "audit-skips", "view"):
        subparser = subparsers.add_parser(command)
        subparser.add_argument("--wiki-root", default=".project-wiki")
        subparser.add_argument("--intake-id", required=True)
    status_parser = subparsers.choices["status"]
    status_parser.add_argument("--limit", type=int, default=20)
    status_parser.add_argument("--format", choices=("text", "json"), default="text")
    apply_parser = subparsers.choices["apply"]
    apply_parser.add_argument(
        "--updates",
        required=True,
        help="JSON update file, or '-' to read JSON from standard input.",
    )
    inspect_parser = subparsers.choices["inspect"]
    inspect_parser.add_argument("--format", choices=("text", "json"), default="text")
    audit_parser = subparsers.choices["audit"]
    audit_parser.add_argument("--format", choices=("text", "json"), default="text")
    audit_parser.add_argument(
        "--expect-ledger-sha256",
        help="Fail if review-progress.yml no longer matches a previously reviewed audit digest.",
    )
    audit_skips_parser = subparsers.choices["audit-skips"]
    audit_skips_parser.add_argument("--format", choices=("text", "json"), default="text")
    view_parser = subparsers.choices["view"]
    view_selection = view_parser.add_mutually_exclusive_group()
    view_selection.add_argument("--all", dest="view_all", action="store_true")
    view_selection.add_argument("--section")
    view_selection.add_argument("--chunks", nargs="+", metavar="CHUNK_ID")
    view_parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        contract = load_schema_contract()
        wiki_root = Path(args.wiki_root).expanduser().resolve()
        document_root = intake_document_root(wiki_root, args.intake_id, contract)
        ledger_path = document_root / contract.intake_artifacts.review_progress
        manifest_path = document_root / contract.intake_artifacts.chunks_manifest
        ledger, ledger_sha256 = load_ledger(ledger_path)
        manifest_ids = load_manifest_ids(manifest_path)
        validate_ledger_identity(ledger, args.intake_id, manifest_ids, contract)
        if args.command == "audit" and args.expect_ledger_sha256 is not None:
            expected_digest = args.expect_ledger_sha256.casefold()
            if re.fullmatch(r"[0-9a-f]{64}", expected_digest) is None:
                raise ReviewProgressError("--expect-ledger-sha256 must be a 64-character hexadecimal digest")
            if expected_digest != ledger_sha256:
                raise ReviewProgressError("ledger changed since the reviewed audit snapshot; rerun audit")
        if args.command == "audit":
            validate_ledger_state(ledger, contract)
            print_audit(build_ledger_audit(args.intake_id, ledger, ledger_sha256), args.format)
            return 0
        if args.command in {"inspect", "audit-skips", "view"}:
            snapshot = load_intake_snapshot(document_root, args.intake_id, ledger, contract)
            if args.command == "inspect":
                print_inspection(snapshot, args.format)
            elif args.command == "audit-skips":
                print_skip_audit(build_skip_audit(snapshot, ledger), args.format)
            else:
                if not args.view_all and args.section is None and args.chunks is None:
                    raise ReviewProgressError("choose exactly one of --all, --section, or --chunks")
                print_view(snapshot, args.view_all, args.section, args.chunks, args.format)
            return 0
        if args.command == "status":
            if args.limit < 1:
                raise ReviewProgressError("--limit must be positive")
            print_status(ledger, args.limit, args.format)
            return 0
        updates = load_updates(args.updates)
        apply_updates(ledger, updates, manifest_ids, contract)
        write_ledger_atomic(ledger_path, ledger)
        print(f"updated review progress: {ledger_path}")
        print(f"review_status: {ledger['review_status']}")
        print(f"summary: {json.dumps(ledger['summary'], sort_keys=True)}")
        return 0
    except SchemaContractDependencyError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    except (
        SchemaContractError,
        ReviewProgressError,
        OSError,
        UnicodeError,
        json.JSONDecodeError,
        KeyError,
        TypeError,
    ) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


def intake_document_root(wiki_root: Path, intake_id: str, contract: SchemaContract) -> Path:
    if contract.type_id_patterns["intake-document"].fullmatch(intake_id) is None:
        raise ReviewProgressError("--intake-id does not match the schema contract")
    root = wiki_root.expanduser().resolve()
    return root / contract.semantic_paths.intake_documents_directory / intake_id


def load_ledger(path: Path) -> tuple[dict[str, Any], str]:
    if not path.is_file():
        raise ReviewProgressError(f"review progress ledger not found: {path}")
    raw = path.read_bytes()
    payload = strict_yaml_load(raw.decode("utf-8"), "review progress ledger")
    if not isinstance(payload, dict):
        raise ReviewProgressError("review progress ledger must be a YAML mapping")
    return payload, hashlib.sha256(raw).hexdigest()


def load_manifest_ids(path: Path) -> list[str]:
    if not path.is_file():
        raise ReviewProgressError(f"chunk manifest not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    chunks = payload.get("chunks") if isinstance(payload, dict) else None
    if not isinstance(chunks, list):
        raise ReviewProgressError("chunk manifest must contain a chunks list")
    ids = [chunk.get("id") for chunk in chunks if isinstance(chunk, dict)]
    if len(ids) != len(chunks) or any(not isinstance(value, str) for value in ids):
        raise ReviewProgressError("chunk manifest contains invalid chunk IDs")
    return ids


def load_intake_snapshot(
    document_root: Path,
    intake_id: str,
    ledger: dict[str, Any],
    contract: SchemaContract,
) -> dict[str, Any]:
    manifest = load_manifest(
        document_root / contract.intake_artifacts.chunks_manifest,
        intake_id,
        contract,
    )
    source_info = load_source_info(
        document_root / contract.intake_artifacts.source_info,
        intake_id,
        manifest,
        contract,
    )
    chunks = [load_chunk(document_root, entry, intake_id, contract) for entry in manifest["chunks"]]
    validate_ledger_state(ledger, contract)
    ledger_by_id = {entry["id"]: entry for entry in ledger["chunks"]}
    for chunk in chunks:
        chunk["review_status"] = ledger_by_id[chunk["id"]]["status"]
    page_values = [
        page
        for chunk in chunks
        for page in (chunk["page_start"], chunk["page_end"])
        if isinstance(page, int)
    ]
    return {
        "intake_id": intake_id,
        "title": source_info["title"],
        "source": {
            "filename": source_info["source_filename"],
            "file_type": source_info["file_type"],
            "sha256": source_info["source_sha256"],
        },
        "extraction": {
            "word_count": source_info["word_count"],
            "chunk_count": source_info["chunk_count"],
            "page_start": min(page_values) if page_values else None,
            "page_end": max(page_values) if page_values else None,
            "warnings": load_extraction_warnings(
                document_root / contract.intake_artifacts.intake_report
            ),
        },
        "review": {"status": ledger["review_status"], "summary": ledger["summary"]},
        "structure": build_source_structure(chunks, source_info["file_type"]),
        "_chunks": chunks,
    }


def load_extraction_warnings(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ReviewProgressError(f"intake report not found: {path}")
    lines = path.read_text(encoding="utf-8").splitlines()
    try:
        start = lines.index("## Extraction Warnings") + 1
    except ValueError:
        return {"available": False, "items": []}
    items: list[str] = []
    for line in lines[start:]:
        if line.startswith("## "):
            break
        if line.startswith("- "):
            value = line[2:].strip()
            if value and value != "None recorded by the extractor.":
                items.append(value)
    return {"available": True, "items": items}


def load_manifest(path: Path, intake_id: str, contract: SchemaContract) -> dict[str, Any]:
    if not path.is_file():
        raise ReviewProgressError(f"chunk manifest not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ReviewProgressError("chunk manifest must be a JSON object")
    if payload.get("version") != contract.intake_chunks_manifest_version:
        raise ReviewProgressError("chunk manifest version does not match the schema contract")
    if payload.get("id") != intake_id:
        raise ReviewProgressError("chunk manifest ID does not match --intake-id")
    entries = payload.get("chunks")
    if not isinstance(entries, list) or not entries or any(not isinstance(entry, dict) for entry in entries):
        raise ReviewProgressError("chunk manifest must contain a non-empty chunks list")
    seen: set[str] = set()
    for sequence, entry in enumerate(entries, start=1):
        chunk_id = entry.get("id")
        if (
            not isinstance(chunk_id, str)
            or contract.type_id_patterns["intake-chunk"].fullmatch(chunk_id) is None
            or not chunk_id.startswith(f"{intake_id}-")
        ):
            raise ReviewProgressError(f"manifest chunk {sequence} has an invalid ID")
        if chunk_id in seen:
            raise ReviewProgressError(f"manifest contains duplicate chunk ID: {chunk_id}")
        seen.add(chunk_id)
        if entry.get("sequence") != sequence:
            raise ReviewProgressError(f"manifest chunk {chunk_id} has an invalid sequence")
        heading = entry.get("heading")
        if heading is not None and (not isinstance(heading, str) or not heading.strip()):
            raise ReviewProgressError(f"manifest chunk {chunk_id} has an invalid heading")
        for field in ("page_start", "page_end"):
            value = entry.get(field)
            if value is not None and (not isinstance(value, int) or isinstance(value, bool) or value < 1):
                raise ReviewProgressError(f"manifest chunk {chunk_id} has an invalid {field}")
        if (
            isinstance(entry.get("page_start"), int)
            and isinstance(entry.get("page_end"), int)
            and entry["page_start"] > entry["page_end"]
        ):
            raise ReviewProgressError(f"manifest chunk {chunk_id} has a reversed page range")
        for field in ("word_count", "char_count"):
            value = entry.get(field)
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                raise ReviewProgressError(f"manifest chunk {chunk_id} has an invalid {field}")
        hints = entry.get("hints")
        if not isinstance(hints, list) or any(not isinstance(value, str) for value in hints):
            raise ReviewProgressError(f"manifest chunk {chunk_id} has invalid hints")
        if not isinstance(entry.get("text_path"), str):
            raise ReviewProgressError(f"manifest chunk {chunk_id} has no valid text_path")
    return payload


def load_source_info(
    path: Path,
    intake_id: str,
    manifest: dict[str, Any],
    contract: SchemaContract,
) -> dict[str, Any]:
    if not path.is_file():
        raise ReviewProgressError(f"source info not found: {path}")
    payload = strict_yaml_load(path.read_text(encoding="utf-8"), "source info")
    if not isinstance(payload, dict):
        raise ReviewProgressError("source info must be a YAML mapping")
    if payload.get("version") != contract.intake_source_info_version:
        raise ReviewProgressError("source info version does not match the schema contract")
    if payload.get("id") != intake_id:
        raise ReviewProgressError("source info ID does not match --intake-id")
    chunks = manifest["chunks"]
    expected_words = sum(entry["word_count"] for entry in chunks)
    if payload.get("chunk_count") != len(chunks) or payload.get("word_count") != expected_words:
        raise ReviewProgressError("source info counts do not match the chunk manifest")
    for field in ("title", "source_filename", "source_sha256", "file_type"):
        if not isinstance(payload.get(field), str) or not payload[field].strip():
            raise ReviewProgressError(f"source info has an invalid {field}")
    if re.fullmatch(r"[0-9a-fA-F]{64}", payload["source_sha256"]) is None:
        raise ReviewProgressError("source info has an invalid source_sha256")
    manifest_source = manifest.get("source")
    if not isinstance(manifest_source, dict):
        raise ReviewProgressError("chunk manifest has invalid source provenance")
    expected_source = {
        "filename": payload["source_filename"],
        "sha256": payload["source_sha256"],
        "path": payload.get("source_path"),
    }
    if any(manifest_source.get(field) != value for field, value in expected_source.items()):
        raise ReviewProgressError("source info provenance does not match the chunk manifest")
    if manifest.get("title") != payload["title"]:
        raise ReviewProgressError("source info title does not match the chunk manifest")
    return payload


def load_chunk(
    document_root: Path,
    entry: dict[str, Any],
    intake_id: str,
    contract: SchemaContract,
) -> dict[str, Any]:
    chunk_id = entry["id"]
    pure_path = PurePosixPath(entry["text_path"])
    expected_parent = PurePosixPath(contract.intake_artifacts.chunk_directory)
    if pure_path.is_absolute() or ".." in pure_path.parts or pure_path.parent != expected_parent:
        raise ReviewProgressError(f"manifest chunk {chunk_id} has an unsafe text_path")
    chunk_path = document_root.joinpath(*pure_path.parts)
    try:
        resolved = chunk_path.resolve(strict=True)
    except FileNotFoundError as error:
        raise ReviewProgressError(f"chunk text file not found: {entry['text_path']}") from error
    document_resolved = document_root.resolve()
    if document_resolved != resolved and document_resolved not in resolved.parents:
        raise ReviewProgressError(f"manifest chunk {chunk_id} text_path escapes the intake directory")
    if chunk_path.is_symlink() or not resolved.is_file():
        raise ReviewProgressError(f"manifest chunk {chunk_id} text_path is not a regular file")
    metadata, text = parse_chunk_text(resolved.read_text(encoding="utf-8"), chunk_id)
    if metadata.get("id") != chunk_id or metadata.get("type") != "intake-chunk":
        raise ReviewProgressError(f"chunk file metadata does not match {chunk_id}")
    related = metadata.get("related")
    if not isinstance(related, list) or intake_id not in related:
        raise ReviewProgressError(f"chunk file {chunk_id} does not reference its parent intake")
    if len(re.findall(r"\S+", text)) != entry["word_count"] or len(text) != entry["char_count"]:
        raise ReviewProgressError(f"chunk file content does not match manifest counts: {chunk_id}")
    return {**entry, "text": text}


def parse_chunk_text(raw: str, chunk_id: str) -> tuple[dict[str, Any], str]:
    lines = raw.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        raise ReviewProgressError(f"chunk file {chunk_id} has no frontmatter")
    end_index = next((index for index, line in enumerate(lines[1:], start=1) if line.strip() == "---"), None)
    if end_index is None:
        raise ReviewProgressError(f"chunk file {chunk_id} has unclosed frontmatter")
    metadata = strict_yaml_load("".join(lines[1:end_index]), f"chunk {chunk_id} frontmatter")
    if not isinstance(metadata, dict):
        raise ReviewProgressError(f"chunk file {chunk_id} frontmatter must be a mapping")
    body = "".join(lines[end_index + 1 :])
    marker = "## Text\n\n"
    if marker not in body or f"# {chunk_id}\n" not in body.split(marker, 1)[0]:
        raise ReviewProgressError(f"chunk file {chunk_id} has an invalid generated wrapper")
    text = body.split(marker, 1)[1]
    if not text.endswith("\n"):
        raise ReviewProgressError(f"chunk file {chunk_id} text is not newline terminated")
    return metadata, text[:-1]


def validate_ledger_state(ledger: dict[str, Any], contract: SchemaContract) -> None:
    entries = ledger["chunks"]
    counts = {status: 0 for status in contract.review_progress.entry_statuses}
    for entry in entries:
        status = entry.get("status")
        if status not in counts:
            raise ReviewProgressError(f"review progress contains invalid status: {status!r}")
        counts[status] += 1
    expected_summary = {"total": len(entries), **counts}
    if ledger.get("summary") != expected_summary:
        raise ReviewProgressError("review progress summary does not match its chunk entries")
    expected_status = (
        "complete"
        if all(entry.get("status") in contract.review_progress.complete_entry_statuses for entry in entries)
        else "in-progress"
    )
    if ledger.get("review_status") != expected_status:
        raise ReviewProgressError("review progress status does not match its chunk entries")


def build_source_structure(chunks: list[dict[str, Any]], file_type: str) -> dict[str, Any]:
    sections: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    source_section_count = 0
    for chunk in chunks:
        if is_source_section_start(chunk, file_type):
            source_section_count += 1
            current = new_section(f"SEC-{source_section_count:03d}", "source-section", chunk["heading"])
            sections.append(current)
        elif current is None:
            current = new_section("SEC-000", "unsectioned", "Unsectioned content")
            sections.append(current)
        add_chunk_to_section(current, chunk)
    if source_section_count == 0:
        return {
            "kind": "page-only" if file_type == "pdf" else "unstructured",
            "reliable": False,
            "guidance": "use-all",
            "sections": [],
        }
    return {
        "kind": "source-sections-flat",
        "reliable": True,
        "guidance": "use-section-or-all",
        "sections": sections,
    }


def is_source_section_start(chunk: dict[str, Any], file_type: str) -> bool:
    heading = chunk.get("heading")
    if not isinstance(heading, str):
        return False
    first_line = next((line.strip() for line in chunk["text"].splitlines() if line.strip()), "")
    if file_type in {"md", "markdown", "txt"}:
        return first_line.startswith("#") and first_line.lstrip("#").strip() == heading.strip()
    if file_type == "docx":
        return first_line == heading.strip()
    return False


def new_section(section_id: str, kind: str, title: str) -> dict[str, Any]:
    return {
        "id": section_id,
        "kind": kind,
        "title": title,
        "chunk_start": None,
        "chunk_end": None,
        "chunk_count": 0,
        "word_count": 0,
        "page_start": None,
        "page_end": None,
        "_chunk_ids": [],
        "_sequence_start": None,
        "_sequence_end": None,
    }


def add_chunk_to_section(section: dict[str, Any], chunk: dict[str, Any]) -> None:
    section["_chunk_ids"].append(chunk["id"])
    section["_sequence_start"] = section["_sequence_start"] or chunk["sequence"]
    section["_sequence_end"] = chunk["sequence"]
    section["chunk_start"] = section["chunk_start"] or chunk["id"]
    section["chunk_end"] = chunk["id"]
    section["chunk_count"] += 1
    section["word_count"] += chunk["word_count"]
    if chunk["page_start"] is not None:
        section["page_start"] = (
            chunk["page_start"]
            if section["page_start"] is None
            else min(section["page_start"], chunk["page_start"])
        )
    if chunk["page_end"] is not None:
        section["page_end"] = (
            chunk["page_end"]
            if section["page_end"] is None
            else max(section["page_end"], chunk["page_end"])
        )


def print_inspection(snapshot: dict[str, Any], output_format: str) -> None:
    payload = {key: value for key, value in snapshot.items() if not key.startswith("_")}
    payload["structure"] = dict(payload["structure"])
    payload["structure"]["sections"] = [
        {key: value for key, value in section.items() if not key.startswith("_")}
        for section in snapshot["structure"]["sections"]
    ]
    if output_format == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(f"intake_id: {payload['intake_id']}")
    print(f"title: {payload['title']}")
    print(f"source: {payload['source']['filename']} ({payload['source']['file_type']})")
    print(f"extraction: {json.dumps(payload['extraction'], sort_keys=True)}")
    print(f"review: {json.dumps(payload['review'], sort_keys=True)}")
    print(
        "structure: "
        f"{payload['structure']['kind']} "
        f"(reliable={str(payload['structure']['reliable']).lower()}, "
        f"guidance={payload['structure']['guidance']})"
    )
    for section, source_section in zip(
        payload["structure"]["sections"],
        snapshot["structure"]["sections"],
    ):
        pages = page_label(section["page_start"], section["page_end"])
        print(
            f"- {section['id']} | {section['kind']} | {clean_marker_value(section['title'])} | "
            f"chunks {source_section['_sequence_start']}-{source_section['_sequence_end']} | "
            f"{section['word_count']} words | {pages}"
        )


def build_ledger_audit(
    intake_id: str,
    ledger: dict[str, Any],
    ledger_sha256: str,
) -> dict[str, Any]:
    return {
        "version": 1,
        "intake_id": intake_id,
        "audit_status": "review-complete" if ledger.get("review_status") == "complete" else "review-incomplete",
        "ledger_snapshot": {
            "sha256": ledger_sha256,
            "updated": str(ledger.get("updated", "")),
            "review_status": ledger.get("review_status"),
            "summary": ledger.get("summary"),
        },
    }


def build_skip_audit(snapshot: dict[str, Any], ledger: dict[str, Any]) -> dict[str, Any]:
    ledger_by_id = {entry["id"]: entry for entry in ledger["chunks"]}
    skipped_chunks: list[dict[str, Any]] = []
    for chunk in snapshot["_chunks"]:
        entry = ledger_by_id[chunk["id"]]
        if entry.get("status") != "skipped":
            continue
        text = chunk["text"]
        notes = entry.get("notes") if isinstance(entry.get("notes"), str) else ""
        normative_terms = sorted({match.group(0).casefold() for match in AUDIT_NORMATIVE_TERM_PATTERN.finditer(text)})
        signals: list[str] = []
        if normative_terms:
            signals.append("normative-language")
        if AUDIT_DEFERRED_NOTE_PATTERN.search(notes):
            signals.append("deferred-or-unmodeled-note")
        skipped_chunks.append({
            "id": chunk["id"],
            "sequence": chunk["sequence"],
            "page_start": chunk["page_start"],
            "page_end": chunk["page_end"],
            "heading": chunk["heading"],
            "word_count": chunk["word_count"],
            "notes": notes,
            "signals": signals,
            "normative_terms": normative_terms,
        })
    return {
        "version": 1,
        "intake_id": snapshot["intake_id"],
        "skip_count": len(skipped_chunks),
        "skipped_chunks": skipped_chunks,
        "contiguous_skip_runs": contiguous_skip_runs(snapshot["_chunks"], ledger_by_id),
    }


def contiguous_skip_runs(
    chunks: list[dict[str, Any]],
    ledger_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    runs: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    for chunk in chunks:
        if ledger_by_id[chunk["id"]].get("status") == "skipped":
            current.append(chunk)
            continue
        if len(current) > 1:
            runs.append(current)
        current = []
    if len(current) > 1:
        runs.append(current)
    return [
        {
            "start_id": run[0]["id"],
            "end_id": run[-1]["id"],
            "count": len(run),
            "word_count": sum(chunk["word_count"] for chunk in run),
        }
        for run in runs
    ]


def print_audit(payload: dict[str, Any], output_format: str) -> None:
    if output_format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return
    print(f"audit_status: {payload['audit_status']}")
    print(f"intake_id: {payload['intake_id']}")
    print(f"ledger_sha256: {payload['ledger_snapshot']['sha256']}")
    print(f"ledger_updated: {payload['ledger_snapshot']['updated']}")
    print(f"ledger_review_status: {payload['ledger_snapshot']['review_status']}")
    print(f"ledger_summary: {json.dumps(payload['ledger_snapshot']['summary'], sort_keys=True)}")


def print_skip_audit(payload: dict[str, Any], output_format: str) -> None:
    if output_format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return
    print(f"intake_id: {payload['intake_id']}")
    print(f"skip_count: {payload['skip_count']}")
    for chunk in payload["skipped_chunks"]:
        signals = ",".join(chunk["signals"]) or "none"
        print(
            f"- {chunk['id']} | {page_label(chunk['page_start'], chunk['page_end'])} | "
            f"{chunk['word_count']} words | signals={signals}"
        )


def print_view(
    snapshot: dict[str, Any],
    view_all: bool,
    section_id: str | None,
    requested_chunk_ids: list[str] | None,
    output_format: str,
) -> None:
    chunks = snapshot["_chunks"]
    scope: dict[str, Any] = {"kind": "all"}
    if requested_chunk_ids is not None:
        available_ids = {chunk["id"] for chunk in chunks}
        normalized_ids: list[str] = []
        for requested_id in requested_chunk_ids:
            chunk_id = (
                f"{snapshot['intake_id']}-{requested_id}"
                if re.fullmatch(r"CH-\d{3}", requested_id, re.IGNORECASE)
                else requested_id
            )
            if chunk_id not in available_ids:
                raise ReviewProgressError(f"unknown chunk ID for this intake: {requested_id}")
            if chunk_id in normalized_ids:
                raise ReviewProgressError(f"duplicate chunk ID: {requested_id}")
            normalized_ids.append(chunk_id)
        selected_ids = set(normalized_ids)
        chunks = [chunk for chunk in chunks if chunk["id"] in selected_ids]
        scope = {"kind": "chunks", "ids": [chunk["id"] for chunk in chunks]}
    elif not view_all:
        structure = snapshot["structure"]
        if not structure["reliable"]:
            raise ReviewProgressError("section view is unavailable for this document; use --all")
        section = next(
            (candidate for candidate in structure["sections"] if candidate["id"] == section_id),
            None,
        )
        if section is None:
            raise ReviewProgressError(f"unknown section ID: {section_id}")
        selected_ids = set(section["_chunk_ids"])
        chunks = [chunk for chunk in chunks if chunk["id"] in selected_ids]
        scope = {
            "kind": "section",
            "id": section["id"],
            "section_kind": section["kind"],
            "title": section["title"],
        }
    payload = {
        "intake_id": snapshot["intake_id"],
        "title": snapshot["title"],
        "scope": scope,
        "chunks": [
            {
                "id": chunk["id"],
                "page_start": chunk["page_start"],
                "page_end": chunk["page_end"],
                "heading": chunk["heading"],
                "review_status": chunk["review_status"],
                "text": chunk["text"],
            }
            for chunk in chunks
        ],
    }
    if output_format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    print(f"Document: {snapshot['intake_id']} | {clean_marker_value(snapshot['title'])}")
    if scope["kind"] == "section":
        print(f"Scope: {scope['id']} | {scope['section_kind']} | {clean_marker_value(scope['title'])}")
    elif scope["kind"] == "chunks":
        print(f"Scope: chunks | {', '.join(scope['ids'])}")
    else:
        print("Scope: all")
    for chunk in chunks:
        print()
        print(
            f"--- {chunk['id']} | {page_label(chunk['page_start'], chunk['page_end'])} | "
            f"{clean_marker_value(chunk['heading'] or 'No source heading')} | {chunk['review_status']} ---"
        )
        print()
        print(chunk["text"])


def page_label(page_start: int | None, page_end: int | None) -> str:
    if page_start is None or page_end is None:
        return "pages n/a"
    if page_start == page_end:
        return f"page {page_start}"
    return f"pages {page_start}-{page_end}"


def clean_marker_value(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().replace("|", "/")


def validate_ledger_identity(
    ledger: dict[str, Any],
    intake_id: str,
    manifest_ids: list[str],
    contract: SchemaContract,
) -> None:
    if ledger.get("version") != contract.intake_review_progress_version:
        raise ReviewProgressError("review progress version does not match the schema contract")
    if ledger.get("intake_id") != intake_id:
        raise ReviewProgressError("review progress intake_id does not match --intake-id")
    entries = ledger.get("chunks")
    if not isinstance(entries, list) or any(not isinstance(entry, dict) for entry in entries):
        raise ReviewProgressError("review progress chunks must be a list of mappings")
    ledger_ids = [entry.get("id") for entry in entries]
    if ledger_ids != manifest_ids:
        raise ReviewProgressError("review progress must cover manifest chunks exactly and in order")


def load_updates(source: str) -> list[dict[str, Any]]:
    text = sys.stdin.read() if source == "-" else Path(source).read_text(encoding="utf-8")
    payload = json.loads(text)
    updates = payload.get("updates") if isinstance(payload, dict) else payload
    if not isinstance(updates, list) or not updates or any(not isinstance(update, dict) for update in updates):
        raise ReviewProgressError("updates must be a non-empty JSON list of objects")
    return updates


def apply_updates(
    ledger: dict[str, Any],
    updates: list[dict[str, Any]],
    manifest_ids: list[str],
    contract: SchemaContract,
) -> None:
    entries = ledger["chunks"]
    entries_by_id = {entry["id"]: entry for entry in entries}
    seen: set[str] = set()
    for update in updates:
        unknown_fields = set(update) - {"id", "status", "classifications", "target_ids", "notes"}
        if unknown_fields:
            raise ReviewProgressError(f"update contains unknown fields: {sorted(unknown_fields)}")
        chunk_id = update.get("id")
        if not isinstance(chunk_id, str) or chunk_id not in entries_by_id:
            raise ReviewProgressError(f"update references unknown chunk ID: {chunk_id!r}")
        if chunk_id in seen:
            raise ReviewProgressError(f"updates contain duplicate chunk ID: {chunk_id}")
        seen.add(chunk_id)
        status = update.get("status")
        if status not in contract.review_progress.entry_statuses:
            raise ReviewProgressError(f"update for {chunk_id} has invalid status: {status!r}")
        classifications = update.get("classifications", [])
        target_ids = update.get("target_ids", [])
        notes = update.get("notes")
        if (
            not isinstance(classifications, list)
            or any(not isinstance(value, str) or value not in contract.review_progress.classifications for value in classifications)
            or len(classifications) != len(set(classifications))
        ):
            raise ReviewProgressError(f"update for {chunk_id} has invalid classifications")
        if (
            not isinstance(target_ids, list)
            or any(not isinstance(value, str) or contract.generic_id_pattern.fullmatch(value) is None for value in target_ids)
            or len(target_ids) != len(set(target_ids))
        ):
            raise ReviewProgressError(f"update for {chunk_id} has invalid target_ids")
        if notes is not None and (not isinstance(notes, str) or not notes.strip()):
            raise ReviewProgressError(f"update for {chunk_id} has invalid notes")
        if status == "classified" and not classifications:
            raise ReviewProgressError(f"classified update for {chunk_id} requires classifications")
        if status == "skipped":
            if classifications or target_ids:
                raise ReviewProgressError(f"skipped update for {chunk_id} cannot contain classifications or target_ids")
            if not isinstance(notes, str) or not notes.strip():
                raise ReviewProgressError(f"skipped update for {chunk_id} requires notes")
        entries_by_id[chunk_id].update(
            status=status,
            classifications=classifications,
            target_ids=target_ids,
            notes=notes,
        )

    status_counts = {status: 0 for status in contract.review_progress.entry_statuses}
    for entry in entries:
        status = entry.get("status")
        if status not in status_counts:
            raise ReviewProgressError(f"existing ledger entry has invalid status: {status!r}")
        status_counts[status] += 1
    ledger["updated"] = date.today().isoformat()
    ledger["summary"] = {"total": len(manifest_ids), **status_counts}
    ledger["review_status"] = (
        "complete"
        if all(entry.get("status") in contract.review_progress.complete_entry_statuses for entry in entries)
        else "in-progress"
    )


def print_status(ledger: dict[str, Any], limit: int, output_format: str) -> None:
    entries = ledger["chunks"]
    classification_counts: dict[str, int] = {}
    target_ids: set[str] = set()
    for entry in entries:
        for classification in entry.get("classifications", []):
            if isinstance(classification, str):
                classification_counts[classification] = classification_counts.get(classification, 0) + 1
        for target_id in entry.get("target_ids", []):
            if isinstance(target_id, str):
                target_ids.add(target_id)
    next_entries = [
        {"id": entry["id"], "status": entry["status"]}
        for entry in entries
        if entry.get("status") in {"pending", "reviewed"}
    ][:limit]
    payload = {
        "intake_id": ledger["intake_id"],
        "review_status": ledger["review_status"],
        "summary": ledger["summary"],
        "classification_counts": dict(sorted(classification_counts.items())),
        "registered_target_count": len(target_ids),
        "next": next_entries,
    }
    if output_format == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(f"intake_id: {payload['intake_id']}")
    print(f"review_status: {payload['review_status']}")
    print(f"summary: {json.dumps(payload['summary'], sort_keys=True)}")
    print(f"classification_counts: {json.dumps(payload['classification_counts'], sort_keys=True)}")
    print(f"registered_target_count: {payload['registered_target_count']}")
    print("next:")
    for entry in next_entries:
        print(f"- {entry['id']} ({entry['status']})")


def write_ledger_atomic(path: Path, ledger: dict[str, Any]) -> None:
    entries = ledger["chunks"]
    summary = ledger["summary"]
    lines = [
        f"version: {ledger['version']}",
        f"intake_id: {ledger['intake_id']}",
        f"updated: {ledger['updated']}",
        f"review_status: {ledger['review_status']}",
        "summary:",
        f"  total: {summary['total']}",
        f"  pending: {summary['pending']}",
        f"  reviewed: {summary['reviewed']}",
        f"  classified: {summary['classified']}",
        f"  skipped: {summary['skipped']}",
        "chunks:",
    ]
    for entry in entries:
        lines.extend(
            [
                f"  - id: {entry['id']}",
                f"    status: {entry['status']}",
                f"    classifications: {json.dumps(entry['classifications'], ensure_ascii=False)}",
                f"    target_ids: {json.dumps(entry['target_ids'], ensure_ascii=False)}",
                f"    notes: {'null' if entry['notes'] is None else json.dumps(entry['notes'], ensure_ascii=False)}",
            ]
        )
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            temporary.write("\n".join(lines) + "\n")
            temporary.flush()
            os.fsync(temporary.fileno())
        temporary_path.replace(path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


if __name__ == "__main__":
    raise SystemExit(main())