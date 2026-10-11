#!/usr/bin/env python3
"""Conservative, consent-driven updates for standalone project-wiki Git clones.

The only network source in production is the fixed upstream HTTPS main branch.
Checks never update the install. An apply is a verified, clean fast-forward.
"""
from __future__ import annotations

import argparse
import configparser
from contextlib import contextmanager
try:
    import fcntl
except ImportError:  # The updater is optional on non-POSIX hosts.
    fcntl = None
import hashlib
import json
import os
from pathlib import Path
import re
import stat
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


def _safe_git_metadata(gitdir: Path) -> None:
    """Reject Git metadata paths able to redirect local Git writes.

    A standalone .git directory cannot use linked worktree commondir metadata.
    Refuse *all* symlinks and special entries under .git (including nested
    refs, logs and objects). This is conservative and is not a race-proof
    defense against another process modifying metadata during the operation.
    """
    try:
        stack = [gitdir]
        while stack:
            folder = stack.pop()
            with os.scandir(folder) as entries:
                for entry in entries:
                    if folder == gitdir and entry.name == "commondir":
                        raise UpdateProblem("unsupported_install", "unsafe_git_metadata")
                    mode = entry.stat(follow_symlinks=False).st_mode
                    if stat.S_ISDIR(mode):
                        stack.append(Path(entry.path))
                    elif not stat.S_ISREG(mode):
                        raise UpdateProblem("unsupported_install", "unsafe_git_metadata")
    except (OSError, ValueError):
        raise UpdateProblem("unsupported_install", "unsafe_git_metadata")

    for name in ("info/attributes", "info/grafts", "objects/info/alternates",
                 "shallow", "index.lock", "MERGE_HEAD", "REBASE_HEAD",
                 "CHERRY_PICK_HEAD", "REVERT_HEAD", "BISECT_LOG",
                 "rebase-apply", "rebase-merge", "sequencer"):
        if (gitdir / name).exists():
            raise UpdateProblem("unsupported_install", "unsafe_git_metadata")


def _safe_config(gitdir: Path) -> None:
    _safe_git_metadata(gitdir)  # Must precede opening even the config file.
    cfg = configparser.RawConfigParser(interpolation=None, strict=False)
    try:
        with (gitdir / "config").open("r", encoding="utf-8") as f:
            cfg.read_file(f)
    except (OSError, UnicodeError, configparser.Error):
        raise UpdateProblem("unsupported_install", "git_config_unreadable")
    for section in cfg.sections():
        # Git accepts both modern [filter "x"] and legacy [filter.x].
        name = section.casefold()
        prefix = name.split(None, 1)[0].split(".", 1)[0]
        if prefix in {"include", "includeif", "filter", "url", "submodule"} or name == "extensions":
            raise UpdateProblem("unsupported_install", "unsafe_git_config")
        if name == "core":
            blocked = {
                "worktree", "sparsecheckout", "sparsecheckoutcone",
                "hookspath", "fsmonitor", "attributesfile", "splitindex",
            }
            if (any(option.casefold() in blocked for option in cfg.options(section))
                    or cfg.get(section, "bare", fallback="false").casefold() != "false"):
                raise UpdateProblem("unsupported_install", "unsafe_git_config")


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
                or any(p.casefold() in {".gitattributes", ".git", "__pycache__"} for p in parts)
                or path.casefold().endswith(".pyc")
                or any(p in {".", ".."} for p in parts)):
            raise UpdateProblem("unsupported_install", "unsafe_tree")


def _safe_ignored_caches(root: Path) -> None:
    # Normal Python imports generate ignored bytecode. Never delete these files;
    # _safe_tree keeps both checkout revisions from writing into their paths.
    # Git omits special files such as FIFOs from ls-files/status. Inspect entry
    # types without following links, so those cannot hide inside ignored caches.
    try:
        stack = [root]
        while stack:
            folder = stack.pop()
            with os.scandir(folder) as entries:
                for entry in entries:
                    if folder == root and entry.name == ".git":
                        continue
                    mode = entry.stat(follow_symlinks=False).st_mode
                    if stat.S_ISDIR(mode):
                        stack.append(Path(entry.path))
                    elif not stat.S_ISREG(mode):
                        raise OSError("unsafe working-tree entry")
    except OSError:
        raise UpdateProblem("local_changes", "working_tree_not_clean")
    ignored = _git(root, "ls-files", "--others", "--ignored", "--exclude-standard", "-z")
    for relative in ignored.stdout.split("\0"):
        if not relative:
            continue
        path = Path(relative)
        if (path.is_absolute() or ".." in path.parts
                or path.parent.name != "__pycache__" or path.suffix != ".pyc"):
            raise UpdateProblem("local_changes", "working_tree_not_clean")
        try:
            current = root
            for component in path.parts[:-1]:
                current = current / component
                if not stat.S_ISDIR(current.lstat().st_mode):
                    raise OSError("unsafe cache ancestor")
            if not stat.S_ISREG((root / path).lstat().st_mode):
                raise OSError("unsafe cache file")
        except OSError:
            raise UpdateProblem("local_changes", "working_tree_not_clean")


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
        if _text(root, "status", "--porcelain=v1", "--untracked-files=all"):
            raise UpdateProblem("local_changes", "working_tree_not_clean")
        _safe_ignored_caches(root)
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
        location = Path(override).expanduser()
    else:
        base = os.environ.get("XDG_STATE_HOME", "")
        parent = (Path(base).expanduser() if base and Path(base).is_absolute()
                  else Path.home() / ".local" / "state")
        location = parent / "project-wiki" / "skill-updates"
    # Normalize without following any symlink (Path.resolve would hide one).
    return Path(os.path.abspath(location))


