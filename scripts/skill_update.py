#!/usr/bin/env python3
"""Conservative, consent-driven updates for standalone project-wiki Git clones.

The only network source in production is the fixed upstream HTTPS main branch.
Checks never update the install. An apply is a verified, clean fast-forward.
"""
from __future__ import annotations

import argparse
import configparser
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time

UPSTREAM_URL = "https://github.com/giodra96/project-wiki.git"
BRANCH = "main"
SHA = re.compile(r"[0-9a-fA-F]{40}\Z")
LOCAL_TIMEOUT = 5
NETWORK_TIMEOUT = 15
PROTOCOL_VERSION = 1


class UpdateProblem(Exception):
    def __init__(self, status: str, reason: str, *, refresh: bool = False):
        super().__init__(reason)
        self.status = status
        self.reason = reason
        self.refresh = refresh


class GitFailure(Exception):
    pass


def _result(status: str, installed: str | None = None,
            upstream: str | None = None, *, refresh: bool = False,
            reason: str | None = None) -> dict:
    return {
        "protocol_version": PROTOCOL_VERSION,
        "status": status,
        "installed_revision": installed,
        "upstream_revision": upstream,
        "can_apply": status == "update_available",
        "requires_refresh": refresh,
        "reason": reason,
    }


def _git_env(protocol: str = "") -> dict[str, str]:
    # Remove caller-provided Git repository, config, execution and tracing knobs.
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("GIT_")}
    env.update({
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_SYSTEM": os.devnull,
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_NO_REPLACE_OBJECTS": "1",
        "GIT_LFS_SKIP_SMUDGE": "1",
        "GIT_ALLOW_PROTOCOL": protocol,
        "GCM_INTERACTIVE": "never",
    })
    env.pop("SSH_ASKPASS", None)
    env.pop("GIT_ASKPASS", None)
    return env


