# Contributing to Project Wiki

Thank you for your interest in contributing to **Project Wiki**! 

Project Wiki provides durable, traceable project memory for AI coding agents. It exists as an open, portable, IDE-neutral agent skill. Whether you are adding support for a new host agent, refining document templates, fixing an ingestion edge case, or improving semantic linting, your contributions are welcome.

This guide outlines our development workflow, core architectural principles, and quality standards.

---

## Quick Navigation

- [Code of Conduct](CODE_OF_CONDUCT.md)
- [Security Policy](SECURITY.md)
- [Canonical Wiki Structure](references/wiki-structure.md)
- [Workflows Specification](references/workflows.md)
- [Document Ingestion](references/document-ingestion.md)
- [Document Templates](assets/document-templates.md)

---

## Local Development & Testing

Since Project Wiki is an agent skill composed of runtime prompt instructions, reference markdown specifications, and a Python extraction helper, testing involves running both the script and live agent interactions.

### 1. Clone the repository

```bash
git clone https://github.com/giodra96/project-wiki.git ~/Projects/project-wiki
cd ~/Projects/project-wiki
```

### 2. Set up Python environment (for document intake)

Text and Markdown extractions use standard library Python. For testing PDF and DOCX parsing:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r scripts/requirements.txt
```

Verify the CLI smoke test:

```bash
python3 scripts/ingest_document.py --help
```

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
- Place extensive workflows and step-by-step procedures in `references/workflows.md`.
- Place canonical tree layouts, frontmatter schemas, and ID rules in `references/wiki-structure.md`.
- Place reusable generated markdown and YAML shapes in `assets/document-templates.md`.

### 2. Respect the Knowledge Provenance Principle
- External ingested documents (`.project-wiki/intake/`) are **provenance (evidence)**, not canonical project truth.
- Information becomes canonical only after it has been reviewed and integrated into official `requirements/`, `decisions/`, or `technical/` records.
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
- [ ] Workflow names stay aligned across `SKILL.md`, `references/workflows.md`, and `README.md`.
- [ ] Templates in `assets/document-templates.md` match `references/wiki-structure.md`.
- [ ] The always-on instruction block (`PROJECT-WIKI`) stays aligned across files.
- [ ] Python smoke check passes:
  ```bash
  python3 scripts/ingest_document.py --help
  ```
- [ ] Tested live with at least one compatible coding agent.

---

## License & Attribution

By contributing to Project Wiki, you agree that your contributions will be licensed under the project's [MIT License](LICENSE).
