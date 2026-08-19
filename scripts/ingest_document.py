#!/usr/bin/env python3
"""Extract PDF/DOCX/text documents into project-wiki intake artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


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


@dataclass(frozen=True)
class Chunk:
    id: str
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
    return parser.parse_args()


def main() -> int:
    args = parse_args()
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

    wiki_root = Path(args.wiki_root).expanduser().resolve()
    intake_root = wiki_root / "intake"
    documents_root = intake_root / "documents"
    documents_root.mkdir(parents=True, exist_ok=True)

    doc_id = args.doc_id or next_doc_id(documents_root)
    if not re.fullmatch(r"DOCIN-\d{8}-\d{3}", doc_id):
        print("error: --doc-id must match DOCIN-YYYYMMDD-NNN", file=sys.stderr)
        return 2

    title = args.title or source.stem.replace("_", " ").replace("-", " ").strip().title()
    created = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    doc_dir = documents_root / doc_id
    doc_dir.mkdir(parents=True, exist_ok=False)

    try:
        blocks = extract_blocks(source)
    except MissingDependencyError as error:
        print(f"error: {error}", file=sys.stderr)
        return 3

    if not blocks or not any(block.text.strip() for block in blocks):
        print("error: no extractable text found. Scanned PDFs may require OCR, which is not supported in V1.", file=sys.stderr)
        return 4

    chunks = build_chunks(doc_id, blocks, args.max_words)
    source_hash = sha256_file(source)
    copied_source_path = copy_source(source, doc_dir) if args.copy_source else None

    write_source_info(
        path=doc_dir / "source-info.yml",
        doc_id=doc_id,
        title=title,
        source=source,
        source_hash=source_hash,
        copied_source_path=copied_source_path,
        created=created,
        file_type=suffix.lstrip("."),
        word_count=sum(chunk.word_count for chunk in chunks),
        chunk_count=len(chunks),
    )
    write_chunk_files(doc_dir / "chunks", doc_id, title, source, created, chunks)
    write_extracted_markdown(doc_dir / "extracted.md", doc_id, title, source, created, blocks, chunks)
    write_chunks_json(doc_dir / "chunks.json", doc_id, title, source, source_hash, created, args.max_words, chunks)
    write_intake_report(doc_dir / "intake-report.md", doc_id, title, source, created, chunks)
    ensure_intake_index(intake_root / "INDEX.md", doc_id, title, source)

    print(f"created intake document: {doc_id}")
    print(f"output: {doc_dir}")
    print("artifacts: source-info.yml, extracted.md, chunks.json, chunks/, intake-report.md")
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

    for paragraph in document.paragraphs:
        text = normalize_text(paragraph.text)
        if not text:
            continue
        style_name = getattr(paragraph.style, "name", "") or ""
        if style_name.lower().startswith("heading"):
            current_heading = text
            blocks.append(TextBlock(text=text, heading=current_heading))
        else:
            blocks.append(TextBlock(text=text, heading=current_heading))

    for table_index, table in enumerate(document.tables, start=1):
        rows: list[str] = []
        for row in table.rows:
            cells = [normalize_text(cell.text) for cell in row.cells]
            if any(cells):
                rows.append(" | ".join(cells))
        if rows:
            blocks.append(TextBlock(text="\n".join(rows), heading=f"Table {table_index}"))

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
        if first_line.startswith("#"):
            current_heading = first_line.lstrip("#").strip() or current_heading
        blocks.append(TextBlock(text=block, heading=current_heading))
    return blocks


def build_chunks(doc_id: str, blocks: Iterable[TextBlock], max_words: int) -> list[Chunk]:
    chunks: list[Chunk] = []
    current_words: list[str] = []
    current_pages: list[int] = []
    current_heading: str | None = None

    def emit() -> None:
        nonlocal current_words, current_pages, current_heading
        if not current_words:
            return
        text = " ".join(current_words).strip()
        sequence = len(chunks) + 1
        page_start = min(current_pages) if current_pages else None
        page_end = max(current_pages) if current_pages else None
        chunks.append(
            Chunk(
                id=f"{doc_id}-CH-{sequence:03d}",
                sequence=sequence,
                heading=current_heading,
                page_start=page_start,
                page_end=page_end,
                word_count=len(current_words),
                char_count=len(text),
                hints=detect_hints(text),
                text=text,
            )
        )
        current_words = []
        current_pages = []
        current_heading = None

    for block in blocks:
        words = block.text.split()
        if not words:
            continue
        while words:
            remaining = max_words - len(current_words)
            if remaining <= 0:
                emit()
                remaining = max_words
            take = words[:remaining]
            words = words[remaining:]
            if current_heading is None:
                current_heading = block.heading
            current_words.extend(take)
            if block.page is not None:
                current_pages.append(block.page)
            if len(current_words) >= max_words:
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


def next_doc_id(documents_root: Path) -> str:
    today = datetime.now().strftime("%Y%m%d")
    pattern = re.compile(rf"DOCIN-{today}-(\d{{3}})$")
    used = []
    for path in documents_root.glob(f"DOCIN-{today}-*"):
        match = pattern.fullmatch(path.name)
        if match:
            used.append(int(match.group(1)))
    next_number = max(used, default=0) + 1
    return f"DOCIN-{today}-{next_number:03d}"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file_obj:
        for chunk in iter(lambda: file_obj.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def copy_source(source: Path, doc_dir: Path) -> Path:
    target = doc_dir / f"source{source.suffix.lower()}"
    shutil.copy2(source, target)
    return target


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
) -> None:
    lines = [
        "version: 1",
        f"id: {yaml_scalar(doc_id)}",
        "type: intake-document",
        "status: active",
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
        "confidence: confirmed",
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
) -> None:
    lines = [
        "---",
        f"id: {doc_id}-EXTRACTED",
        "type: intake-extraction-index",
        "status: active",
        f"title: {yaml_scalar(f'Extraction Index - {title}')}",
        f"created: {yaml_scalar(created)}",
        f"updated: {yaml_scalar(created)}",
        "tags: [intake, extracted-text, extraction-index]",
        f"related: [{yaml_scalar(doc_id)}]",
        f"source_paths: [{yaml_scalar(source.as_posix())}]",
        "confidence: confirmed",
        "---",
        "",
        f"# Extraction Index - {title}",
        "",
        f"Source: `{source.as_posix()}`",
        "",
        "Generated headings and metadata are in English. Full extracted text is stored progressively in `chunks/CH-*.md` by default to avoid token-heavy files.",
        "",
        "## Progressive Text Access",
        "",
        "- Read [intake-report.md](./intake-report.md) first.",
        "- Read [chunks.json](./chunks.json) as a lightweight manifest.",
        "- Open files under [chunks/](./chunks/) progressively until the requested review or integration is complete.",
        "",
        "## Extraction Summary",
        "",
        f"- Extracted block count: {len(blocks)}",
        f"- Chunk count: {len(chunks)}",
        f"- Total extracted words: {sum(chunk.word_count for chunk in chunks)}",
        "- Full text embedded in this file: no",
        "",
        "## Chunk Files",
        "",
    ]

    for chunk in chunks:
        page_part = f", pages {chunk.page_start}-{chunk.page_end}" if chunk.page_start is not None else ""
        lines.append(f"- [{chunk.id}](./{chunk_text_path(chunk)}) ({chunk.word_count} words{page_part})")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def chunk_text_path(chunk: Chunk) -> str:
    return f"chunks/CH-{chunk.sequence:03d}.md"


def chunk_preview(text: str, max_chars: int = 280) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if len(compact) <= max_chars:
        return compact
    return compact[: max_chars - 1].rstrip() + "..."


def write_chunk_files(path: Path, doc_id: str, title: str, source: Path, created: str, chunks: list[Chunk]) -> None:
    path.mkdir(parents=True, exist_ok=True)
    for chunk in chunks:
        chunk_path = path / f"CH-{chunk.sequence:03d}.md"
        page_range = "null"
        if chunk.page_start is not None and chunk.page_end is not None:
            page_range = f"{chunk.page_start}-{chunk.page_end}"
        lines = [
            "---",
            f"id: {yaml_scalar(chunk.id)}",
            "type: intake-chunk",
            "status: active",
            f"title: {yaml_scalar(f'{title} - Chunk {chunk.sequence:03d}')}",
            f"created: {yaml_scalar(created)}",
            f"updated: {yaml_scalar(created)}",
            "tags: [intake, chunk]",
            f"related: [{yaml_scalar(doc_id)}]",
            f"source_paths: [{yaml_scalar(source.as_posix())}]",
            "confidence: confirmed",
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
        "version": 1,
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
            "chunk_directory": "chunks/",
            "inline_text": False,
            "signals_file": None,
            "note": "No separate signals.json is generated in V1. Lightweight extraction hints are stored per chunk. Full chunk text is always stored in chunks/ to avoid token-heavy manifests.",
        },
        "chunks": chunk_entries,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_intake_report(path: Path, doc_id: str, title: str, source: Path, created: str, chunks: list[Chunk]) -> None:
    hint_counts: dict[str, int] = {}
    for chunk in chunks:
        for hint in chunk.hints:
            hint_counts[hint] = hint_counts.get(hint, 0) + 1

    candidate_chunks = [chunk for chunk in chunks if chunk.hints]
    lines = [
        "---",
        f"id: {doc_id}",
        "type: intake-document",
        "status: active",
        f"title: {yaml_scalar(title)}",
        f"created: {yaml_scalar(created)}",
        f"updated: {yaml_scalar(created)}",
        "tags: [intake, source-document]",
        "related: []",
        f"source_paths: [{yaml_scalar(source.as_posix())}]",
        "confidence: confirmed",
        "---",
        "",
        f"# Document Intake Report - {title}",
        "",
        "## Source",
        "",
        f"- Intake ID: `{doc_id}`",
        f"- Source path: `{source.as_posix()}`",
        f"- Source filename: `{source.name}`",
        "- Intake status: `active`",
        "",
        "## Generated Artifacts",
        "",
        "- [source-info.yml](./source-info.yml)",
        "- [extracted.md](./extracted.md)",
        "- [chunks.json](./chunks.json)",
        "- [chunks/](./chunks/)",
        "",
        "## Extraction Summary",
        "",
        f"- Chunk count: {len(chunks)}",
        f"- Total extracted words: {sum(chunk.word_count for chunk in chunks)}",
        "- Separate signals file: not generated in V1",
        "- Lightweight hints: stored inside `chunks.json` per chunk",
        "- Full chunk text: stored in separate files under `chunks/`",
        "- Candidate listing: every chunk with lightweight hints is listed below; this is not an integration cap",
        "",
        "## Hint Summary",
        "",
    ]
    if hint_counts:
        for hint, count in sorted(hint_counts.items()):
            lines.append(f"- `{hint}`: {count} chunk(s)")
    else:
        lines.append("- No lightweight hints detected.")

    lines.extend(["", "## Candidate Chunks For Agent Review", ""])
    if candidate_chunks:
        lines.append("Every chunk with lightweight hints is listed here. Chunks without hints may still be relevant; use `chunks.json` to review the full document progressively when integrating requirements.")
        lines.append("")
        for chunk in candidate_chunks:
            page_part = f", pages {chunk.page_start}-{chunk.page_end}" if chunk.page_start is not None else ""
            hints = ", ".join(f"`{hint}`" for hint in chunk.hints)
            lines.append(f"- [`{chunk.id}`](./{chunk_text_path(chunk)}) ({chunk.word_count} words{page_part}): {hints}")
    else:
        lines.append("- No candidate chunks detected by lightweight hints. The agent should still review the document context if requested by the user.")

    lines.extend(
        [
            "",
            "## Agent Review Checklist",
            "",
            "For each relevant chunk, determine whether it is:",
            "",
            "- A new requirement.",
            "- A refinement of an existing requirement.",
            "- A lightweight change request.",
            "- An ADR-level decision.",
            "- Technical documentation for implemented behavior.",
            "- A conflict with the current KB or as-is technical state.",
            "- An open question.",
            "- Background information that should not enter the canonical KB.",
            "",
            "Read `chunks.json` as a lightweight manifest first, then open chunk files progressively until every item relevant to the requested integration has been classified. Do not stop at a fixed number of candidate chunks.",
            "",
            "Clear, low-risk information may be integrated directly into the KB and logged. Create `review.md` only when the source information is significant, ambiguous, risky, conflicting, authority-unclear, or materially cross-section. The review must still cover all relevant information rather than a truncated sample.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def ensure_intake_index(path: Path, doc_id: str, title: str, source: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = f"- [{doc_id}](./documents/{doc_id}/intake-report.md) - {title} (`active`, source: `{source.name}`)"
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
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())