# Document Ingestion

Use this reference when `update` receives an external requirements document, finds a new file in `.project-wiki/sources/inbox/`, or receives a retrievable local document path.

Runtime paths and artifact names come from [`schema/project-wiki.yml`](../schema/project-wiki.yml); this reference explains how to use them.

The document ingestion pipeline extracts source text into `.project-wiki/intake/` so the agent can review relevant chunks, compare them against the current KB and as-is technical state, then either update the canonical KB directly or create `review.md` for user confirmation. When the user asks to integrate a document, the review must cover all information judged relevant, even for very large sources; progressive chunk review is a context-management strategy, not a permission to truncate findings.

Do not read external PDF or DOCX source documents directly into model context. Always pass a local file path to `./scripts/ingest_document.py` first, then review the generated intake artifacts. If the user provides a chat attachment, use a local attachment path when the environment exposes one; otherwise ask the user to place the file in the workspace and provide the path.

Short pasted meeting notes and appunti may be processed directly from chat. External documents and long source files should go through `.project-wiki/sources/inbox/` or an explicit local path.

## Source Inbox

Preferred workflow for external documents:

```text
.project-wiki/sources/
  INDEX.md
  SOURCE_REGISTRY.yml
  inbox/
  processed/YYYY-MM/
  rejected/
  ignored/
```

During every `update`, run the deterministic inbox preflight even if the user also pasted notes in chat:

```text
python3 /path/to/project-wiki/scripts/check_inbox.py \
  --wiki-root .project-wiki \
  --format json \
  --quarantine-skips
```

The preflight requires a valid `SOURCE_REGISTRY.yml`, validates complete historical intake artifacts, cross-checks source hashes in `source-info.yml`, `chunks.json`, and any copied source, hashes supported inbox files, filters housekeeping files, detects byte-identical files in the inbox, and detects content already present in ingestion history. Register and ingest only files classified `process`. Do not ingest `skip` files. Resolve `review` files before changing source history or starting ingestion.

Bind every authorized inbox decision to ingestion using the reported hash:

```text
python3 /path/to/project-wiki/scripts/ingest_document.py \
  .project-wiki/sources/inbox/source-document.pdf \
  --wiki-root .project-wiki \
  --expected-sha256 <sha256-from-checker>
```

If the source bytes change after preflight or during extraction, ingestion stops without publishing an intake document. Run the preflight again instead of overriding the mismatch.

Use `sources/inbox/` as a drop zone only. Do not treat files there as canonical knowledge and do not read PDF/DOCX files directly into model context.

Do not create guide files inside `sources/inbox/`. Store source-area instructions in `sources/INDEX.md`. Ignore inbox housekeeping files such as `README.md`, `.gitkeep`, `.DS_Store`, hidden files, files beginning with `_`, and temporary or partial download files; do not register or ingest them.

## Principle

Document intake is provenance, not canonical project knowledge.

Canonical knowledge lives in:

- `requirements/`
- `changes/`
- `technical/`
- `implementation/`
- `traceability/`
- `REGISTRY.yml`
- `STATUS.md`

Intake artifacts explain where information came from. Do not treat intake content as authoritative until it is integrated into the canonical KB.

Source extraction artifacts should be treated as immutable provenance. Do not edit `extracted.md`, `chunks.json`, copied source files, or source hashes to make them look cleaner after ingestion.

If extraction is materially wrong before integration, mark the intake as `rejected` or `superseded`, log the outcome, and rerun ingestion. Do not create corrective notes for known-bad extraction by default. If extraction issues are minor but usable, record warnings in `intake-report.md`. If a problem is discovered after integration, update the affected canonical KB files and append a wiki audit log entry.

## Supported Formats In V1

Supported:

- `.pdf` text-based PDFs through PyMuPDF.
- `.docx` through python-docx.
- `.txt`.
- `.md` and `.markdown`.

Not supported in V1:

- OCR for scanned PDFs.
- Legacy `.doc` files.
- Image or diagram understanding.
- A separate `signals.json` file.

V1 stores lightweight extraction hints inside `chunks.json` instead of generating `signals.json`. `chunks.json` is a lightweight manifest by default. Full chunk text is stored in separate files under `chunks/` so large documents can be reviewed progressively without loading the whole source into context.

## Scripts

Use `./scripts/check_inbox.py` before processing source inbox files. It emits either a concise text report or structured JSON. It is read-only unless `--quarantine-skips` is supplied; that option rechecks hashes and transactionally moves only `skip` files to `sources/ignored/`.

Deterministic actions:

- `process`: new unique content, or an unambiguous retry of one existing `pending` or `failed` source. Retry reports include `selected_registry_id`.
- `skip`: a byte-identical inbox duplicate, content already registered as `processed`, `ignored`, `rejected`, or `superseded`, or content found in an existing intake. Intake history prevents stale `pending` or `failed` registry state from causing reingestion.
- `review`: either a historical source path was reused with different bytes or multiple processable registry records match the same hash. These cases require version intent or registry reconciliation, respectively.

