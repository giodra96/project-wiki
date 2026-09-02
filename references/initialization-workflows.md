# Project Wiki Initialization Workflows

Use these workflows for `init` and `scan`. Runtime paths, artifacts, generated values, and lifecycle contracts come from `schema/project-wiki.yml`.

## Init Workflow

1. Require `.project-wiki/` to be absent. Run `python3 /path/to/project-wiki/scripts/wiki_scaffold.py create --wiki-root .project-wiki`. The helper generates the canonical tree in same-filesystem staging, validates scaffold recipes and the resulting wiki, and publishes only with an exclusive no-replace operation.
2. Treat `scaffold_created: true` as structural setup only. The helper deliberately reports `project_initialization_complete: false` and `semantic_content_captured: false`; continue every remaining step below. If `.project-wiki/` already exists, do not run or bypass the helper and do not merge missing files mechanically; inspect the existing wiki and use `maintain` or schema migration as appropriate.
3. Create or update both always-on project instruction files (`AGENTS.md` and `.github/copilot-instructions.md`) using [Always-On Project Instruction Bootstrap](./automatic-workflows.md#always-on-project-instruction-bootstrap).
4. Preserve untouched scaffold documents as `status: placeholder` and `confidence: unknown` until project-specific evidence is captured.
5. Ask for or extract only the minimum project identity needed for `PROJECT.md`: name, goal, domain, stakeholders, success criteria, constraints.
6. Initialize `REGISTRY.yml` with root docs, placeholders, and any captured requirements.
7. Initialize `STATUS.md` with current state, next documentation steps, and open questions.
8. Append an initial wiki audit entry to `logs/wiki-log-YYYY-MM.md` listing generated and updated files, including the always-on project instruction files.
9. Keep requirements separate from future changes; do not create CR files for the initial plan unless the user explicitly describes a change from an earlier baseline.

## Scan Existing Project Workflow

1. Read `.project-wiki/INDEX.md` if it exists. If no wiki exists, inspect the repository narrowly first: root files, package/build config, source tree, tests, entrypoints, API routes, data schemas, deployment files, and README/docs.
2. If `.project-wiki/` is absent, run `python3 /path/to/project-wiki/scripts/wiki_scaffold.py create --wiki-root .project-wiki`. Treat its output as structural setup only and continue the scan. Never run it against an existing, partial, or legacy wiki.
3. If an older wiki exists, run [Schema Migration Workflow](./maintenance-workflows.md#schema-migration-workflow) before generating new scan artifacts.
4. Create or update both always-on project instruction files (`AGENTS.md` and `.github/copilot-instructions.md`) using [Always-On Project Instruction Bootstrap](./automatic-workflows.md#always-on-project-instruction-bootstrap).
5. Write `implementation/scans/scan-YYYYMMDD.md` with findings grouped by confirmed, inferred, and unknown.
6. Populate `technical/codebase-map.md` with the repository structure, main entrypoints, framework conventions, test commands if discoverable, and important source paths.
7. Populate `technical/architecture.md` with a concise architecture overview. Mark unverified architectural claims as `confidence: inferred`.
8. Create or update module docs under `technical/modules/` for major bounded areas only. Avoid documenting every file.
9. Update `technical/api/`, `technical/data/`, and `technical/integrations/` only when the codebase exposes clear APIs, schemas, or external services.
10. Fill requirements only when they are explicitly stated in product-intent sources such as README files, product docs, issue or ticket descriptions, imported requirements documents, meeting notes, or user-provided notes.
    - Keep `requirements/INDEX.md`, `requirements/functional/INDEX.md`, and `requirements/non-functional/INDEX.md` routing-only.
    - Create project-specific topic files only when stable requirement areas are explicitly present. Put all confirmed `REQ-*` and `NFR-*` records in those topic files, never in an index.
    - Do not turn implemented behavior into confirmed product requirements by assumption; document observed behavior in `technical/`, and if it appears to imply product intent without an explicit source, record an inferred open question instead.
    - Do not store observed implementation facts, technical constraints, concerns, candidate behavior, or candidate-area lists inferred from code in functional or non-functional requirement files; document them in `technical/` and capture product-intent uncertainty as inferred open questions in `requirements/open-questions.md`.
    - Do not create `Candidate Areas Requiring Confirmation` sections in requirement indexes.
11. Run [Open Questions Reconciliation](./update-workflows.md#open-questions-reconciliation-workflow) before adding new open questions from scan findings.
12. Update `traceability/code-map.md` to connect major wiki docs to source directories.
13. Add evidence-supported suggested follow-up questions, missing source material items, and risky assumptions to the scan report when they matter to implementation, scope, risk, or decision-making. Keep the report readable by grouping, splitting, or promoting important findings instead of dropping them.
14. Create alerts for significant scan findings that represent real risk, contradiction, blocking gaps, or dangerous assumptions.
15. Update root and section indexes, `REGISTRY.yml`, and `STATUS.md` with a compact discovery summary and links to detailed reports.
16. Append a wiki audit entry to `logs/wiki-log-YYYY-MM.md` listing generated and updated wiki documents, including the always-on project instruction files.