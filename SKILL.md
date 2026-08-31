---
name: project-wiki
description: 'Use when: creating, scanning, updating, syncing, maintaining, or automatically consulting a project wiki, knowledge base, requirements archive, change request history, ADR log, technical documentation, traceability map, wiki audit log, document intake for PDF/DOCX requirements, semantic lint, alerts, analysis notes, always-on project instructions, copilot-instructions, AGENTS.md, or agent-readable project memory in .project-wiki/. Works for Copilot, Claude Code, Codex, and other IDE chat agents.'
argument-hint: 'init | scan | update | sync | maintain'
---

# Project Wiki

Create and maintain an agent-readable project knowledge base in `.project-wiki/` without loading the entire wiki into context. The skill is IDE-neutral.

Current project wiki schema version: `1.5.0` (canonical value: `./schema/project-wiki.yml`).

## Route The Task

Select one primary mode for an explicit wiki request and load only its workflow:

| Trigger | Load |
| --- | --- |
| `init` - Initialize an empty project wiki | [Init Workflow](./references/initialization-workflows.md#init-workflow) |
| `scan` - Scan an existing repository | [Scan Existing Project Workflow](./references/initialization-workflows.md#scan-existing-project-workflow) |
| `update` - Process notes, requirements, meetings, or durable analysis | [Update Workflow](./references/update-workflows.md#update-workflow) |
| `update` - Ingest PDF, DOCX, text, or Markdown sources | [Document Intake Workflow](./references/update-workflows.md#document-intake-workflow), then [Document Ingestion](./references/document-ingestion.md) |
| `sync` - Reconcile code changed outside the current agent task | [Sync Workflow](./references/synchronization-workflow.md#sync-workflow) |
| `maintain` - Validate, migrate, repair, or semantically lint a wiki | [Maintain Workflow](./references/maintenance-workflows.md#maintain-workflow) |
| Before implementing, modifying, debugging, refactoring, testing, documenting, or planning code when `.project-wiki/INDEX.md` exists | [Automatic Context Preflight](./references/automatic-workflows.md#automatic-context-preflight) |
| After agent-made source changes | [Automatic Post-Implementation Wiki Update](./references/automatic-workflows.md#automatic-post-implementation-wiki-update) |

Load [Document Templates](./assets/document-templates.md) only when creating an artifact. Load [Wiki Structure](./references/wiki-structure.md) or the [Schema Contract](./schema/project-wiki.yml) only when exact structure or contract values are needed. Use [Common Policies](./references/common-policies.md) when finalizing wiki edits.

## Operating Contract

1. Read `.project-wiki/INDEX.md` first when it exists, follow its routes, and open only the smallest relevant set of files. Use `REGISTRY.yml` only when indexes do not resolve the task.
2. Before code planning or changes, run the automatic context preflight. After agent-made source changes, run the automatic post-implementation workflow; reserve `sync` for external or manual changes.
3. Follow the selected workflow completely. Prefer the supplied deterministic scripts over reproducing structural, validation, duplicate, extraction, or ledger logic in model reasoning.
4. After every meaningful wiki edit, reconcile affected indexes, `REGISTRY.yml`, `STATUS.md`, traceability, and `logs/wiki-log-YYYY-MM.md` as required by the selected workflow.

## Invariants

- Keep stable IDs, required frontmatter, relative wiki links, and the complete canonical structure. Preserve history and original requirements rather than silently replacing them.
- Put explicit business or product intent in `requirements/`; put implemented or observed behavior in `technical/`. Record unconfirmed product intent inferred from code as an open question.
- Reconcile existing open questions before creating new ones. Represent significant risks, contradictions, blocking gaps, or critical assumptions as alerts and resolve rather than delete them.
- Mark uncertain scan findings as `confidence: inferred` or `confidence: unknown`.
- Keep indexes as compact routing maps. File durable non-canonical synthesis only when significant and link it to evidence or related records.
- Treat document intake as immutable provenance. Never load external PDF or DOCX files directly into model context; use the ingestion and review-progress scripts and complete every chunk disposition.
- Write all wiki content and generated instruction blocks in English. Reply in the user's language unless requested otherwise.
