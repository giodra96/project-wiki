# Repository Source Scope

Configuration and troubleshooting reference; ordinary wiki work uses the helpers without loading this page or interpreting exclusion patterns.

## Configuration

`init` creates `.project-wiki/.wikiignore` with comments only. Populate it before `scan` to limit the first scan. Direct first scans proceed without exclusions. Migration creates the file only if missing; existing rules are preserved. Its canonical location comes from `semantic_paths.wiki_ignore_file` in the schema manifest.

Patterns are relative to the repository root. `#` starts a comment; blank lines are ignored. Leading `/` anchors a pattern; trailing `/` excludes directories and their contents. Bare names match at any depth. `*`, `?`, character classes, and `**` support wildcard matching; backslashes escape special characters. `!` introduces an inclusion exception, with the last applicable rule winning. A child cannot be included while its parent directory is excluded; exclude the parent's contents instead:

```text
/vendor/
/generated/
*.min.js
/legacy/*
!/legacy/README.md
```

## Helper Commands

Run these from the repository root using the installed skill's script path:

```bash
python3 /path/to/project-wiki/scripts/wiki_scope.py list src --format json
python3 /path/to/project-wiki/scripts/wiki_scope.py read src/main.py --start-line 1 --end-line 80
python3 /path/to/project-wiki/scripts/wiki_scope.py search src --pattern 'handle_request' --limit 20
python3 /path/to/project-wiki/scripts/wiki_scope.py diff --base HEAD
```

Use `--wiki-root` for a different wiki location. Narrow `list` and `search` to relevant paths to keep output compact. `read` requires files; `search` uses a regular expression and defaults to at most 100 matches. Binary sources are omitted from reads/searches. `diff` defaults to unstaged tracked changes; `--cached` selects staged changes. Use `read` for new untracked files. Rename sides are evaluated independently, so an included side cannot expose an excluded source's patch. `filter` accepts path names on stdin; use `--null` for NUL-separated names and trailing `/` for directories.

All source helpers apply exclusions before returning content, pruning excluded directories. They reuse one matcher per instance; empty/comments-only rules do not start it. Scope evaluation errors stop source processing. Inbox discovery, hashing, ingestion, and source validation use the same filter internally. Rules are independent of version-control tracking and nested configurations.

## History

Excluded sources emit no new content or tracking information. Existing wiki documentation, traceability, intake artifacts, and audit history remain consultable; they are not refreshed from excluded sources. Exclusion alone does not mean deletion, missing evidence, or drift. Validators preserve structural checks on wiki records while skipping existence/content/hash checks for excluded raw sources. Removing an exclusion returns that source to scope.

These helpers govern wiki source access, not filesystem permissions or unrelated coding work. They do not change the agent host's permissions. Raw documents follow source exclusions; canonical wiki records and already extracted history remain structurally validated.
