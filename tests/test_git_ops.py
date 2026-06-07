import unittest
import tempfile
import git
import shutil
from pathlib import Path

from git import Repo

from yagso.infrastructure.git_ops import GitOperations
from yagso.domain.submodule import SubmoduleDefinition


class TestGitOps(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Set up test repository state once for all tests."""
        cls.test_root = Path('tests/sample1/yagso_test_root')

    def setUp(self):
        """Reset test repository to clean state before each test."""
        git_ops = GitOperations(Path('tests/sample1/yagso_test_root'))

        try:
            submodule_path = self.test_root / 'libs/addedsub'
            if submodule_path.exists():
                # Remove any adding submodule that may have been added in a previous test
                block0 = {
                    "name": 'testaddedsub',
                    "path": 'libs/addedsub'
                }
                git_ops.remove_submodule(block0, True)
        except Exception:
            pass

        try:
            submodule_path = self.test_root / 'lib2/lib3'
            if submodule_path.exists():
                block1 = {
                    "name": 'innerLib3Test',
                    "path": 'lib2/lib3'
                }
                git_ops.remove_submodule(block1, True)
        except Exception:
            pass

        repo = Repo(self.test_root)

        # Reset main repository
        repo.git.reset('--hard', 'HEAD')

        # Reset all submodules recursively
        repo.git.submodule('foreach', '--recursive', 'git reset --hard HEAD')

    def test_rebuild_submodule_metadata(self):
        git_ops = GitOperations(Path('tests/sample1/yagso_test_root'))

        try:
            git_ops.rebuild_submodule_metadata()
        except Exception as e:
            self.fail(f"rebuild_submodule_metadata raised an exception: {e}")

    def test_backup_restore_submodule_metadata(self):
        git_ops = GitOperations(Path('tests/sample1/yagso_test_root'))

        try:
            git_ops.backup_submodule_metadata()

            git_ops_.restore_submodule_metadata()
        except Exception as e:
            self.fail(f"backup_submodule_metadata raised an exception: {e}")

    def test_remove_submodule(self):
        # First add a submodule then remove it to test the cleanup logic

        sub_def = SubmoduleDefinition(
            root_path='.',
            name='testaddedsub',
            path='libs/addedsub',
            url='https://github.com/Didifred/yagso_test_repo_3.git',
            commit='HEAD'
        )

        git_ops = GitOperations(Path('tests/sample1/yagso_test_root'))

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
                git_ops.remove_submodule(block, False)
            except Exception as e:
                self.fail(f"remove_submodule raised an exception: {e}")
        else:
            self.fail("Submodule block not found after adding submodule, cannot test remove_submodule")

    def test_add_submodule(self):

        sub_def = SubmoduleDefinition(
            root_path='.',
            name='testaddedsub',
            path='libs/addedsub',
            url='https://github.com/Didifred/yagso_test_repo_3.git',
            commit='HEAD'
        )

        git_ops = GitOperations(Path('tests/sample1/yagso_test_root'))

        try:
            git_ops.add_submodule(sub_def)
        except Exception as e:
            self.fail(f"add_submodule raised an exception: {e}")


if __name__ == '__main__':
    unittest.main()
