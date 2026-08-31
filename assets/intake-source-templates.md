# Project Wiki Intake And Source Templates

Use these templates for source provenance, intake routing, and blocking decision review.

## SOURCE_REGISTRY.yml

```yaml
version: 1
updated: YYYY-MM-DD
sources: []
```

Example entry:

```yaml
  - id: SRC-YYYYMMDD-001
    status: processed
    original_path: sources/inbox/client-requirements.pdf
    current_path: sources/processed/YYYY-MM/client-requirements.pdf
    filename: client-requirements.pdf
    sha256: "..."
    intake_id: DOCIN-YYYYMMDD-001
    processed_at: YYYY-MM-DD
    tags: [requirements]
    notes: "Imported during update workflow."
```

## Sources INDEX.md

```markdown
# Sources

This section stores raw source documents used by document-based update workflows. Source documents are raw input, not canonical project knowledge.

## How To Use

- Drop new PDF, DOCX, text, or Markdown files into [inbox/](./inbox/).
- Run `/project-wiki update`.
- The agent runs the project-wiki deterministic inbox preflight with skip quarantine, registers only files classified `process` in [SOURCE_REGISTRY.yml](./SOURCE_REGISTRY.yml), runs document ingestion, and moves successfully processed files to `processed/YYYY-MM/` when possible.
- Keep human instructions in this file. Do not create `README.md` or other guide files inside `inbox/`.

## Routing Rules

- Never read PDF/DOCX source files directly into model context.
- Use source files only through the document ingestion script.
- Treat the inbox preflight report as authoritative for SHA-256 hashes, validated registry and intake-history matches, retry-record selection, inbox duplicates, and quarantine destinations; use agent review only for changed content at a historical path, ambiguous registry history, or explicit reprocessing.
- Use `intake/` artifacts for review and canonical KB integration.
- Ignore inbox housekeeping files such as `README.md`, `.gitkeep`, `.DS_Store`, hidden files, files beginning with `_`, and temporary or partial download files.

## Inbox

- No pending source files registered yet.

## Processed Sources

- None yet.

## Failed, Rejected, Ignored, Or Superseded Sources

- None yet.
```

## Intake INDEX.md

```markdown
# Document Intake

This section stores external source documents imported for project-wiki update workflows. Intake documents are provenance, not canonical project knowledge until accepted information is integrated into requirements, changes, technical docs, implementation docs, or traceability maps.

## When To Read

- Process a new PDF, DOCX, text, or Markdown requirements document.
- Review the source provenance behind a requirement, CR, ADR, or open question.
- Investigate conflicts between an imported document and the current KB or as-is technical state.

## Routing Rules

- Read active and reviewed intake documents only when working on document-based updates, provenance, audits, or conflict investigation.
- Read the compact `intake-report.md`, then use `review_progress.py inspect` for structure and coverage. Do not load `chunks.json`, `review-progress.yml`, or generated chunk wrappers directly unless troubleshooting.
- Use `view --section SEC-NNN` only for reliable source-defined sections reported by `inspect`; review every listed section and unsectioned unit. Use `view --all` whenever structure is absent, incomplete, ambiguous, or full-document context may matter.
- After complete coverage, run `review_progress.py audit`; require `review-complete` and record its ledger summary and SHA-256. Rerun after ledger corrections.
- Before a terminal intake status, run `audit --expect-ledger-sha256 <final-ledger-sha256>` with the digest from the reviewed audit.
- Do not mark an intake reviewed or integrated until the ledger is complete. Every classified integrated chunk must link to its registered target IDs; every skipped chunk needs a reason.
- Do not read integrated, archived, superseded, or rejected intake documents during normal coding tasks unless explicitly requested.
- Use canonical KB files, not intake documents, as the source of truth after integration.

## Active Intake Documents

- None yet.

## Reviewed, Integrated, Archived, Superseded, Or Rejected Documents

- None yet.
```

## Document Intake Review

Write this template to `review.md` only when canonical integration requires a blocking, auditable human decision. Keep the review focused on that decision rather than restating the complete source.

```markdown
---
id: DOCIN-YYYYMMDD-001-REVIEW
type: intake-review
status: reviewed
title: Review - Source Document Title
created: YYYY-MM-DD
updated: YYYY-MM-DD
tags: [intake, review]
related: [DOCIN-YYYYMMDD-001]
source_paths: []
confidence: inferred
---

# Document Intake Review - Source Document Title

## Review Coverage

- Ledger: [review-progress.yml](./review-progress.yml)
- Total chunks: TBD
- Classified: TBD
- Skipped with reason: TBD
- Pending or reviewed: 0
- Validator result: passed

## Blocking Decision Needed

- Exact question: TBD
- Why conservative integration cannot proceed: TBD
- Approval authority: TBD

## Options And Consequences

| Option | Canonical Effect | Risks Or Trade-Offs | Evidence |
| --- | --- | --- | --- |
| TBD | TBD | TBD | TBD |

## Affected Canonical Scope

| Candidate | Proposed Target | Action | Rationale |
| --- | --- | --- | --- |
| DOCIN-YYYYMMDD-001-CH-001 | requirements/functional/<project-topic>.md or requirements/non-functional/<project-topic>.md | Add requirement | TBD |

## Affected Atomic Requirement Plan

Include this section only when the blocking decision changes requirement topic scope, target files, or permitted ID ranges. Complete the full decomposition plan after approval and before canonical authoring.

| Family | Topic | Target File | Reserved IDs | Planned Atomic Records | Evidence Chunks |
| --- | --- | --- | --- | ---: | --- |
| functional | Authentication | requirements/functional/authentication.md | REQ-001..REQ-005 | 5 | DOCIN-YYYYMMDD-001-CH-001, DOCIN-YYYYMMDD-001-CH-002 |
| non-functional | Security | requirements/non-functional/security.md | NFR-001..NFR-003 | 3 | DOCIN-YYYYMMDD-001-CH-003 |

## Related Durable Records

- Open questions, alerts, blocked records, or alternatives that preserve non-blocking uncertainty: TBD

## Approval Outcome

Pending user confirmation.
```