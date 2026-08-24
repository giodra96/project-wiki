# Project Wiki Governance Templates

Use these templates for durable analysis, alerts, maintenance reports, schema migrations, and audit logs.

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

## Deterministic Validation

- Command: `python3 /path/to/project-wiki/scripts/validate_wiki.py --wiki-root .project-wiki --format json`
- Result: passed | findings-remain | validator-error
- Errors: TBD
- Warnings: TBD
- Unresolved finding codes: TBD

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
- Target schema version: 1.4.0
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