## Summary

<!-- Briefly explain the goal of this PR and what problem it solves. -->

## Changes

<!-- List the specific files and architectural changes made in this PR. -->
- 

## Affected Areas

- [ ] Skill entrypoint (`SKILL.md`)
- [ ] Workflow index and focused procedures (`references/workflows.md`, `references/*-workflow*.md`)
- [ ] Canonical wiki structure & schemas (`references/wiki-structure.md`)
- [ ] Document ingestion & parsing (`scripts/` or `references/document-ingestion.md`)
- [ ] Template index and focused catalogs (`assets/document-templates.md`, `assets/*-templates.md`)
- [ ] Documentation (`README.md`, `CONTRIBUTING.md`, etc.)

## Contributor Checklist

Please verify each item before requesting a review:

- [ ] **Prompt Compactness**: `SKILL.md` remains compact; extensive procedures reside in `references/` and templates in `assets/`.
- [ ] **Discovery & Metadata**: `name: project-wiki` is preserved and discovery keywords in `description` reflect any added capabilities.
- [ ] **Workflow Alignment**: Mode names (`init`, `scan`, `update`, `sync`, `maintain`) and automatic behaviors stay consistent across all documents.
- [ ] **Schema Version**: Compatible with Wiki Schema `1.4.0` (canonical value in `schema/project-wiki.yml`; migration documented if updated).
- [ ] **Contract Drift**: `python3 scripts/check_contracts.py` passes.
- [ ] **Smoke Test**: Passed locally:
  ```bash
  python3 -m unittest discover -s tests -v
  python3 scripts/check_contracts.py
  ```
- [ ] **Agent Tested**: Verified behavior with at least one compatible coding agent (e.g., GitHub Copilot, Claude Code, Antigravity, Codex, Cursor).
