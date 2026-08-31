#!/usr/bin/env python3
"""Extract PDF/DOCX/text documents into project-wiki intake artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

try:
    from .schema_contract import SchemaContract, SchemaContractError, load_schema_contract
except ImportError:
    from schema_contract import SchemaContract, SchemaContractError, load_schema_contract  # type: ignore[no-redef]


SUPPORTED_SUFFIXES = {".pdf", ".docx", ".txt", ".md", ".markdown"}

HINT_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("requirement-language", re.compile(r"\b(shall|must|required|requirement|deve|dovra|obbligatorio|requisito)\b", re.I)),
    ("recommendation-language", re.compile(r"\b(should|recommended|prefer|dovrebbe|consigliato)\b", re.I)),
    ("actor-mentioned", re.compile(r"\b(user|admin|administrator|operator|customer|client|utente|amministratore|operatore|cliente)\b", re.I)),
    ("priority-or-deadline", re.compile(r"\b(priority|deadline|milestone|urgent|high priority|priorita|scadenza|urgente)\b", re.I)),
    ("security-or-compliance", re.compile(r"\b(security|privacy|gdpr|compliance|permission|auth|authorization|sicurezza|permesso|autorizzazione)\b", re.I)),
    ("data-or-integration", re.compile(r"\b(database|data model|api|integration|webhook|export|import|csv|dati|integrazione)\b", re.I)),
    ("risk-or-constraint", re.compile(r"\b(risk|constraint|limitation|out of scope|blocked|rischio|vincolo|fuori ambito|bloccato)\b", re.I)),
]


@dataclass(frozen=True)
class TextBlock:
    text: str
    heading: str | None = None
    page: int | None = None
    starts_section: bool = False


@dataclass(frozen=True)
class Chunk:
    id: str
    text_path: str
    sequence: int
    heading: str | None
    page_start: int | None
    page_end: int | None
    word_count: int
    char_count: int
    hints: list[str]
    text: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract a PDF, DOCX, TXT, or Markdown document into .project-wiki intake artifacts."
    )
    parser.add_argument("source", help="Path to the source document.")
    parser.add_argument(
        "--wiki-root",
        default=".project-wiki",
        help="Target project wiki root. Defaults to .project-wiki in the current directory.",
    )
    parser.add_argument(
        "--doc-id",
        help="Stable intake document ID. Defaults to the next DOCIN-YYYYMMDD-NNN ID.",
    )
    parser.add_argument(
        "--title",
        help="Document title to use in reports. Defaults to the source filename stem.",
    )
    parser.add_argument(
        "--max-words",
        type=int,
        default=350,
        help="Maximum words per chunk. Defaults to 350.",
    )
    parser.add_argument(
        "--copy-source",
        action="store_true",
        help="Copy the source file into the intake document directory as source.<ext>.",
    )
    parser.add_argument(
        "--expected-sha256",
        help="Require the source to match the SHA-256 authorized by the inbox preflight.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        contract = load_schema_contract()
    except SchemaContractError as error:
        print(f"error: invalid schema contract: {error}", file=sys.stderr)
        return 2
    artifacts = contract.intake_artifacts
    source = Path(args.source).expanduser().resolve()
    if not source.exists() or not source.is_file():
        print(f"error: source file not found: {source}", file=sys.stderr)
        return 2

    suffix = source.suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        supported = ", ".join(sorted(SUPPORTED_SUFFIXES))
        print(f"error: unsupported file type '{suffix}'. Supported types: {supported}", file=sys.stderr)
        return 2

    if args.max_words < 80:
        print("error: --max-words must be at least 80", file=sys.stderr)
        return 2

    expected_source_hash = args.expected_sha256.lower() if args.expected_sha256 else None
    if expected_source_hash is not None and not re.fullmatch(r"[0-9a-f]{64}", expected_source_hash):
        print("error: --expected-sha256 must be a 64-character hexadecimal SHA-256", file=sys.stderr)
        return 2

    wiki_root = Path(args.wiki_root).expanduser().resolve()
    documents_root = wiki_root / contract.semantic_paths.intake_documents_directory

    doc_id = args.doc_id or next_doc_id(documents_root, contract)
    if contract.type_id_patterns["intake-document"].fullmatch(doc_id) is None:
        print("error: --doc-id must match DOCIN-YYYYMMDD-NNN", file=sys.stderr)
        return 2

    title = args.title or source.stem.replace("_", " ").replace("-", " ").strip().title()
    created = datetime.now(timezone.utc).astimezone().date().isoformat()
    doc_dir = documents_root / doc_id
    if doc_dir.exists():
        print(f"error: intake document already exists: {doc_id}", file=sys.stderr)
        return 2

    snapshot_root: Path | None = None
    try:
        snapshot_root = Path(tempfile.mkdtemp(prefix="project-wiki-source-"))
        snapshot_path = snapshot_root / f"source{suffix}"
        source_hash = snapshot_source(source, snapshot_path)
    except OSError as error:
        if snapshot_root is not None and snapshot_root.exists():
            shutil.rmtree(snapshot_root)
        print(f"error: failed to snapshot source document: {error}", file=sys.stderr)
        return 5

    try:
        if expected_source_hash is not None and source_hash != expected_source_hash:
            print("error: source SHA-256 does not match the inbox preflight; run check_inbox.py again", file=sys.stderr)
            return 6

        try:
            blocks = extract_blocks(snapshot_path)
        except MissingDependencyError as error:
            print(f"error: {error}", file=sys.stderr)
            return 3

        if not blocks or not any(block.text.strip() for block in blocks):
            print("error: no extractable text found. Scanned PDFs may require OCR, which is not supported in V1.", file=sys.stderr)
            return 4

        if sha256_file(snapshot_path) != source_hash:
            print("error: source snapshot changed during extraction", file=sys.stderr)
            return 6

        chunks = build_chunks(doc_id, blocks, args.max_words, contract)
        try:
            documents_root.mkdir(parents=True, exist_ok=True)
            staging_dir = Path(tempfile.mkdtemp(prefix=f".{doc_id}-", dir=documents_root))
        except OSError as error:
            print(f"error: failed to create intake staging area for {doc_id}: {error}", file=sys.stderr)
            return 5

        published = False
        completed = False
        try:
            staged_source_path = (
                copy_source(snapshot_path, staging_dir, artifacts.copied_source_stem)
                if args.copy_source
                else None
            )
            copied_source_path = Path(staged_source_path.name) if staged_source_path else None

            write_source_info(
                path=staging_dir / artifacts.source_info,
                doc_id=doc_id,
                title=title,
                source=source,
                source_hash=source_hash,
                copied_source_path=copied_source_path,
                created=created,
                file_type=suffix.lstrip("."),
                word_count=sum(chunk.word_count for chunk in chunks),
                chunk_count=len(chunks),
                status=required_generated_status(contract, "intake-document"),
                artifact_version=contract.intake_source_info_version,
                confidence=contract.generated_values["intake_confidence"],
            )
            write_chunk_files(
                staging_dir / artifacts.chunk_directory,
                doc_id,
                title,
                source,
                created,
                chunks,
                status=required_generated_status(contract, "intake-chunk"),
                confidence=contract.generated_values["intake_confidence"],
            )
            write_extracted_markdown(
                staging_dir / artifacts.extraction_index,
                doc_id,
                title,
                source,
                created,
                blocks,
                chunks,
                status=required_generated_status(contract, "intake-extraction-index"),
                artifacts=artifacts,
                confidence=contract.generated_values["intake_confidence"],
            )
            write_chunks_json(
                staging_dir / artifacts.chunks_manifest,
                doc_id,
                title,
                source,
                source_hash,
                created,
                args.max_words,
                chunks,
                artifact_version=contract.intake_chunks_manifest_version,
                artifacts=artifacts,
            )
            write_review_progress(
                staging_dir / artifacts.review_progress,
                doc_id,
                created,
                chunks,
                artifact_version=contract.intake_review_progress_version,
            )
            write_intake_report(
                staging_dir / artifacts.intake_report,
                doc_id,
                title,
                source,
                created,
                chunks,
                status=required_generated_status(contract, "intake-document"),
                artifacts=artifacts,
                confidence=contract.generated_values["intake_confidence"],
            )
            validate_intake_artifacts(
                staging_dir,
                doc_id,
                chunks,
                staged_source_path,
                artifacts,
            )

            if not file_matches_sha256(source, source_hash):
                print("error: source changed after the inbox preflight; run check_inbox.py again", file=sys.stderr)
                return 6
            if doc_dir.exists():
                raise FileExistsError(doc_dir)
            staging_dir.rename(doc_dir)
            published = True
            ensure_intake_index(
                wiki_root / contract.semantic_paths.intake_index_file,
                doc_id,
                title,
                source,
                status=required_generated_status(contract, "intake-document"),
                report_path=doc_dir / artifacts.intake_report,
            )
            completed = True
        except FileExistsError:
            print(f"error: intake document already exists: {doc_id}", file=sys.stderr)
            return 2
        except (OSError, ValueError) as error:
            print(f"error: failed to create intake document {doc_id}: {error}", file=sys.stderr)
            return 5
        finally:
            if staging_dir.exists():
                shutil.rmtree(staging_dir)
            if published and not completed and doc_dir.exists():
                shutil.rmtree(doc_dir)
    finally:
        shutil.rmtree(snapshot_root)

    print(f"created intake document: {doc_id}")
    print(f"output: {doc_dir}")
    print(
        "artifacts: "
        f"{artifacts.source_info}, {artifacts.extraction_index}, "
        f"{artifacts.chunks_manifest}, {artifacts.chunk_directory}/, "
        f"{artifacts.intake_report}, {artifacts.review_progress}"
    )
    return 0


class MissingDependencyError(RuntimeError):
    pass


def extract_blocks(source: Path) -> list[TextBlock]:
    suffix = source.suffix.lower()
    if suffix == ".pdf":
        return extract_pdf(source)
    if suffix == ".docx":
        return extract_docx(source)
    return extract_text(source)


def extract_pdf(source: Path) -> list[TextBlock]:
    try:
        import fitz  # type: ignore[import-not-found]
    except ImportError as exc:
        raise MissingDependencyError("PDF extraction requires PyMuPDF. Install with: pip install -r scripts/requirements.txt") from exc

    blocks: list[TextBlock] = []
    with fitz.open(source) as document:
        for page_index, page in enumerate(document, start=1):
            text = normalize_text(page.get_text("text"))
            if text:
                blocks.append(TextBlock(text=text, heading=f"Page {page_index}", page=page_index))
    return blocks


def extract_docx(source: Path) -> list[TextBlock]:
    try:
        import docx  # type: ignore[import-not-found]
    except ImportError as exc:
        raise MissingDependencyError("DOCX extraction requires python-docx. Install with: pip install -r scripts/requirements.txt") from exc

    document = docx.Document(source)
    blocks: list[TextBlock] = []
    current_heading: str | None = None
    table_index = 0

    for item in document.iter_inner_content():
        if hasattr(item, "rows"):
            table_index += 1
            rows: list[str] = []
            for row in item.rows:
                cells = [normalize_text(cell.text) for cell in row.cells]
                if any(cells):
                    rows.append(" | ".join(cells))
            if rows:
                blocks.append(
                    TextBlock(
                        text="\n".join(rows),
                        heading=current_heading or f"Table {table_index}",
                        starts_section=True,
                    )
                )
            continue

        text = normalize_text(item.text)
        if not text:
            continue
        style_name = getattr(item.style, "name", "") or ""
        if style_name.lower().startswith("heading"):
            current_heading = text
            blocks.append(TextBlock(text=text, heading=current_heading, starts_section=True))
        else:
            blocks.append(TextBlock(text=text, heading=current_heading))

    return blocks


def extract_text(source: Path) -> list[TextBlock]:
    text = normalize_text(source.read_text(encoding="utf-8", errors="replace"))
    blocks: list[TextBlock] = []
    current_heading: str | None = None
    for raw_block in re.split(r"\n\s*\n", text):
        block = raw_block.strip()
        if not block:
            continue
        first_line = block.splitlines()[0].strip()
        starts_section = first_line.startswith("#")
        if starts_section:
            current_heading = first_line.lstrip("#").strip() or current_heading
        blocks.append(TextBlock(text=block, heading=current_heading, starts_section=starts_section))
    return blocks


def build_chunks(
    doc_id: str,
    blocks: Iterable[TextBlock],
    max_words: int,
    contract: SchemaContract | None = None,
) -> list[Chunk]:
    contract = contract or load_schema_contract()
    chunks: list[Chunk] = []
    current_parts: list[str] = []
    current_word_count = 0
    current_pages: list[int] = []
    current_heading: str | None = None

    def emit() -> None:
        nonlocal current_parts, current_word_count, current_pages, current_heading
        if not current_parts:
            return
        text = "\n\n".join(current_parts).strip()
        sequence = len(chunks) + 1
        page_start = min(current_pages) if current_pages else None
        page_end = max(current_pages) if current_pages else None
        chunks.append(
            Chunk(
                id=(
                    f"{doc_id}-{contract.id_generation.intake_chunk_label}-"
                    f"{sequence:0{contract.id_generation.intake_chunk_sequence_width}d}"
                ),
                text_path=(
                    f"{contract.intake_artifacts.chunk_directory}/"
                    f"{contract.id_generation.intake_chunk_label}-"
                    f"{sequence:0{contract.id_generation.intake_chunk_sequence_width}d}.md"
                ),
                sequence=sequence,
                heading=current_heading,
                page_start=page_start,
                page_end=page_end,
                word_count=current_word_count,
                char_count=len(text),
                hints=detect_hints(text),
                text=text,
            )
        )
        current_parts = []
        current_word_count = 0
        current_pages = []
        current_heading = None

    for block in blocks:
        word_spans = list(re.finditer(r"\S+", block.text))
        if not word_spans:
            continue
        if block.starts_section and current_parts:
            emit()
        position = 0
        while position < len(word_spans):
            remaining = max_words - current_word_count
            if remaining <= 0:
                emit()
                remaining = max_words
            end_position = min(position + remaining, len(word_spans))
            segment = block.text[
                word_spans[position].start() : word_spans[end_position - 1].end()
            ]
            if current_heading is None:
                current_heading = block.heading
            current_parts.append(segment)
            current_word_count += end_position - position
            if block.page is not None:
                current_pages.append(block.page)
            position = end_position
            if current_word_count >= max_words:
                emit()

    emit()
    return chunks


def detect_hints(text: str) -> list[str]:
    return [label for label, pattern in HINT_PATTERNS if pattern.search(text)]


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def next_doc_id(documents_root: Path, contract: SchemaContract | None = None) -> str:
    contract = contract or load_schema_contract()
    generation = contract.id_generation
    today = datetime.now().strftime(generation.intake_date_format)
    prefix = generation.intake_document_prefix
    width = generation.intake_sequence_width
    pattern = re.compile(rf"{re.escape(prefix)}-{today}-(\d{{{width}}})$")
    used = []
    for path in documents_root.glob(f"{prefix}-{today}-*"):
        match = pattern.fullmatch(path.name)
        if match:
            used.append(int(match.group(1)))
    next_number = max(used, default=0) + 1
    return f"{prefix}-{today}-{next_number:0{width}d}"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file_obj:
        for chunk in iter(lambda: file_obj.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def snapshot_source(source: Path, target: Path) -> str:
    digest = hashlib.sha256()
    with source.open("rb") as source_file, target.open("xb") as snapshot_file:
        for chunk in iter(lambda: source_file.read(1024 * 1024), b""):
            digest.update(chunk)
            snapshot_file.write(chunk)
        snapshot_file.flush()
        os.fsync(snapshot_file.fileno())
    return digest.hexdigest()


def file_matches_sha256(path: Path, expected_hash: str) -> bool:
    try:
        return sha256_file(path) == expected_hash
    except OSError:
        return False


def required_generated_status(contract: SchemaContract, document_type: str) -> str:
    status = contract.generated_status_for_type(document_type)
    if status is None:
        raise SchemaContractError(f"schema contract has no generated status for {document_type}")
    return status


def copy_source(source: Path, doc_dir: Path, copied_source_stem: str = "source") -> Path:
    target = doc_dir / f"{copied_source_stem}{source.suffix.lower()}"
    shutil.copy2(source, target)
    return target


def validate_intake_artifacts(
    doc_dir: Path,
    doc_id: str,
    chunks: list[Chunk],
    copied_source_path: Path | None,
    artifacts: Any,
) -> None:
    required_files = [
        doc_dir / artifacts.source_info,
        doc_dir / artifacts.extraction_index,
        doc_dir / artifacts.chunks_manifest,
        doc_dir / artifacts.intake_report,
        doc_dir / artifacts.review_progress,
    ]
    required_files.extend(doc_dir / chunk_text_path(chunk) for chunk in chunks)
    if copied_source_path is not None:
        required_files.append(copied_source_path)

    missing = [path.relative_to(doc_dir).as_posix() for path in required_files if not path.is_file()]
    if missing:
        raise ValueError(f"staged intake is missing required artifacts: {', '.join(missing)}")

    empty = [path.relative_to(doc_dir).as_posix() for path in required_files if path.stat().st_size == 0]
    if empty:
        raise ValueError(f"staged intake contains empty artifacts: {', '.join(empty)}")

    try:
        manifest = json.loads((doc_dir / artifacts.chunks_manifest).read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid {artifacts.chunks_manifest}: {error}") from error

    entries = manifest.get("chunks")
    if manifest.get("id") != doc_id or not isinstance(entries, list) or len(entries) != len(chunks):
        raise ValueError(f"{artifacts.chunks_manifest} does not match the staged intake")

    expected_chunks = [(chunk.id, chunk_text_path(chunk)) for chunk in chunks]
    actual_chunks = [(entry.get("id"), entry.get("text_path")) for entry in entries if isinstance(entry, dict)]
    if actual_chunks != expected_chunks:
        raise ValueError(f"{artifacts.chunks_manifest} contains inconsistent chunk references")

    progress_text = (doc_dir / artifacts.review_progress).read_text(encoding="utf-8")
    if f"intake_id: {doc_id}\n" not in progress_text:
        raise ValueError(f"{artifacts.review_progress} does not match the staged intake")
    for chunk_id, _ in expected_chunks:
        if progress_text.count(f"  - id: {chunk_id}\n") != 1:
            raise ValueError(f"{artifacts.review_progress} contains inconsistent chunk references")


def yaml_scalar(value: object) -> str:
    if value is None:
        return "null"
    text = str(value)
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def write_source_info(
    path: Path,
    doc_id: str,
    title: str,
    source: Path,
    source_hash: str,
    copied_source_path: Path | None,
    created: str,
    file_type: str,
    word_count: int,
    chunk_count: int,
    status: str,
    artifact_version: int,
    confidence: str,
) -> None:
    lines = [
        f"version: {artifact_version}",
        f"id: {yaml_scalar(doc_id)}",
        "type: intake-document",
        f"status: {status}",
        f"title: {yaml_scalar(title)}",
        f"created: {yaml_scalar(created)}",
        f"updated: {yaml_scalar(created)}",
        f"source_path: {yaml_scalar(source.as_posix())}",
        f"source_filename: {yaml_scalar(source.name)}",
        f"source_sha256: {yaml_scalar(source_hash)}",
        "immutable_source: true",
        f"file_type: {yaml_scalar(file_type)}",
        f"copied_source_path: {yaml_scalar(copied_source_path.as_posix() if copied_source_path else None)}",
        f"word_count: {word_count}",
        f"chunk_count: {chunk_count}",
        f"confidence: {confidence}",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_extracted_markdown(
    path: Path,
    doc_id: str,
    title: str,
    source: Path,
    created: str,
    blocks: list[TextBlock],
    chunks: list[Chunk],
    status: str,
    artifacts: Any,
    confidence: str,
) -> None:
    lines = [
        "---",
        f"id: {doc_id}-EXTRACTED",
        "type: intake-extraction-index",
        f"status: {status}",
        f"title: {yaml_scalar(f'Extraction Index - {title}')}",
        f"created: {yaml_scalar(created)}",
        f"updated: {yaml_scalar(created)}",
        "tags: [intake, extracted-text, extraction-index]",
        f"related: [{yaml_scalar(doc_id)}]",
        f"source_paths: [{yaml_scalar(source.as_posix())}]",
        f"confidence: {confidence}",
        "---",
        "",
        f"# Extraction Index - {title}",
        "",
        f"Source: `{source.as_posix()}`",
        "",
        (
            "Generated headings and metadata are in English. Full extracted text is stored progressively in "
            f"`{artifacts.chunk_directory}/{Path(chunks[0].text_path).name if chunks else '*.md'}`-style files "
            "to avoid token-heavy indexes."
        ),
        "",
        "## Progressive Text Access",
        "",
        f"- Read [{artifacts.intake_report}](./{artifacts.intake_report}) first.",
        f"- Use `review_progress.py inspect --intake-id {doc_id}` for the compact outline and review state.",
        f"- Use `review_progress.py view --intake-id {doc_id} --all` when structure is unclear or full context matters.",
        "- Use `view --section SEC-NNN` only for source-defined sections reported as reliable by `inspect`.",
        f"- Track every disposition through `review_progress.py apply`; the ledger remains [{artifacts.review_progress}](./{artifacts.review_progress}).",
        "",
        "## Extraction Summary",
        "",
        f"- Extracted block count: {len(blocks)}",
        f"- Chunk count: {len(chunks)}",
        f"- Total extracted words: {sum(chunk.word_count for chunk in chunks)}",
        "- Full text embedded in this file: no",
    ]
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def chunk_text_path(chunk: Chunk) -> str:
    return chunk.text_path


def chunk_preview(text: str, max_chars: int = 280) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if len(compact) <= max_chars:
        return compact
    return compact[: max_chars - 1].rstrip() + "..."


def write_chunk_files(
    path: Path,
    doc_id: str,
    title: str,
    source: Path,
    created: str,
    chunks: list[Chunk],
    status: str,
    confidence: str,
) -> None:
    path.mkdir(parents=True, exist_ok=True)
    for chunk in chunks:
        chunk_path = path / Path(chunk.text_path).name
        page_range = "null"
        if chunk.page_start is not None and chunk.page_end is not None:
            page_range = f"{chunk.page_start}-{chunk.page_end}"
        lines = [
            "---",
            f"id: {yaml_scalar(chunk.id)}",
            "type: intake-chunk",
            f"status: {status}",
            f"title: {yaml_scalar(f'{title} - Chunk {chunk.sequence:03d}')}",
            f"created: {yaml_scalar(created)}",
            f"updated: {yaml_scalar(created)}",
            "tags: [intake, chunk]",
            f"related: [{yaml_scalar(doc_id)}]",
            f"source_paths: [{yaml_scalar(source.as_posix())}]",
            f"confidence: {confidence}",
            "---",
            "",
            f"# {chunk.id}",
            "",
            f"- Parent intake: `{doc_id}`",
            f"- Sequence: {chunk.sequence}",
            f"- Heading: {chunk.heading or 'None'}",
            f"- Page range: {page_range}",
            f"- Word count: {chunk.word_count}",
            f"- Hints: {', '.join(f'`{hint}`' for hint in chunk.hints) if chunk.hints else 'None'}",
            "",
            "## Text",
            "",
            chunk.text,
            "",
        ]
        chunk_path.write_text("\n".join(lines), encoding="utf-8")


def write_chunks_json(
    path: Path,
    doc_id: str,
    title: str,
    source: Path,
    source_hash: str,
    created: str,
    max_words: int,
    chunks: list[Chunk],
    artifact_version: int,
    artifacts: Any,
) -> None:
    chunk_entries: list[dict[str, object]] = []
    for chunk in chunks:
        entry: dict[str, object] = {
            "id": chunk.id,
            "sequence": chunk.sequence,
            "heading": chunk.heading,
            "page_start": chunk.page_start,
            "page_end": chunk.page_end,
            "word_count": chunk.word_count,
            "char_count": chunk.char_count,
            "hints": chunk.hints,
            "text_path": chunk_text_path(chunk),
            "preview": chunk_preview(chunk.text),
        }
        chunk_entries.append(entry)

    payload = {
        "version": artifact_version,
        "id": doc_id,
        "type": "intake-chunks",
        "title": title,
        "created": created,
        "source": {
            "path": source.as_posix(),
            "filename": source.name,
            "sha256": source_hash,
        },
        "chunking": {
            "max_words": max_words,
            "text_storage": "external-chunk-files",
            "chunk_directory": f"{artifacts.chunk_directory}/",
            "inline_text": False,
            "signals_file": None,
            "note": (
                "No separate signals.json is generated in V1. Lightweight extraction hints are stored per chunk. "
                f"Full chunk text is always stored in {artifacts.chunk_directory}/ to avoid token-heavy manifests."
            ),
        },
        "chunks": chunk_entries,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_review_progress(
    path: Path,
    doc_id: str,
    updated: str,
    chunks: list[Chunk],
    artifact_version: int,
) -> None:
    lines = [
        f"version: {artifact_version}",
        f"intake_id: {doc_id}",
        f"updated: {updated}",
        "review_status: in-progress",
        "summary:",
        f"  total: {len(chunks)}",
        f"  pending: {len(chunks)}",
        "  reviewed: 0",
        "  classified: 0",
        "  skipped: 0",
        "chunks:",
    ]
    for chunk in chunks:
        lines.extend(
            [
                f"  - id: {chunk.id}",
                "    status: pending",
                "    classifications: []",
                "    target_ids: []",
                "    notes: null",
            ]
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_intake_report(
    path: Path,
    doc_id: str,
    title: str,
    source: Path,
    created: str,
    chunks: list[Chunk],
    status: str,
    artifacts: Any,
    confidence: str,
    warnings: list[str] | None = None,
) -> None:
    warnings = warnings or []
    lines = [
        "---",
        f"id: {doc_id}",
        "type: intake-document",
        f"status: {status}",
        f"title: {yaml_scalar(title)}",
        f"created: {yaml_scalar(created)}",
        f"updated: {yaml_scalar(created)}",
        "tags: [intake, source-document]",
        "related: []",
        f"source_paths: [{yaml_scalar(source.as_posix())}]",
        f"confidence: {confidence}",
        "---",
        "",
        f"# Document Intake Report - {title}",
        "",
        "## Source",
        "",
        f"- Intake ID: `{doc_id}`",
        f"- Source path: `{source.as_posix()}`",
        f"- Source filename: `{source.name}`",
        "",
        "## Extraction Summary",
        "",
        f"- Chunk count: {len(chunks)}",
        f"- Total extracted words: {sum(chunk.word_count for chunk in chunks)}",
        f"- Review coverage: [{artifacts.review_progress}](./{artifacts.review_progress})",
        "- Full source text embedded in this report: no",
        "",
        "## Extraction Warnings",
        "",
    ]
    if warnings:
        lines.extend(f"- {warning}" for warning in warnings)
    else:
        lines.append("- None recorded by the extractor.")

    lines.extend(
        [
            "",
            "## Review Access",
            "",
            f"- Run `review_progress.py inspect --intake-id {doc_id}` for a compact structure and progress view.",
            f"- Run `review_progress.py view --intake-id {doc_id} --all` when structure is absent, incomplete, ambiguous, or full-document context matters.",
            "- Use `view --section SEC-NNN` only when `inspect` reports reliable source-defined sections.",
            "- After coverage is complete, run `review_progress.py audit`; require `review-complete` and record its ledger summary and SHA-256. Rerun after ledger corrections.",
            "- Before a terminal intake status, run `audit --expect-ledger-sha256 <final-ledger-sha256>` with the digest from the reviewed audit.",
            "- Review every section and any unsectioned content before completion; never invent sections to reduce context.",
            f"- Record dispositions with `review_progress.py apply`; do not complete the intake while [{artifacts.review_progress}](./{artifacts.review_progress}) contains `pending` or `reviewed` entries.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def ensure_intake_index(
    path: Path,
    doc_id: str,
    title: str,
    source: Path,
    status: str = "active",
    report_path: Path | None = None,
) -> None:
    if report_path is None:
        contract = load_schema_contract()
        wiki_root = path
        for _ in PurePosixPath(contract.semantic_paths.intake_index_file).parts:
            wiki_root = wiki_root.parent
        report_path = (
            wiki_root
            / contract.semantic_paths.intake_documents_directory
            / doc_id
            / contract.intake_artifacts.intake_report
        )
    relative_report = Path(os.path.relpath(report_path, path.parent)).as_posix()
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = f"- [{doc_id}](./{relative_report}) - {title} (`{status}`, source: `{source.name}`)"
    if path.exists():
        content = path.read_text(encoding="utf-8")
        if doc_id in content:
            return
        if "## Active Intake Documents" in content:
            content = content.replace("## Active Intake Documents\n", f"## Active Intake Documents\n\n{entry}\n", 1)
        else:
            content = content.rstrip() + f"\n\n## Active Intake Documents\n\n{entry}\n"
    else:
        content = "\n".join(
            [
                "# Document Intake",
                "",
                "This section stores external source documents imported for project-wiki update workflows. Intake documents are provenance, not canonical project knowledge until integrated into requirements, changes, technical docs, implementation docs, or traceability maps.",
                "",
                "Do not read integrated, archived, superseded, or rejected intake documents during normal coding tasks unless explicitly requested. Use intake only for document-based update, audit, provenance, or conflict investigation.",
                "",
                "## Active Intake Documents",
                "",
                entry,
                "",
                "## Reviewed, Integrated, Archived, Superseded, Or Rejected Documents",
                "",
                "- None yet.",
                "",
            ]
        )
    atomic_write_text(path, content.rstrip() + "\n")


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}-", dir=path.parent)
    temporary_path = Path(temporary_name)
    try:
        mode = path.stat().st_mode & 0o777 if path.exists() else 0o644
        os.fchmod(descriptor, mode)
        with os.fdopen(descriptor, "w", encoding="utf-8") as file_obj:
            file_obj.write(content)
            file_obj.flush()
            os.fsync(file_obj.fileno())
        temporary_path.replace(path)
    finally:
        temporary_path.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())