# Project Wiki Help

Project Wiki maintains project knowledge in `.project-wiki/`. Ask an agent using the skill:

| Command | When to use it and what it does |
| --- | --- |
| `/project-wiki init` | Create an empty wiki and capture initial project context. Existing wikis are not overwritten. |
| `/project-wiki scan` | Document an existing codebase. Creates the wiki if absent, then updates technical records, traceability, and status. |
| `/project-wiki update` | Integrate notes, requirements, decisions, or documents. Add your notes or a local document path to the request. |
| `/project-wiki sync` | Reconcile the wiki with current code, including committed changes and experiments performed with auto-sync disabled. |
| `/project-wiki maintain` | Validate structure, migrate older wikis, repair safe issues, and review stale or inconsistent knowledge. |
| `/project-wiki config` | Show effective project preferences. |
| `/project-wiki config set automation.auto_sync false` | Disable automatic wiki updates during ordinary agent work. |
| `/project-wiki config set automation.auto_sync true` | Re-enable automatic wiki updates. |
| `/project-wiki help` | Display this guide without inspecting or modifying the project. |

Ordinary coding requests automatically consult relevant wiki context. With auto-sync enabled, the agent updates affected wiki records when durable knowledge, evidence, or recorded work state changes. Routine changes with no such impact produce no wiki edits or skip logs.

Preferences live in `.project-wiki/config.yml`; missing configuration defaults to enabled. With auto-sync disabled, the agent keeps consulting the wiki but skips automatic impact assessment and all automatic wiki writes, including metadata and logs. Explicit wiki requests still run. Use `sync` to reconcile accumulated changes; re-enabling auto-sync alone does not recover them. Invalid configuration is reported and suspends automatic writes. Configuration commands change only `config.yml` and do not trigger sync.

To exclude sources from the first scan, run `init`, edit `.project-wiki/.wikiignore` with repository-root-relative patterns, then run `scan`. Existing wiki history remains consultable. Initialization and scanning install project instructions in `AGENTS.md` and `.github/copilot-instructions.md`, preserving unrelated content. For older installations, run `maintain` with the updated skill to refresh these instructions.

Chat commands are interpreted by the agent, not the shell. To display this same guide from a terminal, replace the path with the installed skill directory:

```bash
python3 /path/to/project-wiki/scripts/wiki_help.py
```

The help helper uses only the Python standard library, reads this bundled guide, and never reads or writes project files or executes examples. Its English output is fixed regardless of the current directory or configuration. Exit code `0` means success; `2` means invalid usage or an unreadable/empty guide.
