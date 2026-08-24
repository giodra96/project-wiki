# Project Wiki Workflows

Use this index after loading `SKILL.md`. Load only the workflow family needed for the current mode or trigger, then follow explicit cross-links when a shared procedure is required.

Current project wiki schema version: `1.4.0` (from `schema/project-wiki.yml`).

## Mode Selection

Choose exactly one primary mode for explicit wiki-management requests. Context lookup before code work is automatic and is not a user-facing mode.

| Mode | Use When | Procedure |
| --- | --- | --- |
| `init` | Starting a new project or creating an empty wiki before code exists. | [Initialization workflows](./initialization-workflows.md#init-workflow) |
| `scan` | A repository already contains meaningful code and needs an initial wiki. | [Initialization workflows](./initialization-workflows.md#scan-existing-project-workflow) |
| `update` | The user provides meeting minutes, documents, chat notes, planning notes, or new requirements. | [Update workflows](./update-workflows.md#update-workflow) |
| `sync` | Code changed outside the agent chat flow and the wiki must be reconciled with the current repository state. | [Synchronization workflow](./synchronization-workflow.md#sync-workflow) |
| `maintain` | Cleaning indexes, fixing links, refreshing registry entries, semantic lint, alert review, and stale wiki areas. | [Maintenance workflows](./maintenance-workflows.md#maintain-workflow) |

## Automatic Behavior

Use [Automatic workflows](./automatic-workflows.md) for context preflight, post-implementation wiki updates, and always-on project instruction bootstrap.

## Shared Policies

Use [Common policies](./common-policies.md) for language, change-request rules, and the post-update checklist.