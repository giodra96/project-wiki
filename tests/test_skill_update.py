"""Offline integration tests for conservative skill updates."""
from __future__ import annotations

from contextlib import redirect_stdout
import fcntl
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

MODULE = Path(__file__).resolve().parents[1] / "scripts" / "skill_update.py"
spec = importlib.util.spec_from_file_location("skill_update", MODULE)
assert spec and spec.loader
update = importlib.util.module_from_spec(spec)
spec.loader.exec_module(update)


def git(directory: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(directory), *arguments],
        capture_output=True, text=True, check=True, timeout=8,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0",
             "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull},
    )
    return result.stdout.strip()


class SkillUpdateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.source = self.base / "local-fixture-source"
        self.install = self.base / "install"
        self.state_dir = self.base / "private-state"
        git(self.base, "init", "-q", "-b", "main", str(self.source))
        git(self.source, "config", "user.name", "Updater Tests")
        git(self.source, "config", "user.email", "update@example.invalid")
        (self.source / "README.md").write_text("version 1\n")
        git(self.source, "add", "README.md")
        git(self.source, "commit", "-qm", "initial")
        self.first = git(self.source, "rev-parse", "HEAD")
        git(self.base, "clone", "-q", str(self.source), str(self.install))
        git(self.install, "config", "user.name", "Updater Tests")
        git(self.install, "config", "user.email", "update@example.invalid")
        git(self.install, "remote", "set-url", "origin", update.UPSTREAM_URL)
        self._enable_offline_fetch()

    def _enable_offline_fetch(self):
        # Replace the sole remote-fetch function, never the origin guard.
        def local_fixture_fetch(bare):
            return update._git(
                bare, "fetch", "--no-tags", "--no-recurse-submodules",
                str(self.source), "refs/heads/main", protocol="file",
            )
        patch = mock.patch.object(update, "_fetch_main", side_effect=local_fixture_fetch)
        patch.start()
        self.addCleanup(patch.stop)

    def commit_upstream(self, text=None, filename="README.md"):
        location = self.source / filename
        location.parent.mkdir(exist_ok=True, parents=True)
        location.write_text(text if text is not None else "next version\n")
        git(self.source, "add", "--all")
        git(self.source, "commit", "-qm", "fixture-next")
        return git(self.source, "rev-parse", "HEAD")

    def invoke(self, action="check", revision=None, yes=False, root=None):
        args = [action, "--skill-root", str(root or self.install),
                "--format", "json", "--state-dir", str(self.state_dir)]
        if revision is not None:
            args += ["--revision", revision]
        if yes:
            args += ["--yes"]
        stream = io.StringIO()
        with redirect_stdout(stream):
            code = update.main(args)
        result = json.loads(stream.getvalue())
        self.assertEqual(result["protocol_version"], 1)
        self.assertEqual(set(result), {
            "protocol_version", "status", "installed_revision",
            "upstream_revision", "can_apply", "requires_refresh", "reason",
        })
        self.assertEqual(result["can_apply"], result["status"] == "update_available")
        return code, result

    def assert_status(self, wanted, *args, **kwargs):
        code, result = self.invoke(*args, **kwargs)
        self.assertEqual(result["status"], wanted, result)
        if kwargs.get("action") == "check" or not args or args[0] == "check":
            self.assertEqual(code, 0)
        return code, result

    def test_up_to_date(self):
        code, result = self.invoke()
        self.assertEqual((code, result["status"]), (0, "up_to_date"))
        self.assertEqual(result["installed_revision"], self.first)
        self.assertEqual(result["upstream_revision"], self.first)

    def test_update_offer_and_json(self):
        ahead = self.commit_upstream()
        code, result = self.invoke()
        self.assertEqual((code, result["status"]), (0, "update_available"))
        self.assertEqual((result["installed_revision"], result["upstream_revision"]),
                         (self.first, ahead))
        self.assertFalse(result["requires_refresh"])
        self.assertEqual(git(self.install, "rev-parse", "HEAD"), self.first)
        self.assertFalse(list(self.state_dir.glob("*.json")))

    def test_decline_suppresses_exact_sha_but_new_revision_is_offered(self):
        offered = self.commit_upstream()
        self.assertEqual(self.invoke()[1]["status"], "update_available")
        code, result = self.invoke("decline", offered)
        self.assertEqual((code, result["status"]), (0, "suppressed"))
        self.assertEqual(self.invoke()[1]["status"], "suppressed")
        path = update._state_file(self.install.resolve(), self.state_dir)
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(json.loads(path.read_text())["suppressed_revision"], offered)
        new_offer = self.commit_upstream("version 3\n")
        self.assertNotEqual(new_offer, offered)
        self.assertEqual(self.invoke()[1]["status"], "update_available")
        self.assertEqual(git(self.install, "rev-parse", "HEAD"), self.first)

    def test_apply_requires_consent_exact_revision_and_updates(self):
        ahead = self.commit_upstream()
        code, denied = self.invoke("apply", ahead)
        self.assertNotEqual(code, 0)
        self.assertEqual(denied["reason"], "explicit_consent_required")
        code, missing = self.invoke("apply", yes=True)
        self.assertNotEqual(code, 0)
        self.assertEqual(missing["reason"], "revision_required")
        code, invalid = self.invoke("apply", "bad", True)
        self.assertNotEqual(code, 0)
        self.assertEqual(invalid["reason"], "revision_required")
        code, applied = self.invoke("apply", ahead, True)
        self.assertEqual((code, applied["status"]), (0, "updated"))
        self.assertEqual(applied["installed_revision"], ahead)
        self.assertEqual((self.install / "README.md").read_text(), "next version\n")
        self.assertEqual(git(self.install, "remote", "get-url", "origin"),
                         update.UPSTREAM_URL)
        self.assertEqual(self.invoke()[1]["status"], "up_to_date")

    def test_stale_offer_never_applies_or_declines(self):
        old = self.commit_upstream()
        newer = self.commit_upstream("further\n")
        for action, yes in (("apply", True), ("decline", False)):
            code, result = self.invoke(action, old, yes)
            self.assertNotEqual(code, 0)
            self.assertEqual(result["reason"], "offered_revision_changed")
            self.assertTrue(result["requires_refresh"])
            self.assertEqual(result["upstream_revision"], newer)
        self.assertEqual(git(self.install, "rev-parse", "HEAD"), self.first)
        self.assertFalse(list(self.state_dir.glob("*.json")))

    def test_decline_needs_sha(self):
        for revision in (None, "123", "z" * 40):
            code, result = self.invoke("decline", revision)
            self.assertEqual((code, result["reason"]), (1, "revision_required"))

    def test_unavailable_network_is_nonfatal_check_and_fatal_apply(self):
        self.commit_upstream()
        with mock.patch.object(update, "_fetch_main", side_effect=update.GitFailure()):
            code, result = self.invoke()
            self.assertEqual((code, result["status"]), (0, "unavailable"))
            code, result = self.invoke("apply", "0" * 40, True)
            self.assertNotEqual(code, 0)
            self.assertEqual(result["status"], "unavailable")

    def test_local_changes_tracked_untracked_ignored(self):
        self.commit_upstream()
        readme = self.install / "README.md"
        readme.write_text("local edit")
        self.assertEqual(self.invoke()[1]["status"], "local_changes")
        readme.write_text("version 1\n")
        (self.install / "untracked.txt").write_text("not safe")
        self.assertEqual(self.invoke()[1]["status"], "local_changes")
        (self.install / "untracked.txt").unlink()
        # .git/info/exclude is Git metadata but not checkout behavior.
        with (self.install / ".git" / "info" / "exclude").open("a") as f:
            f.write("\nignored.dat\n")
        (self.install / "ignored.dat").write_text("ignored")
        self.assertEqual(self.invoke()[1]["status"], "local_changes")

    def test_reject_non_clone_copy_and_parent_repository(self):
        plain = self.base / "plain"
        plain.mkdir()
        shutil.copyfile(self.install / "README.md", plain / "README.md")
        self.assertEqual(self.invoke(root=plain)[1]["status"], "unsupported_install")
        parent = self.base / "unrelated-parent"
        git(self.base, "init", "-q", "-b", "main", str(parent))
        child = parent / "skill-copy"
        shutil.copytree(plain, child)
        self.assertEqual(self.invoke(root=child)[1]["status"], "unsupported_install")
        self.assertEqual(self.invoke(root=parent)[1]["status"], "unsupported_install")

    def test_worktree_and_symlink_skill_path(self):
        worktree = self.base / "linked-worktree"
        git(self.install, "worktree", "add", "-q", "--detach", str(worktree))
        self.assertTrue((worktree / ".git").is_file())
        self.assertEqual(self.invoke(root=worktree)[1]["status"], "unsupported_install")
        alias = self.base / "symlink-install"
        alias.symlink_to(self.install, target_is_directory=True)
        self.assertEqual(self.invoke(root=alias)[1]["status"], "up_to_date")

    def test_changed_origin_branch_and_remote_config(self):
        self.commit_upstream()
        git(self.install, "remote", "set-url", "origin", "https://example.invalid/fork.git")
        result = self.invoke()[1]
        self.assertEqual(result["reason"], "unexpected_origin")
        git(self.install, "remote", "set-url", "origin", update.UPSTREAM_URL)
        git(self.install, "switch", "-qc", "other")
        self.assertEqual(self.invoke()[1]["reason"], "requires_main_branch")
        git(self.install, "switch", "-q", "main")
        git(self.install, "config", "--add", "include.path", "/not/read")
        self.assertEqual(self.invoke()[1]["reason"], "unsafe_git_config")

    def test_forward_vs_diverged(self):
        self.commit_upstream()
        self.assertEqual(self.invoke()[1]["status"], "update_available")
        (self.install / "README.md").write_text("local commit\n")
        git(self.install, "add", "README.md")
        git(self.install, "commit", "-qm", "local non-upstream commit")
        self.assertEqual(self.invoke()[1]["status"], "diverged")

    def test_upstream_rewind_is_diverged(self):
        self.commit_upstream()
        git(self.install, "fetch", "-q", str(self.source), "main")
        git(self.install, "merge", "-q", "--ff-only", "FETCH_HEAD")
        git(self.source, "reset", "--hard", self.first)
        self.assertEqual(self.invoke()[1]["status"], "diverged")

    def test_untrusted_tree_rejected(self):
        self.commit_upstream("* -filter=evil\n", ".gitattributes")
        self.assertEqual(self.invoke()[1]["reason"], "unsafe_tree")

    def test_symlinks_from_upstream_rejected(self):
        (self.source / "remote-link").symlink_to("/etc/passwd")
        git(self.source, "add", "remote-link")
        git(self.source, "commit", "-qm", "symlink")
        self.assertEqual(self.invoke()[1]["reason"], "unsafe_tree")
        self.assertFalse((self.install / "remote-link").exists())

    def test_attributes_and_local_filter_rejected(self):
        (self.install / ".git" / "info" / "attributes").write_text("* filter=evil\n")
        self.assertEqual(self.invoke()[1]["reason"], "unsafe_git_metadata")
        (self.install / ".git" / "info" / "attributes").unlink()
        git(self.install, "config", "filter.evil.smudge", "/bin/false")
        self.assertEqual(self.invoke()[1]["reason"], "unsafe_git_config")

    def test_active_merge_metadata_rejected(self):
        (self.install / ".git" / "MERGE_HEAD").write_text(self.first + "\n")
        self.assertEqual(self.invoke()[1]["reason"], "unsafe_git_metadata")

    def test_corrupt_state_never_offers_updates(self):
        self.commit_upstream()
        self.state_dir.mkdir(exist_ok=True)
        state = update._state_file(self.install.resolve(), self.state_dir)
        for broken in ('not-json', '{"protocol_version":1}', '{"protocol_version":99,"suppressed_revision":null}'):
            state.write_text(broken)
            code, result = self.invoke()
            self.assertEqual((code, result["status"], result["reason"]),
                             (0, "error", "state_corrupt"))

    def test_failed_apply_does_not_change_head_or_files(self):
        ahead = self.commit_upstream()
        actual = update._git

        def failed_local_fetch(directory, *args, **kwargs):
            if directory == self.install and args and args[0] == "fetch":
                raise update.GitFailure("simulated_failure")
            return actual(directory, *args, **kwargs)

        with mock.patch.object(update, "_git", side_effect=failed_local_fetch):
            code, result = self.invoke("apply", ahead, True)
        self.assertEqual(result["reason"], "apply_fetch_failed")
        self.assertNotEqual(code, 0)
        self.assertEqual(git(self.install, "rev-parse", "HEAD"), self.first)
        self.assertEqual((self.install / "README.md").read_text(), "version 1\n")

    def test_detects_racing_working_tree_changes_before_checkout(self):
        ahead = self.commit_upstream()
        actual = update._git

        def edit_during_fetch(directory, *args, **kwargs):
            result = actual(directory, *args, **kwargs)
            if directory == self.install and args and args[0] == "fetch":
                (self.install / "README.md").write_text("concurrent edit")
            return result

        with mock.patch.object(update, "_git", side_effect=edit_during_fetch):
            code, result = self.invoke("apply", ahead, True)
        self.assertEqual(result["reason"], "install_changed_working_tree_not_clean")
        self.assertNotEqual(code, 0)
        self.assertEqual(git(self.install, "rev-parse", "HEAD"), self.first)
        self.assertEqual((self.install / "README.md").read_text(), "concurrent edit")

    def test_post_merge_hook_not_executed(self):
        ahead = self.commit_upstream()
        indicator = self.base / "hook-ran"
        hook = self.install / ".git" / "hooks" / "post-merge"
        hook.write_text("#!/bin/sh\ntouch " + str(indicator) + "\n")
        hook.chmod(0o755)
        code, result = self.invoke("apply", ahead, True)
        self.assertEqual((code, result["status"]), (0, "updated"))
        self.assertFalse(indicator.exists())

    def test_lock_contention_fails_open(self):
        self.state_dir.mkdir(exist_ok=True)
        lockfile = update._state_file(self.install.resolve(), self.state_dir).with_suffix(".lock")
        with lockfile.open("w") as file:
            fcntl.flock(file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            code, result = self.invoke()
            self.assertEqual((code, result["status"], result["reason"]),
                             (0, "unavailable", "lock_busy"))

    def test_changed_origin_after_fetch_aborts_apply(self):
        ahead = self.commit_upstream()
        actual = update._git

        def replace_origin(directory, *args, **kwargs):
            result = actual(directory, *args, **kwargs)
            if directory == self.install and args and args[0] == "fetch":
                git(self.install, "remote", "set-url", "origin",
                    "https://example.invalid/changed.git")
            return result

        with mock.patch.object(update, "_git", side_effect=replace_origin):
            code, result = self.invoke("apply", ahead, True)
        self.assertNotEqual(code, 0)
        self.assertEqual(result["reason"], "install_changed_unexpected_origin")
        self.assertEqual(git(self.install, "rev-parse", "HEAD"), self.first)

    def test_changed_branch_after_fetch_aborts_apply(self):
        ahead = self.commit_upstream()
        git(self.install, "branch", "other")
        actual = update._git

        def switch_branch(directory, *args, **kwargs):
            result = actual(directory, *args, **kwargs)
            if directory == self.install and args and args[0] == "fetch":
                git(self.install, "switch", "-q", "other")
            return result

        with mock.patch.object(update, "_git", side_effect=switch_branch):
            code, result = self.invoke("apply", ahead, True)
        self.assertNotEqual(code, 0)
        self.assertEqual(result["reason"], "install_changed_requires_main_branch")
        self.assertEqual(git(self.install, "rev-parse", "HEAD"), self.first)

    def test_failed_checkout_keeps_original_head_and_files(self):
        ahead = self.commit_upstream()
        actual = update._git

        def failed_merge(directory, *args, **kwargs):
            if directory == self.install and args and args[0] == "merge":
                raise update.GitFailure("simulated_merge_failure")
            return actual(directory, *args, **kwargs)

        with mock.patch.object(update, "_git", side_effect=failed_merge):
            code, result = self.invoke("apply", ahead, True)
        self.assertNotEqual(code, 0)
        self.assertEqual(result["reason"], "fast_forward_failed")
        self.assertEqual(git(self.install, "rev-parse", "HEAD"), self.first)
        self.assertEqual((self.install / "README.md").read_text(), "version 1\n")

    def test_json_on_invalid_arguments(self):
        output = io.StringIO()
        with redirect_stdout(output):
            code = update.main(["apply", "--skill-root", str(self.install),
                                "--invalid-argument"])
        self.assertNotEqual(code, 0)
        self.assertEqual(json.loads(output.getvalue())["reason"], "invalid_arguments")

    def test_xdg_state_location(self):
        with mock.patch.dict(os.environ, {"XDG_STATE_HOME": str(self.base / "xdg")}):
            self.assertEqual(
                update._state_directory(None),
                self.base / "xdg" / "project-wiki" / "skill-updates",
            )

    def test_environment_blocks_git_injection(self):
        with mock.patch.dict(os.environ, {
            "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": "core.hooksPath",
            "GIT_CONFIG_VALUE_0": "/tmp/evil",
            "GIT_DIR": "/not/this-repo",
        }):
            env = update._git_env()
            self.assertNotIn("GIT_CONFIG_COUNT", env)
            self.assertNotIn("GIT_DIR", env)
            self.assertEqual(env["GIT_TERMINAL_PROMPT"], "0")
            self.assertEqual(env["GIT_CONFIG_GLOBAL"], os.devnull)
            self.assertEqual(self.invoke()[1]["status"], "up_to_date")


if __name__ == "__main__":
    unittest.main()
