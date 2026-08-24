---
name: project-wiki
description: 'Use when: creating, scanning, updating, syncing, maintaining, or automatically consulting a project wiki, knowledge base, requirements archive, change request history, ADR log, technical documentation, traceability map, wiki audit log, document intake for PDF/DOCX requirements, semantic lint, alerts, analysis notes, always-on project instructions, copilot-instructions, AGENTS.md, or agent-readable project memory in .project-wiki/. Works for Copilot, Claude Code, Codex, and other IDE chat agents.'
argument-hint: 'init | scan | update | sync | maintain'
---

# Project Wiki

Use this skill to create and maintain an agent-readable project knowledge base in `.project-wiki/`. The wiki preserves project requirements, agile change history, technical documentation, implementation state, traceability links, and a wiki audit log without loading all documents into chat context.

The skill is IDE-neutral. Apply the workflow with any chat-based coding agent that can read and write files in a repository.

Current project wiki schema version: `1.4.0` (canonical value: `./schema/project-wiki.yml`).

## Operating Principle

Always treat `.project-wiki/INDEX.md` as the routing entrypoint and `.project-wiki/REGISTRY.yml` as the structured document catalog. Read only the smallest set of linked files needed for the current task, then update the affected wiki files, local indexes, registry, and status notes.

## When to Use

- Start a new project and create a complete wiki scaffold.
- Scan an existing codebase and generate the initial project wiki.
- Convert meeting minutes, documents, chat notes, or planning notes into wiki updates.
- Ingest PDF, DOCX, text, or Markdown requirements documents into structured intake artifacts.
- Check `.project-wiki/sources/inbox/` during every update and process new source files that were not processed before.
- Sync manual code changes back into the wiki when code was changed outside the agent chat flow.
- Track agile change requests, additional requirements, scope changes, and technical decisions.
- Reconcile existing open questions when new information arrives, before creating new open questions.
- Document implemented code, modules, APIs, data models, tests, deployment, integrations, and security notes.
- File durable answers and meaningful project analyses back into existing wiki docs or linked analysis pages.
- Track active and resolved alerts for significant gaps, conflicts, risks, and inconsistencies.
- Log meaningful knowledge base edits for auditability.
- Install always-on project instructions during wiki initialization or scan.
- Migrate older `.project-wiki/` structures to the current schema during maintenance.
- Find the right project context before implementing or modifying code.

## Required Resources

Load these files only when needed:

- `./references/wiki-structure.md` for the canonical `.project-wiki/` folder tree, file responsibilities, IDs, and linking rules.
- `./references/workflows.md` to route to the focused workflow family for the current mode or automatic trigger.
- `./references/automatic-workflows.md` for automatic context preflight, post-implementation updates, and always-on instruction bootstrap.
- `./references/document-ingestion.md` for PDF/DOCX/text document intake, extraction artifacts, chunking, review gating, and KB integration rules.
- `./assets/document-templates.md` to route to the focused frontmatter and body template family for the artifact being created.
- `./schema/project-wiki.yml` for the canonical machine-readable schema version, tree, frontmatter fields, statuses, ID patterns, and documentation bindings.
- `./scripts/check_contracts.py` for deterministic drift checks between the schema manifest, README, workflows, templates, and reference tree.
- `./scripts/check_inbox.py` for deterministic source inbox discovery, hashing, and duplicate classification.
- `./scripts/validate_wiki.py` for deterministic wiki structure, YAML, frontmatter, ID, registry, path, and link validation.
- `./scripts/review_progress.py` for deterministic large-document review batches and atomic ledger updates.
- `./scripts/ingest_document.py` and `./scripts/requirements.txt` for external document extraction during document-based update workflows.

## Default Workflow

