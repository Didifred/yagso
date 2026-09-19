"""Regression tests for the bug-fix + status-feature batch.

These tests run offline (no git fixture repo, no network): the git-backed
integration tests live in test_cli.py / test_git_ops.py. The `_search_submodule`
rewrite and the merged `get_submodule_field` are pure logic over dicts, so they
are exercised here directly.
"""
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from yagso.core.orchestrator import (
    SubmoduleOrchestrator,
    DiffStatus,
)
from yagso.domain.manifest import Manifest
from yagso.domain.bom import Bom
from yagso.domain.submodule import SubmoduleDefinition
from yagso.infrastructure.manifest_manager import ManifestManager

# pylint: skip-file


def _sub(name="lib1", path="lib1", url="https://github.com/a/b.git",
         commit="c1111111111111111111111111111111111111111", branch=None):
    return SubmoduleDefinition(
        root_path=path,
        name=name,
        path=path,
        url=url,
        commit=commit,
        tracking_branch=branch,
    )


def _block(name="lib1", path="lib1", url="https://github.com/a/b.git",
           commit="c1111111111111111111111111111111111111111", branch=None):
    b = {"name": name, "path": path, "url": url, "commit": commit}
    if branch:
        b["branch"] = branch
    return b


class TestSearchSubmodule(unittest.TestCase):
    """The rewritten _search_submodule, tested as pure dict logic."""

    def setUp(self):
        self.orch = SubmoduleOrchestrator(Path("."))

    def test_unchanged(self):
        blocks = [_block()]
        result = self.orch._search_submodule(_sub(), blocks)
        self.assertEqual(result.status, DiffStatus.UNCHANGED)
        self.assertEqual(result.name, "lib1")
        self.assertEqual(blocks, [], "matched block must be consumed")

    def test_modified_commit(self):
        blocks = [_block(commit="c2222222222222222222222222222222222222222")]
        result = self.orch._search_submodule(_sub(), blocks)
        self.assertEqual(result.status, DiffStatus.MODIFIED)
        self.assertEqual(blocks, [])

    def test_modified_name(self):
        blocks = [_block(name="other")]
        result = self.orch._search_submodule(_sub(), blocks)
        self.assertEqual(result.status, DiffStatus.MODIFIED)
        self.assertEqual(blocks, [])

    def test_modified_branch(self):
        blocks = [_block(branch="develop")]
        result = self.orch._search_submodule(
            _sub(branch="main"), blocks)
        self.assertEqual(result.status, DiffStatus.MODIFIED)
        self.assertEqual(blocks, [])

    def test_url_change_same_repo(self):
        blocks = [_block(url="git@github.com:a/b.git")]
        with patch("yagso.core.orchestrator.GitOperations.is_same_repo",
                   return_value=True) as mock:
            result = self.orch._search_submodule(_sub(), blocks)
        mock.assert_called_once()
        self.assertEqual(result.status, DiffStatus.MODIFIED)
        self.assertEqual(blocks, [])

    def test_url_change_different_repo(self):
        # A genuinely different repository at the same path: the old block is
        # left in place so the caller's removal pass drops it (remove + add).
        blocks = [_block(url="https://github.com/x/y.git")]
        with patch("yagso.core.orchestrator.GitOperations.is_same_repo",
                   return_value=False):
            result = self.orch._search_submodule(_sub(), blocks)
        self.assertEqual(result.status, DiffStatus.ADDED)
        self.assertEqual(len(blocks), 1, "orphan block must survive for removal pass")

    def test_added_when_not_found(self):
        blocks = [_block(path="lib2", name="lib2",
                         url="https://github.com/a/c.git")]
        sub = _sub(path="lib3", name="lib3", url="https://github.com/a/d.git")
        result = self.orch._search_submodule(sub, blocks)
        self.assertEqual(result.status, DiffStatus.ADDED)
        self.assertEqual(len(blocks), 1, "unrelated block untouched")

    def test_moved_same_identity_different_path(self):
        blocks = [_block(path="old/lib1")]
        result = self.orch._search_submodule(_sub(), blocks)
        self.assertEqual(result.status, DiffStatus.MOVED)
        self.assertEqual(result.name, "lib1")
        self.assertEqual(blocks, [])

    def test_moved_not_poisoned_by_previous_block(self):
        # Regression: the old implementation compared against a loop-carried
        # `git_name` that was set to the manifest's own name after the first
        # non-matching block, so a *different* submodule sharing url+commit
        # was misclassified as MOVED and removed from the blocks list.
        # Here B2 has a different name and must NOT be consumed.
        blocks = [
            _block(
                path="lib1",
                name="lib1",
                url="https://github.com/a/b.git",
                commit="c1111111111111111111111111111111111111111"),
            _block(
                path="lib2",
                name="lib2",
                url="https://github.com/a/b.git",
                commit="c1111111111111111111111111111111111111111"),
        ]
        sub = _sub(path="moved/lib1", name="lib1")
        result = self.orch._search_submodule(sub, blocks)
        self.assertEqual(result.status, DiffStatus.MOVED)
        self.assertEqual(result.name, "lib1")
        self.assertEqual(
            [b["name"] for b in blocks], ["lib2"],
            "lib2 shares url+commit but not name: must survive as orphan")


