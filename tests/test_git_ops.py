"""Test git_ops.py """
import unittest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, PropertyMock, patch

import git

from yagso.infrastructure.git_ops import GitOperations
from yagso.domain.submodule import SubmoduleDefinition
from tests.common import BaseGitTest

# pylint: disable=all


class TestCommitMoveTags(unittest.TestCase):
    """Tag movement tests independent of the shared sample repository."""

    def test_commit_all_moves_only_head_tags(self) -> None:
        """Move all old HEAD tags only for repositories receiving a new commit."""
        scenarios = [
            (True, True, True),
            (False, True, False),
            (True, False, False),
        ]
        for enabled, dirty, expected in scenarios:
            with self.subTest(enabled=enabled, dirty=dirty):
                repo = MagicMock()
                repo.head.is_detached = False
                repo.active_branch.name = 'main'
                repo.working_tree_dir = 'root'
                repo.is_dirty.return_value = True
                child = MagicMock()
                child.name = 'child-name'
                child.path = 'libs/child'
                child.module_exists.return_value = True
                child_repo = child.module.return_value
                child_repo.submodules = []
                child_repo.is_dirty.return_value = dirty
                tag = MagicMock()
                tag.name = 'release'
                tag.commit = child_repo.head.commit
                second_tag = MagicMock()
                second_tag.name = 'second-release'
                second_tag.commit = child_repo.head.commit
                unrelated_tag = MagicMock()
                unrelated_tag.name = 'unrelated'
                child_repo.tags = [tag, second_tag, unrelated_tag]
                repo.submodules = [child]
                with GitOperations(Path('root')) as ops:
                    ops._repo = repo
                    with patch.object(ops, '_checkout_ref_or_commit', return_value='main'):
                        ops.commit_all('update', move_tags=enabled)
                if expected:
                    self.assertEqual(child_repo.git.tag.call_count, 2)
                    child_repo.git.tag.assert_any_call('--force', '--', 'release', 'HEAD')
                    child_repo.git.tag.assert_any_call('--force', '--', 'second-release', 'HEAD')
                else:
                    child_repo.git.tag.assert_not_called()
                repo.git.tag.assert_not_called()

    def test_commit_all_moves_nested_tags_after_commits(self) -> None:
        """Move nested HEAD tags before committing the parent gitlink update."""
        repo = MagicMock()
        repo.head.is_detached = False
        repo.working_tree_dir = 'root'
        child = MagicMock()
        child.path = 'libs/child'
        child.name = 'child'
        child_repo = child.module.return_value
        leaf = MagicMock()
        leaf.path = 'nested/leaf'
        leaf.name = 'leaf'
        leaf_repo = leaf.module.return_value
        repo.submodules = [child]
        child_repo.submodules = [leaf]
        leaf_repo.submodules = []
        child_repo.tags = []
        tag = MagicMock()
        tag.name = 'release'
        tag.commit = leaf_repo.head.commit
        leaf_repo.tags = [tag]
        events = MagicMock()
        events.attach_mock(leaf_repo.index.commit, 'leaf_commit')
        events.attach_mock(leaf_repo.git.tag, 'leaf_tag')
        events.attach_mock(child_repo.index.commit, 'child_commit')
        events.attach_mock(repo.index.commit, 'root_commit')
        with GitOperations(Path('root')) as ops:
            ops._repo = repo
            with patch.object(ops, '_checkout_ref_or_commit', return_value='main'):
                ops.commit_all('update', move_tags=True)
        self.assertEqual([event[0] for event in events.mock_calls],
                         ['leaf_commit', 'leaf_tag', 'child_commit', 'root_commit'])

    def test_commit_all_wraps_tag_move_error(self) -> None:
        """Report a failed tag update through the existing commit error contract."""
        repo = MagicMock()
        repo.head.is_detached = False
        child = MagicMock()
        child.path = 'child'
        child_repo = child.module.return_value
        child_repo.submodules = []
        tag = MagicMock()
        tag.name = 'release'
        tag.commit = child_repo.head.commit
        child_repo.tags = [tag]
        child_repo.git.tag.side_effect = git.GitCommandError('tag', 1)
        repo.submodules = [child]
        with GitOperations(Path('root')) as ops:
            ops._repo = repo
            with patch.object(ops, '_checkout_ref_or_commit', return_value='main'):
                with self.assertRaisesRegex(RuntimeError, 'Failed to commit changes'):
                    ops.commit_all('update', move_tags=True)


