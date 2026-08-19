# Project Wiki Document Templates

Use these templates when creating `.project-wiki/` files. Replace placeholders with project-specific values and keep frontmatter fields compact.

## Root INDEX.md

```markdown
# Project Wiki Index

This wiki stores the project knowledge base for requirements, changes, technical documentation, implementation state, and traceability. Use this file as the routing entrypoint; open only the linked files needed for the current task.

Last updated: YYYY-MM-DD

## Current State

- Status: [STATUS.md](./STATUS.md)
- Project brief: [PROJECT.md](./PROJECT.md)
- Registry: [REGISTRY.yml](./REGISTRY.yml)

## Task Routing

| Task | Start Here |
| --- | --- |
| Understand project goals | [PROJECT.md](./PROJECT.md), [requirements/INDEX.md](./requirements/INDEX.md) |
| Work with requirements | [requirements/INDEX.md](./requirements/INDEX.md), [traceability/requirement-map.md](./traceability/requirement-map.md) |
| Process meeting notes or new docs | [changes/INDEX.md](./changes/INDEX.md), [implementation/INDEX.md](./implementation/INDEX.md) |
| Process external requirements document | [sources/INDEX.md](./sources/INDEX.md), [intake/INDEX.md](./intake/INDEX.md), [changes/INDEX.md](./changes/INDEX.md), [requirements/INDEX.md](./requirements/INDEX.md) |
| Review active alerts | [alerts/INDEX.md](./alerts/INDEX.md), [STATUS.md](./STATUS.md) |
| Review durable analyses | [analysis/INDEX.md](./analysis/INDEX.md) |
| Run wiki maintenance lint | [maintenance/INDEX.md](./maintenance/INDEX.md) |
| Analyze change impact | [changes/CHANGELOG.md](./changes/CHANGELOG.md), [traceability/change-impact-map.md](./traceability/change-impact-map.md) |
| Modify code | [technical/codebase-map.md](./technical/codebase-map.md), [traceability/code-map.md](./traceability/code-map.md) |
| Work on architecture | [technical/architecture.md](./technical/architecture.md), [changes/decisions/](./changes/decisions/) |
| Work on APIs | [technical/api/](./technical/api/) |
| Work on data | [technical/data/](./technical/data/) |
| Work on tests | [technical/testing.md](./technical/testing.md) |
| Work on deployment | [technical/deployment.md](./technical/deployment.md) |
| Work on security | [technical/security.md](./technical/security.md) |
| Review active work | [implementation/current-plan.md](./implementation/current-plan.md), [implementation/work-items/](./implementation/work-items/) |
| Sync manual code changes | [technical/codebase-map.md](./technical/codebase-map.md), [traceability/code-map.md](./traceability/code-map.md), [implementation/scans/](./implementation/scans/) |
| Review wiki audit history | [logs/INDEX.md](./logs/INDEX.md) |

## Sections

- [Requirements](./requirements/INDEX.md)
- [Changes](./changes/INDEX.md)
- [Technical Documentation](./technical/INDEX.md)
- [Implementation](./implementation/INDEX.md)
- [Traceability](./traceability/INDEX.md)
- [Analysis](./analysis/INDEX.md)
- [Maintenance](./maintenance/INDEX.md)
- [Alerts](./alerts/INDEX.md)
- [Sources](./sources/INDEX.md)
- [Document Intake](./intake/INDEX.md)
- [Wiki Audit Log](./logs/INDEX.md)
```

## REGISTRY.yml

```yaml
version: 1
updated: YYYY-MM-DD
documents: []
```

## WIKI_VERSION.yml

```yaml
schema: project-wiki
schema_version: 1.3.0
schema_updated: 2026-07-23
last_migrated: YYYY-MM-DD
maintained_by_skill: project-wiki
notes: Current schema applied.
```

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

## Always-On Project Instruction Block

Use this block during `init` and `scan`.

For GitHub Copilot or VS Code Copilot, create or update `.github/copilot-instructions.md`.

For Claude Code, Codex, or any non-Copilot agent, create or update `AGENTS.md` at the repository root.

Do not create both files unless the user explicitly asks for both instruction targets. If the agent family is unclear, ask which target to use before writing.

Preserve existing file content and insert or replace only this marked block.

