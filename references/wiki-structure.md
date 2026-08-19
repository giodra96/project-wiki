# Project Wiki Structure

Current schema version: `1.3.0`.

This reference defines the canonical `.project-wiki/` structure. Create the full structure for every project; unused files may remain empty with `status: placeholder` until they become useful.

## Canonical Tree

```text
.project-wiki/
  INDEX.md
  WIKI_VERSION.yml
  REGISTRY.yml
  STATUS.md
  PROJECT.md
  GLOSSARY.md

  requirements/
    INDEX.md
    product-brief.md
    functional-requirements.md
    non-functional-requirements.md
    functional/
      <project-topic>.md
    non-functional/
      <project-topic>.md
    constraints.md
    open-questions.md

  changes/
    INDEX.md
    CHANGELOG.md
    requests/
      CR-YYYYMMDD-001-short-title.md
    decisions/
      ADR-0001-short-title.md

  technical/
    INDEX.md
    architecture.md
    codebase-map.md
    modules/
      module-name.md
    api/
      api-name.md
    data/
      data-model.md
    integrations/
      integration-name.md
    testing.md
    deployment.md
    security.md

  implementation/
    INDEX.md
    current-plan.md
    work-items/
      WI-YYYYMMDD-001-short-title.md
    scans/
      scan-YYYYMMDD.md
      sync-YYYYMMDD-001.md

  traceability/
    INDEX.md
    requirement-map.md
    change-impact-map.md
    code-map.md

  analysis/
    INDEX.md
    AN-YYYYMMDD-001-short-title.md

  maintenance/
    INDEX.md
    lint-YYYYMMDD.md
    schema-migration-YYYYMMDD.md

  alerts/
    INDEX.md
    ALERT-YYYYMMDD-001-short-title.md

  intake/
    INDEX.md
    documents/
      DOCIN-YYYYMMDD-001/
        source-info.yml
        extracted.md
        chunks.json
        chunks/
          CH-001.md
        intake-report.md
        review.md

  sources/
    INDEX.md
    SOURCE_REGISTRY.yml
    inbox/
    processed/
      YYYY-MM/
    rejected/
    ignored/

  logs/
    INDEX.md
    wiki-log-YYYY-MM.md

  templates/
    requirement.md
    change-request.md
    adr.md
    module-doc.md
    api-doc.md
    analysis.md
    alert.md
    source-index.md
    source-registry.yml
    document-intake-index.md
    document-intake-review.md
    maintenance-lint.md
    schema-migration.md
    scan-report.md
    sync-report.md
    work-item.md
    wiki-log.md
```

## Root Files

`INDEX.md` is the agent routing map. Keep it short. It should answer: "What should I open for this task?"

`WIKI_VERSION.yml` records the project wiki schema version currently applied to this repository. `maintain` uses it to detect and migrate older wiki structures.

`REGISTRY.yml` is the structured catalog of documents, IDs, tags, status, source paths, and relationships.

`STATUS.md` records the current state of the project wiki: active work, recent changes, blockers, stale areas, and the last scan.

`PROJECT.md` stores project identity, goals, stakeholders, domain context, success criteria, and global constraints.

`GLOSSARY.md` stores domain terms, abbreviations, naming conventions, and ambiguous vocabulary.

## Schema Versioning

Every project wiki must include `.project-wiki/WIKI_VERSION.yml`.

```yaml
schema: project-wiki
schema_version: 1.3.0
schema_updated: 2026-07-23
last_migrated: YYYY-MM-DD
maintained_by_skill: project-wiki
notes: Current schema applied.
```

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

Allowed `status` values: `active`, `draft`, `placeholder`, `superseded`, `deprecated`, `blocked`, `resolved`.

Alert records may also use `open`, `dismissed`, or `accepted-risk`.

Open question records may use `open`, `partially-resolved`, `resolved`, `superseded`, `dismissed`, or `duplicate`.