class TestGitOps(BaseGitTest):

    def test_get_remote_name_prefers_current_branch_upstream(self):
        git_ops = GitOperations.__new__(GitOperations)
        git_ops._repo = MagicMock()
        upstream = MagicMock()
        upstream.remote_name = 'upstream'
        git_ops._repo.active_branch.tracking_branch.return_value = upstream
        origin_remote = MagicMock()
        origin_remote.name = 'origin'
        git_ops._repo.remotes = [origin_remote]

        self.assertEqual(git_ops.get_remote_name(git_ops.repo), 'upstream')

    def test_get_remote_name_falls_back_to_origin_without_upstream(self):
        git_ops = GitOperations.__new__(GitOperations)
        git_ops._repo = MagicMock()
        git_ops._repo.active_branch.tracking_branch.return_value = None
        origin_remote = MagicMock()
        origin_remote.name = 'origin'
        git_ops._repo.remotes = [origin_remote]

        self.assertEqual(git_ops.get_remote_name(git_ops.repo), 'origin')

    def test_get_remote_converts_tracking_reference_to_remote(self):
        git_ops = GitOperations.__new__(GitOperations)
        git_ops._repo = MagicMock()
        tracking_reference = MagicMock()
        tracking_reference.remote_name = 'origin'
        git_ops._repo.active_branch.tracking_branch.return_value = tracking_reference
        origin = git_ops._repo.remote.return_value

        self.assertIs(git_ops.get_remote(git_ops.repo), origin)
        git_ops._repo.remote.assert_called_once_with('origin')

    def test_push_all_passes_dry_run_to_git(self):
        git_ops = GitOperations.__new__(GitOperations)
        git_ops._repo = MagicMock()
        origin = git_ops._repo.remote.return_value
        tracking_ref = MagicMock()
        tracking_ref.remote_name = 'origin'
        git_ops._repo.active_branch.tracking_branch.return_value = tracking_ref
        git_ops._repo.submodules = []

        git_ops.push_all(p_dry_run=True)

        origin.push.assert_called_once_with(None, dry_run=True)

    def test_push_all_force_pushes_only_moved_tags(self):
        git_ops = GitOperations.__new__(GitOperations)
        git_ops._repo = MagicMock()
        repo = git_ops._repo
        remote = repo.remote.return_value
        remote.name = 'origin'
        tracking_ref = MagicMock()
        tracking_ref.remote_name = 'origin'
        tracking_ref.remote_head = 'main'
        repo.active_branch.tracking_branch.return_value = tracking_ref
        repo.submodules = []

        head_commit = MagicMock()
        head_commit.hexsha = 'a' * 40
        repo.head.commit = head_commit
        tag = MagicMock()
        tag.name = 'release'
        tag.commit = head_commit
        same_tag = MagicMock()
        same_tag.name = 'same'
        same_tag.commit = head_commit
        repo.tags = [tag, same_tag]
        repo.git.ls_remote.return_value = (
            f"{'c' * 40}\trefs/tags/release\n"
            f"{'b' * 40}\trefs/tags/release^{{}}\n"
            f"{'a' * 40}\trefs/tags/same\n")

        git_ops.push_all()

        remote.push.assert_called_once_with(
            ['HEAD:refs/heads/main', '+refs/tags/release:refs/tags/release'], dry_run=False)

    def test_push_all_uses_local_branch_without_upstream(self):
        git_ops = GitOperations.__new__(GitOperations)
        git_ops._repo = MagicMock()
        repo = git_ops._repo
        repo.active_branch.tracking_branch.return_value = None
        repo.active_branch.name = 'main'
        remote = MagicMock()
        remote.name = 'origin'
        repo.remotes = [remote]
        repo.submodules = []
        head_commit = MagicMock()
        head_commit.hexsha = 'a' * 40
        repo.head.commit = head_commit
        tag = MagicMock()
        tag.name = 'release'
        tag.commit = head_commit
        repo.tags = [tag]
        repo.git.ls_remote.return_value = f"{'b' * 40}\trefs/tags/release\n"

        git_ops.push_all()

        remote.push.assert_called_once_with(
            ['HEAD:refs/heads/main', '+refs/tags/release:refs/tags/release'], dry_run=False)

    def test_push_all_raises_on_push_error(self):
        git_ops = GitOperations.__new__(GitOperations)
        git_ops._repo = MagicMock()
        git_ops._repo.tags = []
        tracking_ref = MagicMock()
        tracking_ref.remote_name = 'origin'
        git_ops._repo.active_branch.tracking_branch.return_value = tracking_ref
        info = MagicMock()
        info.flags = info.ERROR = 1
        info.summary = 'rejected'
        git_ops._repo.remote.return_value.push.return_value = [info]

        with self.assertRaisesRegex(RuntimeError, 'Push failed: rejected'):
            git_ops.push_all()

    def test_has_moved_head_tag_unchanged_annotated_tag(self):
        repo = MagicMock()
        remote = MagicMock()
        remote.name = 'origin'
        repo.head.commit.hexsha = 'a' * 40
        tag = MagicMock()
        tag.name = 'release'
        tag.commit.hexsha = 'a' * 40
        repo.tags = [tag]
        repo.git.ls_remote.return_value = (
            f"{'c' * 40}\trefs/tags/release\n"
            f"{'a' * 40}\trefs/tags/release^{{}}\n")

        self.assertEqual(GitOperations._get_moved_head_tags(repo, remote), [])
        repo.git.ls_remote.assert_called_once_with(
            '--tags', 'origin', 'refs/tags/release', 'refs/tags/release^{}')

    def test_has_moved_head_tag_ignores_missing_remote_and_non_commit_tags(self):
        repo = MagicMock()
        remote = MagicMock()
        remote.name = 'origin'
        repo.head.commit.hexsha = 'a' * 40
        tag = MagicMock()
        tag.name = 'release'
        tag.commit.hexsha = 'a' * 40
        tree_tag = MagicMock()
        type(tree_tag).commit = PropertyMock(side_effect=ValueError('tree'))
        repo.tags = [tree_tag, tag]
        repo.git.ls_remote.return_value = ''

        self.assertEqual(GitOperations._get_moved_head_tags(repo, remote), [])

    def test_dry_run_new_branch_summary_includes_sha_range(self):
        repo = MagicMock()
        remote = MagicMock()
        remote.name = 'origin'
        info = MagicMock()
        info.summary = '[new branch]\n'
        # info.flags = git.remote.PushInfo.NEW_HEAD
        info.local_ref.commit.hexsha = 'a' * 40
        info.old_commit = None
        base_commit = MagicMock()
        base_commit.hexsha = 'b' * 40
        repo.git.symbolic_ref.return_value = 'refs/remotes/origin/main'
        repo.merge_base.return_value = [base_commit]

        summary = GitOperations._format_push_summary(repo, remote, info, dry_run=True)

        self.assertEqual(
            summary,
            f"{'b' * 7}..{'a' * 7}")

    def test_push_all_pushes_only_yagso_submodule_commits(self):
        git_ops = GitOperations.__new__(GitOperations)
        git_ops._repo = MagicMock()
        git_ops._repo.submodules = []
        root_tracking_ref = MagicMock()
        root_tracking_ref.remote_name = 'origin'
        git_ops._repo.active_branch.tracking_branch.return_value = root_tracking_ref

        yagso_submodule = MagicMock()
        yagso_submodule.module_exists.return_value = True
        yagso_repo = yagso_submodule.module.return_value
        yagso_repo.head.commit.message = "bump change in lib1 : update"
        yagso_repo.submodules = []
        yagso_repo.active_branch.name = "yagso/test"
        yagso_remote = MagicMock()
        yagso_remote.name = 'origin'
        tracking_ref = MagicMock()
        tracking_ref.remote_name = 'origin'
        yagso_repo.active_branch.tracking_branch.return_value = tracking_ref
        yagso_repo.remote.return_value = yagso_remote
        yagso_repo.remotes = [yagso_remote]

        user_submodule = MagicMock()
        user_submodule.module_exists.return_value = True
        user_repo = user_submodule.module.return_value
        user_repo.head.commit.message = "user commit"
        user_repo.submodules = []

        git_ops._repo.submodules = [yagso_submodule, user_submodule]

        git_ops.push_all()

        yagso_remote.push.assert_called_once_with(
            ["HEAD:refs/heads/yagso/test"], dry_run=False)
        user_repo.remote.assert_not_called()

    @unittest.skip("Utility method test, not a real test case")
    def test_rebuild_submodule_metadata(self):

        with GitOperations(Path.cwd()) as git_ops:
            try:
                git_ops.rebuild_submodule_metadata()
            except Exception as e:
                self.fail(f"rebuild_submodule_metadata raised an exception: {e}")

    @unittest.skip("Utility method test, not a real test case")
    def test_backup_restore_submodule_metadata(self):
        with GitOperations(Path.cwd()) as git_ops:
            try:
                git_ops.backup_submodule_metadata()

                git_ops.restore_submodule_metadata()
            except Exception as e:
                self.fail(f"backup_submodule_metadata raised an exception: {e}")

    def test_add_then_remove_submodule(self):
        # First add a submodule then remove it to test the cleanup logic

        sub_def = SubmoduleDefinition(
            root_path='.',
            name='testaddedsub',
            path='libs/addedsub',
            url='https://github.com/Didifred/yagso_test_repo_3.git',
            commit='HEAD'
        )

        with GitOperations(Path.cwd()) as git_ops:
            try:
                git_ops.add_submodule(sub_def)

                blocks = git_ops.read_gitmodules_blocks()

                found = False
                block = None

                for block in blocks:
                    if block.get("name") == sub_def.name:
                        found = True
                        break

            except Exception as e:
                self.fail(f"add_submodule raised an exception: {e}")

            if found and block is not None:
                try:
                    git_ops.remove_submodule(block)
                except Exception as e:
                    self.fail(f"remove_submodule raised an exception: {e}")
            else:
                self.fail("Submodule block not found after adding submodule, cannot test remove_submodule")

    def test_remove_submodule(self):
        # First add a submodule then remove it to test the cleanup logic

        block = {
            "name": "lib1",
            "path": "lib1",
        }

        with GitOperations(Path.cwd()) as git_ops:
            try:
                git_ops.remove_submodule(block)
            except Exception as e:
                self.fail(f"remove_submodule raised an exception: {e}")

    def test_add_submodule(self):

        sub_def = SubmoduleDefinition(
            root_path='.',
            name='testaddedsub',
            path='libs/addedsub',
            url='https://github.com/Didifred/yagso_test_repo_3.git',
            commit='HEAD'
        )

        with GitOperations(Path.cwd()) as git_ops:
            try:
                git_ops.add_submodule(sub_def)
            except Exception as e:
                self.fail(f"add_submodule raised an exception: {e}")

    def test_get_refs_containing_commit_at_path(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_path = Path(tmp_dir) / 'repo'
            remote_path = Path(tmp_dir) / 'remote.git'

            git.Repo.init(remote_path, bare=True)
            repo = git.Repo.init(repo_path)
            try:
                repo.config_writer().set_value('user', 'name', 'Test User').release()
                repo.config_writer().set_value('user', 'email', 'test@example.com').release()
                repo.create_remote('origin', remote_path.as_posix())

                (repo_path / 'README.md').write_text('hello\n', encoding='utf-8')
                repo.index.add(['README.md'])
                commit = repo.index.commit('initial commit')

                repo.git.checkout('-b', 'feature')
                repo.git.push('origin', 'feature')
                repo.git.fetch('origin', 'feature:refs/remotes/origin/feature')
                repo.git.symbolic_ref(
                    'refs/remotes/origin/HEAD', 'refs/remotes/origin/feature')

                with GitOperations(repo_path) as git_ops:
                    refs = git_ops.get_refs_containing_commit_at_path(commit.hexsha)

                self.assertIn('origin|feature', refs)
                self.assertNotIn('feature', refs)
                self.assertNotIn('origin/feature', refs)
                self.assertNotIn('origin/HEAD', refs)
                self.assertNotIn('origin', refs)
                self.assertNotIn('HEAD', refs)
            finally:
                repo.close()

    def test_checkout_ref_or_commit(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_path = Path(tmp_dir) / 'repo'
            repo = git.Repo.init(repo_path)

            try:
                repo.config_writer().set_value('user', 'name', 'Test User').release()
                repo.config_writer().set_value('user', 'email', 'test@example.com').release()

                (repo_path / 'README.md').write_text('hello\n', encoding='utf-8')
                repo.index.add(['README.md'])
                commit = repo.index.commit('initial commit')

                # Detach HEAD by checking out the commit directly
                repo.git.checkout(commit.hexsha)
                self.assertTrue(repo.head.is_detached)

                # Call the helper
                with GitOperations(repo_path) as ops:
                    ops._checkout_ref_or_commit(repo, 'default')

                # After the helper, we should be on the repository's default branch.
                self.assertFalse(repo.head.is_detached)
                self.assertIn(repo.active_branch.name, ('main', 'master'))
                self.assertEqual(repo.head.commit.hexsha, commit.hexsha)

                (repo_path / 'README.md').write_text('hello again\n', encoding='utf-8')
                repo.index.add(['README.md'])
                commit2 = repo.index.commit('second commit')
                # checkout initial commit to detach HEAD
                repo.git.checkout(commit.hexsha)
                self.assertTrue(repo.head.is_detached)

                # Call the helper
                with GitOperations(repo_path) as ops:
                    ops._checkout_ref_or_commit(repo, 'default')

                self.assertFalse(repo.head.is_detached)
                branch_name = f"yagso/{commit.hexsha[:7]}"
                self.assertIn(branch_name, [b.name for b in repo.branches])
                self.assertEqual(repo.head.commit.hexsha, commit.hexsha)

            finally:
                repo.close()

    def test_checkout_ref_or_commit_tag_branch(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_path = Path(tmp_dir) / 'repo'
            repo = git.Repo.init(repo_path)

            try:
                repo.config_writer().set_value('user', 'name', 'Test User').release()
                repo.config_writer().set_value('user', 'email', 'test@example.com').release()

                (repo_path / 'README.md').write_text('hello\n', encoding='utf-8')
                repo.index.add(['README.md'])
                commit = repo.index.commit('initial commit')

                # Detach HEAD by checking out the commit directly
                repo.git.checkout(commit.hexsha)
                self.assertTrue(repo.head.is_detached)

                # Call the helper
                with GitOperations(repo_path) as ops:
                    ops._checkout_ref_or_commit(repo, 'default')

                tag_name = 'release/1.0'
                repo.create_tag(tag_name, ref=commit.hexsha)

                # After the helper, we should be on the repository's default branch.
                self.assertFalse(repo.head.is_detached)
                self.assertIn(repo.active_branch.name, ('main', 'master'))
                self.assertEqual(repo.head.commit.hexsha, commit.hexsha)

                (repo_path / 'README.md').write_text('hello again\n', encoding='utf-8')
                repo.index.add(['README.md'])
                commit2 = repo.index.commit('second commit')
                # checkout initial commit to detach HEAD
                repo.git.checkout(commit.hexsha)
                self.assertTrue(repo.head.is_detached)

                # Call the helper
                with GitOperations(repo_path) as ops:
                    ops._checkout_ref_or_commit(repo, 'default')

                self.assertFalse(repo.head.is_detached)
                branch_name = f"yagso/{tag_name}"
                self.assertIn(branch_name, [b.name for b in repo.branches])
                self.assertEqual(repo.head.commit.hexsha, commit.hexsha)

            finally:
                repo.close()


class TestUpdateDefaults(unittest.TestCase):

    def test_convert_full_sha_to_short_sha(self):
        reference = "0123456789abcdef0123456789abcdef01234567"
        self.assertEqual(GitOperations.convert_to_short_sha(reference), reference[:7])

    def test_convert_non_sha_reference_unchanged(self):
        for reference in ("main", "0123456", "refs/tags/v1.0"):
            with self.subTest(reference=reference):
                self.assertEqual(GitOperations.convert_to_short_sha(reference), reference)

    def test_update_always_initializes_submodules(self):
        ops = GitOperations.__new__(GitOperations)
        ops._repo = MagicMock()
        repo = ops._repo

        ops.update_all_submodules({"remote": False})
        repo.git.submodule.assert_called_once_with("update", "--init", "--recursive")

        ops.update_all_submodules({"remote": True})
        repo.git.submodule.assert_called_with(
            "update", "--init", "--remote", "--recursive")


class TestCommitAllDetachedHead(unittest.TestCase):

    def test_commit_all_raises_on_detached_head(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_path = Path(tmp) / "repo"
            repo = git.Repo.init(repo_path)
            try:
                repo.config_writer().set_value('user', 'name', 'Test').release()
                repo.config_writer().set_value('user', 'email', 'test@example.com').release()
                (repo_path / "README.md").write_text("hi\n", encoding="utf-8")
                repo.index.add(["README.md"])
                commit = repo.index.commit("initial")
                repo.git.checkout(commit.hexsha)
                self.assertTrue(repo.head.is_detached)

                with GitOperations(repo_path) as ops:
                    with self.assertRaises(RuntimeError):
                        ops.commit_all("should not commit on detached HEAD")
            finally:
                repo.close()


if __name__ == '__main__':
    unittest.main()