class TestStatusReport(unittest.TestCase):
    """The new read-only `status` dry-run, offline via _diff_manifest."""

    def setUp(self):
        self.orch = SubmoduleOrchestrator(Path("."))

    def _manifest(self, *subs):
        return Manifest(submodules=list(subs))

    def test_all_unchanged(self):
        subs = [_sub(), _sub(name="lib2", path="lib2",
                             url="https://github.com/a/c.git")]
        blocks = [_block(), _block(name="lib2", path="lib2",
                                   url="https://github.com/a/c.git")]
        report = self.orch._diff_manifest(self._manifest(*subs), blocks)
        self.assertEqual([r.status for r in report],
                         [DiffStatus.UNCHANGED, DiffStatus.UNCHANGED])
        self.assertEqual(blocks, [])

    def test_orphan_block_reported_removed(self):
        subs = [_sub()]
        blocks = [_block(), _block(name="orphan", path="lib9",
                                   url="https://github.com/a/c.git")]
        report = self.orch._diff_manifest(self._manifest(*subs), blocks)
        by_path = {r.path: r.status for r in report}
        self.assertEqual(by_path["lib1"], DiffStatus.UNCHANGED)
        self.assertEqual(by_path["lib9"], DiffStatus.REMOVED)
        self.assertEqual(len(report), 2)

    def test_added_and_modified_flags(self):
        subs = [
            _sub(),
            _sub(name="newlib", path="libs/newlib",
                 url="https://github.com/a/d.git"),
        ]
        blocks = [_block(commit="c2222222222222222222222222222222222222222")]
        report = self.orch._diff_manifest(self._manifest(*subs), blocks)
        by_path = {r.path: r.status for r in report}
        self.assertEqual(by_path["lib1"], DiffStatus.MODIFIED)
        self.assertEqual(by_path["libs/newlib"], DiffStatus.ADDED)

    def test_nested_status_report_recurses(self):
        parent = _sub(name="outer", path="outer",
                      url="https://github.com/a/b.git")
        child = _sub(name="inner", path="inner",
                     url="https://github.com/a/c.git")
        parent.submodules = [child]
        top_blocks = [_block(name="outer", path="outer",
                             url="https://github.com/a/b.git",
                             commit=parent.commit)]

        with patch("yagso.core.orchestrator.GitOperations.read_gitmodules_blocks",
                   side_effect=[top_blocks, []]):
            report = self.orch._diff_manifest(
                self._manifest(parent),
                list(top_blocks),
                root_path=Path("/repo"),
            )

        by_path = {r.path: r.status for r in report}
        self.assertEqual(by_path["outer"], DiffStatus.UNCHANGED)
        self.assertEqual(by_path["inner"], DiffStatus.ADDED)

    def test_status_report_missing_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError):
                self.orch.status_report(Path(tmp))


