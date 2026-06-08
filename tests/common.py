"""Shared test base for git-backed integration tests.

Provides a single `setUpClass` and `setUp` that prepare and reset the
sample repository used across tests. Tests that need this behaviour should
inherit from `BaseGitTest`.
"""
from pathlib import Path
from yagso.infrastructure.git_ops import GitOperations
from git import Repo
import gc
import unittest


class BaseGitTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Set up test repository state once for all tests.

        This prepares `tests/sample1/yagso_test_root` by rebuilding
        submodule metadata and taking a backup copy so individual tests
        can reset to a known-good state.
        """
        cls.test_root = Path('tests/sample1/yagso_test_root')

    def setUp(self):
        """Reset test repository to clean state before each test.

        Removes any artifacts left by previous tests (added submodules),
        restores backed-up submodule metadata and resets the working tree
        in the main repository and all submodules.
        """
        # Reset main repository and all submodules recursively
        # repo = Repo(self.test_root)
        # repo.git.reset('--hard', 'HEAD')
        # repo.git.submodule('foreach', '--recursive', 'git reset --hard HEAD')

        # Rebuild and backup submodule metadata to ensure we have a clean state to reset to in tests

        with GitOperations(self.test_root) as git_ops:
            try:
                git_ops.rebuild_submodule_metadata()
            except Exception as e:
                raise RuntimeError(f"Failed to rebuild submodule metadata: {e}") from e

            try:
                git_ops.backup_submodule_metadata()
            except Exception as e:
                raise RuntimeError(f"Failed to backup submodule metadata: {e}") from e

        # Reset main repository and all submodules recursively
        # repo = Repo(self.test_root)
        # repo.git.reset('--hard', 'HEAD')
        # repo.git.submodule('foreach', '--recursive', 'git reset --hard HEAD')

    def tearDown(self):
        gc.collect()   # forces release of lingering file handles on Windows
