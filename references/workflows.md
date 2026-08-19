# Project Wiki Workflows

Use these workflows after loading `SKILL.md`. All outputs target `.project-wiki/` in the current repository.

Current project wiki schema version: `1.3.0`.

## Mode Selection

Choose exactly one primary mode for explicit wiki-management requests. Context lookup before code work is automatic and is not a user-facing mode.

| Mode | Use When |
| --- | --- |
| `init` | Starting a new project or creating an empty wiki before code exists. |
| `scan` | A repository already contains meaningful code and needs an initial wiki. |
| `update` | The user provides meeting minutes, documents, chat notes, planning notes, or new requirements. |
| `sync` | Code changed outside the agent chat flow and the wiki must be reconciled with the current repository state. |
| `maintain` | Cleaning indexes, fixing links, refreshing registry entries, semantic lint, alert review, and stale wiki areas. |

## Automatic Context Preflight

Run this automatically whenever `.project-wiki/INDEX.md` exists and the user asks to implement, modify, debug, refactor, test, document, or plan code. The user should not need to invoke a separate `consult` mode.

1. Read `.project-wiki/INDEX.md` first.
2. Use the routing table to identify the smallest relevant section.
3. Read the section `INDEX.md`, then only the linked documents needed for the task.
4. If the needed context is missing, read `REGISTRY.yml` and traceability maps before broad code search.
5. Summarize only the wiki facts that affect the task, then proceed with the requested work.
6. If implementation changes invalidate wiki content, update the wiki as part of the same task.

Skip this preflight only when the task is unrelated to the project wiki and unrelated to code or project behavior, or when `.project-wiki/INDEX.md` does not exist yet.

## Automatic Post-Implementation Wiki Update

Run this automatically after source code changes made by the agent through chat. The user should not need to invoke `sync` for agent-made changes.

1. Identify which source paths changed and which wiki records were consulted before implementation.
2. Document implemented or changed behavior under `technical/`, especially module, API, data, integration, testing, deployment, and security docs. Use overview files such as `architecture.md` and `codebase-map.md` as routing/summaries; create or update focused technical docs under the existing technical folders when an implemented area needs its own documentation.
3. Update implementation docs when the change affects active plans, work items, or scan notes.
4. Update traceability maps when source paths now implement, modify, or invalidate requirements, CRs, ADRs, or technical docs.
5. Run Open Questions Reconciliation when the implementation clarifies previously unresolved behavior.
6. Update `REGISTRY.yml`, relevant section indexes, and `STATUS.md`.
7. If the implementation introduced behavior not already represented by a requirement or CR, do not turn it into a confirmed product requirement by assumption. Document observed behavior in `technical/`; create a lightweight CR only when the change reflects a confirmed product or scope change, otherwise record an inferred open question when product intent needs confirmation.
8. Append a wiki audit entry to `logs/wiki-log-YYYY-MM.md` when wiki files changed.
9. In the final response, mention the wiki files updated alongside the code changes.

## Always-On Project Instruction Bootstrap

Install this during `init` and `scan` so future coding tasks consult and update `.project-wiki/` even when the user does not explicitly invoke this skill.

1. Detect the current agent family.
2. If the agent is GitHub Copilot or VS Code Copilot, create or update `.github/copilot-instructions.md`.
3. If the agent is not Copilot, create or update `AGENTS.md` at the repository root.
4. Do not create both files unless the user explicitly asks for both Copilot and non-Copilot instruction targets.
5. If the agent family is unclear, ask the user which instruction target to use before writing the always-on file.
6. Preserve existing file content. Do not overwrite unrelated instructions.
7. Insert or replace only the block delimited by `<!-- PROJECT-WIKI:BEGIN -->` and `<!-- PROJECT-WIKI:END -->`.
8. The block must instruct agents to read `.project-wiki/INDEX.md` before source code changes, update the wiki after agent-made source code changes, use `sync` for manual or external code changes, log meaningful wiki edits, write all wiki content in English, and respond to the user in the user's chat language.
9. Include the created or updated instruction file in `logs/wiki-log-YYYY-MM.md`.

## Init Workflow

