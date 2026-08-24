# Project Wiki Common Policies

Apply these policies to every project-wiki mode and automatic workflow.

## Language Policy

1. Write all `.project-wiki/` documents in English.
2. Write generated always-on instruction blocks in English.
3. Write templates, logs, CRs, ADRs, technical docs, scan reports, and sync reports in English.
4. Reply to the user in chat using the language used by the user, unless the user explicitly requests another language.
5. If source material is provided in another language, extract and normalize the project knowledge into English while preserving important domain terms.

## Change Request Rules

Change requests are intentionally agile and lightweight. They should capture what changed, why it matters, and what it affects.

A CR is needed when:

- A requirement changes after the initial baseline.
- A new requirement appears after the initial baseline.
- Scope, priority, deadline, assumption, or constraint changes.
- A meeting or document changes planned behavior.

A CR is not needed when:

- The agent is documenting the initial project plan.
- A small technical note only clarifies existing implementation.
- The change is purely editorial in the wiki.

## Post-Update Checklist

After any non-trivial wiki update, verify:

- New or changed docs have frontmatter.
- IDs are stable and unique.
- Related docs link both ways when useful.
- `REGISTRY.yml` contains all new records.
- Root and section indexes route to the new docs.
- `STATUS.md` reflects current active work and unresolved questions.
- Existing open questions were reconciled before creating new ones when new information arrived.
- Requirement files contain only confirmed or explicitly sourced product intent; observed implementation facts, technical constraints, concerns, candidate behavior, and code-inferred candidate areas are documented in `technical/` and linked to inferred open questions when product intent needs confirmation.
- Requirement overview files route to topic files when topic splitting was used; `REGISTRY.yml` paths point to the final requirement anchors.
- Traceability maps changed when requirements, CRs, ADRs, technical docs, or source paths changed.
- `logs/wiki-log-YYYY-MM.md` records what changed in the knowledge base and why.
- Generated or updated project wiki content is written in English, while the chat response uses the user's language.