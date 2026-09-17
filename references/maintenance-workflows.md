# Project Wiki Maintenance Workflows

Use these workflows for structural validation, schema migration, semantic lint, alerts, and audit logs. Runtime paths, artifacts, generated values, and lifecycle contracts come from `schema/project-wiki.yml`.

## Maintain Workflow

Use this mode to keep the wiki healthy. `maintain` includes structural cleanup and semantic lint.

1. Run [Schema Migration Workflow](#schema-migration-workflow).
2. Run [Deterministic Structural Validation Workflow](#deterministic-structural-validation-workflow). Apply low-risk structural fixes and rerun the validator until it passes or only blocked findings remain.
3. Do not ask the model to rediscover broken links, malformed YAML/frontmatter, duplicate IDs, invalid statuses, missing registry paths, or canonical-tree gaps already covered by the validator.
4. Check whether new CRs, ADRs, module docs, or work items are meaningfully represented in traceability maps; path and ID validity are deterministic, while adequacy of the relationship is semantic.
5. Run [Open Questions Reconciliation](./update-workflows.md#open-questions-reconciliation-workflow) to close, narrow, supersede, dismiss, or de-duplicate stale questions when evidence supports it.
6. Run [Semantic Lint Workflow](#semantic-lint-workflow) only after deterministic validation results are known.
7. Review open alerts and update alert status when evidence supports resolution, dismissal, or accepted risk.
8. Compact verbose index content by moving detail into the appropriate document.
9. Mark stale documents as `superseded`, `deprecated`, or `placeholder` rather than deleting history.
10. Apply low-risk fixes directly. For high-impact contradictions, stale claims, alert resolutions, or canonical meaning changes, write the lint finding and ask for user confirmation before changing canonical docs.
11. Update `STATUS.md` with deterministic validation status, semantic maintenance results, active alert counts, open question counts, schema version status, and compact discovery summary links.
12. Record maintenance changes using [Wiki Audit Log Workflow](#wiki-audit-log-workflow).

## Schema Migration Workflow

Use this workflow during `maintain` and when `scan` finds an existing `.project-wiki/` that may not match the current schema.

The skill's current schema contract comes from `schema/project-wiki.yml`. Human references and templates explain the contract but are not independent schema sources.

1. Read `.project-wiki/WIKI_VERSION.yml` if it exists. If it is missing, treat the wiki as `pre-versioned`.
2. Read the current schema version from `schema/project-wiki.yml` and compare it with the recorded project wiki version.
3. If the schema is current, record that no schema migration was needed and continue normal maintenance.
4. If the schema is older or missing, create or update `.project-wiki/maintenance/schema-migration-YYYYMMDD.md` with planned and applied migration actions.
5. Preserve existing content. Do not delete or overwrite user/project-authored files during schema migration.
6. Create missing canonical directories and placeholder files from [Wiki structure](./wiki-structure.md), including `sources/`, `analysis/`, `maintenance/`, `alerts/`, `logs/`, and local templates.
   - For migration from schema 1.4, create `requirements/functional/INDEX.md` and `requirements/non-functional/INDEX.md`.
   - If legacy `functional-requirements.md` or `non-functional-requirements.md` contains atomic records, move them into evidence-backed topic files only after semantic review; never discard or mechanically regroup them.
   - If legacy atomic records contain inline or free-text source evidence, migrate verified edges into `traceability/requirement-evidence.yml`; do not infer ambiguous ranges or delete human notes without review.
   - Remove an empty legacy overview after updating links and registry. If it contains unresolved content, retain it temporarily as `superseded` until migration is complete.
7. Update `.project-wiki/WIKI_VERSION.yml` to the current schema version only after all migration actions succeed.
8. Ensure `sources/SOURCE_REGISTRY.yml` exists and uses version `1`.
9. Align logs and local templates with [Wiki Audit Log Workflow](#wiki-audit-log-workflow).
10. Detect old intake artifacts where `extracted.md` or `chunks.json` contains full document text. Do not read those files. Mark the intake as `superseded` or report that it should be regenerated with the current script before review.
11. For active or reviewed legacy intakes missing `review-progress.yml`, create a ledger from `chunks.json` with every chunk pending and resume review. For terminal legacy intakes, create a complete ledger with explicit legacy skip reasons rather than claiming retrospective semantic coverage.
12. Update the always-on instruction block in both `AGENTS.md` and `.github/copilot-instructions.md` using [Always-On Project Instruction Bootstrap](./automatic-workflows.md#always-on-project-instruction-bootstrap).
13. Update root and section indexes, `REGISTRY.yml`, `STATUS.md`, and `logs/INDEX.md` to reflect the migrated structure.
14. Ask for user confirmation before risky migration actions such as moving large source files, deleting old intake directories, or changing canonical meaning.
15. Append one ISO-week wiki audit entry describing the schema migration.

## Deterministic Structural Validation Workflow

Run this workflow during every `maintain`, after schema migration and before semantic lint.

```text
python3 /path/to/project-wiki/scripts/validate_wiki.py \
   --wiki-root .project-wiki \
   --format json
```

Exit codes:

```text
0  structural validation passed
1  deterministic structural findings exist
2  validator could not run because of dependency or filesystem failure
```

The validator is read-only and deterministically checks:

- Canonical directories and required files.
- YAML and JSON syntax.
- Required Markdown frontmatter fields, ISO dates, allowed statuses, confidence values, and alert severities.
- Stable ID shape, uniqueness, type compatibility, and standalone filename alignment.
- `REGISTRY.yml` and `SOURCE_REGISTRY.yml` shape, duplicate IDs, related IDs, source hashes, paths, anchors, catalog completeness, and update-date consistency.
- CommonMark link targets, headings, explicit anchors, reference links, and fragments without following external URLs.
- Intake chunk manifest IDs and referenced chunk files.

Treat the JSON findings and codes as authoritative structural facts. Apply low-risk repairs, rerun the same command, and include the final command status plus any unresolved codes in `maintenance/lint-YYYYMMDD.md`. Do not replace validator output with an agent-authored structural scan.

The validator deliberately does not decide contradictions, implicit requirements, stale meaning, meaningful backlink adequacy, traceability quality, orphan concepts, risky assumptions, or missing source material. Those remain in [Semantic Lint Workflow](#semantic-lint-workflow) because they require project context and evidence.

## Semantic Lint Workflow

Create or update `.project-wiki/maintenance/lint-YYYYMMDD.md` during `maintain`.

Run this only after [Deterministic Structural Validation Workflow](#deterministic-structural-validation-workflow). Record the validator result under `Deterministic Validation`, then use agent analysis for the semantic checks below.

Check for:

- Missing meaningful backlinks whose necessity depends on document semantics; target existence is handled by the validator.
- Requirements without traceability.
- CRs or ADRs not reflected in requirements, technical docs, or traceability maps.
- Technical docs without source paths.
- Contradictions between requirements, CRs, ADRs, technical docs, intake reviews, and as-is code.
- Stale claims superseded by newer CRs, ADRs, scans, sync reports, or source documents.
- Orphan pages with no meaningful inbound links.
- Important concepts mentioned repeatedly but lacking a canonical page.
- Open questions that are stale, blocking, or already resolved.
- Open questions that can be closed, narrowed, superseded, dismissed, or de-duplicated based on current evidence.
- Missing source material and risky assumptions.

Report sections should include:

- Deterministic Validation.
- Structural Fixes Applied.
- Structural Issues Requiring Review.
- Contradictions.
- Stale Claims.
- Traceability Gaps.
- Orphan Pages.
- Suggested Follow-Up Questions.
- Missing Source Material.
- Risky Assumptions.
- Alert Candidates.

Keep suggested follow-up questions, missing source material, and risky assumptions concise without using a fixed target count. Every item must include why it matters and related docs or evidence. When many evidence-supported items are important, group related findings or promote confirmed questions to `requirements/open-questions.md` and significant risks, contradictions, blocking gaps, or dangerous assumptions to alerts.

## Alert Workflow

Use alerts for significant warning conditions. Do not create alerts for every suggested question.

Create or update `alerts/ALERT-YYYYMMDD-NNN-short-title.md` when a scan, update, document review, sync, maintain pass, or code task finds a meaningful risk, contradiction, blocking gap, undocumented assumption, or inconsistency that could cause incorrect requirements, architecture, implementation, security, compliance, data handling, or project planning.

Alert statuses and severities come from `schema/project-wiki.yml`.

When resolving an alert:

1. Read the alert and related docs.
2. Update canonical KB files, traceability, registry, and status as needed.
3. Set alert status to `resolved`, `dismissed`, or `accepted-risk`.
4. Add resolution date, resolution summary, and resolution evidence links.
5. Move the alert from open to resolved/dismissed/accepted-risk section in `alerts/INDEX.md`.
6. Record the alert outcome using [Wiki Audit Log Workflow](#wiki-audit-log-workflow).

Do not delete resolved alerts.

## Wiki Audit Log Workflow

Wiki logs record knowledge base edits; `changes/CHANGELOG.md` records project history.

1. Log useful changes, including small informative corrections. Skip purely editorial/mechanical edits, incidental metadata updates, and checks with no changes unless explicitly requested. A new prompt alone does not require a new entry.
2. Use `logs/wiki-log-YYYY-Www.md` with the ISO week-year and two-digit week (e.g. `2026-W38`, Monday–Sunday). Create it only for its first entry; include the week's date range and update `logs/INDEX.md`, newest weeks first.
3. Extend only the last entry in the entire history if it belongs to the current ISO week and the same ongoing activity; otherwise append. Never revisit earlier entries: A → B → A creates three entries. If the activity or ordering is unclear, append.
4. Extensions preserve the original ID, date, mode, heading, anchors, and prior information. Accumulate changed file links and relevant IDs without duplicates; integrate new results and every alert/open-question ID and outcome. Preserve successive state changes in the cumulative summary.
5. Keep mandatory audit events separate and do not extend them on later prompts: init/scan baselines, migrations, material integrity/provenance repairs, document integration, pending review creation, and final integration/rejection/postponement or required intake rejection/supersession.
6. Keep the heading `## [YYYY-MM-DD] mode | WLOG-YYYYMMDD-NNN | Summary` and unique daily IDs. The body contains `Changed:` links; add `Summary:`, `Questions:`, `Alerts:`, source references, or attribution only when applicable. Omit Trigger, duplicate metadata, empty fields, and `TBD`. Link to details instead of copying them.
7. Retain required intake ID, final audit status, ledger summary, and exact ledger SHA-256. Earlier entries may only receive formatting/link repairs; clarify historical meaning with a new corrective entry.
