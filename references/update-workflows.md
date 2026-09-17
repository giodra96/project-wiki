# Project Wiki Update Workflows

Use these workflows for notes and durable answers; document intake and reconciliation route to their focused references. Machine contracts come from `schema/project-wiki.yml`.

## Update Workflow

Use this mode when the user pastes meeting minutes, documents, task notes, or planning conversation into chat.

1. Check `.project-wiki/sources/inbox/` for new source files, even when the user also pasted notes in chat.
2. If source files are present, run [Source Inbox Workflow](./source-inbox.md#source-inbox-workflow) first.
3. If the update includes an explicit PDF, DOCX, text, or Markdown document path or an attachment with a retrievable local path, run [Document Intake Workflow](#document-intake-workflow) for that path. Do not read PDF/DOCX source documents directly into model context.
4. Classify each useful pasted note, reviewed source item, or reviewed document item into one or more buckets: requirement, change request, technical decision, technical documentation, implementation work item, open question, glossary term, or status update.
5. Run [Open Questions Reconciliation](./common-policies.md#open-questions-reconciliation-workflow) before creating new open questions.
6. Determine whether the note modifies the original plan. If yes, create or update a lightweight `CR-YYYYMMDD-###` record under `changes/requests/`.
7. If the note records a technical decision with meaningful alternatives or consequences, create or update an `ADR-####` under `changes/decisions/`.
8. If the note describes implemented behavior, observed code behavior, or code structure, update the relevant file under `technical/` instead of burying it in a CR or requirement. Put the note in requirements only when it states business or product intent.
9. If the note introduces a future task, create or update a `WI-YYYYMMDD-###` work item under `implementation/work-items/`.
10. Link every new record to related IDs and source paths when known.
11. Store every confirmed `REQ-*` or `NFR-*` in a project-specific topic file under `requirements/functional/` or `requirements/non-functional/`; even small projects use at least one concise topic. Keep all requirements indexes routing-only. Store constraints as `CON-*` records in `requirements/constraints.md`.
12. Update `changes/CHANGELOG.md` with a concise dated entry for each meaningful change.
13. Update traceability maps whenever the note affects requirements, architecture, modules, APIs, data, integrations, tests, deployment, or security.
14. Update `REGISTRY.yml`, relevant section indexes, `sources/SOURCE_REGISTRY.yml` when source files were processed, and `STATUS.md`.
15. Record the update using [Wiki Audit Log Workflow](./common-policies.md#wiki-audit-log-workflow).
16. Report what was updated and list any unresolved ambiguities as open questions.

## Source Inbox Workflow

Run [Source Inbox Workflow](./source-inbox.md#source-inbox-workflow) at the start of every `update`; its checker owns duplicate decisions and hash-bound ingestion.

## Document Intake Workflow

Follow [Document Ingestion](./document-ingestion.md) for the complete extraction, review, integration, and finalization procedure. Generated provenance includes `source-info.yml`, `extracted.md`, `chunks.json`, `chunks/`, `intake-report.md`, and `review-progress.yml`; `review.md` is conditional on a blocking decision.

Before setting intake status to `reviewed` or `integrated`, require `audit_status: review-complete`, the ledger summary, and its SHA-256. After any ledger correction, rerun `audit`; immediately before terminal status mutation use `audit --expect-ledger-sha256 <final-ledger-sha256>` and retain the evidence in the wiki log.

## Document-Based Update Gating

An explicit `update` request authorizes conservative integration by default. For external documents or long pasted specifications, apply [Direct Integration vs Blocking Review](./document-ingestion.md#direct-integration-vs-blocking-review), which owns blocking decisions and mandatory logging.

## Durable Answer Filing Workflow

Use this workflow when a user question or agent answer creates durable project knowledge. Do not file every answer into the wiki.

File an answer back into the wiki only when it creates lasting value, such as a stable tradeoff analysis, cross-module impact map, requirement clarification, resolved open question, risk analysis, or meaningful connection between requirements, CRs, ADRs, technical docs, and source paths.

1. Decide whether the answer belongs in an existing canonical file. If yes, update that file instead of creating a new analysis page.
2. If the answer is useful but non-canonical or exploratory, create or update `analysis/AN-YYYYMMDD-NNN-short-title.md`.
3. Every analysis page must link to related requirements, CRs, ADRs, technical docs, alerts, work items, intake records, or source paths. Do not create isolated analysis pages.
4. If the answer resolves an open question, update `requirements/open-questions.md` and link the evidence.
5. If the answer identifies a significant risk or contradiction, create or update an alert.
6. Update `analysis/INDEX.md`, `REGISTRY.yml`, and `STATUS.md` when relevant; log the meaningful knowledge update using [Wiki Audit Log Workflow](./common-policies.md#wiki-audit-log-workflow).
7. Do not file routine chat answers, generic explanations, transient debugging notes, duplicated content, or unapproved speculation.

## Open Questions Reconciliation Workflow

Use [Open Questions Reconciliation Workflow](./common-policies.md#open-questions-reconciliation-workflow) whenever new information arrives, before creating new questions.
