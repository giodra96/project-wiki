# Project Wiki Technical And Implementation Templates

Use these templates for technical documentation, scans, synchronization reports, work items, and traceability maps.

## Module Documentation

```markdown
---
id: MOD-001
type: module
status: active
title: Module Name
created: YYYY-MM-DD
updated: YYYY-MM-DD
tags: []
related: []
source_paths: []
confidence: inferred
---

# Module Name

## Responsibility

TBD

## Source Paths

- TBD

## Public Interfaces

TBD

## Important Flows

TBD

## Dependencies

TBD

## Tests

TBD

## Notes For Agents

TBD
```

## API Documentation

```markdown
---
id: API-001
type: api
status: active
title: API Name
created: YYYY-MM-DD
updated: YYYY-MM-DD
tags: []
related: []
source_paths: []
confidence: inferred
---

# API Name

## Purpose

TBD

## Endpoints Or Operations

TBD

## Contracts

TBD

## Authentication And Authorization

TBD

## Error Handling

TBD

## Related Code

TBD
```

## Scan Report

```markdown
---
id: SCAN-YYYYMMDD
type: scan-report
status: active
title: Codebase Scan YYYY-MM-DD
created: YYYY-MM-DD
updated: YYYY-MM-DD
tags: [scan]
related: []
source_paths: []
confidence: inferred
---

# Codebase Scan YYYY-MM-DD

## Scope

TBD

## Confirmed Findings

- TBD

## Inferred Findings

- TBD

## Unknowns

- TBD

## Important Paths

- TBD

## Suggested Wiki Updates

- TBD
```

## Sync Report

```markdown
---
id: SYNC-YYYYMMDD-001
type: sync-report
status: active
title: Manual Code Sync YYYY-MM-DD
created: YYYY-MM-DD
updated: YYYY-MM-DD
tags: [sync]
related: []
source_paths: []
confidence: inferred
---

# Manual Code Sync YYYY-MM-DD

## Baseline

TBD

## Changed Source Paths

- TBD

## Confirmed Wiki Updates

- TBD

## Inferred Wiki Updates

- TBD

## Open Questions

- TBD

## Traceability Updates

- TBD
```

## Work Item

```markdown
---
id: WI-YYYYMMDD-001
type: work-item
status: active
title: Short work item title
created: YYYY-MM-DD
updated: YYYY-MM-DD
tags: []
related: []
source_paths: []
confidence: confirmed
---

# WI-YYYYMMDD-001 - Short Work Item Title

## Goal

TBD

## Context

TBD

## Scope

TBD

## Out Of Scope

TBD

## Acceptance Notes

TBD

## Related Wiki Docs

- TBD
```

## Traceability Map

```markdown
# Traceability Map

Last updated: YYYY-MM-DD

| Source | Related Change | Decision | Technical Doc | Source Paths | Notes |
| --- | --- | --- | --- | --- | --- |
| REQ-001 | CR-YYYYMMDD-001 | ADR-0001 | technical/modules/example.md | src/example/ | TBD |
```