# Project Wiki Configuration

Project preferences live in `.project-wiki/config.yml`, independently of the installed skill. The file can be edited directly and committed with the repository. It has no document ID, frontmatter, or registry entry. Configuration versioning is independent of `WIKI_VERSION.yml`.

```yaml
config_version: 1

automation:
  auto_sync: true
```

## Configuration Workflow

Route `/project-wiki config` to the helper's `show` command; route `/project-wiki config set automation.auto_sync false` (or `true`) to `set`:

```text
python3 /path/to/project-wiki/scripts/wiki_config.py --wiki-root .project-wiki show
python3 /path/to/project-wiki/scripts/wiki_config.py --wiki-root .project-wiki set automation.auto_sync false
python3 /path/to/project-wiki/scripts/wiki_config.py --wiki-root .project-wiki set automation.auto_sync true
```

`show` returns JSON with effective `config` and `source` (`file` or `defaults`). `set` additionally reports `changed`; it requires an existing wiki directory, validates before writing, and atomically replaces only `config.yml`. Changed settings normalize formatting and comments; unchanged settings preserve the file. Do not reset an invalid file with `set`; report the error and correct only the invalid setting when the user requests a repair.

Configuration commands edit only this file: do not update wiki content, status, registries, or audit logs for a preference change. They do not trigger sync. Exit code `0` means success; `2` means a configuration, I/O, or invocation error.

## Automatic Write Gate

After reading `INDEX.md`, run `wiki_config.py ... show` before automatic workflows. Reuse the result within a coherent task, but refresh it before post-implementation processing if the configuration may have changed, including changes made by the task itself.

- Missing file: default to `automation.auto_sync: true`. Do not create it merely by reading configuration. New scaffolds include it; existing wikis do not require a configuration file or content restructuring. On a schema upgrade, use `maintain` to refresh version metadata and always-on instructions.
- `true`: run the normal semantic impact assessment and update affected records only when needed.
- `false`: skip the entire automatic post-implementation assessment and all automatic wiki writes, including durable answer filing, question/alert reconciliation, work state, traceability, metadata, and audit logs. Do not create deferred-work markers or log skips. Keep context preflight active, and verify task-relevant claims against current sources because the wiki may be stale. Briefly mention the disabled auto-sync in the final coding response, without claiming the wiki is current.
- Invalid YAML, duplicate or unknown keys, unsupported version, wrong types, or read errors: report the error, suspend automatic wiki writes, and continue the requested code work with context preflight. Never silently fall back to enabled automation or rewrite configuration.

Explicit requests to initialize, scan, update, sync, maintain, or edit the wiki remain authorized with `auto_sync: false`. Configuration errors also do not disable an explicit workflow, although invalid configuration remains a validation finding; preserve it unless repair is requested. An explicit instruction for the current task can override the automatic write gate without changing the stored preference.

Re-enabling auto-sync affects subsequent automatic processing; it does not reconcile the backlog. Use explicit `sync` to reconcile all accumulated changes, including committed changes. Do not advance or invent synchronization baselines when automatic updates are skipped.

## Scope

Version 1 supports only `automation.auto_sync`, a boolean. A present file must contain `config_version: 1` and the `automation.auto_sync` setting. Unsupported keys are errors so misspellings cannot silently enable automatic writes. There are no global preferences, local overrides, or profiles.

When upgrading existing wikis, refresh the marked instruction blocks in both `AGENTS.md` and `.github/copilot-instructions.md` using the existing bootstrap during `scan` or `maintain`. Preserve the user's configuration. The generated blocks reference the configuration dynamically; never embed the current boolean value.
