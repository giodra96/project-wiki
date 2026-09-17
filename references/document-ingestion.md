# Document Ingestion

Use for external PDF, DOCX, text, or Markdown documents, including processable inbox sources. Short pasted notes use [Update Workflow](./update-workflows.md#update-workflow). Machine paths and lifecycle contracts come from [`schema/project-wiki.yml`](../schema/project-wiki.yml).

Review every source chunk and compare findings with the KB and as-is technical state. Progressive review manages context; it never permits truncating findings. Follow the procedure below and [Direct Integration vs Blocking Review](#direct-integration-vs-blocking-review).

## Source Inbox

At every `update`, check the inbox even when chat notes are present. For inbox files, use [Source Inbox Workflow](./source-inbox.md#source-inbox-workflow) before ingestion; it owns registration, duplicate actions, archiving, retries, and hash verification.

## Provenance

Intake is provenance, not canonical knowledge until integrated. Keep `extracted.md`, `chunks.json`, chunk text, copied sources, and source hashes immutable; only review state is mutable through the helper. If an extraction problem is discovered after integration, correct affected canonical records and append a wiki audit entry. Pre-integration extraction failures follow the workflow below.

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

## Script Options

Use the installed skill's scripts from the target repository root. Install missing dependencies from `scripts/requirements.txt` only when package installation is allowed.

```text
--doc-id DOCIN-YYYYMMDD-NNN  Use a stable explicit intake ID.
--title "Document Title"    Override the report title.
--max-words 350              Set chunk size (default: 350 words).
--copy-source                Preserve a copy inside the intake directory.
--expected-sha256 HASH       Bind ingestion to the inbox preflight decision.
```

Use `--copy-source` only when requested or when a temporary original would otherwise be lost. Existing intake IDs are never overwritten. Extraction/publication failure rolls back newly generated output; do not mark a failed source processed.

## Document Intake Workflow

Use this workflow when `update` receives an external PDF, DOCX, text, or Markdown document.

1. For inbox sources, complete [Source Inbox Workflow](./source-inbox.md#source-inbox-workflow) first. Pass its reported hash as `--expected-sha256 <sha256>`; on a mismatch rerun preflight instead of overriding it.
2. Never read external PDF/DOCX source documents directly into model context. Use a local file path and let the script extract text.
3. If the user provides only an attachment and no local path is available, ask the user to place the document in the workspace and provide the path.
4. Run the script from the target repository root with the skill script path, for example: `python3 /path/to/project-wiki/scripts/ingest_document.py <document-path> --wiki-root .project-wiki`.
5. If PDF or DOCX dependencies are missing, install them from `./scripts/requirements.txt` or ask the user before proceeding if package installation is not allowed.
6. The script must create `.project-wiki/intake/INDEX.md` and `.project-wiki/intake/documents/DOCIN-YYYYMMDD-NNN/` with `source-info.yml`, `extracted.md`, `chunks.json`, `chunks/`, `intake-report.md`, and `review-progress.yml`.
7. Do not generate or expect `signals.json` in V1. Lightweight extraction hints remain machine metadata inside `chunks.json`; do not load the manifest merely to inspect them.
8. Read the compact `intake-report.md`, then run `review_progress.py inspect --wiki-root .project-wiki --intake-id <DOCIN-ID>` using its compact text output. Do not read `chunks.json`, `review-progress.yml`, `extracted.md`, or chunk wrappers directly unless troubleshooting a helper failure.
9. If `inspect` reports clear, reliable source-defined sections, use `review_progress.py view --wiki-root .project-wiki --intake-id <DOCIN-ID> --section <SEC-ID>` and review every reported section, including `SEC-000` unsectioned content when present.
10. Use `review_progress.py view --wiki-root .project-wiki --intake-id <DOCIN-ID> --all` whenever structure is absent, incomplete, ambiguous, or full-document context may matter. Never invent sections merely to reduce context.
11. Use `review_progress.py apply` with JSON updates for every `pending` or `reviewed` chunk marker shown by `view`; preserve existing final dispositions. A chunk may map to multiple classifications and target IDs. Use `reviewed` only as an incomplete checkpoint; final entries must be `classified` or `skipped` with a reason.
12. Compare candidate document items against `.project-wiki/INDEX.md`, `REGISTRY.yml`, relevant requirements, changes, technical docs, implementation docs, and traceability maps.
13. Run [Open Questions Reconciliation](./common-policies.md#open-questions-reconciliation-workflow) before proposing new open questions from document findings.
14. When integrating requirements from document findings, define the atomic topic plan before canonical authoring and use the record locations and requirement-evidence sidecar contract from [Requirement Authoring](../assets/requirements-change-templates.md#requirements-topic-scaling).
15. Keep intake documents as provenance only. Do not treat intake content as canonical project knowledge until it is integrated into the KB.
16. Do not consult `integrated`, `archived`, `superseded`, or `rejected` intake documents during normal coding tasks unless the user asks for provenance, audit, or conflict investigation.
17. Apply [Direct Integration vs Blocking Review](#direct-integration-vs-blocking-review). Continue with direct conservative integration unless a blocking, auditable human decision prevents canonical representation.
18. On the direct path, write planned REQ/NFR records in their topic files and CON records in `requirements/constraints.md`, record every record-to-chunk edge in `traceability/requirement-evidence.yml`, and preserve non-blocking uncertainty through OQ, alerts, status, confidence, blocked records, or explicit alternatives.
19. On the blocking path, create `review.md` focused only on the exact decision, evidence, options, affected canonical scope, and consequences. After approval, resume this integration once; do not create another review gate for the same decision.
20. Before setting intake status to `reviewed` or `integrated`, run `inspect` again and require `review_status: complete`, then run `review_progress.py audit`. Require `audit_status: review-complete` and retain its ledger summary and SHA-256.
21. After any ledger correction, rerun `audit`. Immediately before changing the intake to a terminal status, run `audit --expect-ledger-sha256 <final-ledger-sha256>` using the latest digest; a mismatch requires another audit. Copy the final audit status, ledger summary, and SHA-256 into the wiki log.
22. Reconcile ledger summary counts and run `validate_wiki.py`. Deterministic errors block completion; audit candidates do not. For `integrated`, every requirement-classified chunk must target at least one registered atomic REQ/NFR/CON, and ledger targets must match the requirement-evidence sidecar bidirectionally.
23. If extraction is materially wrong before integration, mark the intake `rejected` or `superseded`, append a wiki audit log entry, and rerun ingestion instead of preserving known-bad extraction as a correction note.
24. If extraction has minor usable issues, keep the intake and record extraction warnings in `intake-report.md`.
25. If a previous intake was generated with full document text embedded in `extracted.md` or `chunks.json` and it caused context overflow before integration, mark it `superseded` or remove the failed intake and rerun ingestion with the current script.
26. When the source came from `.project-wiki/sources/inbox/`, update `sources/SOURCE_REGISTRY.yml` and `sources/INDEX.md` after ingestion.

## Review Helper Commands

Hints are machine metadata, not semantic decisions or an exclusion filter. `inspect` returns validated structure and aggregate state; `view` emits the complete selected text with provenance markers.

Review progress states:

- `pending`: not yet examined.
- `reviewed`: examined but not given a final disposition; still incomplete.
- `classified`: final disposition recorded with one or more semantic classifications. After integration, include every registered target wiki ID produced or updated from that chunk.
- `skipped`: deliberately excluded after reading the chunk; `notes` must explain why.

The helper computes completion from final dispositions and matching counts; the validator enforces it for `reviewed`/`integrated` intakes and requires registered targets for integrated classifications.

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

Use the compact ISO-week [Wiki Audit Log Workflow](./common-policies.md#wiki-audit-log-workflow), retaining required intake audit evidence. Logging is mandatory in both paths:

- Direct path: log the integrated KB update once.
- Review path: log creation of pending `review.md`, then log final integration, rejection, or postponement separately.

`review.md` should include only the canonical scope affected by the blocking decision, while remaining evidence-linked. Keep non-blocking follow-up questions, missing source material, assumptions, and conflicts in their durable OQ, alert, or canonical records rather than using them to widen the approval gate.

For direct integration, define the Atomic Requirement Decomposition Plan before canonical authoring. If a blocking decision changes topic scope or permitted ranges, include the affected plan rows in `review.md` and finalize the complete plan after approval. Persist exact record-to-chunk edges in `traceability/requirement-evidence.yml`. An intake cannot become `integrated` while requirement decomposition is described as future work.

## review.md Template

When a blocking review is required, use the [Document Intake Review template](../assets/intake-source-templates.md#document-intake-review). Do not treat a pending `review.md` or its unapproved choice as canonical project knowledge.


## Implementation Details

Consult this section for extraction troubleshooting, artifact compatibility, or helper development. Ordinary intake follows the operational workflow above.

### Transactional Publication

The script creates one temporary source snapshot while calculating its SHA-256, verifies the optional preflight hash against those exact bytes, and uses that snapshot for both extraction and `--copy-source`. It verifies that neither the snapshot nor original source changed before publication, then writes all generated artifacts to a hidden staging directory under `intake/documents/`. It validates the required files and chunk manifest before atomically renaming the staging directory to the final `DOCIN-*` path.

The intake index is also replaced atomically. If artifact generation, validation, publication, or index update fails, the script removes staged output and rolls back a newly published intake document. Existing intake IDs are never overwritten and produce a concise CLI error.

### Structure-Preserving Chunking

Headings start a new chunk and retain their section label. Within a chunk, source line breaks remain line breaks and separate extracted blocks remain separated by a blank line. The word limit may split an oversized block, but it must not flatten the preserved text structure inside each resulting segment.

DOCX extraction processes top-level paragraphs and tables in their document order. Table rows retain line boundaries, and tables inherit the current heading when they belong to a named section.

### Generated Artifacts

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

### Chunk JSON

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
