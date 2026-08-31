# Project Wiki Update Workflows

Use these workflows for notes, source documents, document intake, durable answers, and open-question reconciliation. Runtime paths, artifacts, generated values, and lifecycle contracts come from `schema/project-wiki.yml`.

## Update Workflow

Use this mode when the user pastes meeting minutes, documents, task notes, or planning conversation into chat.

1. Check `.project-wiki/sources/inbox/` for new source files, even when the user also pasted notes in chat.
2. If source files are present, run [Source Inbox Workflow](#source-inbox-workflow) first.
3. If the update includes an explicit PDF, DOCX, text, or Markdown document path or an attachment with a retrievable local path, run [Document Intake Workflow](#document-intake-workflow) for that path. Do not read PDF/DOCX source documents directly into model context.
4. Classify each useful pasted note, reviewed source item, or reviewed document item into one or more buckets: requirement, change request, technical decision, technical documentation, implementation work item, open question, glossary term, or status update.
5. Run [Open Questions Reconciliation](#open-questions-reconciliation-workflow) before creating new open questions.
6. Determine whether the note modifies the original plan. If yes, create or update a lightweight `CR-YYYYMMDD-###` record under `changes/requests/`.
7. If the note records a technical decision with meaningful alternatives or consequences, create or update an `ADR-####` under `changes/decisions/`.
8. If the note describes implemented behavior, observed code behavior, or code structure, update the relevant file under `technical/` instead of burying it in a CR or requirement. Put the note in requirements only when it states business or product intent.
9. If the note introduces a future task, create or update a `WI-YYYYMMDD-###` work item under `implementation/work-items/`.
10. Link every new record to related IDs and source paths when known.
11. Store every confirmed `REQ-*` or `NFR-*` in a project-specific topic file under `requirements/functional/` or `requirements/non-functional/`; even small projects use at least one concise topic. Keep all requirements indexes routing-only. Store constraints as `CON-*` records in `requirements/constraints.md`.
12. Update `changes/CHANGELOG.md` with a concise dated entry for each meaningful change.
13. Update traceability maps whenever the note affects requirements, architecture, modules, APIs, data, integrations, tests, deployment, or security.
14. Update `REGISTRY.yml`, relevant section indexes, `sources/SOURCE_REGISTRY.yml` when source files were processed, and `STATUS.md`.
15. Append a wiki audit entry to `logs/wiki-log-YYYY-MM.md` with the source note type and changed documents.
16. Report what was updated and list any unresolved ambiguities as open questions.

## Source Inbox Workflow

Use this workflow at the start of every `update`.

The checker derives `process`, `skip`, and `review` actions from the source workflow contract in `schema/project-wiki.yml`; apply the returned action rather than reproducing that mapping in agent reasoning.

1. Ensure `.project-wiki/sources/INDEX.md`, `.project-wiki/sources/SOURCE_REGISTRY.yml`, and source folders exist: `inbox/`, `processed/`, `rejected/`, and `ignored/`.
2. Treat `sources/INDEX.md` as the human guide for the source area. Do not create guide files inside `sources/inbox/`.
3. Run the deterministic preflight before registering or ingesting any inbox file: `python3 /path/to/project-wiki/scripts/check_inbox.py --wiki-root .project-wiki --format json --quarantine-skips`.
4. If the checker exits non-zero, stop inbox processing and report the registry, intake-history, hash, or filesystem error. Do not ingest files while duplicate history is missing, incomplete, invalid, or changed during preflight.
5. Treat the checker report as authoritative for supported-file discovery, housekeeping exclusions, SHA-256 calculation, validated historical hash matches across `SOURCE_REGISTRY.yml` and complete intake artifacts, retry-record selection, byte-identical duplicates within the current inbox, and duplicate quarantine destinations. Do not independently recompute or semantically infer these facts.
6. Apply report actions mechanically:
   - `process` with reason `new-unique`: add one `pending` entry to `SOURCE_REGISTRY.yml` with a stable `SRC-YYYYMMDD-NNN` ID and the reported SHA-256.
   - `process` with reason `registered-pending` or `registered-failed`: reuse only `selected_registry_id`; do not create a second source record. Set a retried `failed` entry back to `pending` before ingestion.
   - `skip`: do not register another pending source and do not run ingestion. With `--quarantine-skips`, the checker revalidates each hash and moves the redundant file to the reported `quarantined_to` path under `sources/ignored/`; the agent only records the result in `sources/INDEX.md`.
   - `review` with reason `historical-path-with-new-content`: do not ingest automatically. Determine whether the content is a new version, an accidental overwrite, or an explicit reprocessing request. Create a new source record or supersede history only after that semantic decision.
   - `review` with reason `ambiguous-processable-history`: do not choose a registry record heuristically. Reconcile the duplicate `pending` or `failed` records before rerunning preflight.
7. When the user explicitly requests reprocessing of a file classified `skip`, treat that request as an override, preserve the previous registry history, and record the reason for the new intake. Do not weaken the default duplicate check.
8. Run [Document Intake Workflow](#document-intake-workflow) only for files authorized by a `process` action or an explicitly resolved `review`/reprocessing override. For every inbox file, pass the report hash to ingestion as `--expected-sha256 <sha256>` so changed content cannot be processed under an earlier preflight decision.
9. After successful ingestion, move the file to `.project-wiki/sources/processed/YYYY-MM/`, then mark the source as `processed` with `processed_at`, the generated `DOCIN-*` intake ID, the archived `current_path`, and the same SHA-256 recorded by the intake. A processed record is invalid unless archived bytes, registry hash, and intake provenance agree.
10. If ingestion fails, mark the source as `failed` with the error summary and leave it in `inbox/` unless the user asks to move it.
11. Update `sources/INDEX.md` with `pending`, `processed`, `failed`, `rejected`, `ignored`, `superseded`, and review-required source summaries.
12. Continue the normal `update` flow using the generated intake reports and any pasted chat notes.

The preflight is read-only by default. `--quarantine-skips` is the only mutating mode: it rechecks hashes and transactionally moves files classified `skip` to `sources/ignored/`; it never changes `SOURCE_REGISTRY.yml`. The agent remains responsible for source record lifecycle updates, but it must not duplicate the checker's byte-level reasoning or choose among ambiguous records.

## Document Intake Workflow

Use this workflow when `update` receives an external PDF, DOCX, text, or Markdown document.

1. Load `./references/document-ingestion.md` before running the intake script.
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
13. Run [Open Questions Reconciliation](#open-questions-reconciliation-workflow) before proposing new open questions from document findings.
14. When integrating requirements from document findings, define the atomic topic plan before canonical authoring and use the record locations and requirement-evidence sidecar contract from [Wiki structure](./wiki-structure.md#requirements-topic-scaling).
15. Keep intake documents as provenance only. Do not treat intake content as canonical project knowledge until it is integrated into the KB.
16. Do not consult `integrated`, `archived`, `superseded`, or `rejected` intake documents during normal coding tasks unless the user asks for provenance, audit, or conflict investigation.
17. Apply [Document-Based Update Gating](#document-based-update-gating). Continue with direct conservative integration unless a blocking, auditable human decision prevents canonical representation.
18. On the direct path, write each planned REQ/NFR/CON in its topic file, record every record-to-chunk edge in `traceability/requirement-evidence.yml`, and preserve non-blocking uncertainty through OQ, alerts, status, confidence, blocked records, or explicit alternatives.
19. On the blocking path, create `review.md` focused only on the exact decision, evidence, options, affected canonical scope, and consequences. After approval, resume this integration once; do not create another review gate for the same decision.
20. Before setting intake status to `reviewed` or `integrated`, run `inspect` again and require `review_status: complete`, then run `review_progress.py audit`. Require `audit_status: review-complete` and retain its ledger summary and SHA-256.
21. After any ledger correction, rerun `audit`. Immediately before changing the intake to a terminal status, run `audit --expect-ledger-sha256 <final-ledger-sha256>` using the latest digest; a mismatch requires another audit. Copy the final audit status, ledger summary, and SHA-256 into the wiki log.
22. Reconcile ledger summary counts and run `validate_wiki.py`. Deterministic errors block completion; audit candidates do not. For `integrated`, every requirement-classified chunk must target at least one registered atomic REQ/NFR/CON, and ledger targets must match the requirement-evidence sidecar bidirectionally.
23. If extraction is materially wrong before integration, mark the intake `rejected` or `superseded`, append a wiki audit log entry, and rerun ingestion instead of preserving known-bad extraction as a correction note.
24. If extraction has minor usable issues, keep the intake and record extraction warnings in `intake-report.md`.
25. If a previous intake was generated with full document text embedded in `extracted.md` or `chunks.json` and it caused context overflow before integration, mark it `superseded` or remove the failed intake and rerun ingestion with the current script.
26. When the source came from `.project-wiki/sources/inbox/`, update `sources/SOURCE_REGISTRY.yml` and `sources/INDEX.md` after ingestion.

## Document-Based Update Gating

Use this rule when `update` processes an external document such as PDF, DOCX, extracted text, or a long pasted specification.

Apply [Direct Integration vs Blocking Review](./document-ingestion.md#direct-integration-vs-blocking-review). An explicit `update` request authorizes conservative integration by default. Create `review.md` only when an auditable human decision is required and status, confidence, OQ, alerts, blocked records, or preserved alternatives cannot represent the uncertainty safely.

Document size, density, number of findings, cross-section impact, security/privacy/compliance subject matter, OQ, alerts, or ADR candidates do not trigger review by themselves. A gate must identify the exact blocking question and cannot cap review coverage or atomic decomposition.

Logging is mandatory: direct integration gets one wiki audit entry; review creation and the final approved, rejected, or postponed outcome are logged separately. Do not treat pending `review.md` content as canonical project knowledge until the user approves integration.

## Durable Answer Filing Workflow

Use this workflow when a user question or agent answer creates durable project knowledge. Do not file every answer into the wiki.

File an answer back into the wiki only when it creates lasting value, such as a stable tradeoff analysis, cross-module impact map, requirement clarification, resolved open question, risk analysis, or meaningful connection between requirements, CRs, ADRs, technical docs, and source paths.

1. Decide whether the answer belongs in an existing canonical file. If yes, update that file instead of creating a new analysis page.
2. If the answer is useful but non-canonical or exploratory, create or update `analysis/AN-YYYYMMDD-NNN-short-title.md`.
3. Every analysis page must link to related requirements, CRs, ADRs, technical docs, alerts, work items, intake records, or source paths. Do not create isolated analysis pages.
4. If the answer resolves an open question, update `requirements/open-questions.md` and link the evidence.
5. If the answer identifies a significant risk or contradiction, create or update an alert.
6. Update `analysis/INDEX.md`, `REGISTRY.yml`, `STATUS.md` when relevant, and `logs/wiki-log-YYYY-MM.md`.
7. Do not file routine chat answers, generic explanations, transient debugging notes, duplicated content, or unapproved speculation.

## Open Questions Reconciliation Workflow

Run this workflow whenever new information arrives through `update`, document intake, `scan`, `sync`, automatic post-implementation wiki updates, durable answer filing, or `maintain`.

Reconcile existing open questions before creating new ones.

1. Read `requirements/open-questions.md` and relevant open alerts.
2. Compare new information against existing open questions and related requirements, CRs, ADRs, technical docs, intake records, analysis pages, and traceability maps.
3. For each affected open question, choose one outcome:
   - `resolved`: the new information answers the question.
   - `partially-resolved`: part of the question is answered; narrow the remaining question.
   - `superseded`: the question is replaced by a newer requirement, CR, ADR, or question.
   - `dismissed`: the question is no longer relevant.
   - `duplicate`: merge it into another open question.
   - `still-open`: no meaningful change.
4. Update `requirements/open-questions.md` with status, updated date, resolution or narrowed question, evidence links, and related IDs.
5. If reconciliation affects requirements, CRs, ADRs, technical docs, alerts, or traceability, update those files too.
6. Create new open questions only after existing questions have been reconciled and de-duplicated.
7. If an unresolved question represents a significant risk, contradiction, blocking gap, or dangerous assumption, create or update an alert.
8. Update `REGISTRY.yml`, relevant indexes, `STATUS.md`, and traceability when files changed.
9. If reconciliation changes any wiki file, append a wiki audit entry to `logs/wiki-log-YYYY-MM.md`. If the workflow only checks questions and makes no changes, do not log unless the user explicitly requested an audit trail.