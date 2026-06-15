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
import subprocess
import sys
import scripts.run_tests_with_watcher_toggle as watcher_toggle


class BaseGitTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Set up test repository state once for all tests.
        """
        cls._test_root = Path('tests/sample1/yagso_test_root')
        # Save original working directory
        cls._orig_cwd = Path.cwd()

        # Ensure VS Code watcher excludes are enabled for tests
        watcher_toggle.add_watcherExclude()
        # Ensure VS Code watcher excludes are enabled for tests
        # try:
        #    subprocess.run([sys.executable, str(
        #        'scripts/run_tests_with_watcher_toggle.py'), 'add'], check=True)
        # except Exception as e:
        #    raise RuntimeError(f"Failed to enable watcher excludes: {e}") from e

    @classmethod
    def tearDownClass(cls):
        """Clean up test repository state after all tests have run.
        """
        # Restore VS Code watcher excludes to original state
        watcher_toggle.remove_watcherExclude()
        # try:
        #    subprocess.run([sys.executable, str(
        #        'scripts/run_tests_with_watcher_toggle.py'), 'remove'], check=True)
        # except Exception as e:
        #    raise RuntimeError(f"Failed to restore watcher excludes: {e}") from e

    def setUp(self):
        """Reset test repository to clean state before each test.
        """

        with GitOperations(self._test_root) as git_ops:
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

        try:
            os.chdir(str(self._test_root))
        except Exception as e:
            raise RuntimeError(
                f"Failed to change working directory to {self._test_root}: {e}") from e

    def tearDown(self):
        gc.collect()   # forces release of lingering file handles on Windows

        # Change back to original working directory
        try:
            os.chdir(str(self._orig_cwd))
        except Exception as e:
            raise RuntimeError(
                f"Failed to restore working directory to {
                    self._orig_cwd}: {e}") from e