1. Determine the task mode: `init`, `scan`, `update`, `sync`, or `maintain`.
2. For any task that involves implementing, modifying, debugging, refactoring, testing, or planning code, automatically run the context preflight from `./references/automatic-workflows.md` before touching source files.
3. After AI-assisted source code changes, automatically update the affected wiki docs, registry, status, and traceability maps before finishing.
4. If `.project-wiki/INDEX.md` exists, read it first. If not, use `init` or `scan` depending on whether the repository already contains meaningful source code.
5. Open only the local index or document paths needed for the task.
6. Make wiki edits with stable document IDs, frontmatter, relative links, and traceability references.
7. During `init` or `scan`, create or update the always-on project instruction file: `.github/copilot-instructions.md` for GitHub Copilot, or `AGENTS.md` for any non-Copilot agent.
8. When new information arrives, reconcile existing open questions before creating new ones.
9. Update `.project-wiki/REGISTRY.yml`, `.project-wiki/STATUS.md`, the relevant section `INDEX.md` files, and `.project-wiki/logs/wiki-log-YYYY-MM.md` after every meaningful wiki change.
10. When the wiki update affects code behavior or implementation plans, update traceability maps so requirements, changes, decisions, docs, and source paths stay connected.

## Non-Negotiable Rules

- Keep the complete wiki structure, even if some files are initially empty or marked `status: placeholder`.
- Maintain `.project-wiki/WIKI_VERSION.yml`; during `maintain`, compare it with the current schema version and migrate older wiki structures conservatively.
- Do not dump large documents into `INDEX.md`; use indexes as routing maps, not knowledge storage.
- Preserve original requirements separately from later changes.
- Treat change requests as lightweight historical records, not heavyweight approval artifacts.
- Mark uncertain scan results as `confidence: inferred` or `confidence: unknown` instead of presenting guesses as facts.
- Create durable analysis pages only for significant non-canonical synthesis; every analysis page must link to related requirements, CRs, ADRs, technical docs, alerts, or source paths.
- Convert significant risks, contradictions, blocking gaps, and critical assumptions into `alerts/ALERT-*` records; resolve alerts instead of deleting them.
- Before opening new questions, check whether new information resolves, narrows, supersedes, dismisses, or duplicates existing open questions.
- Use parseable wiki log headings: `## [YYYY-MM-DD] mode | WLOG-YYYYMMDD-NNN | Summary`.
- Prefer relative links inside `.project-wiki/` so the wiki remains portable across IDEs and repositories.
- Keep IDs stable once created. Rename titles if needed, but do not casually change IDs.
- Before source code changes, consult the wiki automatically when `.project-wiki/INDEX.md` exists; the user should not need to explicitly request it.
- After source code changes made through the agent, update the wiki automatically; the user should not need to run `sync` for agent-made changes.
- Log every meaningful knowledge base update in `.project-wiki/logs/wiki-log-YYYY-MM.md`; `changes/CHANGELOG.md` tracks project changes, while `logs/` tracks wiki edits.
- Put explicit business or product intent in `requirements/`; put implemented or observed code behavior in `technical/`. Unconfirmed code-inferred requirements belong in `requirements/open-questions.md`, not in requirement files.
- Scale requirements by project-specific topic when needed: keep overview files as routing for small projects, and create `requirements/functional/` or `requirements/non-functional/` topic files only when stable requirement areas accumulate enough content to improve retrieval.
- Keep document intake as immutable provenance, not canonical project knowledge. Never read external PDF/DOCX source documents directly into model context; use `./scripts/ingest_document.py` and the generated intake artifacts.
- Before registering or ingesting files from `.project-wiki/sources/inbox/`, run `./scripts/check_inbox.py --wiki-root .project-wiki --format json --quarantine-skips` and follow its deterministic `process`, `skip`, and `review` actions. Do not reimplement byte-level duplicate detection, retry-record selection, or duplicate movement in model reasoning.
- During `maintain`, run `./scripts/validate_wiki.py --wiki-root .project-wiki --format json` before semantic lint. Treat its structural findings as authoritative and do not reproduce those checks with model reasoning.
- For document integration, open chunks progressively until every relevant item is classified. Use qualitative review gating from `./references/document-ingestion.md`: direct integration for clear low-impact information, `review.md` for significant ambiguity, risk, conflict, or materially cross-section updates.
- For document integration, track every manifest chunk in `review-progress.yml`. Process all chunks in batches, record every classification or an evidence-based skip reason, and never mark an intake `reviewed` or `integrated` while coverage is incomplete.
- Write all project wiki files, templates, logs, and always-on project instruction blocks in English. Reply in chat using the language used by the user.