class TestGetSubmoduleFieldMerged(unittest.TestCase):
    """The duplicate method was merged into one handling Manifest AND Bom."""

    def setUp(self):
        self.manager = ManifestManager()

    def _manifest_dict(self):
        return {
            "version": "1.1",
            "submodules": [{
                "name": "lib1",
                "path": "lib1",
                "url": "https://github.com/a/b.git",
                "commit": "c1111111111111111111111111111111111111111",
            }],
        }

    def test_get_from_manifest(self):
        manifest = Manifest.from_dict(self._manifest_dict())
        self.assertEqual(
            self.manager.get_submodule_field(manifest, "lib1", "commit"),
            "c1111111111111111111111111111111111111111")

    def test_get_from_bom(self):
        bom = Bom.from_dict({
            "version": "1.0",
            "submodules": [{
                "path": "lib1",
                "commit": "c1111111111111111111111111111111111111111",
                "files": ["a.c"],
            }],
        })
        self.assertEqual(
            self.manager.get_submodule_field(bom, "lib1", "files"), ["a.c"])

    def test_missing_submodule_raises_filenotfound(self):
        manifest = Manifest.from_dict(self._manifest_dict())
        with self.assertRaises(FileNotFoundError):
            self.manager.get_submodule_field(manifest, "nope", "commit")

    def test_invalid_field_raises_valueerror(self):
        manifest = Manifest.from_dict(self._manifest_dict())
        with self.assertRaises(ValueError):
            self.manager.get_submodule_field(manifest, "lib1", "no_such_field")

    def test_nested_lookup(self):
        data = self._manifest_dict()
        data["submodules"][0]["submodules"] = [{
            "name": "inner",
            "path": "inner",
            "url": "https://github.com/a/c.git",
            "commit": "c3333333333333333333333333333333333333333",
        }]
        manifest = Manifest.from_dict(data)
        self.assertEqual(
            self.manager.get_submodule_field(manifest, "lib1/inner", "name"),
            "inner")


class TestPushAndUpdateDefaults(unittest.TestCase):
    """push_changes now delegates to GitOperations.push_all(); update defaults
    match the README (no init unless requested)."""

    def test_push_changes_delegates_to_push_all(self):
        orch = SubmoduleOrchestrator(Path("."))
        with patch("yagso.core.orchestrator.GitOperations") as mock_cls:
            mock_ops = mock_cls.return_value.__enter__.return_value
            orch.push_changes()
        mock_ops.push_all.assert_called_once_with()

    def test_update_defaults_to_no_init(self):
        from yagso.infrastructure.git_ops import GitOperations
        ops = GitOperations.__new__(GitOperations)
        ops._repo = MagicMock()
        repo = ops._repo

        ops.update_all_submodules({})
        repo.git.submodule.assert_called_once_with("update", "--recursive")

        ops.update_all_submodules({"init": True})
        repo.git.submodule.assert_called_with("update", "--init", "--recursive")

        ops.update_all_submodules({"init": True, "remote": True})
        repo.git.submodule.assert_called_with(
            "update", "--init", "--remote", "--recursive")


class TestCommitAllDetachedHead(unittest.TestCase):
    """commit_all must raise (not silently proceed) on a detached HEAD."""

    def test_commit_all_raises_on_detached_head(self):
        from yagso.infrastructure.git_ops import GitOperations
        import git as gitlib
        with tempfile.TemporaryDirectory() as tmp:
            repo_path = Path(tmp) / "repo"
            repo = gitlib.Repo.init(repo_path)
            try:
                repo.config_writer().set_value('user', 'name', 'Test').release()
                repo.config_writer().set_value('user', 'email', 'test@example.com').release()
                (repo_path / "README.md").write_text("hi\n", encoding="utf-8")
                repo.index.add(["README.md"])
                commit = repo.index.commit("initial")
                repo.git.checkout(commit.hexsha)  # detach
                self.assertTrue(repo.head.is_detached)

                with GitOperations(repo_path) as ops:
                    with self.assertRaises(RuntimeError):
                        ops.commit_all("should not commit on detached HEAD")
            finally:
                repo.close()


if __name__ == "__main__":
    unittest.main()
