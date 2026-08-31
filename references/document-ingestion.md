# Document Ingestion

Use this reference when `update` receives an external requirements document, finds a new file in `.project-wiki/sources/inbox/`, or receives a retrievable local document path.

Runtime paths and artifact names come from [`schema/project-wiki.yml`](../schema/project-wiki.yml); this reference explains how to use them.

The document ingestion pipeline extracts source text into `.project-wiki/intake/` so the agent can review every chunk, compare it against the current KB and as-is technical state, and integrate conservatively by default. Create `review.md` only when canonical integration requires a blocking, auditable human decision that cannot be represented safely through status, confidence, open questions, alerts, or preserved alternatives. Progressive review is a context-management strategy, not permission to truncate findings.

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

V1 stores lightweight extraction hints inside `chunks.json` instead of generating `signals.json`. The manifest excludes full text but may still grow with the number of chunks, so it remains machine-facing. Full chunk text is stored in separate files under `chunks/` and exposed to the model through validated `view` output.

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

`source-info.yml` stores source path, filename, hash, `immutable_source: true`, file type, status, word count, and chunk count. When `--copy-source` is used, `copied_source_path` is relative to the intake directory; validators and inbox checks continue to accept legacy absolute values.

`extracted.md` is a compact extraction index. It records extraction counts and routes agents to `review_progress.py`; it never stores full text or enumerates chunks.

`chunks.json` stores the machine-facing chunk manifest with stable chunk IDs, metadata, previews, `text_path` values, and lightweight hints. Full chunk text lives in `chunks/CH-*.md`. Agents should access both through `review_progress.py` rather than loading them into model context.

`chunks/CH-*.md` stores the full text of individual chunks for provenance and coverage. Agents consume clean full-document or source-section views rather than these generated wrappers.

`intake-report.md` compactly summarizes extraction results and warnings and routes the agent to `inspect` and `view`.

`review-progress.yml` is mutable workflow state. It contains one entry for every manifest chunk, aggregate counts, classifications, target wiki IDs, and skip reasons. Unlike extraction provenance, update this file through `review_progress.py apply` after reviewing content.

`review.md` is created by the agent, not by the script, only when a blocking, auditable human decision is required before canonical integration can proceed.

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

Hints are machine metadata, not semantic decisions or an exclusion filter. `review_progress.py inspect` validates the manifest and ledger and returns only a compact outline and aggregate review state. `review_progress.py view` validates and reads the selected chunk files, removes generated wrappers, and emits the complete selected source text with compact provenance markers.

Use `view --section SEC-NNN` only when `inspect` reports reliable source-defined sections. Review every reported section, including `SEC-000` when unsectioned source content exists. Use `view --all` whenever structure is absent, incomplete, ambiguous, or full-document context may matter. Never invent sections merely to reduce context. Chunking remains a storage, provenance, and coverage mechanism; it does not authorize excluding any source text.

Review progress states:

- `pending`: not yet examined.
- `reviewed`: examined but not given a final disposition; still incomplete.
- `classified`: final disposition recorded with one or more semantic classifications. After integration, include every registered target wiki ID produced or updated from that chunk.
- `skipped`: deliberately excluded after reading the chunk; `notes` must explain why.

Set ledger `review_status: complete` only when every entry is `classified` or `skipped` and summary counts match the entries. The validator rejects `reviewed` or `integrated` intake status while coverage is incomplete. For an `integrated` intake, it also rejects classified chunks without registered target IDs.

Use the helper instead of recalculating ledger summary fields manually:

```text
python3 /path/to/project-wiki/scripts/review_progress.py inspect \
  --wiki-root .project-wiki \
  --intake-id DOCIN-YYYYMMDD-NNN

python3 /path/to/project-wiki/scripts/review_progress.py view \
  --wiki-root .project-wiki \
  --intake-id DOCIN-YYYYMMDD-NNN \
  --all

python3 /path/to/project-wiki/scripts/review_progress.py apply \
  --wiki-root .project-wiki \
  --intake-id DOCIN-YYYYMMDD-NNN \
  --updates review-updates.json
```

`view` requires exactly one of `--all`, `--section`, or `--chunks`. Use `--chunks CH-012 CH-019` only for targeted rereading after complete source review. Its default Markdown output separates source text with compact markers such as `--- DOCIN-...-CH-012 | pages 8-9 | Authentication | pending ---`. Markers preserve order, provenance, and ledger state without claiming that a chunk boundary is a semantic boundary or a known continuation. The command is read-only.

`audit` is a read-only ledger checkpoint. It reports `review-complete` or `review-incomplete`, the ledger summary, and an exact SHA-256 of the bytes it read. It does not inspect or score canonical content. Before final status mutation, `audit --expect-ledger-sha256 <digest>` deterministically rejects a ledger changed since the latest checkpoint.

