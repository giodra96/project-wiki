# Project Wiki Synchronization Workflow

Use this workflow for code changed manually, by another tool, or outside the current agent chat flow.

## Sync Workflow

`sync` is not the same as `maintain`: sync reconciles wiki content with code reality; maintain audits wiki structure and consistency.

1. Read `.project-wiki/INDEX.md`, `REGISTRY.yml`, `STATUS.md`, and `technical/codebase-map.md` if present.
2. Identify changed source paths since the last documented scan or since the user's stated baseline. Prefer git status, git diff, recent files, or user-provided paths when available.
3. Inspect only the changed source areas and their nearest tests/configuration.
4. Update affected technical docs under `technical/` to reflect current code behavior.
5. Update `traceability/code-map.md` and any relevant requirement or change impact maps.
6. Run [Open Questions Reconciliation](./update-workflows.md#open-questions-reconciliation-workflow) when manual code changes clarify or invalidate existing questions.
7. Create a scan or sync note under `implementation/scans/` when the reconciliation is non-trivial, marking uncertain conclusions as `confidence: inferred`.
8. Update `REGISTRY.yml`, relevant section indexes, and `STATUS.md` with the sync result and any stale or unresolved areas.
9. Append a wiki audit entry to `logs/wiki-log-YYYY-MM.md` with the baseline, inspected source paths, and changed wiki documents.
10. Do not invent requirements from code changes. If manual code appears to change product behavior, record an open question or create a lightweight CR only when the user confirms it is an intended scope change.