```markdown
<!-- PROJECT-WIKI:BEGIN -->
## Project Wiki Protocol

This repository uses `.project-wiki/` as the authoritative project knowledge base for requirements, change history, technical documentation, implementation state, traceability, and wiki audit logs.

When `.project-wiki/INDEX.md` exists:

- Before implementing, modifying, debugging, refactoring, testing, documenting, or planning code, read `.project-wiki/INDEX.md` first and open only the linked wiki files needed for the task.
- After source code changes made through the agent, update affected wiki documents, `REGISTRY.yml`, `STATUS.md`, relevant section indexes, traceability maps, and `logs/wiki-log-YYYY-MM.md` before finishing.
- Use `/project-wiki sync` or the project-wiki sync workflow when source code was changed manually or outside the current agent chat flow.
- Use `/project-wiki update` or the project-wiki update workflow when the user provides meeting notes, documents, planning notes, or new requirements.
- During update, always check `.project-wiki/sources/inbox/` for new source files in addition to any notes pasted in chat.
- For PDF/DOCX source documents, never read the source directly into model context. Use the local file path with the project-wiki ingestion script first.
- Use `/project-wiki maintain` or the project-wiki maintain workflow to migrate older wiki schemas, repair wiki links, indexes, registry entries, stale documents, and traceability gaps.
- When new information arrives, reconcile existing open questions before creating new ones.
- Put explicit business or product intent in `requirements/`; put implemented or observed code behavior in `technical/`. Unconfirmed code-inferred requirements belong in `requirements/open-questions.md`, not in requirement files.
- Treat `alerts/` as the active warning dashboard. Resolve alerts with evidence instead of deleting them.
- File durable, meaningful answers into existing wiki docs or linked `analysis/` pages only when they create lasting project knowledge.
- Keep `changes/CHANGELOG.md` for project-level changes and `logs/wiki-log-YYYY-MM.md` for knowledge base edits.
- Write all `.project-wiki/` content, generated templates, logs, CRs, ADRs, technical docs, scan reports, sync reports, and this instruction block in English.
- Reply to the user in chat using the language used by the user, unless the user explicitly requests another language.

Do not load the entire wiki by default. Use `.project-wiki/INDEX.md` as the routing entrypoint and follow links progressively.
<!-- PROJECT-WIKI:END -->
```

Example entry:

```yaml
  - id: REQ-001
    type: requirement
    title: User authentication
    path: requirements/functional/<project-topic>.md#req-001
    status: active
    tags: [auth, security]
    related: [ADR-0001]
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

## STATUS.md

```markdown
# Project Status

Last updated: YYYY-MM-DD

## Current Focus

- TBD

## Recent Wiki Updates

- YYYY-MM-DD: Wiki initialized.

## Active Work Items

- None captured yet.

## Blockers And Open Questions

- See [requirements/open-questions.md](./requirements/open-questions.md).

## Active Alerts

- No active alerts captured yet.

## Discovery Notes

- No current suggested follow-up questions, missing source material, or risky assumptions.

## Stale Or Placeholder Areas

- TBD

## Last Scan

- None captured yet.
```

## PROJECT.md

```markdown
---
id: PROJECT
type: project
status: active
title: Project Overview
created: YYYY-MM-DD
updated: YYYY-MM-DD
tags: []
related: []
source_paths: []
confidence: confirmed
---

# Project Overview

## Purpose

TBD

## Domain Context

TBD

## Stakeholders

TBD

## Success Criteria

TBD

## Global Constraints

TBD
```

## Requirement Section

Use `REQ-*` for functional requirements and `NFR-*` for non-functional requirements.

```markdown
## REQ-001 - Requirement Title

Status: active
Tags: []
Related: []
Source paths: []
Confidence: confirmed

### Statement

TBD

### Rationale

TBD

### Acceptance Notes

TBD
```

## Requirement Overview File

Use this shape for `requirements/functional-requirements.md` and `requirements/non-functional-requirements.md` when no explicit product-intent source confirms requirements yet.

```markdown
---
id: REQ-FUNCTIONAL-OVERVIEW or REQ-NON-FUNCTIONAL-OVERVIEW
type: requirement-overview
status: placeholder
title: Functional Requirements Overview or Non-Functional Requirements Overview
created: YYYY-MM-DD
updated: YYYY-MM-DD
tags: [requirements, functional] or [requirements, non-functional]
related: [OPEN-QUESTIONS]
source_paths: []
confidence: unknown
---