1. Create the full `.project-wiki/` tree from [Wiki structure](./wiki-structure.md).
2. Create all root files, `WIKI_VERSION.yml`, section indexes, traceability maps, sources, logs, and local templates.
3. Create or update the always-on project instruction file using the Always-On Project Instruction Bootstrap.
4. Mark unknown or unused documents as `status: placeholder` and `confidence: unknown`.
5. Ask for or extract only the minimum project identity needed for `PROJECT.md`: name, goal, domain, stakeholders, success criteria, constraints.
6. Initialize `REGISTRY.yml` with root docs, placeholders, and any captured requirements.
7. Initialize `STATUS.md` with current state, next documentation steps, and open questions.
8. Append an initial wiki audit entry to `logs/wiki-log-YYYY-MM.md`.
9. Keep requirements separate from future changes; do not create CR files for the initial plan unless the user explicitly describes a change from an earlier baseline.

## Scan Existing Project Workflow

1. Read `.project-wiki/INDEX.md` if it exists. If no wiki exists, inspect the repository narrowly first: root files, package/build config, source tree, tests, entrypoints, API routes, data schemas, deployment files, and README/docs.
2. Create the full `.project-wiki/` tree if missing, including `WIKI_VERSION.yml`.
3. If an older wiki exists, run Schema Migration Workflow before generating new scan artifacts.
4. Create or update the always-on project instruction file using the Always-On Project Instruction Bootstrap.
5. Write `implementation/scans/scan-YYYYMMDD.md` with findings grouped by confirmed, inferred, and unknown.
6. Populate `technical/codebase-map.md` with the repository structure, main entrypoints, framework conventions, test commands if discoverable, and important source paths.
7. Populate `technical/architecture.md` with a concise architecture overview. Mark unverified architectural claims as `confidence: inferred`.
8. Create or update module docs under `technical/modules/` for major bounded areas only. Avoid documenting every file.
9. Update `technical/api/`, `technical/data/`, and `technical/integrations/` only when the codebase exposes clear APIs, schemas, or external services.
10. Fill requirements only when they are explicitly stated in product-intent sources such as README files, product docs, issue or ticket descriptions, imported requirements documents, meeting notes, or user-provided notes.
   - Use `requirements/functional-requirements.md` and `requirements/non-functional-requirements.md` as overview/routing files by default.
   - Create project-specific requirement topic files only when stable requirement areas are explicitly present and splitting improves retrieval or traceability.
   - Do not turn implemented behavior into confirmed product requirements by assumption; document observed behavior in `technical/`, and if it appears to imply product intent without an explicit source, record an inferred open question instead.
   - Do not store observed implementation facts, technical constraints, concerns, candidate behavior, or candidate-area lists inferred from code in functional or non-functional requirement files; document them in `technical/` and capture product-intent uncertainty as inferred open questions in `requirements/open-questions.md`.
   - Do not create `Candidate Areas Requiring Confirmation` sections in functional or non-functional requirement overview files.
11. Run Open Questions Reconciliation before adding new open questions from scan findings.
12. Update `traceability/code-map.md` to connect major wiki docs to source directories.
13. Add evidence-supported suggested follow-up questions, missing source material items, and risky assumptions to the scan report when they matter to implementation, scope, risk, or decision-making. Keep the report readable by grouping, splitting, or promoting important findings instead of dropping them.
14. Create alerts for significant scan findings that represent real risk, contradiction, blocking gaps, or dangerous assumptions.
15. Update root and section indexes, `REGISTRY.yml`, and `STATUS.md` with a compact discovery summary and links to detailed reports.
16. Append a wiki audit entry to `logs/wiki-log-YYYY-MM.md` listing generated and updated wiki documents, including the always-on project instruction file.

## Update Workflow

Use this mode when the user pastes meeting minutes, documents, task notes, or planning conversation into chat.

