#!/usr/bin/env python3
"""Filter repository source paths using .wikiignore exclusion patterns."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import weakref
from pathlib import Path, PurePosixPath
from typing import Iterable, Iterator

try:
    from .schema_contract import SchemaContract, load_schema_contract
except ImportError:
    from schema_contract import SchemaContract, load_schema_contract


class WikiScopeError(RuntimeError):
    pass


class WikiScope:
    def __init__(self, wiki_root: Path, contract: SchemaContract | None = None) -> None:
        contract = contract or load_schema_contract()
        # Lexical paths preserve exclusions for deleted paths and symlink names.
        self.wiki_root = Path(os.path.abspath(wiki_root))
        self.repository_root = self.wiki_root.parent
        ignore_file = self.wiki_root / contract.semantic_paths.wiki_ignore_file
        try:
            self.rules = ignore_file.read_bytes()
        except FileNotFoundError:
            self.rules = b""
        self.has_rules = any(line.strip() and not line.startswith(b"#") for line in self.rules.splitlines())
        self.cache: dict[str, bool] = {}
        self._matcher: tempfile.TemporaryDirectory | None = None
        self._cleanup: weakref.finalize | None = None

    def close(self) -> None:
        if self._matcher is not None:
            assert self._cleanup is not None
            self._cleanup()
            self._matcher = None

    def __enter__(self) -> WikiScope:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def normalize(self, path: str | Path) -> str:
        text = str(path)
        directory = text.endswith("/")
        if "\0" in text:
            raise WikiScopeError("source paths cannot contain NUL characters")
        candidate = Path(text)
        if candidate.is_absolute():
            candidate = Path(os.path.abspath(candidate))
            try:
                text = candidate.relative_to(self.repository_root).as_posix()
            except ValueError:
                raise WikiScopeError("source path is outside the repository") from None
        else:
            pure = PurePosixPath(text)
            if ".." in pure.parts:
                raise WikiScopeError("source paths must be relative to the repository root")
            text = pure.as_posix()
        return text.rstrip("/") + ("/" if directory else "")

    def ignored_many(self, paths: Iterable[str | Path]) -> list[bool]:
        normalized = [self.normalize(path) for path in paths]
        missing = list(dict.fromkeys(path for path in normalized if path not in self.cache))
        if missing:
            if not self.has_rules:
                self.cache.update((path, False) for path in missing)
            else:
                self.cache.update(self._match(missing))
        return [self.cache[path] for path in normalized]

    def ignored(self, path: str | Path) -> bool:
        return self.ignored_many([path])[0]

    def _match(self, paths: list[str]) -> dict[str, bool]:
        # An isolated, empty worktree prevents source reads, nested .gitignore
        # files, the real Git index, or user Git configuration affecting scope.
        environment = {
            key: value for key, value in os.environ.items()
            if not key.startswith("GIT_")
        }
        environment.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
        command = ["git", "-c", f"core.excludesFile={os.devnull}", "-c", "core.ignoreCase=false"]
        try:
            if self._matcher is None:
                temporary = tempfile.TemporaryDirectory(prefix="wiki-scope-")
                root = Path(temporary.name)
                initialization = subprocess.run(
                    [*command, "init", "--quiet", "--template=", temporary.name],
                    env=environment, capture_output=True, check=False,
                )
                if initialization.returncode:
                    temporary.cleanup()
                    raise WikiScopeError("cannot initialize the isolated ignore matcher")
                (root / ".gitignore").write_bytes(self.rules)
                self._matcher = temporary
                self._cleanup = weakref.finalize(self, temporary.cleanup)
            result = subprocess.run(
                [*command, "check-ignore", "--no-index", "--verbose", "--non-matching", "-z", "--stdin"],
                cwd=self._matcher.name, env=environment,
                input=b"".join(os.fsencode(path) + b"\0" for path in paths),
                capture_output=True, check=False,
            )
            if result.returncode not in (0, 1):
                raise WikiScopeError("cannot evaluate wiki ignore rules")
        except FileNotFoundError as error:
            if self._matcher is None and "temporary" in locals():
                temporary.cleanup()
            raise WikiScopeError("Git is required to evaluate .wikiignore") from error
        fields = result.stdout.split(b"\0")[:-1]
        if len(fields) != 4 * len(paths):
            raise WikiScopeError("unexpected output from the ignore matcher")
        return {
            os.fsdecode(fields[index + 3]): bool(fields[index + 2]) and not fields[index + 2].startswith(b"!")
            for index in range(0, len(fields), 4)
        }

    def source_files(self, start: Path | None = None, *, skip_wiki: bool = True) -> Iterator[Path]:
        """Discover included sources, pruning excluded directories before descent."""
        start = Path(os.path.abspath(start or self.repository_root))
        if start != self.repository_root and self.ignored(start.as_posix() + "/"):
            return
        pending = [start]
        while pending:
            directory = pending.pop()
            with os.scandir(directory) as scanner:
                entries = sorted(scanner, key=lambda entry: entry.name)
            candidates = []
            for entry in entries:
                path = Path(entry.path)
                if entry.name == ".git" or (skip_wiki and path == self.wiki_root):
                    continue
                is_directory = entry.is_dir(follow_symlinks=False)
                candidates.append((path, is_directory))
            ignored = self.ignored_many(
                path.as_posix() + ("/" if is_directory else "")
                for path, is_directory in candidates
            )
            for (path, is_directory), excluded in zip(candidates, ignored):
                if excluded:
                    continue
                if is_directory:
                    pending.append(path)
                else:
                    yield path

    def read_source(self, path: str | Path, *, start_line: int = 1, end_line: int | None = None) -> str | None:
        """Return only included UTF-8 sources; excluded and binary files emit nothing."""
        normalized = self.normalize(path)
        if self.ignored(normalized):
            return None
        candidate = self.repository_root / normalized
        resolved = candidate.resolve()
        # Aliases cannot expose excluded targets or files outside the repository.
        if not resolved.is_relative_to(self.repository_root.resolve()):
            return None
        resolved_name = resolved.relative_to(self.repository_root.resolve()).as_posix()
        if self.ignored(resolved_name):
            return None
        try:
            content = resolved.read_text(encoding="utf-8")
        except UnicodeError:
            return None
        if "\0" in content:
            return None
        return "".join(content.splitlines(keepends=True)[start_line - 1:end_line])

    def selected_files(self, paths: Iterable[str]) -> Iterator[Path]:
        """Select narrow source areas without descending into excluded directories."""
        selected = list(paths)
        if not selected:
            yield from self.source_files()
            return
        seen: set[Path] = set()
        for path in selected:
            normalized = self.normalize(path)
            if self.ignored(normalized):
                continue
            candidate = self.repository_root / normalized
            if candidate.is_symlink():
                continue
            files = self.source_files(candidate) if candidate.is_dir() else iter([candidate])
            for source in files:
                if source not in seen:
                    seen.add(source)
                    yield source

    def source_diff(self, paths: Iterable[str], *, cached: bool = False, base: str | None = None) -> str:
        """Return a patch for included changed files without rename-side leakage."""
        selected = [self.normalize(path) for path in paths]
        command = ["git", "--literal-pathspecs", "diff", "--no-ext-diff", "--no-textconv", "--no-renames"]
        if cached:
            command.append("--cached")
        if base is not None:
            if base.startswith("-") or ".." in base:
                raise WikiScopeError("invalid diff baseline")
            command.append(base)
        # Obtain candidate names from the index/tree, not an unrestricted diff
        # that might open ignored worktree files while computing changes.
        names = subprocess.run(
            ["git", "--literal-pathspecs", "ls-files", "--cached", "-z", "--", *selected],
            cwd=self.repository_root, capture_output=True, check=False,
        )
        if names.returncode:
            raise WikiScopeError("cannot discover source changes")
        candidates = [os.fsdecode(path) for path in names.stdout.split(b"\0") if path]
        reference = base or ("HEAD" if cached else None)
        if reference is not None:
            tree = subprocess.run(
                ["git", "--literal-pathspecs", "ls-tree", "-r", "--full-tree", "--name-only", "-z", reference, "--", *selected],
                cwd=self.repository_root, capture_output=True, check=False,
            )
            if tree.returncode:
                # A staged diff in an unborn repository has no baseline tree.
                unborn = subprocess.run(
                    ["git", "rev-parse", "--verify", "HEAD"],
                    cwd=self.repository_root, capture_output=True, check=False,
                )
                if base is not None or not unborn.returncode:
                    raise WikiScopeError("cannot read diff baseline tree")
            else:
                candidates.extend(os.fsdecode(path) for path in tree.stdout.split(b"\0") if path)
        candidates = list(dict.fromkeys(candidates))
        included = [path for path, ignored in zip(candidates, self.ignored_many(candidates)) if not ignored]
        if not included:
            return ""
        patch = subprocess.run(
            [*command, "--", *included], cwd=self.repository_root,
            capture_output=True, check=False,
        )
        if patch.returncode:
            raise WikiScopeError("cannot read included source changes")
        return patch.stdout.decode("utf-8", errors="replace")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("list", "filter", "read", "search", "diff"))
    parser.add_argument("paths", nargs="*", help="Repository-relative files or directories; narrow discovery/search/diff to these paths.")
    parser.add_argument("--wiki-root", default=".project-wiki")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--null", action="store_true", help="Use NUL-separated paths for input and text output.")
    parser.add_argument("--pattern", help="Regular expression for search.")
    parser.add_argument("--limit", type=int, default=100, help="Maximum search results (default: 100).")
    parser.add_argument("--start-line", type=int, default=1)
    parser.add_argument("--end-line", type=int)
    parser.add_argument("--cached", action="store_true", help="Read staged changes with diff.")
    parser.add_argument("--base", help="Baseline revision for diff; defaults to unstaged changes.")
    args = parser.parse_intermixed_args()
    try:
        scope = WikiScope(Path(args.wiki_root))
        if args.start_line < 1 or (args.end_line is not None and args.end_line < args.start_line):
            raise WikiScopeError("invalid source line range")
        if args.command == "read":
            if not args.paths:
                raise WikiScopeError("read requires at least one source path")
            documents = []
            for path in args.paths:
                content = scope.read_source(path, start_line=args.start_line, end_line=args.end_line)
                if content is not None:
                    documents.append({"path": scope.normalize(path), "content": content})
            if args.format == "json":
                print(json.dumps({"documents": documents}))
            else:
                for document in documents:
                    print(f"--- {document['path']} ---\n{document['content']}", end="\n")
            return 0
        if args.command == "search":
            if args.pattern is None or args.limit < 1:
                raise WikiScopeError("search requires --pattern and a positive --limit")
            pattern = re.compile(args.pattern)
            matches = []
            for path in scope.selected_files(args.paths):
                content = scope.read_source(path)
                if content is None:
                    continue
                for number, line in enumerate(content.splitlines(), 1):
                    if pattern.search(line):
                        matches.append({"path": scope.normalize(path), "line": number, "text": line})
                    if len(matches) >= args.limit:
                        break
                if len(matches) >= args.limit:
                    break
            if args.format == "json":
                print(json.dumps({"matches": matches}))
            else:
                for match in matches:
                    print(f"{match['path']}:{match['line']}:{match['text']}")
            return 0
        if args.command == "diff":
            patch = scope.source_diff(args.paths, cached=args.cached, base=args.base)
            if args.format == "json":
                print(json.dumps({"diff": patch}))
            else:
                sys.stdout.write(patch)
            return 0
        if args.command == "list":
            paths = sorted(path.relative_to(scope.repository_root).as_posix() for path in scope.selected_files(args.paths))
        else:
            delimiter = b"\0" if args.null else b"\n"
            paths = [os.fsdecode(path) for path in sys.stdin.buffer.read().split(delimiter) if path]
            paths = [path for path, ignored in zip(paths, scope.ignored_many(paths)) if not ignored]
        if args.format == "json":
            print(json.dumps({"paths": paths}, ensure_ascii=True))
        elif paths:
            separator = "\0" if args.null else "\n"
            sys.stdout.write(separator.join(paths) + separator)
        return 0
    except (OSError, RuntimeError, re.error) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    finally:
        if "scope" in locals():
            scope.close()


if __name__ == "__main__":
    raise SystemExit(main())
