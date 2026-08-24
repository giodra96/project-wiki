# Contributing to Project Wiki

Thank you for your interest in contributing to **Project Wiki**! 

Project Wiki provides durable, traceable project memory for AI coding agents. It exists as an open, portable, IDE-neutral agent skill. Whether you are adding support for a new host agent, refining document templates, fixing an ingestion edge case, or improving semantic linting, your contributions are welcome.

This guide outlines our development workflow, core architectural principles, and quality standards.

---

## Quick Navigation

- [Code of Conduct](CODE_OF_CONDUCT.md)
- [Security Policy](SECURITY.md)
- [Machine-Readable Schema Contract](schema/project-wiki.yml)
- [Human Wiki Structure Reference](references/wiki-structure.md)
- [Workflow Index](references/workflows.md)
- [Document Ingestion](references/document-ingestion.md)
- [Document Templates](assets/document-templates.md)

---

## Local Development & Testing

Project Wiki combines runtime instructions, reference documentation, templates, a schema contract, and Python helpers for ingestion, validation, and drift checks. Testing covers the automated toolchain plus representative live-agent interactions.

### 1. Clone the repository

```bash
git clone https://github.com/giodra96/project-wiki.git ~/Projects/project-wiki
cd ~/Projects/project-wiki
```

### 2. Set up Python environment (for document intake)

Text and Markdown extraction uses standard library Python. Inbox and wiki structure checks use PyYAML and markdown-it-py, while PDF and DOCX parsing uses the remaining helper dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r scripts/requirements.txt
```

Verify the CLI smoke tests:

```bash
python3 scripts/check_contracts.py --help
python3 scripts/check_inbox.py --help
python3 scripts/ingest_document.py --help
python3 scripts/validate_wiki.py --help
```

Run the automated ingestion tests:

```bash
python3 -m unittest discover -s tests -v
```

The suite covers:

- Chunk sizing, semantic section boundaries, metadata, hints, and stable chunk IDs.
- Intake ID allocation, malformed IDs, and existing-ID collisions.
- Empty input and missing PyMuPDF, python-docx, or PyYAML dependencies.
- Parseable and mutually consistent YAML, Markdown frontmatter, and JSON artifacts.
- Idempotent intake indexes and cleanup or rollback after failures.
- Inbox duplicate detection, historical intake validation, and hash-verified quarantine.
- Canonical wiki tree, YAML/frontmatter, IDs, statuses, registries, paths, links, anchors, and validator JSON output.
- Manifest loading and drift detection across schema versions, README/workflow paths, canonical tree, and templates.

GitHub Actions runs the same suite, Python compilation, and CLI smoke checks on Python 3.10 and 3.13 for every push and pull request.

### Schema Contract Changes

For any schema version, tree, registry version, frontmatter, status, ID, template inventory, or workflow-contract change:

1. Edit `schema/project-wiki.yml` first.
2. Update the checked human views in `references/`, `README.md`, and the affected catalog routed by `assets/document-templates.md`.
3. Add or update a mutation test in `tests/test_schema_contract.py`.
4. Run `python3 scripts/check_contracts.py` and the full unittest suite.

Do not update duplicated version or path strings independently of the manifest.

### 3. Link the skill into your preferred agent

To test changes in real agent sessions, symlink your local working copy into your agent's skill directory:

```bash
# For Agent Skills compatible agents (Antigravity, OpenCode, etc.)
mkdir -p ~/.agents/skills
ln -s "$(pwd)" ~/.agents/skills/project-wiki

# For Claude Code
mkdir -p ~/.claude/skills
ln -s "$(pwd)" ~/.claude/skills/project-wiki

