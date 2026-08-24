# Project Wiki Requirements And Change Templates

Use these templates for requirement records, open questions, change requests, and architectural decisions.

## Requirement Section

Use `REQ-*` for functional requirements and `NFR-*` for non-functional requirements.

```markdown
<a id="req-001"></a>

## REQ-001 - Requirement Title

Status: active
Tags: []
Related: []
Source paths: []
Confidence: confirmed

### Statement

TBD

### Rationale

TBD

### Acceptance Notes

TBD
```

## Requirement Overview File

Use this shape for `requirements/functional-requirements.md` and `requirements/non-functional-requirements.md` when no explicit product-intent source confirms requirements yet.

```markdown
---
id: REQUIREMENTS-OVERVIEW
type: requirement-overview
status: placeholder
title: Requirements Overview
created: YYYY-MM-DD
updated: YYYY-MM-DD
tags: [requirements]
related: [OPEN-QUESTIONS]
source_paths: []
confidence: unknown
---

# Requirements Overview

No confirmed functional or non-functional requirements are captured yet.

## Routing

- Observed implementation or technical evidence: link to the relevant `technical/` docs.
- Questions to confirm product intent: [open-questions.md](./open-questions.md)

## Placeholder

Add requirements here only after they are confirmed by user notes, requirements documents, README content, issues, tickets, or stakeholder clarification.

Do not add `Candidate Areas Requiring Confirmation`, observed behavior, technical concerns, or code-inferred candidate lists to this file.
```

## Requirement Topic File

Use this file shape under `requirements/functional/<project-topic>.md` or `requirements/non-functional/<project-topic>.md` only when a stable project-specific requirement topic has emerged.

```markdown
---
id: REQ-TOPIC-YYYYMMDD-001
type: requirements-topic
status: active
title: Requirement Topic Title
created: YYYY-MM-DD
updated: YYYY-MM-DD
tags: [requirements]
related: []
source_paths: []
confidence: confirmed
---

# Requirement Topic Title

## Scope

TBD

## Requirements

Use the Requirement Section template for each requirement stored here.

## Routing Notes

- Overview: [../functional-requirements.md](../functional-requirements.md) or [../non-functional-requirements.md](../non-functional-requirements.md)
- Traceability: [../../traceability/requirement-map.md](../../traceability/requirement-map.md)
```

## Open Question

```markdown
<a id="oq-001"></a>

## OQ-001 - Short Question Title

Status: open
Created: YYYY-MM-DD
Updated: YYYY-MM-DD
Related: []
Source paths: []
Confidence: confirmed

### Question

TBD

### Current Context

TBD

### Resolution

Pending.

### Resolution Evidence

- TBD
```

## Change Request

Write change requests under `changes/requests/`.

```markdown
---
id: CR-YYYYMMDD-001
type: change-request
status: active
title: Short change title
created: YYYY-MM-DD
updated: YYYY-MM-DD
tags: []
related: []
source_paths: []
confidence: confirmed
---

# CR-YYYYMMDD-001 - Short Change Title

## Summary

TBD

## Source

- Meeting, document, chat note, or user request: TBD

## What Changed

TBD

## Reason

TBD

## Impact

- Requirements: TBD
- Technical docs: TBD
- Implementation: TBD
- Tests: TBD

## Follow-Up

- TBD
```

## ADR

Write architectural decision records under `changes/decisions/`.

```markdown
---
id: ADR-0001
type: decision
status: active
title: Short decision title
created: YYYY-MM-DD
updated: YYYY-MM-DD
tags: []
related: []
source_paths: []
confidence: confirmed
---

# ADR-0001 - Short Decision Title

## Context

TBD

## Decision

TBD

## Alternatives Considered

- TBD

## Consequences

- TBD

## Related

- TBD
```