# Project Wiki Intake And Source Templates

Use these templates for source provenance, intake routing, and document review approval.

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
- For large documents, read `intake-report.md`, `chunks.json`, and `review-progress.yml`, then process every manifest chunk in batches. Hints prioritize order but do not exclude chunks.
- Do not mark an intake reviewed or integrated until the ledger is complete. Every classified integrated chunk must link to its registered target IDs; every skipped chunk needs a reason.
- Do not read integrated, archived, superseded, or rejected intake documents during normal coding tasks unless explicitly requested.
- Use canonical KB files, not intake documents, as the source of truth after integration.

## Active Intake Documents

- None yet.

## Reviewed, Integrated, Archived, Superseded, Or Rejected Documents

- None yet.
```

## Document Intake Review

Write this template to `review.md` inside the intake document directory when qualitative review gating requires approval.

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

## Review Decision Needed

TBD

## Proposed Canonical KB Updates

| Candidate | Proposed Target | Action | Rationale |
| --- | --- | --- | --- |
| DOCIN-YYYYMMDD-001-CH-001 | requirements/functional/<project-topic>.md or requirements/non-functional/<project-topic>.md | Add requirement | TBD |

## Potential Conflicts With Current KB Or As-Is State

- TBD

## Open Questions

- TBD

## Existing Open Questions Reconciled

| Open Question | Outcome | Evidence | Notes |
| --- | --- | --- | --- |
| OQ-001 | resolved | DOCIN-YYYYMMDD-001-CH-001 | TBD |

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

- TBD

## Approval Outcome

Pending user confirmation.
```