# Functional Requirements Overview or Non-Functional Requirements Overview

No confirmed functional or non-functional requirements are captured yet.

## Routing

- Observed implementation or technical evidence: link to the relevant `technical/` docs.
- Questions to confirm product intent: [open-questions.md](./open-questions.md)

## Placeholder

Add requirements here only after they are confirmed by user notes, requirements documents, README content, issues, tickets, or stakeholder clarification.

Do not add `Candidate Areas Requiring Confirmation`, observed behavior, technical concerns, or code-inferred candidate lists to this file.
```

## Requirement Topic File

Use this file shape under `requirements/functional/<project-topic>.md` or `requirements/non-functional/<project-topic>.md` only when a stable project-specific requirement topic has emerged.

```markdown
---
id: REQ-TOPIC-YYYYMMDD-001
type: requirements-topic
status: active
title: Requirement Topic Title
created: YYYY-MM-DD
updated: YYYY-MM-DD
tags: [requirements]
related: []
source_paths: []
confidence: confirmed
---

# Requirement Topic Title

## Scope

TBD

## Requirements

Use the Requirement Section template for each requirement stored here.

## Routing Notes

- Overview: [../functional-requirements.md](../functional-requirements.md) or [../non-functional-requirements.md](../non-functional-requirements.md)
- Traceability: [../../traceability/requirement-map.md](../../traceability/requirement-map.md)
```

## Open Question

```markdown
## OQ-001 - Short Question Title

Status: open
Created: YYYY-MM-DD
Updated: YYYY-MM-DD
Related: []
Source paths: []
Confidence: confirmed

### Question

TBD

### Current Context

TBD

### Resolution

Pending.

### Resolution Evidence

- TBD
```

## Change Request

```markdown
---
id: CR-YYYYMMDD-001
type: change-request
status: active
title: Short change title
created: YYYY-MM-DD
updated: YYYY-MM-DD
tags: []
related: []
source_paths: []
confidence: confirmed
---

# CR-YYYYMMDD-001 - Short Change Title

## Summary

TBD

## Source

- Meeting, document, chat note, or user request: TBD

## What Changed

TBD

## Reason

TBD

## Impact

- Requirements: TBD
- Technical docs: TBD
- Implementation: TBD
- Tests: TBD

## Follow-Up

- TBD
```

## ADR

```markdown
---
id: ADR-0001
type: decision
status: active
title: Short decision title
created: YYYY-MM-DD
updated: YYYY-MM-DD
tags: []
related: []
source_paths: []
confidence: confirmed
---

# ADR-0001 - Short Decision Title

## Context

TBD

## Decision

TBD

## Alternatives Considered

- TBD

## Consequences

- TBD

## Related

- TBD
```

## Module Documentation

```markdown
---
id: MOD-001
type: module
status: active
title: Module Name
created: YYYY-MM-DD
updated: YYYY-MM-DD
tags: []
related: []
source_paths: []
confidence: inferred
---

# Module Name

## Responsibility

TBD

## Source Paths

- TBD

## Public Interfaces

TBD

## Important Flows

TBD

## Dependencies

TBD

## Tests

TBD

## Notes For Agents

TBD
```

## API Documentation

```markdown
---
id: API-001
type: api
status: active
title: API Name
created: YYYY-MM-DD
updated: YYYY-MM-DD
tags: []
related: []
source_paths: []
confidence: inferred
---

# API Name

## Purpose

TBD

## Endpoints Or Operations

TBD

## Contracts

TBD

## Authentication And Authorization

TBD

## Error Handling

TBD

## Related Code

TBD
```

## Scan Report

```markdown
---
id: SCAN-YYYYMMDD
type: scan-report
status: active
title: Codebase Scan YYYY-MM-DD
created: YYYY-MM-DD
updated: YYYY-MM-DD
tags: [scan]
related: []
source_paths: []
confidence: inferred
---

# Codebase Scan YYYY-MM-DD

## Scope

TBD

## Confirmed Findings

- TBD

## Inferred Findings

- TBD

## Unknowns

- TBD

## Important Paths

- TBD

## Suggested Wiki Updates

