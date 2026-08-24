#!/usr/bin/env python3
"""Inspect and update project-wiki document review progress ledgers."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from datetime import date
from pathlib import Path
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect or update an intake review progress ledger.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("status", "apply"):
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
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        contract = load_schema_contract()
        document_root = intake_document_root(Path(args.wiki_root), args.intake_id, contract)
        ledger_path = document_root / contract.intake_artifacts.review_progress
        manifest_path = document_root / contract.intake_artifacts.chunks_manifest
        ledger = load_ledger(ledger_path)
        manifest_ids = load_manifest_ids(manifest_path)
        validate_ledger_identity(ledger, args.intake_id, manifest_ids, contract)
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


def load_ledger(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ReviewProgressError(f"review progress ledger not found: {path}")
    payload = strict_yaml_load(path.read_text(encoding="utf-8"), "review progress ledger")
    if not isinstance(payload, dict):
        raise ReviewProgressError("review progress ledger must be a YAML mapping")
    return payload


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