1. Check `.project-wiki/sources/inbox/` for new source files, even when the user also pasted notes in chat.
2. If source files are present, run Source Inbox Workflow first.
3. If the update includes an explicit PDF, DOCX, text, or Markdown document path or an attachment with a retrievable local path, run Document Intake Workflow for that path. Do not read PDF/DOCX source documents directly into model context.
4. Classify each useful pasted note, reviewed source item, or reviewed document item into one or more buckets: requirement, change request, technical decision, technical documentation, implementation work item, open question, glossary term, or status update.
5. Run Open Questions Reconciliation before creating new open questions.
6. Determine whether the note modifies the original plan. If yes, create or update a lightweight `CR-YYYYMMDD-###` record under `changes/requests/`.
7. If the note records a technical decision with meaningful alternatives or consequences, create or update an `ADR-####` under `changes/decisions/`.
8. If the note describes implemented behavior, observed code behavior, or code structure, update the relevant file under `technical/` instead of burying it in a CR or requirement. Put the note in requirements only when it states business or product intent.
9. If the note introduces a future task, create or update a `WI-YYYYMMDD-###` work item under `implementation/work-items/`.
10. Link every new record to related IDs and source paths when known.
11. Place requirements in overview files for small or early projects. When a stable project-specific topic accumulates enough related requirements that an overview becomes noisy, create or update a topic file under `requirements/functional/` or `requirements/non-functional/`, move the related requirements there, and leave a routing summary in the overview.
12. Update `changes/CHANGELOG.md` with a concise dated entry for each meaningful change.
13. Update traceability maps whenever the note affects requirements, architecture, modules, APIs, data, integrations, tests, deployment, or security.
14. Update `REGISTRY.yml`, relevant section indexes, `sources/SOURCE_REGISTRY.yml` when source files were processed, and `STATUS.md`.
15. Append a wiki audit entry to `logs/wiki-log-YYYY-MM.md` with the source note type and changed documents.
16. Report what was updated and list any unresolved ambiguities as open questions.

## Source Inbox Workflow

Use this workflow at the start of every `update`.

1. Ensure `.project-wiki/sources/INDEX.md`, `.project-wiki/sources/SOURCE_REGISTRY.yml`, and source folders exist: `inbox/`, `processed/`, `rejected/`, and `ignored/`.
2. Treat `sources/INDEX.md` as the human guide for the source area. Do not create guide files inside `sources/inbox/`.
3. List files in `.project-wiki/sources/inbox/` with supported extensions: `.pdf`, `.docx`, `.txt`, `.md`, `.markdown`.
4. Ignore housekeeping files before registration: `README.md`, `.gitkeep`, `.DS_Store`, hidden files, files beginning with `_`, and temporary or partial download files such as `*.tmp`, `*.part`, and `*.download`.
5. Do not add ignored housekeeping files to `SOURCE_REGISTRY.yml` and do not run document ingestion for them.
6. For each discovered source file, compute or record its SHA-256 hash and check `SOURCE_REGISTRY.yml` for an existing matching hash or path.
7. Skip files already marked `processed`, `ignored`, `rejected`, or `superseded` unless the user explicitly asks to reprocess them.
8. Add new files to `SOURCE_REGISTRY.yml` with status `pending` and a stable `SRC-YYYYMMDD-NNN` ID.
9. Run Document Intake Workflow for each pending source file.
10. After successful ingestion, mark the source as `processed`, link it to the generated `DOCIN-*` intake ID, and move the file to `.project-wiki/sources/processed/YYYY-MM/` when possible.
11. If ingestion fails, mark the source as `failed` with the error summary and leave it in `inbox/` unless the user asks to move it.
12. Update `sources/INDEX.md` with pending, processed, failed, rejected, ignored, and superseded source summaries.
13. Continue the normal `update` flow using the generated intake reports and any pasted chat notes.

## Document Intake Workflow

Use this workflow when `update` receives an external PDF, DOCX, text, or Markdown document.