`audit-skips` is an optional diagnostic that lists skipped chunks, contiguous runs, notes, and lexical signals. Use it only when investigating exclusions; its output is not a semantic verdict or a finalization requirement. Use `view --chunks` for any source units selected for rereading.

The update file is a JSON list. Each object contains `id`, `status`, and optional `classifications`, `target_ids`, and `notes`. The helper rejects invalid or duplicate chunk IDs and writes the ledger atomically. The existing `status --limit` command remains available for compatibility and diagnostics, but it is not the recommended content-access workflow.

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
2. Run `review_progress.py inspect` using its compact text output. Do not read `chunks.json`, `review-progress.yml`, `extracted.md`, or generated chunk wrappers directly unless troubleshooting a helper failure.
3. If `inspect` reports reliable source-defined sections, use `view --section` for every listed section and unsectioned unit. Otherwise, or whenever section boundaries may hide cross-section meaning, use `view --all`.
4. Read all text emitted by the selected view and identify every useful item, including multiple requirements associated with one chunk marker and requirements spanning adjacent markers.
5. Use `review_progress.py apply` for every displayed `pending` or `reviewed` chunk: set it to `classified` with all applicable classifications, `skipped` with a reason, or `reviewed` only as an incomplete checkpoint. Preserve existing final dispositions. The helper recalculates summary counts, `updated`, and completion.
6. Run `inspect` again. Continue until every manifest chunk is `classified` or `skipped` and `review_status` is `complete`.
7. Run `audit`, require `review-complete`, and preserve its ledger summary and digest in the wiki log. Rerun after ledger corrections. Use optional `audit-skips` or `view --chunks` only for a specific exclusion investigation.
8. Read `.project-wiki/INDEX.md` and follow links to relevant KB files.
9. Compare candidate items against requirements, CRs, ADRs, technical docs, implementation docs, traceability maps, and current as-is state.
10. Reconcile existing open questions before proposing new open questions from the document.
11. When integrating requirements, use requirement topic scaling from [Wiki structure](./wiki-structure.md#requirements-topic-scaling).
12. Record all resulting registered wiki IDs in each classified ledger entry, run the validator, then apply the direct-integration vs blocking-review rules below. Deterministic findings block completion; unresolved audit candidates are reported but do not.

## Direct Integration vs Blocking Review

An explicit `update` request authorizes conservative canonical integration of supplied information and processable inbox sources unless the user asks for review-only output. Integrate clear information directly. Preserve non-blocking ambiguity through accurate status and confidence, open questions, alerts, blocked records, or explicit alternatives instead of stopping the workflow.

Create `review.md` and request approval only when a human decision is required before any conservative canonical representation can proceed. Blocking decisions include:

- deciding whether a source is authoritative for this project or in scope;
- selecting which part of a source is authorized when inclusion cannot be represented conservatively;
- choosing between incompatible baselines or alternatives when preserving both as unresolved is insufficient;
- replacing, invalidating, or re-baselining confirmed canonical intent without prior authorization;
- making a legally, contractually, or architecturally binding choice that the source leaves to an approver;
- honoring an explicit user request to review a proposal before integration.

Document length, density, number of findings, cross-section impact, security/privacy/compliance subject matter, open questions, alerts, or ADR candidates are not review triggers by themselves. Integrate the unambiguous source-backed content and preserve unresolved details without inventing a choice.

When a gate is required, `review.md` must focus on the exact blocking question, available options, evidence, affected canonical scope, and consequences. Do not duplicate the full source or create a second approval after the user resolves the blocking decision. Resume the same integration once, preserving all other unresolved matters as OQ or alerts.

Logging is mandatory in both paths:

- Direct path: log the integrated KB update once.
- Review path: log creation of pending `review.md`, then log final integration, rejection, or postponement separately.

`review.md` should include only the canonical scope affected by the blocking decision, while remaining evidence-linked. Keep non-blocking follow-up questions, missing source material, assumptions, and conflicts in their durable OQ, alert, or canonical records rather than using them to widen the approval gate.

For direct integration, define the Atomic Requirement Decomposition Plan before canonical authoring. If a blocking decision changes topic scope or permitted ranges, include the affected plan rows in `review.md` and finalize the complete plan after approval. Persist exact record-to-chunk edges in `traceability/requirement-evidence.yml`. An intake cannot become `integrated` while requirement decomposition is described as future work.

## review.md Template

When a blocking review is required, use the [Document Intake Review template](../assets/intake-source-templates.md#document-intake-review). Do not treat a pending `review.md` or its unapproved choice as canonical project knowledge.
