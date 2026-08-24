# Project Wiki Initialization Workflows

Use these workflows for `init` and `scan`. Runtime paths, artifacts, generated values, and lifecycle contracts come from `schema/project-wiki.yml`.

## Init Workflow

1. Create the full `.project-wiki/` tree from [Wiki structure](./wiki-structure.md).
2. Create all root files, `WIKI_VERSION.yml`, section indexes, traceability maps, sources, logs, and local templates.
3. Create or update the always-on project instruction file using [Always-On Project Instruction Bootstrap](./automatic-workflows.md#always-on-project-instruction-bootstrap).
4. Mark unknown or unused documents as `status: placeholder` and `confidence: unknown`.
5. Ask for or extract only the minimum project identity needed for `PROJECT.md`: name, goal, domain, stakeholders, success criteria, constraints.
6. Initialize `REGISTRY.yml` with root docs, placeholders, and any captured requirements.
7. Initialize `STATUS.md` with current state, next documentation steps, and open questions.
8. Append an initial wiki audit entry to `logs/wiki-log-YYYY-MM.md`.
9. Keep requirements separate from future changes; do not create CR files for the initial plan unless the user explicitly describes a change from an earlier baseline.

## Scan Existing Project Workflow

1. Read `.project-wiki/INDEX.md` if it exists. If no wiki exists, inspect the repository narrowly first: root files, package/build config, source tree, tests, entrypoints, API routes, data schemas, deployment files, and README/docs.
2. Create the full `.project-wiki/` tree if missing, including `WIKI_VERSION.yml`.
3. If an older wiki exists, run [Schema Migration Workflow](./maintenance-workflows.md#schema-migration-workflow) before generating new scan artifacts.
4. Create or update the always-on project instruction file using [Always-On Project Instruction Bootstrap](./automatic-workflows.md#always-on-project-instruction-bootstrap).
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
11. Run [Open Questions Reconciliation](./update-workflows.md#open-questions-reconciliation-workflow) before adding new open questions from scan findings.
12. Update `traceability/code-map.md` to connect major wiki docs to source directories.
13. Add evidence-supported suggested follow-up questions, missing source material items, and risky assumptions to the scan report when they matter to implementation, scope, risk, or decision-making. Keep the report readable by grouping, splitting, or promoting important findings instead of dropping them.
14. Create alerts for significant scan findings that represent real risk, contradiction, blocking gaps, or dangerous assumptions.
15. Update root and section indexes, `REGISTRY.yml`, and `STATUS.md` with a compact discovery summary and links to detailed reports.
16. Append a wiki audit entry to `logs/wiki-log-YYYY-MM.md` listing generated and updated wiki documents, including the always-on project instruction file.