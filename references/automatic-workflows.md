# Automatic Project Wiki Workflows

Use these workflows after loading `SKILL.md`. Runtime paths, artifacts, generated values, and lifecycle contracts come from `schema/project-wiki.yml`.

## Automatic Context Preflight

Run this automatically whenever `.project-wiki/INDEX.md` exists and the user asks to implement, modify, debug, refactor, test, document, or plan code. The user should not need to invoke a separate `consult` mode.

1. Read `.project-wiki/INDEX.md` first.
2. Use the routing table to identify the smallest relevant section.
3. Read the section `INDEX.md`, then only the linked documents needed for the task.
4. If the needed context is missing, read `REGISTRY.yml` and traceability maps before broad code search.
5. Summarize only the wiki facts that affect the task, then proceed with the requested work.
6. If implementation changes invalidate wiki content, update the wiki as part of the same task.

Skip this preflight only when the task is unrelated to the project wiki and unrelated to code or project behavior, or when `.project-wiki/INDEX.md` does not exist yet.

## Automatic Post-Implementation Wiki Update

Run this automatically after source code changes made by the agent through chat. The user should not need to invoke `sync` for agent-made changes.

1. Identify which source paths changed and which wiki records were consulted before implementation.
2. Document implemented or changed behavior under `technical/`, especially module, API, data, integration, testing, deployment, and security docs. Use overview files such as `architecture.md` and `codebase-map.md` as routing/summaries; create or update focused technical docs under the existing technical folders when an implemented area needs its own documentation.
3. Update implementation docs when the change affects active plans, work items, or scan notes.
4. Update traceability maps when source paths now implement, modify, or invalidate requirements, CRs, ADRs, or technical docs.
5. Run Open Questions Reconciliation when the implementation clarifies previously unresolved behavior.
6. Update `REGISTRY.yml`, relevant section indexes, and `STATUS.md`.
7. If the implementation introduced behavior not already represented by a requirement or CR, do not turn it into a confirmed product requirement by assumption. Document observed behavior in `technical/`; create a lightweight CR only when the change reflects a confirmed product or scope change, otherwise record an inferred open question when product intent needs confirmation.
8. Append a wiki audit entry to `logs/wiki-log-YYYY-MM.md` when wiki files changed.
9. In the final response, mention the wiki files updated alongside the code changes.

## Always-On Project Instruction Bootstrap

Install this during `init` and `scan` so future coding tasks consult and update `.project-wiki/` even when the user does not explicitly invoke this skill.

1. Always create or update both repository-level always-on instruction files outside `.project-wiki/`:
   - `AGENTS.md` at the repository root
   - `.github/copilot-instructions.md`
2. Preserve existing file content in both files. Do not overwrite unrelated instructions.
3. In each file, insert or replace only the block delimited by `<!-- PROJECT-WIKI:BEGIN -->` and `<!-- PROJECT-WIKI:END -->`.
4. The block must instruct agents to read `.project-wiki/INDEX.md` before source code changes, update the wiki after agent-made source code changes, use `sync` for manual or external code changes, log meaningful wiki edits, write all wiki content in English, and respond to the user in the user's chat language.
5. Include both created or updated instruction files in `logs/wiki-log-YYYY-MM.md`.