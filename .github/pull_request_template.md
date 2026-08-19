## Summary

<!-- Briefly explain the goal of this PR and what problem it solves. -->

## Changes

<!-- List the specific files and architectural changes made in this PR. -->
- 

## Affected Areas

- [ ] Skill entrypoint (`SKILL.md`)
- [ ] Workflow procedures (`references/workflows.md`)
- [ ] Canonical wiki structure & schemas (`references/wiki-structure.md`)
- [ ] Document ingestion & parsing (`scripts/` or `references/document-ingestion.md`)
- [ ] Generated document templates (`assets/document-templates.md`)
- [ ] Documentation (`README.md`, `CONTRIBUTING.md`, etc.)

## Contributor Checklist

Please verify each item before requesting a review:

- [ ] **Prompt Compactness**: `SKILL.md` remains compact; extensive procedures reside in `references/` and templates in `assets/`.
- [ ] **Discovery & Metadata**: `name: project-wiki` is preserved and discovery keywords in `description` reflect any added capabilities.
- [ ] **Workflow Alignment**: Mode names (`init`, `scan`, `update`, `sync`, `maintain`) and automatic behaviors stay consistent across all documents.
- [ ] **Schema Version**: Compatible with Wiki Schema `1.3.0` (or migration documented if schema updated).
- [ ] **Smoke Test**: Passed locally:
  ```bash
  python3 scripts/ingest_document.py --help
  ```
- [ ] **Agent Tested**: Verified behavior with at least one compatible coding agent (e.g., GitHub Copilot, Claude Code, Antigravity, Codex, Cursor).
