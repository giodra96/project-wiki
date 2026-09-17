# Project Wiki Source Inbox

## Source Inbox Workflow

Use this workflow at the start of every `update`.

The checker derives `process`, `skip`, and `review` actions from the source workflow contract in `schema/project-wiki.yml`; apply the returned action rather than reproducing that mapping in agent reasoning.

1. Ensure `.project-wiki/sources/INDEX.md`, `.project-wiki/sources/SOURCE_REGISTRY.yml`, and source folders exist: `inbox/`, `processed/`, `rejected/`, and `ignored/`.
2. Treat `sources/INDEX.md` as the human guide for the source area. Do not create guide files inside `sources/inbox/`.
3. Run the deterministic preflight before registering or ingesting any inbox file: `python3 /path/to/project-wiki/scripts/check_inbox.py --wiki-root .project-wiki --format json --quarantine-skips`.
4. If the checker exits non-zero, stop inbox processing and report the registry, intake-history, hash, or filesystem error. Do not ingest files while duplicate history is missing, incomplete, invalid, or changed during preflight.
5. Treat the checker report as authoritative for supported-file discovery, housekeeping exclusions, SHA-256 calculation, validated historical hash matches across `SOURCE_REGISTRY.yml` and complete intake artifacts, retry-record selection, byte-identical duplicates within the current inbox, and duplicate quarantine destinations. Do not independently recompute or semantically infer these facts.
6. Apply report actions mechanically:
   - `process` with reason `new-unique`: add one `pending` entry to `SOURCE_REGISTRY.yml` with a stable `SRC-YYYYMMDD-NNN` ID and the reported SHA-256.
   - `process` with reason `registered-pending` or `registered-failed`: reuse only `selected_registry_id`; do not create a second source record. Set a retried `failed` entry back to `pending` before ingestion.
   - `skip`: do not register another pending source and do not run ingestion. With `--quarantine-skips`, the checker revalidates each hash and moves the redundant file to the reported `quarantined_to` path under `sources/ignored/`; the agent only records the result in `sources/INDEX.md`.
   - `review` with reason `historical-path-with-new-content`: do not ingest automatically. Determine whether the content is a new version, an accidental overwrite, or an explicit reprocessing request. Create a new source record or supersede history only after that semantic decision.
   - `review` with reason `ambiguous-processable-history`: do not choose a registry record heuristically. Reconcile the duplicate `pending` or `failed` records before rerunning preflight.
7. When the user explicitly requests reprocessing of a file classified `skip`, treat that request as an override, preserve the previous registry history, and record the reason for the new intake. Do not weaken the default duplicate check.
8. Run [Document Intake Workflow](./document-ingestion.md#document-intake-workflow) only for files authorized by a `process` action or an explicitly resolved `review`/reprocessing override. For every inbox file, pass the report hash to ingestion as `--expected-sha256 <sha256>` so changed content cannot be processed under an earlier preflight decision.
9. After successful ingestion, move the file to `.project-wiki/sources/processed/YYYY-MM/`, then mark the source as `processed` with `processed_at`, the generated `DOCIN-*` intake ID, the archived `current_path`, and the same SHA-256 recorded by the intake. A processed record is invalid unless archived bytes, registry hash, and intake provenance agree.
10. If ingestion fails, mark the source as `failed` with the error summary and leave it in `inbox/` unless the user asks to move it.
11. Update `sources/INDEX.md` with `pending`, `processed`, `failed`, `rejected`, `ignored`, `superseded`, and review-required source summaries.
12. Continue the normal `update` flow using the generated intake reports and any pasted chat notes.

The preflight is read-only by default. `--quarantine-skips` is the only mutating mode: it rechecks hashes and transactionally moves files classified `skip` to `sources/ignored/`; it never changes `SOURCE_REGISTRY.yml`. The agent remains responsible for source record lifecycle updates, but it must not duplicate the checker's byte-level reasoning or choose among ambiguous records.
