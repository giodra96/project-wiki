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
schema_version: 1.5.1
schema_updated: 2026-09-02
last_migrated: YYYY-MM-DD
maintained_by_skill: project-wiki
notes: Current schema applied.
```

## Always-On Project Instruction Block
 
Use this block during `init` and `scan`. Always create or update both repository-level always-on instruction files outside `.project-wiki/`:

- `AGENTS.md` at the repository root
- `.github/copilot-instructions.md`

Preserve existing file content in both files and insert or replace only this marked block.

```markdown
<!-- PROJECT-WIKI:BEGIN -->
## Project Wiki Protocol

When `.project-wiki/INDEX.md` exists:

- Before implementing, modifying, debugging, refactoring, testing, documenting, or planning code, read `.project-wiki/INDEX.md` and only the linked context needed for the task.
- After agent-made source changes, update affected wiki docs, indexes, `REGISTRY.yml`, `STATUS.md`, traceability, and the monthly wiki log before finishing. Record observed behavior in `technical/`; do not infer product requirements from code.
- Use the project-wiki `update` workflow for notes, requirements, or external documents; `sync` for manual or external code changes; and `maintain` for validation or migration. Follow each workflow's deterministic scripts and never load PDF/DOCX sources directly into model context.
- Reconcile existing open questions before creating new ones. Log every meaningful wiki edit. Write wiki content in English and reply in the user's language unless requested otherwise.

Do not load the whole wiki. Route progressively from `.project-wiki/INDEX.md`.
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