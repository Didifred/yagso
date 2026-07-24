import unittest
import tempfile
import git
import shutil
from pathlib import Path

from git import Repo

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

    def test_get_refs_containing_commit_at_path_filters_local_branch_aligned_with_remote(self):
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

                with GitOperations(repo_path) as git_ops:
                    refs = git_ops.get_refs_containing_commit_at_path(repo_path, commit.hexsha)

                self.assertIn('origin/feature', refs)
                self.assertNotIn('feature', refs)
            finally:
                repo.close()


if __name__ == '__main__':
    unittest.main()
