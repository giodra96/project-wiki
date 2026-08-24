# Project Wiki Core Templates

Use these templates for root wiki files, section indexes, and always-on project instructions. Replace placeholders with project-specific values and keep frontmatter compact.

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

Example entries:

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

## WIKI_VERSION.yml

```yaml
schema: project-wiki
schema_version: 1.4.0
schema_updated: 2026-08-24
last_migrated: YYYY-MM-DD
maintained_by_skill: project-wiki
notes: Current schema applied.
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
- During update, always run the project-wiki deterministic inbox preflight with skip quarantine before registering or ingesting `.project-wiki/sources/inbox/` files. Follow its `process`, `skip`, `review`, `selected_registry_id`, and `quarantined_to` outputs instead of reproducing mechanical checks or choices in model reasoning.
- For PDF/DOCX source documents, never read the source directly into model context. Use the local file path with the project-wiki ingestion script first.
- During document integration, process every chunk in batches and update `review-progress.yml`; do not mark an intake reviewed or integrated until all chunks are classified or skipped with a reason.
- Use `/project-wiki maintain` or the project-wiki maintain workflow to migrate older wiki schemas, run deterministic structural validation, then review stale meaning, contradictions, and traceability quality semantically.
- During maintain, treat `validate_wiki.py` findings as authoritative for tree, YAML, frontmatter, IDs, status, registry, path, and link checks; do not reproduce those checks in model reasoning.
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