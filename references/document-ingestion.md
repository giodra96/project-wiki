# Document Ingestion

Use this reference when `update` receives an external requirements document, finds a new file in `.project-wiki/sources/inbox/`, or receives a retrievable local document path.

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

During every `update`, check `.project-wiki/sources/inbox/` for new files, even if the user also pasted notes in chat. Register unprocessed files in `SOURCE_REGISTRY.yml`, run the ingestion script, then move successfully processed files to `sources/processed/YYYY-MM/` when possible.

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

## Script

Use `./scripts/ingest_document.py` from this skill.

The source document should be read by the script, not by the model. This applies to small and large PDFs/DOCX files alike; direct model reads are less controlled and can overflow context.

Install dependencies when PDF or DOCX support is needed:

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
```

Do not copy source documents into `.project-wiki/` by default. Use `--copy-source` only when the user wants the original file preserved inside the wiki or when the original path is temporary and would otherwise be lost.

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
```

`source-info.yml` stores source path, filename, hash, `immutable_source: true`, file type, status, word count, and chunk count.

`extracted.md` is a lightweight extraction index. It links to chunk files and records extraction counts. It never stores the full extracted text.

`chunks.json` stores a lightweight chunk manifest with stable chunk IDs, metadata, previews, `text_path` values, and lightweight hints. Full chunk text lives in `chunks/CH-*.md` by default.

`chunks/CH-*.md` stores the full text of individual chunks for progressive review.

`intake-report.md` summarizes extraction results and gives the agent a review checklist.

`review.md` is created by the agent, not by the script, when qualitative review gating calls for user confirmation before canonical KB updates.

## Chunk JSON

`chunks.json` is the only structured analysis artifact generated in V1. It is intentionally a manifest, not a full-text dump.

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

Hints are lightweight retrieval aids, not semantic decisions. The agent reads `chunks.json` first, then opens only the `chunks/CH-*.md` files needed for review. The agent decides whether a chunk is a requirement, CR, ADR, open question, technical doc update, or irrelevant background after comparing it with the KB.

For large documents, do not ask the agent to read every chunk file at once. Use `intake-report.md`, lightweight `extracted.md`, and `chunks.json` as routing surfaces, then inspect chunk files progressively until every item relevant to the requested integration has been classified.

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
3. Open the relevant `chunks/CH-*.md` files identified by `intake-report.md`, hints, previews, or user focus. For integration requests, continue in batches until all relevant chunks have been reviewed and classified.
4. Read `.project-wiki/INDEX.md` and follow links to relevant KB files.
5. Compare candidate items against requirements, CRs, ADRs, technical docs, implementation docs, traceability maps, and current as-is state.
6. Reconcile existing open questions before proposing new open questions from the document.
7. Classify useful items as new requirement, requirement refinement, change request, ADR-level decision, technical documentation update, work item, open question, conflict, or background.
8. When integrating requirements, use requirement topic scaling from [Wiki structure](./wiki-structure.md#requirements-topic-scaling).
9. Apply the direct-update vs `review.md` rules below.

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

## review.md Shape

Use this structure when review is required:

```markdown
---
id: DOCIN-YYYYMMDD-NNN-REVIEW
type: intake-review
status: reviewed
title: Review - Source Document Title
created: YYYY-MM-DD
updated: YYYY-MM-DD
tags: [intake, review]
related: [DOCIN-YYYYMMDD-NNN]
source_paths: []
confidence: inferred
---

# Document Intake Review - Source Document Title

## Review Decision Needed

TBD

## Proposed Canonical KB Updates

TBD

## Potential Conflicts With Current KB Or As-Is State

TBD

## Open Questions

TBD

## Existing Open Questions Reconciled

| Open Question | Outcome | Evidence | Notes |
| --- | --- | --- | --- |
| OQ-001 | resolved | DOCIN-YYYYMMDD-NNN-CH-001 | TBD |

## Suggested Follow-Up Questions

| Question | Why It Matters | Related Evidence | Suggested Action |
| --- | --- | --- | --- |
| TBD | TBD | TBD | TBD |

## Missing Source Material

| Gap | Impact | Related Evidence | Suggested Source |
| --- | --- | --- | --- |
| TBD | TBD | TBD | TBD |

## Risky Assumptions

| Assumption | Risk | Evidence | Proposed Action |
| --- | --- | --- | --- |
| TBD | TBD | TBD | TBD |

## Alert Candidates

| Candidate Alert | Severity | Why It Matters | Related Evidence |
| --- | --- | --- | --- |
| TBD | medium | TBD | TBD |

## Items Not Proposed For Integration

TBD
```

Do not treat a pending `review.md` as canonical project knowledge until the user approves integration.
