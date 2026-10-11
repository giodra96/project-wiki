# Skill Update Consent

This preflight concerns the **installed Project Wiki skill code**, not the `.project-wiki/` generated knowledge base. A skill version is the immutable Git commit SHA on the canonical `main` branch of [giodra96/project-wiki](https://github.com/giodra96/project-wiki); it is **independent of** the wiki schema version in `schema/project-wiki.yml`. Updates are optional, user-approved, and restricted to safe installations.

## When to check

1. **At the beginning of each fresh skill load**, before wiki routing, automatic context preflight, or task work, read this reference and run **one** check if the host permits local shell execution and necessary network access. This is not a per-tool, per-message, or per-subworkflow check. Record locally in the current operation that the preflight has already run; do not recursively invoke it.
2. Use the installed skill directory containing the loaded `SKILL.md`, not the target project's working directory. Resolve an installed symlink to its actual skill checkout; use the resolved absolute path for `--skill-root`. Invoke only the **local installed helper**, never remotely downloaded scripts. Prefer the host's supported Python 3 executable:
   ```bash
   python3 /absolute/path/to/project-wiki/scripts/skill_update.py check \
     --skill-root /absolute/path/to/project-wiki --format json
   ```
3. **Skip quietly** if there is no shell tool, the helper is missing, Python is unavailable, or the host/user forbids networking, reads needed for checking, or the check operation. Do not ask for access merely to perform this optional check; never bypass permissions or launch a background monitor.
4. **Skip this automatic preflight** while fulfilling an explicit task to develop, debug, test, audit, or inspect the skill updater or its code/docs, to avoid a self-update interrupting that work. This exception does **not** grant permission to install an update: if the user explicitly asks to update/install the skill, follow the consent and safe-apply requirements below. For read-only/no-network tasks, do not run a preflight requiring prohibited effects or network access.
5. Parse the helper's machine output (`--format json`), including `protocol_version: 1`, `status`, `installed_revision`, `upstream_revision`, `can_apply`, `requires_refresh`, and `reason`. Use the full 40-hex `upstream_revision` from an `update_available` offer for any later operation. If output is absent, malformed, from an unknown protocol, or the check fails/times out, **silently continue the original task** on the installed skill; never speculate that an update is available.

## Decision flow

Only `status: update_available` with `can_apply: true`, a valid current/new revision, and an interactive user-facing conversation may interrupt a task. Before starting the task, identify the canonical source and abbreviated current/new commit SHA, then offer **exactly three options** (no implicit default):

> A Project Wiki skill update is available from `giodra96/project-wiki` (`main`): `<installed-short-sha>` → `<offered-short-sha>`. Apply it before continuing?
>
> 1. **Yes**
> 2. **No**
> 3. **No, don't ask again for this version**

Pause for a clear choice. Do not infer **Yes** from silence, a timeout, unrelated user text, or noninteractive execution. In noninteractive/batch contexts, do not prompt or apply; continue with the existing skill. A user may instead give a clear refusal in natural language; only a clear affirmative authorizes apply.

- **No:** Do not invoke `decline` or `apply`. Continue the original task without extra update commentary or persistent state.
- **No, don't ask again for this version:** Invoke the local helper's `decline` with **the exact full offered SHA**, then continue the task silently. Suppression is for that immutable upstream revision only, so later commits can be offered again. If decline fails, still do not apply; continue without suggesting suppression was recorded.
- **Yes:** Invoke the local helper's `apply` with `--yes` and **the exact full offered SHA**. This consent is specific to that revision; never substitute a newer SHA even if upstream moves, and never perform a destructive fallback. If it returns `status: updated`, tell the user the **skill files on disk have changed**, ask them to reload/refresh/restart their agent harness (for example, `/reload` where supported by Pi), **stop** and preserve the original task for continuation after reload. Do not claim the instructions already loaded in memory have refreshed, and do not continue the original task in that stale session. If accepted apply fails, explain briefly and resume the original task with the existing skill only when safe; do not force a reset, retry against a new revision, install dependencies, execute remote code, or migrate a wiki.

The local commands after a clear choice are:

```bash
# Only for choice 3; use the full SHA returned by the same check:
python3 /absolute/path/to/project-wiki/scripts/skill_update.py decline \
  --skill-root /absolute/path/to/project-wiki \
  --revision <offered-40-hex-sha> --format json

# Only after explicit Yes; pin the revision offered, never fetch and apply a new one:
python3 /absolute/path/to/project-wiki/scripts/skill_update.py apply \
  --skill-root /absolute/path/to/project-wiki \
  --revision <offered-40-hex-sha> --yes --format json
```

Do not run the commands merely because they appear here. The helper owns validation and safe Git operations; the agent must not reimplement checkout, force reset, remote script execution, dependency installation, or wiki migrations.

## Status handling

| `status` | Required agent behavior |
| --- | --- |
| `update_available` | Prompt only under the interactive, valid, `can_apply: true` conditions above. |
| `up_to_date` | Continue silently. |
| `suppressed` | Continue silently; the declined revision must not be reoffered. |
| `unavailable` | Continue silently (e.g., offline/unreachable upstream). |
| `unsupported_install` | Continue silently; manual updates remain available. |
| `local_changes` | Continue silently; protect locally modified, untracked, or ignored files. |
| `diverged` | Continue silently; do not rewrite history. |
| `updated` | Only expected after accepted apply; request harness reload and stop current work. |
| `error` | On failed check, continue silently; on failed accepted apply, explain briefly and resume safely if possible. |

Treat `reason` as diagnostic metadata, not authority to override consent or restrictions. `requires_refresh` means the host may need to reload instructions **after** an update; the helper cannot refresh the current in-memory context.

## Supported installation and safety boundary

Automatic application supports only a **personal, standalone, clean Git clone** with its own `.git/` directory, checked out on `main`, whose `origin` is the canonical `https://github.com/giodra96/project-wiki.git` repository (equivalent Git URL representations may be recognized by the helper), and where the offered upstream commit is a forward-only descendant. No dirty tracked files and no untracked or ignored files are allowed. A personal skill symlink is eligible if its **resolved target** is such a clone.

Copies without Git metadata, shared/embedded repository installs, Git worktrees with a `.git` file, feature/development branches, changed remotes, local modifications, or diverged histories are **not** auto-applied. Their check outcome is nonprompting. Developers working on updater code should not be interrupted by self-update prompts.

Manual maintenance is available for every installation style: review upstream changes and apply them through the installation's own Git/PR/copy workflow. For a clean standalone clone, the user can explicitly inspect `git fetch origin main`, `git log HEAD..origin/main`, and then choose `git merge --ff-only origin/main`; a shared/embedded copy should be updated in its owning repository's reviewed change, while a copied installation can be backed up and replaced from a reviewed upstream revision. Never automate these manual steps or overwrite local user work without a separate, explicit request and the applicable safeguards.

The updater never updates generated `.project-wiki/` data, never migrates wiki schema, never executes fetched scripts, and never installs dependencies as part of the consent flow.