- TBD
```

## Sync Report

```markdown
---
id: SYNC-YYYYMMDD-001
type: sync-report
status: active
title: Manual Code Sync YYYY-MM-DD
created: YYYY-MM-DD
updated: YYYY-MM-DD
tags: [sync]
related: []
source_paths: []
confidence: inferred
---

# Manual Code Sync YYYY-MM-DD

## Baseline

TBD

## Changed Source Paths

- TBD

## Confirmed Wiki Updates

- TBD

## Inferred Wiki Updates

- TBD

## Open Questions

- TBD

## Traceability Updates

- TBD
```

## Work Item

```markdown
---
id: WI-YYYYMMDD-001
type: work-item
status: active
title: Short work item title
created: YYYY-MM-DD
updated: YYYY-MM-DD
tags: []
related: []
source_paths: []
confidence: confirmed
---

# WI-YYYYMMDD-001 - Short Work Item Title

## Goal

TBD

## Context

TBD

## Scope

TBD

## Out Of Scope

TBD

## Acceptance Notes

TBD

## Related Wiki Docs

- TBD
```

## Section INDEX.md

```markdown
# Section Name

This section contains TBD.

## When To Read

- TBD

## Key Files

- TBD

## Placeholders Or Stale Areas

- TBD
```

## Sources INDEX.md

```markdown
# Sources

This section stores raw source documents used by document-based update workflows. Source documents are raw input, not canonical project knowledge.

## How To Use

- Drop new PDF, DOCX, text, or Markdown files into [inbox/](./inbox/).
- Run `/project-wiki update`.
- The agent checks `inbox/`, registers new files in [SOURCE_REGISTRY.yml](./SOURCE_REGISTRY.yml), runs document ingestion, and moves successfully processed files to `processed/YYYY-MM/` when possible.
- Keep human instructions in this file. Do not create `README.md` or other guide files inside `inbox/`.

## Routing Rules

- Never read PDF/DOCX source files directly into model context.
- Use source files only through the document ingestion script.
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
- For large documents, read `intake-report.md` and `chunks.json` first, then open `chunks/CH-*.md` files progressively until all relevant information for the requested integration has been reviewed.
- Do not read integrated, archived, superseded, or rejected intake documents during normal coding tasks unless explicitly requested.
- Use canonical KB files, not intake documents, as the source of truth after integration.

## Active Intake Documents

- None yet.

## Reviewed, Integrated, Archived, Superseded, Or Rejected Documents

- None yet.
```

## Document Intake Review

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

## Analysis INDEX.md

```markdown
# Analysis

This section stores durable, non-canonical synthesis produced from meaningful project questions or agent analysis. Prefer updating canonical docs when the information clearly belongs in requirements, changes, ADRs, technical docs, implementation docs, or traceability maps.

## When To Read

- Review stable tradeoff analyses, impact maps, or exploratory syntheses.
- Understand connections across requirements, changes, decisions, technical docs, alerts, and source paths.

## Rules

- Do not create isolated analysis pages.
- Every analysis page must link to related wiki records or source paths.
- Do not store routine chat answers, generic explanations, transient debugging notes, or duplicated content here.

## Analysis Pages

- None yet.
```

## Analysis Page

```markdown
---
id: AN-YYYYMMDD-001
type: analysis
status: active
title: Short Analysis Title
created: YYYY-MM-DD
updated: YYYY-MM-DD
tags: [analysis]
related: []
source_paths: []
confidence: inferred
---

# Short Analysis Title

## Why This Was Filed

TBD

## Summary

TBD

## Related Evidence

- TBD

## Implications

TBD

## Follow-Up

- TBD
```

## Alerts INDEX.md

```markdown
# Alerts

This section tracks significant warning conditions: risks, contradictions, blocking gaps, undocumented assumptions, and inconsistencies that could affect requirements, architecture, implementation, security, compliance, data handling, or project planning.

## Open Alerts

- None currently open.

## Resolved, Dismissed, Or Accepted-Risk Alerts

- None yet.

## Rules

- Do not create alerts for every suggested question.
- Resolve alerts with evidence instead of deleting them.
- Keep `STATUS.md` updated with compact active alert counts.
```

## Alert

```markdown
---
id: ALERT-YYYYMMDD-001
type: alert
status: open
severity: medium
title: Short Alert Title
created: YYYY-MM-DD
updated: YYYY-MM-DD
resolved: null
tags: [alert]
related: []
source_paths: []
confidence: inferred
---