1. Load `./references/document-ingestion.md` before running the intake script.
2. Never read external PDF/DOCX source documents directly into model context. Use a local file path and let the script extract text.
3. If the user provides only an attachment and no local path is available, ask the user to place the document in the workspace and provide the path.
4. Run the script from the target repository root with the skill script path, for example: `python3 /path/to/project-wiki/scripts/ingest_document.py <document-path> --wiki-root .project-wiki`.
5. If PDF or DOCX dependencies are missing, install them from `./scripts/requirements.txt` or ask the user before proceeding if package installation is not allowed.
6. The script must create `.project-wiki/intake/INDEX.md` and `.project-wiki/intake/documents/DOCIN-YYYYMMDD-NNN/` with `source-info.yml`, `extracted.md`, `chunks.json`, `chunks/`, and `intake-report.md`.
7. Do not generate or expect `signals.json` in V1. Lightweight extraction hints live inside `chunks.json` and are summarized in `intake-report.md`.
8. Treat `extracted.md` and `chunks.json` as lightweight routing files. The ingestion script must not generate monolithic full-text artifacts.
9. Do not load every chunk file for large documents at once.
10. Read `intake-report.md`, then open necessary files under `chunks/` based on chunk IDs, hints, previews, or user focus. For integration requests, process chunks in batches until all relevant document information has been classified.
11. Compare candidate document items against `.project-wiki/INDEX.md`, `REGISTRY.yml`, relevant requirements, changes, technical docs, implementation docs, and traceability maps.
12. Run Open Questions Reconciliation before proposing new open questions from document findings.
13. When integrating requirements from document findings, use requirement topic scaling from [Wiki structure](./wiki-structure.md#requirements-topic-scaling).
14. Keep intake documents as provenance only. Do not treat intake content as canonical project knowledge until it is integrated into the KB.
15. Do not consult `integrated`, `archived`, `superseded`, or `rejected` intake documents during normal coding tasks unless the user asks for provenance, audit, or conflict investigation.
16. Apply Document-Based Update Gating before modifying canonical KB files.
17. If extraction is materially wrong before integration, mark the intake `rejected` or `superseded`, append a wiki audit log entry, and rerun ingestion instead of preserving known-bad extraction as a correction note.
18. If extraction has minor usable issues, keep the intake and record extraction warnings in `intake-report.md`.
19. If a previous intake was generated with full document text embedded in `extracted.md` or `chunks.json` and it caused context overflow before integration, mark it `superseded` or remove the failed intake and rerun ingestion with the current script.
20. When the source came from `.project-wiki/sources/inbox/`, update `sources/SOURCE_REGISTRY.yml` and `sources/INDEX.md` after ingestion.

## Document-Based Update Gating

Use this rule when `update` processes an external document such as PDF, DOCX, extracted text, or a long pasted specification.

Apply the qualitative direct-update vs review rules from [Document ingestion](./document-ingestion.md#direct-update-vs-reviewmd). In short: integrate clear, low-risk information directly; create `review.md` only for significant, ambiguous, risky, conflicting, authority-unclear, or materially cross-section updates.

Review gating controls approval and auditability. It must not cap the relevant source items proposed for integration, and it should not create repeated review gates for routine items that can be safely integrated and logged.

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

## Sync Workflow

Use this mode when code was changed manually, by another tool, or outside the current agent chat flow. `sync` is not the same as `maintain`: sync reconciles wiki content with code reality; maintain audits wiki structure and consistency.

1. Read `.project-wiki/INDEX.md`, `REGISTRY.yml`, `STATUS.md`, and `technical/codebase-map.md` if present.
2. Identify changed source paths since the last documented scan or since the user's stated baseline. Prefer git status, git diff, recent files, or user-provided paths when available.
3. Inspect only the changed source areas and their nearest tests/configuration.
4. Update affected technical docs under `technical/` to reflect current code behavior.
5. Update `traceability/code-map.md` and any relevant requirement or change impact maps.
6. Run Open Questions Reconciliation when manual code changes clarify or invalidate existing questions.
7. Create a scan or sync note under `implementation/scans/` when the reconciliation is non-trivial, marking uncertain conclusions as `confidence: inferred`.
8. Update `REGISTRY.yml`, relevant section indexes, and `STATUS.md` with the sync result and any stale or unresolved areas.
9. Append a wiki audit entry to `logs/wiki-log-YYYY-MM.md` with the baseline, inspected source paths, and changed wiki documents.
10. Do not invent requirements from code changes. If manual code appears to change product behavior, record an open question or create a lightweight CR only when the user confirms it is an intended scope change.

## Maintain Workflow

Use this mode to keep the wiki healthy. `maintain` includes structural cleanup and semantic lint.

1. Run Schema Migration Workflow.
2. Check root and section indexes for broken, stale, or missing links.
3. Check `REGISTRY.yml` for missing paths, duplicate IDs, invalid statuses, and stale `updated` dates.
4. Check whether new CRs, ADRs, module docs, or work items are represented in traceability maps.
5. Run Open Questions Reconciliation to close, narrow, supersede, dismiss, or de-duplicate stale questions when evidence supports it.
6. Run Semantic Lint Workflow.
7. Review open alerts and update alert status when evidence supports resolution, dismissal, or accepted risk.
8. Compact verbose index content by moving detail into the appropriate document.
9. Mark stale documents as `superseded`, `deprecated`, or `placeholder` rather than deleting history.
10. Apply low-risk fixes directly. For high-impact contradictions, stale claims, alert resolutions, or canonical meaning changes, write the lint finding and ask for user confirmation before changing canonical docs.
11. Update `STATUS.md` with maintenance results, active alert counts, open question counts, schema version status, and compact discovery summary links.
12. Append a wiki audit entry to `logs/wiki-log-YYYY-MM.md` summarizing repaired or flagged wiki issues.

## Schema Migration Workflow

Use this workflow during `maintain` and when `scan` finds an existing `.project-wiki/` that may not match the current schema.

1. Read `.project-wiki/WIKI_VERSION.yml` if it exists. If it is missing, treat the wiki as `pre-versioned`.
2. Compare the recorded schema version with the current project wiki schema version `1.3.0`.
3. If the schema is current, record that no schema migration was needed and continue normal maintenance.
4. If the schema is older or missing, create or update `.project-wiki/maintenance/schema-migration-YYYYMMDD.md` with planned and applied migration actions.
5. Preserve existing content. Do not delete or overwrite user/project-authored files during schema migration.
6. Create missing canonical directories and placeholder files from [Wiki structure](./wiki-structure.md), including `sources/`, `analysis/`, `maintenance/`, `alerts/`, monthly `logs/`, and local templates.
7. Create or update `.project-wiki/WIKI_VERSION.yml` to the current schema version after migration actions are applied.
8. Ensure `sources/SOURCE_REGISTRY.yml` exists and uses version `1`.
9. Ensure logs use monthly `logs/wiki-log-YYYY-MM.md` convention. If old yearly logs exist, migrate entries only when headings are parseable; otherwise leave them in place, mark them legacy, and report the issue.
10. Detect old intake artifacts where `extracted.md` or `chunks.json` contains full document text. Do not read those files. Mark the intake as `superseded` or report that it should be regenerated with the current script before review.
11. Update the always-on instruction block using the Always-On Project Instruction Bootstrap.
12. Update root and section indexes, `REGISTRY.yml`, `STATUS.md`, and `logs/INDEX.md` to reflect the migrated structure.
13. Ask for user confirmation before risky migration actions such as moving large source files, splitting ambiguous legacy logs, deleting old intake directories, or changing canonical meaning.
14. Append a monthly wiki audit log entry describing the schema migration.

## Semantic Lint Workflow

Create or update `.project-wiki/maintenance/lint-YYYYMMDD.md` during `maintain`.

Check for:

- Broken links and missing backlinks.
- Registry entries missing IDs, paths, statuses, tags, or relationships.
- Requirements without traceability.
- CRs or ADRs not reflected in requirements, technical docs, or traceability maps.
- Technical docs without source paths.
- Contradictions between requirements, CRs, ADRs, technical docs, intake reviews, and as-is code.
- Stale claims superseded by newer CRs, ADRs, scans, sync reports, or source documents.
- Orphan pages with no meaningful inbound links.
- Important concepts mentioned repeatedly but lacking a canonical page.
- Open questions that are stale, blocking, or already resolved.
- Open questions that can be closed, narrowed, superseded, dismissed, or de-duplicated based on current evidence.
- Missing source material and risky assumptions.

Report sections should include:

- Structural Fixes Applied.
- Structural Issues Requiring Review.
- Contradictions.
- Stale Claims.
- Traceability Gaps.
- Orphan Pages.
- Suggested Follow-Up Questions.
- Missing Source Material.
- Risky Assumptions.
- Alert Candidates.

Keep suggested follow-up questions, missing source material, and risky assumptions concise without using a fixed target count. Every item must include why it matters and related docs or evidence. When many evidence-supported items are important, group related findings or promote confirmed questions to `requirements/open-questions.md` and significant risks, contradictions, blocking gaps, or dangerous assumptions to alerts.

## Alert Workflow

Use alerts for significant warning conditions. Do not create alerts for every suggested question.

Create or update `alerts/ALERT-YYYYMMDD-NNN-short-title.md` when a scan, update, document review, sync, maintain pass, or code task finds a meaningful risk, contradiction, blocking gap, undocumented assumption, or inconsistency that could cause incorrect requirements, architecture, implementation, security, compliance, data handling, or project planning.

Alert statuses:

```text
open
resolved
dismissed
accepted-risk
```

Alert severities:

```text
critical
high
medium
low
```

When resolving an alert:

1. Read the alert and related docs.
2. Update canonical KB files, traceability, registry, and status as needed.
3. Set alert status to `resolved`, `dismissed`, or `accepted-risk`.
4. Add resolution date, resolution summary, and resolution evidence links.
5. Move the alert from open to resolved/dismissed/accepted-risk section in `alerts/INDEX.md`.
6. Append a wiki audit entry.

Do not delete resolved alerts.

## Wiki Audit Log Workflow

Use the audit log to track knowledge base edits, not project scope changes. `changes/CHANGELOG.md` records project history; `logs/wiki-log-YYYY-MM.md` records wiki maintenance history.

1. Ensure `logs/INDEX.md` and the current monthly `logs/wiki-log-YYYY-MM.md` exist.
2. Append one entry after every meaningful wiki update.
3. Use the parseable heading format: `## [YYYY-MM-DD] mode | WLOG-YYYYMMDD-NNN | Summary`.
4. Include log ID, date, agent or actor when known, mode, trigger, changed wiki documents, related source paths, related IDs, summary, and open questions.
5. Open question reconciliation entries should list resolved, partially resolved, superseded, dismissed, duplicated, and newly created `OQ-*` IDs when applicable.
6. Keep entries concise. Link to detailed CRs, ADRs, scan reports, sync reports, lint reports, alerts, analysis pages, or technical docs instead of duplicating them.
7. Do not rewrite older log entries except to fix broken formatting or links. Add a new corrective entry when history needs clarification.

## Language Policy

1. Write all `.project-wiki/` documents in English.
2. Write generated always-on instruction blocks in English.
3. Write templates, logs, CRs, ADRs, technical docs, scan reports, and sync reports in English.
4. Reply to the user in chat using the language used by the user, unless the user explicitly requests another language.
5. If source material is provided in another language, extract and normalize the project knowledge into English while preserving important domain terms.

## Change Request Rules

Change requests are intentionally agile and lightweight. They should capture what changed, why it matters, and what it affects.

A CR is needed when:

- A requirement changes after the initial baseline.
- A new requirement appears after the initial baseline.
- Scope, priority, deadline, assumption, or constraint changes.
- A meeting or document changes planned behavior.

A CR is not needed when:

- The agent is documenting the initial project plan.
- A small technical note only clarifies existing implementation.
- The change is purely editorial in the wiki.

## Post-Update Checklist

After any non-trivial wiki update, verify:

- New or changed docs have frontmatter.
- IDs are stable and unique.
- Related docs link both ways when useful.
- `REGISTRY.yml` contains all new records.
- Root and section indexes route to the new docs.
- `STATUS.md` reflects current active work and unresolved questions.
- Existing open questions were reconciled before creating new ones when new information arrived.
- Requirement files contain only confirmed or explicitly sourced product intent; observed implementation facts, technical constraints, concerns, candidate behavior, and code-inferred candidate areas are documented in `technical/` and linked to inferred open questions when product intent needs confirmation.
- Requirement overview files route to topic files when topic splitting was used; `REGISTRY.yml` paths point to the final requirement anchors.
- Traceability maps changed when requirements, CRs, ADRs, technical docs, or source paths changed.
- `logs/wiki-log-YYYY-MM.md` records what changed in the knowledge base and why.
- Generated or updated project wiki content is written in English, while the chat response uses the user's language.