The checker is authoritative for byte-level duplicate facts. The agent should not recalculate hashes, compare filenames as a proxy for content, or repeat historical duplicate reasoning. Explicit user-requested reprocessing remains a documented override.

Use `./scripts/ingest_document.py` from this skill.

The source document should be read by the script, not by the model. This applies to small and large PDFs/DOCX files alike; direct model reads are less controlled and can overflow context.

Install dependencies before source inbox checks or PDF/DOCX extraction:

```text
python3 -m pip install -r /path/to/project-wiki/scripts/requirements.txt
```

Run from the target repository root when possible:

```text
python3 /path/to/project-wiki/scripts/ingest_document.py ./docs/client-requirements.pdf --wiki-root .project-wiki
```

Useful options:

```text
--doc-id DOCIN-YYYYMMDD-NNN  Use a stable explicit intake ID.
--title "Document Title"       Override the title used in reports.
--max-words 350                Set chunk size. Defaults to 350 words.
--copy-source                  Copy the source file into the intake directory.
--expected-sha256 HASH         Require the source to match an inbox preflight decision.
```

Do not copy source documents into `.project-wiki/` by default. Use `--copy-source` only when the user wants the original file preserved inside the wiki or when the original path is temporary and would otherwise be lost.

### Transactional Publication

The script creates one temporary source snapshot while calculating its SHA-256, verifies the optional preflight hash against those exact bytes, and uses that snapshot for both extraction and `--copy-source`. It verifies that neither the snapshot nor original source changed before publication, then writes all generated artifacts to a hidden staging directory under `intake/documents/`. It validates the required files and chunk manifest before atomically renaming the staging directory to the final `DOCIN-*` path.

The intake index is also replaced atomically. If artifact generation, validation, publication, or index update fails, the script removes staged output and rolls back a newly published intake document. Existing intake IDs are never overwritten and produce a concise CLI error.

### Structure-Preserving Chunking

Headings start a new chunk and retain their section label. Within a chunk, source line breaks remain line breaks and separate extracted blocks remain separated by a blank line. The word limit may split an oversized block, but it must not flatten the preserved text structure inside each resulting segment.

DOCX extraction processes top-level paragraphs and tables in their document order. Table rows retain line boundaries, and tables inherit the current heading when they belong to a named section.

## Generated Artifacts

The script creates:

```text
.project-wiki/intake/
  INDEX.md
  documents/
    DOCIN-YYYYMMDD-NNN/
      source-info.yml
      extracted.md
      chunks.json
      chunks/
        CH-001.md
        CH-002.md
      intake-report.md
      review-progress.yml
```

`source-info.yml` stores source path, filename, hash, `immutable_source: true`, file type, status, word count, and chunk count.

`extracted.md` is a lightweight extraction index. It links to chunk files and records extraction counts. It never stores the full extracted text.

`chunks.json` stores a lightweight chunk manifest with stable chunk IDs, metadata, previews, `text_path` values, and lightweight hints. Full chunk text lives in `chunks/CH-*.md` by default.

`chunks/CH-*.md` stores the full text of individual chunks for progressive review.

`intake-report.md` summarizes extraction results and gives the agent a review checklist.

`review-progress.yml` is mutable workflow state. It contains one entry for every manifest chunk, aggregate counts, classifications, target wiki IDs, and skip reasons. Unlike extraction provenance, update this file after every review batch.

`review.md` is created by the agent, not by the script, when qualitative review gating calls for user confirmation before canonical KB updates.

## Chunk JSON

`chunks.json` is the structured extraction manifest. It is not a full-text dump; `review-progress.yml` separately records mutable review coverage.

Each chunk has this shape:

```json
{
  "id": "DOCIN-20260716-001-CH-001",
  "sequence": 1,
  "heading": "User Authentication",
  "page_start": 4,
  "page_end": 5,
  "word_count": 214,
  "char_count": 1320,
  "hints": ["requirement-language", "actor-mentioned"],
  "text_path": "chunks/CH-001.md",
  "preview": "Administrators must..."
}
```

Hints are lightweight prioritization aids, not semantic decisions or an exclusion filter. The agent reads `chunks.json` and `review-progress.yml`, then opens every `chunks/CH-*.md` file in manageable batches. It records all classifications found in each chunk, including multiple requirements or targets from one chunk.

For large documents, do not ask the agent to read every chunk file at once. Use `intake-report.md`, lightweight `extracted.md`, `chunks.json`, and `review-progress.yml` as routing surfaces. Process every manifest chunk progressively; hints may determine batch order, but no chunk may remain `pending` or `reviewed` when coverage is declared complete.

Review progress states:

- `pending`: not yet examined.
- `reviewed`: examined but not given a final disposition; still incomplete.
- `classified`: final disposition recorded with one or more semantic classifications. After integration, include every registered target wiki ID produced or updated from that chunk.
- `skipped`: deliberately excluded after reading the chunk; `notes` must explain why.

Set ledger `review_status: complete` only when every entry is `classified` or `skipped` and summary counts match the entries. The validator rejects `reviewed` or `integrated` intake status while coverage is incomplete. For an `integrated` intake, it also rejects classified chunks without registered target IDs.

Use the helper instead of recalculating ledger summary fields manually:

```text
python3 /path/to/project-wiki/scripts/review_progress.py status \
  --wiki-root .project-wiki \
  --intake-id DOCIN-YYYYMMDD-NNN \
  --limit 20 \
  --format json

python3 /path/to/project-wiki/scripts/review_progress.py apply \
  --wiki-root .project-wiki \
  --intake-id DOCIN-YYYYMMDD-NNN \
  --updates batch-updates.json
```

The update file is a JSON list. Each object contains `id`, `status`, and optional `classifications`, `target_ids`, and `notes`. The helper rejects invalid or duplicate chunk IDs and writes the ledger atomically.

If an intake document was generated by an older script version where `extracted.md` or `chunks.json` contains full document text, do not ask the agent to read those files. Mark the intake `superseded` or delete the failed intake if it has not been integrated, then rerun ingestion with the current script.

## Intake Status

Every intake document must have one status:

```text
active      imported and not fully reviewed
reviewed    review.md exists and awaits user decision
integrated  accepted content has been merged into the canonical KB
archived    retained only for provenance
superseded  replaced by a newer source document
rejected    not relevant, not accepted, or invalid as a source
```

`intake/INDEX.md` should keep active and reviewed documents easy to find. Integrated, archived, superseded, and rejected documents should be listed compactly and should not be opened during normal coding tasks.

## Agent Review Process

After ingestion:

1. Read `.project-wiki/intake/documents/DOCIN-YYYYMMDD-NNN/intake-report.md`.
2. Read `chunks.json` as a lightweight manifest.
3. Run `review_progress.py status` and select the returned batch of `pending` or `reviewed` chunk IDs. Hints may prioritize the batch but must not remove chunks from coverage.
4. Open every chunk in the batch and identify all useful items, including multiple requirements within one chunk.
5. Apply the batch with `review_progress.py apply`: set each ledger entry to `classified` with all applicable classifications, `skipped` with a reason, or `reviewed` only as an incomplete checkpoint. The helper recalculates summary counts, `updated`, and completion.
6. Repeat until every manifest chunk is `classified` or `skipped`, then set `review_status: complete`.
7. Read `.project-wiki/INDEX.md` and follow links to relevant KB files.
8. Compare candidate items against requirements, CRs, ADRs, technical docs, implementation docs, traceability maps, and current as-is state.
9. Reconcile existing open questions before proposing new open questions from the document.
10. When integrating requirements, use requirement topic scaling from [Wiki structure](./wiki-structure.md#requirements-topic-scaling).
11. Record all resulting registered wiki IDs in each classified ledger entry, run the validator, then apply the direct-update vs `review.md` rules below.

## Direct Update vs review.md

Direct KB update is allowed for clear, low-risk document updates.

Before creating `review.md`, weigh the new information against the current KB and as-is technical state. Prefer direct integration for clear confirmations, routine additions, editorial clarifications, and low-impact updates that do not materially change scope, priorities, architecture, security, compliance, data, permissions, or core behavior. Avoid repeated review gates for minor items that can be safely integrated and logged.

Create `review.md` and ask for confirmation before modifying canonical KB files when the new information is significant enough that one or more of these are true:

- The source is broad or dense and contains material information that is ambiguous, high-impact, or difficult to integrate safely in one pass.
- The update would affect multiple wiki sections, especially when requirements, changes, technical docs, implementation notes, traceability, alerts, or open questions must be updated together.
- The document conflicts with existing requirements, CRs, ADRs, technical docs, or as-is code.
- The document affects security, privacy, compliance, data, permissions, payments, or core behavior.
- The document contains ADR-level technical decisions.
- The source authority is unclear.
- The update would materially change project scope or priorities.

Logging is mandatory in both paths:

- Direct path: log the integrated KB update once.
- Review path: log creation of pending `review.md`, then log final integration, rejection, or postponement separately.

`review.md` should include all proposed canonical KB updates that are supported by evidence. Suggested follow-up questions, missing source material, risky assumptions, conflicts, and alert candidates should also be evidence-linked; group or prioritize them when a document is large, but do not omit relevant items merely to keep the review short.

## review.md Template

When review is required, use the complete [Document Intake Review template](../assets/intake-source-templates.md#document-intake-review). Do not treat a pending `review.md` as canonical project knowledge until the user approves integration.
