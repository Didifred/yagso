"""Test git_ops """
import unittest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import git

from yagso.infrastructure.git_ops import GitOperations
from yagso.domain.submodule import SubmoduleDefinition
from tests.common import BaseGitTest


class TestGitOps(BaseGitTest):

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
                for block in blocks:
                    if block.get("name") == sub_def.name:
                        found = True
                        break

            except Exception as e:
                self.fail(f"add_submodule raised an exception: {e}")

            if found:
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

                # After the helper, we should be on branch yagso-<commit_hash> for the second commit
                self.assertFalse(repo.head.is_detached)
                branch_name = f"default"
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

    def test_update_defaults_to_no_init(self):
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
