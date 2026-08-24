# Project Wiki Structure

The canonical machine-readable contract is [`schema/project-wiki.yml`](../schema/project-wiki.yml). This reference explains the responsibilities, linking rules, and lifecycle policies behind that contract. Create the full structure for every project; unused files may remain empty with `status: placeholder` until they become useful.

## Contract Routing

Use [`schema/project-wiki.yml`](../schema/project-wiki.yml) for exact tree entries, frontmatter fields, document types, status domains, confidence values, ID patterns, generated values, and artifact names. This reference explains the meaning and lifecycle of those structures without duplicating their complete machine-readable definitions.

## Root Files

`INDEX.md` is the agent routing map. Keep it short. It should answer: "What should I open for this task?"

`WIKI_VERSION.yml` records the project wiki schema version currently applied to this repository. `maintain` uses it to detect and migrate older wiki structures.

`REGISTRY.yml` is the structured catalog of documents, IDs, tags, status, source paths, and relationships.

`STATUS.md` records the current state of the project wiki: active work, recent changes, blockers, stale areas, and the last scan.

`PROJECT.md` stores project identity, goals, stakeholders, domain context, success criteria, and global constraints.

`GLOSSARY.md` stores domain terms, abbreviations, naming conventions, and ambiguous vocabulary.

## Schema Versioning

Every project wiki must include `.project-wiki/WIKI_VERSION.yml`.