def _private_regular(fd: int) -> None:
    info = os.fstat(fd)
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
            or info.st_mode & 0o077 or info.st_nlink != 1):
        raise OSError("unsafe state entry")


def _private_directory(directory: Path) -> None:
    # Existing ancestor symlinks can silently redirect mkdir and state writes.
    for part in (directory, *directory.parents):
        try:
            info = part.lstat()
        except FileNotFoundError:
            continue
        if (not stat.S_ISDIR(info.st_mode)
                or (info.st_mode & 0o022 and not info.st_mode & stat.S_ISVTX)):
            raise OSError("unsafe state directory path")
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = directory.lstat()
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid()
            or info.st_mode & 0o077):
        raise OSError("state directory must be owner-private")


def _state_file(root: Path, directory: Path) -> Path:
    digest = hashlib.sha256(os.fsencode(str(root))).hexdigest()
    return directory / (digest + ".json")


@contextmanager
def _locked(directory: Path, state_path: Path, *, check: bool):
    fd = None
    try:
        _private_directory(directory)
        lock_path = state_path.with_suffix(".lock")
        flags = os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK
        fd = os.open(lock_path, flags, 0o600)
        _private_regular(fd)
    except OSError:
        if fd is not None:
            os.close(fd)
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
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        return {"protocol_version": PROTOCOL_VERSION, "suppressed_revision": None}
    except OSError:
        raise UpdateProblem("error", "state_corrupt")
    try:
        _private_regular(fd)
        with os.fdopen(fd, "r", encoding="utf-8") as f:
            fd = None  # fdopen now owns it
            value = json.load(f)
    except (OSError, UnicodeError, ValueError):
        raise UpdateProblem("error", "state_corrupt")
    finally:
        if fd is not None:
            os.close(fd)
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
    if os.name != "posix" or fcntl is None or not hasattr(os, "O_NOFOLLOW"):
        raise UpdateProblem("unavailable" if action == "check" else "unsupported_install",
                            "posix_updater_only")
    if action in {"decline", "apply"} and (not revision or not SHA.fullmatch(revision)):
        raise UpdateProblem("error", "revision_required")
    if action == "apply" and not yes:
        raise UpdateProblem("error", "explicit_consent_required")
    try:
        root = Path(root_arg).expanduser().resolve(strict=True)
    except (OSError, RuntimeError):
        raise UpdateProblem("unsupported_install", "skill_root_not_found")
    directory = _state_directory(state_dir)
    path = _state_file(root, directory)
    mutation_started = False
    try:
        with _locked(directory, path, check=action == "check"):
            state = _read_state(path)
            installed = _prepare_install(root)
            with _verified_upstream(root, installed) as (bare, upstream, forward):
                if action != "check" and revision.lower() != upstream:
                    return _result("error", installed, upstream,
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
                # Fetching may take time. Revalidate immediately before checkout.
                try:
                    _safe_git_metadata(root / ".git")
                    _git(root, "fetch", "--no-tags", "--no-recurse-submodules",
                         str(bare), upstream, protocol="file", timeout=NETWORK_TIMEOUT)
                except (GitFailure, UpdateProblem):
                    return _result("error", installed, upstream,
                                   reason="apply_fetch_failed")
                try:
                    if _prepare_install(root) != installed:
                        return _result("error", installed, upstream,
                                       reason="installed_revision_changed")
                except UpdateProblem as exc:
                    return _result("error", installed, upstream,
                                   reason="install_changed_" + exc.reason)
                mutation_started = True  # From here disk state may be different.
                try:
                    _git(root, "merge", "--ff-only", "--no-edit", upstream,
                         timeout=NETWORK_TIMEOUT)
                    if _text(root, "rev-parse", "HEAD") != upstream:
                        raise GitFailure("post_update_mismatch")
                except GitFailure:
                    return _result("error", installed, upstream, refresh=True,
                                   reason="fast_forward_failed")
                # HEAD has been verified. A refusal-state cleanup error does
                # not undo the successful update, but still mandates reload.
                try:
                    _write_state(path, None)
                except OSError:
                    return _result("updated", upstream, upstream, refresh=True,
                                   reason="state_reset_failed")
                return _result("updated", upstream, upstream, refresh=True)
    except (OSError, GitFailure, ValueError):
        # Covers unexpected failures when leaving either context manager too.
        raise UpdateProblem("error", "operation_failed", refresh=mutation_started)


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
    if result["reason"] == "invalid_arguments":
        return 1
    return 0 if action == "check" or result["status"] in {
        "suppressed", "updated", "up_to_date",
    } else 1


if __name__ == "__main__":
    sys.exit(main())