Allowed `confidence` values: `confirmed`, `inferred`, `unknown`.

Use `confidence: inferred` for scan results that come from code structure but have not been validated by project owners. Use `confidence: unknown` when a topic is intentionally present but undocumented.

## ID Conventions

Use stable IDs and never reuse deleted IDs.

```text
REQ-001      Functional requirement
NFR-001      Non-functional requirement
REQ-TOPIC-YYYYMMDD-001  Requirement topic document
CON-001      Constraint
OQ-001       Open question
CR-YYYYMMDD-001  Lightweight change request or scope change
ADR-0001     Architecture decision record
MOD-001      Module documentation
API-001      API documentation
DATA-001     Data model documentation
INT-001      Integration documentation
AN-YYYYMMDD-001  Durable non-canonical analysis
ALERT-YYYYMMDD-001  Active or resolved alert
DOCIN-YYYYMMDD-001  Document intake record
DOCIN-YYYYMMDD-001-CH-001  Document intake chunk
SRC-YYYYMMDD-001  Raw source document record
WI-YYYYMMDD-001  Work item
SCAN-YYYYMMDD    Codebase scan report
SYNC-YYYYMMDD-001  Manual code change synchronization report
LINT-YYYYMMDD  Semantic maintenance lint report
MIGRATION-YYYYMMDD  Schema migration report
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

Allowed intake statuses:

```text
active      imported and not fully reviewed
reviewed    review.md exists and awaits user decision
integrated  accepted content has been merged into the canonical KB
archived    retained only for provenance
superseded  replaced by a newer source document
rejected    not relevant, not accepted, or invalid as a source
```

Use [Document ingestion](./document-ingestion.md) for extraction, chunk review, direct-update vs `review.md`, and intake lifecycle rules.

## Source Document Policy

`sources/` is the drop zone and archive for raw source documents used by document-based updates.

```text
sources/inbox/      new files waiting to be processed
sources/processed/  files already ingested, grouped by month
sources/rejected/   files that should not be integrated
sources/ignored/    files intentionally skipped
```

Use `SOURCE_REGISTRY.yml` to avoid duplicate processing. Track source ID, status, original path, current path, filename, SHA-256 hash, related intake ID, processed date, tags, and notes.

Allowed source statuses:

```text
pending     discovered in inbox but not yet processed
processed   ingested and linked to a DOCIN-* record
failed      ingestion failed
rejected    source is invalid or should not be used
ignored     intentionally skipped
superseded  replaced by a newer source
```

Use [Source Inbox Workflow](./workflows.md#source-inbox-workflow) for discovery, processing, movement, and registry updates.

## Durable Analysis Policy

Use `analysis/AN-YYYYMMDD-NNN-short-title.md` for meaningful non-canonical synthesis that should remain discoverable. Every analysis page must link to related requirements, CRs, ADRs, technical docs, alerts, work items, intake documents, or source paths. Use [Durable Answer Filing Workflow](./workflows.md#durable-answer-filing-workflow) for filing rules.

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

Use [Alert Workflow](./workflows.md#alert-workflow) for creation and resolution rules.

## Suggested Discovery Policy

Suggested follow-up questions, missing source material, and risky assumptions are discovery aids, not automatic tasks. Use [Semantic Lint Workflow](./workflows.md#semantic-lint-workflow) and [Document ingestion](./document-ingestion.md#direct-update-vs-reviewmd) for promotion rules.

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

Use [Open Questions Reconciliation Workflow](./workflows.md#open-questions-reconciliation-workflow) for update and logging rules.

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

- Keep root and section indexes concise.
- Do not duplicate long explanations across files; link instead.
- When new notes conflict with existing wiki content, preserve history and record the change rather than silently rewriting the past.
- When a document becomes outdated, mark it `superseded` or update it with a dated note.
- Every meaningful change request should appear in `changes/CHANGELOG.md` and `REGISTRY.yml`.