Use the complete [WIKI_VERSION.yml template](../assets/core-templates.md#wiki_versionyml). Exact schema values come from the machine-readable manifest.

During `maintain`, compare `schema_version` with the current schema version declared in this reference. If the file is missing, treat the wiki as `pre-versioned` and run Schema Migration Workflow. Migration must preserve existing content and log changes.

## Section Responsibilities

`requirements/` preserves the original and current product intent: product brief, functional requirements, non-functional requirements, constraints, and open questions.

Product intent comes from explicit business, user, stakeholder, meeting, issue, ticket, chat, or imported requirements sources. Implemented behavior discovered in code belongs in `technical/` unless an explicit source confirms it as a requirement. Unconfirmed code-inferred requirements belong in `requirements/open-questions.md`, not in functional or non-functional requirement files. Requirement files must not store observed implementation facts, technical constraints, concerns, or candidate-area lists merely because they look requirement-like.

`functional-requirements.md` and `non-functional-requirements.md` are overview/routing files by default. Small projects may keep requirements directly in them, while larger projects may add project-specific topic files under `functional/` and `non-functional/`.

`changes/` preserves lightweight historical changes after the initial plan: change requests, additional requirements, scope shifts, and architectural decisions.

`technical/` documents what has actually been implemented or observed in the code: architecture, codebase map, modules, APIs, data, integrations, testing, deployment, and security. Keep overview files concise and create or update focused docs under the existing technical folders when an implemented area needs more detail.

`implementation/` tracks active implementation plans, work items, and scan reports.

`traceability/` links requirements, changes, decisions, technical docs, implementation notes, and source paths.

`analysis/` stores durable, non-canonical synthesis produced from meaningful user questions or agent analysis. Prefer updating existing canonical docs when the information belongs there. Use one analysis page per durable synthesis and keep `analysis/INDEX.md` as routing only. Every analysis page must link to related wiki records or source paths.

`maintenance/` stores semantic lint and wiki health reports. These reports may identify contradictions, stale claims, orphan pages, missing source material, risky assumptions, and suggested follow-up questions.

Deterministic structural health is checked by `scripts/validate_wiki.py` before semantic lint. The validator owns canonical tree, YAML/JSON, frontmatter, ID, status, registry, path, link, anchor, and intake-manifest checks. Agent-assisted maintenance owns meaning-dependent judgments such as contradictions, implicit requirements, stale claims, meaningful backlinks, traceability adequacy, orphan concepts, risky assumptions, and missing source material.

`alerts/` stores active and resolved warning records for significant gaps, conflicts, risks, and inconsistencies. Alerts are not deleted when resolved; they are closed with resolution evidence.

`intake/` stores external documents imported during `update` workflows. It is provenance and staging, not canonical project knowledge. Intake content becomes canonical only after the accepted information is integrated into requirements, changes, technical docs, implementation docs, or traceability maps.

`sources/` stores raw source documents for document-based `update` workflows. Users can drop new PDF, DOCX, text, or Markdown files into `sources/inbox/`; the agent processes unprocessed files from there using the document ingestion script. Source files are raw input, not canonical project knowledge.

Use `sources/inbox/` only as a drop zone for real source documents. Human instructions belong in `sources/INDEX.md`, not in `sources/inbox/README.md`. Agents must ignore inbox housekeeping files such as `README.md`, `.gitkeep`, `.DS_Store`, hidden files, files beginning with `_`, and temporary or partial download files.

`logs/` stores an append-only audit trail of meaningful knowledge base edits. It records what wiki files changed, why they changed, which mode caused the change, and which source material or code paths were involved.

`templates/` contains project-local templates copied from the skill template pack and adjusted for the project if needed.

## Requirements Topic Scaling

Requirements use progressive topic splitting. Do not predefine product areas or create speculative requirement topic files.

Use `requirements/functional-requirements.md` and `requirements/non-functional-requirements.md` as overview/routing files. For small projects, they may contain requirements directly.

When a stable project-specific requirement topic accumulates enough related requirements that an overview becomes noisy, create a dedicated topic file under `requirements/functional/` or `requirements/non-functional/`, move the related requirements there, leave a concise routing summary in the overview, and update `requirements/INDEX.md`, `REGISTRY.yml`, and traceability maps.

Create a topic file only when it improves retrieval, reduces context load, or clarifies ownership/traceability. Do not apply this splitting policy to `technical/`, `implementation/`, `traceability/`, `glossary/`, `changes/`, `alerts/`, `logs/`, `sources/`, or `intake/` by default; those sections already have their own structure.

Functional and non-functional overview files should use the same structure when requirements are still unconfirmed: current state, routing to relevant `technical/` docs and `open-questions.md`, then a placeholder note. Do not add `Candidate Areas Requiring Confirmation` sections to either overview file.

## Always-On Instruction Files

During `init` and `scan`, create or update one repository-level always-on instruction file outside `.project-wiki/`.

Use `.github/copilot-instructions.md` when the current agent is GitHub Copilot or VS Code Copilot.

Use `AGENTS.md` at the repository root for Claude Code, Codex, or any non-Copilot agent.

Do not create both files unless the user explicitly asks for both instruction targets. If the agent family is unclear, ask before writing.

Preserve existing content in these files. Insert or replace only the block delimited by `<!-- PROJECT-WIKI:BEGIN -->` and `<!-- PROJECT-WIKI:END -->`.

The always-on block must be written in English and must instruct future agents to consult and maintain `.project-wiki/` automatically.

## Document Frontmatter

Every non-index wiki document should start with YAML frontmatter.

```yaml
---
id: DOC-000
type: note
status: active
title: Short title
created: YYYY-MM-DD
updated: YYYY-MM-DD
tags: []
related: []
source_paths: []
confidence: confirmed
---
```

Default document statuses are `active`, `draft`, `placeholder`, `superseded`, `deprecated`, `blocked`, and `resolved`.

Alert records use `open`, `resolved`, `dismissed`, or `accepted-risk`.

Open question records use `open`, `partially-resolved`, `resolved`, `superseded`, `dismissed`, or `duplicate`.

Allowed `confidence` values: `confirmed`, `inferred`, `unknown`.

Use `confidence: inferred` for scan results that come from code structure but have not been validated by project owners. Use `confidence: unknown` when a topic is intentionally present but undocumented.

## ID Conventions

Use stable IDs and never reuse deleted IDs. Exact regexes, examples, embedded-record families, and generation settings live under `id_patterns`, `id_examples`, and `id_generation` in [`schema/project-wiki.yml`](../schema/project-wiki.yml).

```text
REQ-001      Functional requirement
CR-YYYYMMDD-001  Change request
ADR-0001     Architecture decision record
DOCIN-YYYYMMDD-001  Document intake record
WLOG-YYYYMMDD-001  Wiki audit log entry
```

Filename IDs should match the frontmatter ID for standalone records such as CRs, ADRs, work items, and scans.

## Linking Rules

- Use relative Markdown links inside `.project-wiki/`.
- Link from indexes to documents, from documents to related documents, and from traceability maps to all relevant records.
- Prefer links to wiki docs over links directly to source files when the wiki doc explains the code area.
- Store source file or directory references in `source_paths` and traceability maps.
- Keep backlinks when the relationship is important for future implementation work.

Good relationship chain:

```text
REQ-012 -> CR-20260715-001 -> ADR-0004 -> technical/modules/billing.md -> src/billing/
```

## REGISTRY.yml Shape

Keep registry entries compact and machine-friendly.

```yaml
version: 1
updated: YYYY-MM-DD
documents:
  - id: REQ-001
    type: requirement
    title: User authentication
    path: requirements/functional/<project-topic>.md#req-001
    status: active
    tags: [auth, security]
    related: [ADR-0001, CR-20260715-001]
    source_paths: [src/auth/]
    confidence: confirmed
  - id: NFR-001
    type: non-functional-requirement
    title: Availability target
    path: requirements/non-functional/<project-topic>.md#nfr-001
    status: active
    tags: [availability]
    related: []
    source_paths: []
    confidence: confirmed
```

For files that contain multiple IDs, registry paths may point to anchors. For one-record-per-file documents, paths should point to the file.

For stable embedded-record anchors, place an explicit lowercase HTML anchor immediately before the record heading and use that fragment in `REGISTRY.yml`:

```markdown
<a id="req-001"></a>

## REQ-001 - User authentication
```

```yaml
path: requirements/functional/authentication.md#req-001
```

The deterministic validator verifies that a registry fragment exists and identifies the same record ID, rather than merely another anchor in the file.

## INDEX.md Routing Standard

Root `INDEX.md` must include:

- Project wiki purpose in one paragraph.
- Current project status link.
- Task routing table: requirement work, document intake, alerts, analysis, maintenance lint, change analysis, code modification, API work, data work, testing, deployment, security, and project scan.
- Section index links.
- Registry link.
- Last updated date.

Each section `INDEX.md` must include:

- What this section contains.
- When an agent should read this section.
- Links to the most important files.
- Known placeholders or stale areas.

## Document Intake Policy

`intake/` stores document extraction artifacts for provenance. Do not route normal coding tasks into intake documents.

Status values are defined in the schema manifest. Use [Document ingestion](./document-ingestion.md#intake-status) for lifecycle meaning, extraction, chunk review, and direct-update vs `review.md` rules.

## Source Document Policy

`sources/` is the drop zone and archive for raw source documents used by document-based updates.

```text
sources/inbox/      new files waiting to be processed
sources/processed/  files already ingested, grouped by month
sources/rejected/   files that should not be integrated
sources/ignored/    files intentionally skipped
```

Use `SOURCE_REGISTRY.yml` with the deterministic `scripts/check_inbox.py` preflight to avoid duplicate processing. Track source ID, status, original path, current path, filename, SHA-256 hash, related intake ID, processed date, tags, and notes. The preflight cross-checks registry entries with complete intake history, so stale source status does not silently authorize reingestion. Byte-identical duplicate classification, retry-record selection, and skip quarantine are script responsibilities; semantic review is required only when a historical path contains new bytes, processable registry history is ambiguous, or the user explicitly requests reprocessing.

A `processed` source record must include a valid `processed_at` date and `intake_id`. Its archived `current_path` bytes, registry SHA-256, intake `source-info.yml`, and intake `chunks.json` source hash must agree. The validator and inbox preflight fail closed when this provenance chain is incomplete or inconsistent.

Source status values are defined in the schema manifest. Use [Source Inbox Workflow](./update-workflows.md#source-inbox-workflow) for their operational transitions, discovery, processing, movement, and registry updates.

## Durable Analysis Policy

Use `analysis/AN-YYYYMMDD-NNN-short-title.md` for meaningful non-canonical synthesis that should remain discoverable. Every analysis page must link to related requirements, CRs, ADRs, technical docs, alerts, work items, intake documents, or source paths. Use [Durable Answer Filing Workflow](./update-workflows.md#durable-answer-filing-workflow) for filing rules.

## Alert Policy

Use alerts for significant warning conditions, not every suggested question.

Allowed alert severity values:

```text
critical  can cause wrong implementation, compliance/security risk, data loss, or major architectural error
high      blocks or distorts an important feature or decision
medium    significant ambiguity that is manageable but should be resolved
low       minor issue worth tracking
```

Alert lifecycle:

```text
open -> resolved
open -> dismissed
open -> accepted-risk
```

Use [Alert Workflow](./maintenance-workflows.md#alert-workflow) for creation and resolution rules.

## Suggested Discovery Policy

Suggested follow-up questions, missing source material, and risky assumptions are discovery aids, not automatic tasks. Use [Semantic Lint Workflow](./maintenance-workflows.md#semantic-lint-workflow) and [Document ingestion](./document-ingestion.md#direct-update-vs-reviewmd) for promotion rules.

## Open Questions Policy

Open questions are durable records. Do not delete them when answered. Close, narrow, supersede, dismiss, or merge them with evidence. Reconcile existing open questions before creating new ones.

Allowed outcomes:

```text
open                no answer yet
partially-resolved  partly answered; remaining question narrowed
resolved            answered with evidence
superseded          replaced by a newer requirement, CR, ADR, or question
dismissed           no longer relevant
duplicate           merged into another open question
```

Each open question entry should include:

- Stable `OQ-*` ID.
- Status.
- Created and updated dates.
- Related requirements, CRs, ADRs, alerts, intake docs, analysis pages, or source paths.
- The current question.
- Current context.
- Resolution or partial resolution notes.
- Resolution evidence when applicable.

Use [Open Questions Reconciliation Workflow](./update-workflows.md#open-questions-reconciliation-workflow) for update and logging rules.

## Wiki Audit Log

`logs/wiki-log-YYYY-MM.md` records changes to the knowledge base itself. It is separate from `changes/CHANGELOG.md`.

```text
changes/CHANGELOG.md = what changed in the project
logs/wiki-log-YYYY-MM.md = what changed in the knowledge base
```

Append one entry after every meaningful wiki update. Do not log purely mechanical timestamp-only edits unless they are part of a larger operation.

Use this parseable heading format:

```markdown
## [YYYY-MM-DD] mode | WLOG-YYYYMMDD-NNN | Summary
```

Each audit log entry should include:

- Stable log ID.
- Date.
- Agent or actor when known.
- Mode: `init`, `scan`, `update`, `sync`, `maintain`, or `auto-post-implementation`.
- Trigger or source material.
- Changed wiki documents.
- Related source paths when relevant.
- Related requirement, CR, ADR, work item, scan, or sync IDs when relevant.
- Summary.
- Open questions or unresolved uncertainty.
- Open question reconciliation results when relevant: resolved, partially resolved, superseded, dismissed, duplicated, and newly created `OQ-*` IDs.

## Placeholder Policy

When creating the full structure for a new or scanned project, keep unused files with one short placeholder block:

```markdown
---
id: TECH-SECURITY
type: technical
status: placeholder
title: Security
created: YYYY-MM-DD
updated: YYYY-MM-DD
tags: [security]
related: []
source_paths: []
confidence: unknown
---

# Security

No project-specific security documentation has been captured yet.
```

## Quality Rules

- Run `scripts/validate_wiki.py --wiki-root .project-wiki --format json` during every `maintain` after schema migration and before semantic lint.
- Treat deterministic validator findings as authoritative structural facts; repair and rerun instead of reproducing those checks through model reasoning.
- Keep root and section indexes concise.
- Do not duplicate long explanations across files; link instead.
- When new notes conflict with existing wiki content, preserve history and record the change rather than silently rewriting the past.
- When a document becomes outdated, mark it `superseded` or update it with a dated note.
- Every meaningful change request should appear in `changes/CHANGELOG.md` and `REGISTRY.yml`.
