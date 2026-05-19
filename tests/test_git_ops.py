import unittest
import tempfile
import git
from pathlib import Path

from git import Repo

from yagso.infrastructure.git_ops import GitOperations
from yagso.domain.submodule import SubmoduleDefinition


class TestGitOps(unittest.TestCase):
    def test_remove_submodule(self):
        pass

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