# ALERT-YYYYMMDD-001 - Short Alert Title

## Summary

TBD

## Why It Matters

TBD

## Evidence

- TBD

## Suggested Resolution

TBD

## Resolution

Pending.

## Resolution Evidence

- TBD
```

## Maintenance INDEX.md

```markdown
# Maintenance

This section stores semantic lint and wiki health reports.

## Latest Report

- None yet.

## Schema Migration Reports

- None yet.

## Reports

- None yet.
```

## Maintenance Lint Report

```markdown
---
id: LINT-YYYYMMDD
type: maintenance-lint
status: active
title: Wiki Maintenance Lint YYYY-MM-DD
created: YYYY-MM-DD
updated: YYYY-MM-DD
tags: [maintenance, lint]
related: []
source_paths: []
confidence: inferred
---

# Wiki Maintenance Lint YYYY-MM-DD

## Structural Fixes Applied

- TBD

## Structural Issues Requiring Review

- TBD

## Contradictions

- TBD

## Stale Claims

- TBD

## Traceability Gaps

- TBD

## Orphan Pages

- TBD

## Suggested Follow-Up Questions

| Question | Why It Matters | Related Docs | Suggested Action |
| --- | --- | --- | --- |
| TBD | TBD | TBD | TBD |

## Missing Source Material

| Gap | Impact | Related Docs | Suggested Source |
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
```

## Schema Migration Report

```markdown
---
id: MIGRATION-YYYYMMDD
type: schema-migration
status: active
title: Schema Migration YYYY-MM-DD
created: YYYY-MM-DD
updated: YYYY-MM-DD
tags: [maintenance, schema-migration]
related: []
source_paths: []
confidence: confirmed
---

# Schema Migration YYYY-MM-DD

## Version Check

- Previous schema version: TBD
- Target schema version: 1.3.0
- Migration needed: yes | no

## Actions Applied

- TBD

## Actions Requiring User Confirmation

- TBD

## Legacy Items Detected

- TBD

## Files Changed

- TBD

## Result

TBD
```

## Logs INDEX.md

```markdown
# Wiki Audit Logs

This section records meaningful edits to the project knowledge base. It is separate from [changes/CHANGELOG.md](../changes/CHANGELOG.md), which records project changes.

## When To Read

- Audit how and why wiki documents changed.
- Review which meeting notes, syncs, scans, or agent-made code changes affected the wiki.
- Investigate stale, conflicting, or unexpected wiki content.

## Current Log

- [wiki-log-YYYY-MM.md](./wiki-log-YYYY-MM.md)

## Monthly Logs

- [wiki-log-YYYY-MM.md](./wiki-log-YYYY-MM.md)

## Logging Rules

- Append one concise entry after every meaningful wiki update.
- Link to detailed CRs, ADRs, scan reports, sync reports, or technical docs instead of duplicating them.
- Use heading format: `## [YYYY-MM-DD] mode | WLOG-YYYYMMDD-NNN | Summary`.
- Do not rewrite older entries except to fix broken formatting or links.
```

## Wiki Log File

```markdown
# Wiki Log YYYY-MM

This file is an append-only monthly audit trail of meaningful `.project-wiki/` updates for YYYY-MM.

## [YYYY-MM-DD] mode | WLOG-YYYYMMDD-001 | Short Summary

Date: YYYY-MM-DD
Agent: TBD
Mode: init | scan | update | sync | maintain | auto-post-implementation
Trigger: TBD

Changed wiki documents:
- TBD

Related source paths:
- TBD

Related IDs:
- TBD

Open question reconciliation:
- Resolved: TBD
- Partially resolved: TBD
- Superseded: TBD
- Dismissed: TBD
- Duplicated: TBD
- Newly created: TBD

Summary:
TBD

Open questions:
- TBD
```

## Traceability Map

```markdown
# Traceability Map

Last updated: YYYY-MM-DD

| Source | Related Change | Decision | Technical Doc | Source Paths | Notes |
| --- | --- | --- | --- | --- | --- |
| REQ-001 | CR-YYYYMMDD-001 | ADR-0001 | technical/modules/example.md | src/example/ | TBD |
```