# For repository-level testing in a test project
cd /path/to/test-repo
mkdir -p .agents/skills  # or .github/skills
ln -s ~/Projects/project-wiki .agents/skills/project-wiki
```

---

## Core Principles for Contributors

When authoring or modifying skill resources, always uphold these non-negotiable principles:

### 1. Keep `SKILL.md` Compact
`SKILL.md` is loaded directly into the AI agent's active system prompt. To protect the agent's context budget:
- Keep `SKILL.md` under 150 lines.
- Place each extensive workflow in the focused `references/*-workflow*.md` family routed by `references/workflows.md`.
- Define machine-readable tree, frontmatter, status, and ID contracts in `schema/project-wiki.yml`; explain them in `references/wiki-structure.md`.
- Place reusable generated markdown and YAML shapes in the focused catalog routed by `assets/document-templates.md`.

### 2. Respect the Knowledge Provenance Principle
- External ingested documents (`.project-wiki/intake/`) are **provenance (evidence)**, not canonical project truth.
- Information becomes canonical only after it has been reviewed and integrated into official `requirements/`, `changes/decisions/`, or `technical/` records.
- Inferred or scanned code behavior belongs under `technical/` and does not become a confirmed requirement without explicit product-intent backing.

### 3. Ensure Bidirectional Traceability
Every requirement (`REQ-*`), decision (`ADR-*`), and change request (`CR-*`) must be designed to link unambiguously to real repository source paths (`src/...`).

### 4. Progressive Disclosure
Indexes (`INDEX.md`, `requirements/INDEX.md`, etc.) must remain compact routing maps. Never convert an index into an all-in-one summary document.

---

## Types of Contributions

### 🐛 Bug Fixes
1. Check existing [Issues](https://github.com/giodra96/project-wiki/issues) to ensure the bug is not already tracked.
2. Create a branch named `fix/short-description`.
3. Reproduce and fix the issue locally.
4. Open a Pull Request referencing the issue (e.g. `Closes #12`).

### ✨ Workflow & Template Improvements
1. Open an [Issue / Feature Request](https://github.com/giodra96/project-wiki/issues/new/choose) or start a Discussion first to align on design.
2. Create a branch named `feat/short-description`.
3. Update all aligned files (if you change a workflow or template, ensure `references/`, `assets/`, `SKILL.md`, and `README.md` remain strictly synchronized).

### 🔌 New Agent Adapters & Tooling
If you have verified Project Wiki on an emerging coding agent (e.g. Cursor, Roo Code, Windsurf, Hermes), feel free to submit documentation updates, path conventions, or compatibility notes.

---

## Pull Request Verification Checklist

Before submitting a Pull Request, verify the following:

- [ ] `name: project-wiki` is preserved in `SKILL.md`.
- [ ] `description` in `SKILL.md` includes relevant discovery keywords.
- [ ] `argument-hint` lists only user-facing modes (`init | scan | update | sync | maintain`).
- [ ] `SKILL.md` remains compact; detailed procedural logic is placed in `references/`.
- [ ] Workflow names and routes stay aligned across `SKILL.md`, `references/workflows.md`, focused workflow references, and `README.md`.
- [ ] Templates and human references match `schema/project-wiki.yml`.
- [ ] `schema/project-wiki.yml` remains the single machine-readable schema contract and the drift check passes:
  ```bash
  python3 scripts/check_contracts.py
  ```
- [ ] The always-on instruction block (`PROJECT-WIKI`) stays aligned across files.
- [ ] Python helper smoke checks pass:
  ```bash
  python3 scripts/check_contracts.py --help
  python3 scripts/check_inbox.py --help
  python3 scripts/ingest_document.py --help
  python3 scripts/review_progress.py --help
  python3 scripts/validate_wiki.py --help
  ```
- [ ] Automated ingestion tests pass:
  ```bash
  python3 -m unittest discover -s tests -v
  ```
- [ ] New ingestion behavior includes a focused regression test and remains compatible with the Python versions in `.github/workflows/tests.yml`.
- [ ] Tested live with at least one compatible coding agent.

---

## License & Attribution

By contributing to Project Wiki, you agree that your contributions will be licensed under the project's [MIT License](LICENSE).
