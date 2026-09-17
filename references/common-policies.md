# Project Wiki Common Policies

Apply to every mode and automatic workflow; use this checklist when finalizing edits.

## Language Policy

Write wiki content and generated instruction blocks in English, preserving important source-language domain terms. Reply in the user's language unless requested otherwise.

## Change Request Rules

Keep CRs lightweight: what changed, why, and what it affects. Create or update a CR for new or changed requirements after the initial baseline, scope/priority/deadline/assumption/constraint changes, or meetings/documents changing planned behavior. Initial plans, implementation-only clarifications, and editorial edits do not require a CR.

## Post-Update Checklist

- Preserve required frontmatter and stable, unique IDs. Register new records and update affected registry entries, root/section indexes, `STATUS.md`, and meaningful backlinks.
- Keep requirements sourced to explicit product intent; put observed implementation, technical concerns, and code-inferred candidates in `technical/`. Represent uncertain product intent as open questions.
- Keep requirements indexes routing-only; route to every topic and use final atomic anchors in `REGISTRY.yml`. See [Requirement Authoring](../assets/requirements-change-templates.md#requirements-topic-scaling) when creating or relocating records.
- Reconcile affected existing questions before adding new ones using [Open Questions Reconciliation](#open-questions-reconciliation-workflow).
- Update affected traceability when requirements, CRs, ADRs, technical docs, or source paths change.
- Record changes using [Wiki Audit Log Workflow](#wiki-audit-log-workflow); it defines meaningful edits, exceptions, cumulative entries, and mandatory intake evidence.

## Open Questions Reconciliation Workflow

Run this workflow whenever new information arrives through `update`, document intake, `scan`, `sync`, automatic post-implementation wiki updates, durable answer filing, or `maintain`.

Reconcile existing open questions before creating new ones.

1. Read `requirements/open-questions.md` and relevant open alerts.
2. Compare new information against existing open questions and related requirements, CRs, ADRs, technical docs, intake records, analysis pages, and traceability maps.
3. For each affected open question, choose one outcome:
   - `resolved`: the new information answers the question.
   - `partially-resolved`: part of the question is answered; narrow the remaining question.
   - `superseded`: the question is replaced by a newer requirement, CR, ADR, or question.
   - `dismissed`: the question is no longer relevant.
   - `duplicate`: merge it into another open question.
   - `still-open`: no meaningful change.
4. Update `requirements/open-questions.md` with status, updated date, resolution or narrowed question, evidence links, and related IDs.
5. If reconciliation affects requirements, CRs, ADRs, technical docs, alerts, or traceability, update those files too.
6. Create new open questions only after existing questions have been reconciled and de-duplicated.
7. If an unresolved question represents a significant risk, contradiction, blocking gap, or dangerous assumption, create or update an alert.
8. Update `REGISTRY.yml`, relevant indexes, `STATUS.md`, and traceability when files changed.
9. Record reconciliation outcomes using [Wiki Audit Log Workflow](#wiki-audit-log-workflow).

## Wiki Audit Log Workflow

Wiki logs record knowledge base edits; `changes/CHANGELOG.md` records project history.

1. Log useful changes, including small informative corrections. Skip purely editorial/mechanical edits, incidental metadata updates, and checks with no changes unless explicitly requested. A new prompt alone does not require a new entry.
2. Use `logs/wiki-log-YYYY-Www.md` with the ISO week-year and two-digit week (e.g. `2026-W38`, Monday–Sunday). Create it only for its first entry; include the week's date range and update `logs/INDEX.md`, newest weeks first.
3. Extend only the last entry in the entire history if it belongs to the current ISO week and the same ongoing activity; otherwise append. Never revisit earlier entries: A → B → A creates three entries. If the activity or ordering is unclear, append.
4. Extensions preserve the original ID, date, mode, heading, anchors, and prior information. Accumulate changed file links and relevant IDs without duplicates; integrate new results and every alert/open-question ID and outcome. Preserve successive state changes in the cumulative summary.
5. Keep mandatory audit events separate and do not extend them on later prompts: init/scan baselines, migrations, material integrity/provenance repairs, document integration, pending review creation, and final integration/rejection/postponement or required intake rejection/supersession.
6. Keep the heading `## [YYYY-MM-DD] mode | WLOG-YYYYMMDD-NNN | Summary` and unique daily IDs. The body contains `Changed:` links; add `Summary:`, `Questions:`, `Alerts:`, source references, or attribution only when applicable. Omit Trigger, duplicate metadata, empty fields, and `TBD`. Link to details instead of copying them.
7. Retain required intake ID, final audit status, ledger summary, and exact ledger SHA-256. Earlier entries may only receive formatting/link repairs; clarify historical meaning with a new corrective entry.
