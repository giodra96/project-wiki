# Security Policy

## Supported Versions

Security updates and fixes are applied to the latest schema version of Project Wiki.

| Version / Schema | Supported |
| :--- | :--- |
| `1.5.x` (Current) | :white_check_mark: |
| `< 1.5.0` | :x: (Please migrate using `/project-wiki maintain`) |

---

## Security Model & Scope

Project Wiki operates as an IDE-neutral agent skill that reads and writes local repository files. 

Key security aspects relevant to Project Wiki:

1. **Document Ingestion (`scripts/ingest_document.py`)**:
   - The extraction helper parses local PDF, DOCX, TXT, and Markdown files into `.project-wiki/intake/`.
   - It handles file paths safely to prevent arbitrary path traversal or accidental overwriting of files outside `.project-wiki/`.
   - It relies on standard and vetted open-source parsing libraries (`PyMuPDF`, `python-docx`).

2. **Always-On Instructions (`AGENTS.md`, `.github/copilot-instructions.md`)**:
   - The skill injects bounded, marked blocks (`<!-- PROJECT-WIKI:BEGIN -->`) into project instruction files. It preserves all pre-existing user instructions.

3. **Prompt Injection & Provenance Defense**:
   - By design, raw external documents in `.project-wiki/intake/` are treated as **provenance** and are not automatically fed verbatim into the agent's active system context, mitigating indirect prompt injection risks from untrusted external documents.

---

## Reporting a Vulnerability

We take the security of Project Wiki seriously. If you discover a security vulnerability or potential threat:

> [!IMPORTANT]
> **Please do NOT report security vulnerabilities through public GitHub issues, pull requests, or public discussions.**

Instead, please report security issues through:
1. **GitHub Private Vulnerability Reporting**: Go to the **Security** tab of this repository and click **"Report a vulnerability"**.
2. Or contact the project maintainers directly via private channels.

### What to Include in Your Report
- A description of the vulnerability and its potential impact.
- Step-by-step instructions (or proof-of-concept) to reproduce the behavior.
- The host agent, OS, and Python environment where the issue was observed.

### Response Timeline
- **Initial response**: Within 48 hours acknowledging receipt of your report.
- **Triage & validation**: Ongoing updates as the issue is verified and patched.
- **Public disclosure**: Coordinated after a fix has been published.
