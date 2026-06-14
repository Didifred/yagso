"""Shared test base for git-backed integration tests.

Provides a single `setUpClass` and `setUp` that prepare and reset the
sample repository used across tests. Tests that need this behaviour should
inherit from `BaseGitTest`.
"""
import unittest
import gc
from pathlib import Path
from yagso.infrastructure.git_ops import GitOperations
from git import Repo
import os
import shutil


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
        """

        with GitOperations(self.test_root) as git_ops:
            try:
                git_ops.repo.git.reset('--hard', 'HEAD')
                git_ops.repo.git.clean('-ffd')
            except Exception as e:
                raise RuntimeError(f"Failed to reset repository state: {e}") from e

            try:
                git_ops.rebuild_submodule_metadata()
            except Exception as e:
                raise RuntimeError(f"Failed to rebuild submodule metadata: {e}") from e

            try:
                git_ops.backup_submodule_metadata()
            except Exception as e:
                raise RuntimeError(f"Failed to backup submodule metadata: {e}") from e

    def tearDown(self):
        gc.collect()   # forces release of lingering file handles on Windows

    # Reset main repository and all submodules recursively
    #    with Repo(self.test_root) as repo:
    #        try:
    #            # 1. Deinit ALL submodules first → cleans .git/config entries
    #            repo.git.submodule('deinit', '--all', '-f')
    #
    #            # 2. Wipe .git/modules entirely → removes all cached submodule git data
    #            modules_path = os.path.join(repo.git_dir, 'modules')
    #            if os.path.exists(modules_path):
    #                shutil.rmtree(modules_path)

        # 3. Reset + clean working tree
    #            repo.git.reset('--hard', 'HEAD')
    #            repo.git.clean('-ffd')

        # 4. Reinitialize from .gitmodules (now clean state)
    #            repo.git.submodule('update', '--init', '--recursive', '--force')
    #        except Exception as e:
    #            raise RuntimeError(f"Failed to reset repository state: {e}") from e