def _git(directory: Path, *args: str, timeout: int = LOCAL_TIMEOUT,
         protocol: str = "", allow_codes: tuple[int, ...] = (0,)) -> subprocess.CompletedProcess:
    argv = [
        "git", "-c", "core.hooksPath=/dev/null",
        "-c", "core.fsmonitor=false",
        "-c", "core.attributesFile=/dev/null",
        "-c", "protocol.ext.allow=never",
        "-c", "protocol.file.allow=" + ("always" if protocol == "file" else "never"),
        "-C", str(directory), *args,
    ]
    try:
        result = subprocess.run(
            argv, env=_git_env(protocol), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise GitFailure(type(exc).__name__) from exc
    if result.returncode not in allow_codes:
        # Do not leak stderr: Git diagnostics can contain local paths or URLs.
        raise GitFailure("git_failed")
    return result


def _text(directory: Path, *args: str, **kwargs) -> str:
    return _git(directory, *args, **kwargs).stdout.strip()


def _safe_config(gitdir: Path) -> None:
    cfg = configparser.RawConfigParser(interpolation=None, strict=False)
    if (gitdir / "config").is_symlink():
        raise UpdateProblem("unsupported_install", "unsafe_git_metadata")
    try:
        with (gitdir / "config").open("r", encoding="utf-8") as f:
            cfg.read_file(f)
    except (OSError, UnicodeError, configparser.Error):
        raise UpdateProblem("unsupported_install", "git_config_unreadable")
    for section in cfg.sections():
        name = section.casefold()
        if (name.startswith(("include", "filter ", "url ", "submodule "))
                or name == "extensions"):
            raise UpdateProblem("unsupported_install", "unsafe_git_config")
        if name == "core":
            blocked = {
                "worktree", "sparsecheckout", "sparsecheckoutcone",
                "hookspath", "fsmonitor", "attributesfile", "splitindex",
            }
            if (any(option.casefold() in blocked for option in cfg.options(section))
                    or cfg.get(section, "bare", fallback="false").casefold() != "false"):
                raise UpdateProblem("unsupported_install", "unsafe_git_config")
    # Git internals must not redirect reads or checkout writes outside the clone.
    for name in ("config", "HEAD", "index", "objects", "refs", "logs",
                 "packed-refs", "FETCH_HEAD", "ORIG_HEAD", "info/exclude"):
        if (gitdir / name).is_symlink():
            raise UpdateProblem("unsupported_install", "unsafe_git_metadata")
    for name in ("info/attributes", "info/grafts", "objects/info/alternates",
                 "shallow", "index.lock", "MERGE_HEAD", "REBASE_HEAD",
                 "CHERRY_PICK_HEAD", "REVERT_HEAD", "BISECT_LOG",
                 "rebase-apply", "rebase-merge", "sequencer"):
        if (gitdir / name).exists() or (gitdir / name).is_symlink():
            raise UpdateProblem("unsupported_install", "unsafe_git_metadata")


def _safe_tree(directory: Path, commit: str) -> None:
    # A checkout must not create symlinks/submodules or activate attributes/filters.
    result = _git(directory, "ls-tree", "-r", "-z", "--full-tree", commit)
    for record in result.stdout.split("\0"):
        if not record:
            continue
        try:
            meta, path = record.split("\t", 1)
            mode, kind, _ = meta.split(" ", 2)
        except ValueError:
            raise UpdateProblem("unsupported_install", "unsafe_tree")
        parts = Path(path).parts
        if (mode in {"120000", "160000"} or kind not in {"blob", "tree"}
                or any(p.casefold() in {".gitattributes", ".git"} for p in parts)
                or any(p in {".", ".."} for p in parts)):
            raise UpdateProblem("unsupported_install", "unsafe_tree")


def _prepare_install(root: Path) -> str:
    gitdir = root / ".git"
    if (not root.is_dir() or not gitdir.is_dir() or gitdir.is_symlink()
            or not (gitdir / "config").is_file()):
        raise UpdateProblem("unsupported_install", "requires_standalone_git_clone")
    _safe_config(gitdir)
    try:
        top = Path(_text(root, "rev-parse", "--show-toplevel")).resolve()
        if top != root or _text(root, "rev-parse", "--is-bare-repository") != "false":
            raise UpdateProblem("unsupported_install", "requires_repository_root")
        if _text(root, "symbolic-ref", "--quiet", "--short", "HEAD") != BRANCH:
            raise UpdateProblem("unsupported_install", "requires_main_branch")
        origins = _text(root, "config", "--local", "--get-all", "remote.origin.url").splitlines()
        if origins != [UPSTREAM_URL]:
            raise UpdateProblem("unsupported_install", "unexpected_origin")
        if _text(root, "rev-parse", "--is-shallow-repository") != "false":
            raise UpdateProblem("unsupported_install", "shallow_clone")
        head = _text(root, "rev-parse", "--verify", "HEAD^{commit}")
        if not SHA.fullmatch(head):
            raise UpdateProblem("unsupported_install", "invalid_head")
        _safe_tree(root, head)
        # Includes ignored files: checkout must not overwrite or silently skip them.
        if _text(root, "status", "--porcelain=v1", "--untracked-files=all",
                 "--ignored=matching"):
            raise UpdateProblem("local_changes", "working_tree_not_clean")
        return head
    except GitFailure:
        raise UpdateProblem("unsupported_install", "invalid_git_repository")


def _fetch_main(bare: Path) -> None:
    """Test seam: tests replace this *only* to fetch a local fixture.

    Production always fetches canonical HTTPS main, never a supplied URL.
    """
    _git(bare, "fetch", "--no-tags", "--no-recurse-submodules",
         UPSTREAM_URL, "refs/heads/main", timeout=NETWORK_TIMEOUT,
         protocol="https")


@contextmanager
def _verified_upstream(root: Path, head: str):
    # All ancestry operations take place in a new isolated bare repository.
    with tempfile.TemporaryDirectory(prefix="project-wiki-update-") as temp:
        base = Path(temp)
        bare = base / "verified.git"
        _git(base, "init", "--quiet", "--bare", str(bare))
        try:
            _fetch_main(bare)
            upstream = _text(bare, "rev-parse", "--verify", "FETCH_HEAD^{commit}")
            if not SHA.fullmatch(upstream):
                raise GitFailure("bad_remote_revision")
        except GitFailure:
            raise UpdateProblem("unavailable", "upstream_unreachable")
        # Import HEAD only from the install's own .git; never trust its remotes.
        try:
            _git(bare, "fetch", "--no-tags", "--no-recurse-submodules",
                 str(root / ".git"), head, protocol="file")
            _safe_tree(bare, upstream)
            if head == upstream:
                forward = False
            else:
                ancestry = _git(bare, "merge-base", "--is-ancestor", head, upstream,
                                allow_codes=(0, 1))
                forward = ancestry.returncode == 0
        except GitFailure:
            raise UpdateProblem("unavailable", "history_verification_failed")
        yield bare, upstream, forward


def _state_directory(override: str | None) -> Path:
    if override is not None:
        return Path(override).expanduser().resolve()
    base = os.environ.get("XDG_STATE_HOME", "")
    location = Path(base).expanduser() if base and Path(base).is_absolute() else Path.home() / ".local" / "state"
    return location / "project-wiki" / "skill-updates"


def _state_file(root: Path, directory: Path) -> Path:
    digest = hashlib.sha256(os.fsencode(str(root))).hexdigest()
    return directory / (digest + ".json")


@contextmanager
def _locked(directory: Path, state_path: Path, *, check: bool):
    try:
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        if directory.is_symlink() or not directory.is_dir():
            raise OSError("invalid state directory")
        lock_path = state_path.with_suffix(".lock")
        flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(lock_path, flags, 0o600)
    except OSError:
        raise UpdateProblem("unavailable" if check else "error", "state_unavailable")
    try:
        deadline = time.monotonic() + (0.5 if check else 3.0)
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise UpdateProblem("unavailable" if check else "error", "lock_busy")
                time.sleep(0.05)
        yield
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


def _read_state(path: Path) -> dict:
    if not path.exists() and not path.is_symlink():
        return {"protocol_version": PROTOCOL_VERSION, "suppressed_revision": None}
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        with os.fdopen(fd, "r", encoding="utf-8") as f:
            value = json.load(f)
    except (OSError, UnicodeError, ValueError):
        raise UpdateProblem("error", "state_corrupt")
    if (not isinstance(value, dict) or value.get("protocol_version") != PROTOCOL_VERSION
            or "suppressed_revision" not in value
            or not (value.get("suppressed_revision") is None
                    or (isinstance(value["suppressed_revision"], str)
                        and SHA.fullmatch(value["suppressed_revision"])))):
        raise UpdateProblem("error", "state_corrupt")
    return value


def _write_state(path: Path, suppressed: str | None) -> None:
    fd, name = tempfile.mkstemp(prefix=".skill-update-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            os.fchmod(f.fileno(), 0o600)
            json.dump({"protocol_version": PROTOCOL_VERSION,
                       "suppressed_revision": suppressed}, f, sort_keys=True)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def _run(action: str, root_arg: str, state_dir: str | None,
         revision: str | None, yes: bool) -> dict:
    if action in {"decline", "apply"} and (not revision or not SHA.fullmatch(revision)):
        raise UpdateProblem("error", "revision_required", refresh=True)
    if action == "apply" and not yes:
        raise UpdateProblem("error", "explicit_consent_required")
    try:
        root = Path(root_arg).expanduser().resolve(strict=True)
    except (OSError, RuntimeError):
        raise UpdateProblem("unsupported_install", "skill_root_not_found")
    directory = _state_directory(state_dir)
    path = _state_file(root, directory)
    installed = None
    upstream = None
    with _locked(directory, path, check=action == "check"):
        state = _read_state(path)
        installed = _prepare_install(root)
        with _verified_upstream(root, installed) as (bare, upstream, forward):
            if action != "check" and revision.lower() != upstream:
                return _result("error", installed, upstream, refresh=True,
                               reason="offered_revision_changed")
            if upstream == installed:
                return _result("up_to_date", installed, upstream,
                               reason="already_current")
            if not forward:
                return _result("diverged", installed, upstream,
                               reason="not_forward_descendant")
            if action == "check":
                if state["suppressed_revision"] == upstream:
                    return _result("suppressed", installed, upstream,
                                   reason="declined_this_revision")
                return _result("update_available", installed, upstream)
            if action == "decline":
                _write_state(path, upstream)
                return _result("suppressed", installed, upstream,
                               reason="declined_this_revision")
            # Fetching may take time. Revalidate before any local checkout.
            try:
                _git(root, "fetch", "--no-tags", "--no-recurse-submodules",
                     str(bare), upstream, protocol="file", timeout=NETWORK_TIMEOUT)
            except GitFailure:
                return _result("error", installed, upstream, reason="apply_fetch_failed")
            try:
                if _prepare_install(root) != installed:
                    return _result("error", installed, upstream, refresh=True,
                                   reason="installed_revision_changed")
            except UpdateProblem as exc:
                return _result("error", installed, upstream, refresh=True,
                               reason="install_changed_" + exc.reason)
            try:
                _git(root, "merge", "--ff-only", "--no-edit", upstream,
                     timeout=NETWORK_TIMEOUT)
                if _text(root, "rev-parse", "HEAD") != upstream:
                    raise GitFailure("post_update_mismatch")
            except GitFailure:
                return _result("error", installed, upstream, refresh=True,
                               reason="fast_forward_failed")
            _write_state(path, None)
            return _result("updated", upstream, upstream)


def main(argv: list[str] | None = None) -> int:
    class JsonParser(argparse.ArgumentParser):
        def error(self, message: str) -> None:
            raise UpdateProblem("error", "invalid_arguments")

    parser = JsonParser(description=__doc__)
    parser.add_argument("action", choices=("check", "decline", "apply"))
    parser.add_argument("--skill-root", required=True)
    parser.add_argument("--format", choices=("json",), default="json")
    parser.add_argument("--revision")
    parser.add_argument("--yes", action="store_true")
    parser.add_argument("--state-dir", help="Override local state directory (for tests)")
    requested = argv if argv is not None else sys.argv[1:]
    action = requested[0] if requested else None
    try:
        args = parser.parse_args(argv)
        action = args.action
        result = _run(args.action, args.skill_root, args.state_dir,
                      args.revision, args.yes)
    except UpdateProblem as exc:
        result = _result(exc.status, refresh=exc.refresh, reason=exc.reason)
    except (OSError, GitFailure, ValueError):
        result = _result("error", reason="operation_failed")
    print(json.dumps(result, sort_keys=True))
    return 0 if action == "check" or result["status"] in {
        "suppressed", "updated", "up_to_date",
    } else 1


if __name__ == "__main__":
    sys.exit(main())
