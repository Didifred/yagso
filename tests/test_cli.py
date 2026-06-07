import unittest
import sys
import yaml
import copy
from io import StringIO
from pathlib import Path
from git import Repo

from yagso.infrastructure.git_ops import GitOperations
from yagso.cli.controller import CLIController
from yagso.infrastructure.manifest_manager import ManifestManager


class TestCli(unittest.TestCase):
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

        # Rebuild .git from .gitmodules
        # repo.git.submodule('deinit', '--all', '-f')
        # repo.git.submodule('init')
        # repo.git.submodule('update', '--init', '--recursive')

    def test_controller_creation(self):
        """Test that CLIController can be created."""
        controller = CLIController()
        self.assertIsNotNone(controller)

    def test_help_command(self):
        """Test that help command works."""
        controller = CLIController()
        result = controller.run(['--help'])
        # Should return 0 for help
        self.assertEqual(result, 0)

    def test_invalid_command(self):
        """Test that invalid command returns error."""
        controller = CLIController()
        result = controller.run(['invalid'])
        self.assertEqual(result, 1)

    def test_generate_command(self):
        """Test that generate command works."""
        controller = CLIController()

        result = controller.run(['generate', '--root-path', 'tests/sample1/yagso_test_root'])
        self.assertEqual(result, 0)

    def test_configure_command(self):
        """Test that configure command works (identity)."""
        controller = CLIController()

        result = controller.run(['configure', '--root-path', 'tests/sample1/yagso_test_root'])
        self.assertEqual(result, 0)

    def test_configure_command_commit_change(self):
        """Test that configure command works with commit change to develop/YAGSO."""
        # Modify yagso.yaml to change lib3/bis commit to develop/YAGSO
        pathYaml = Path('tests/sample1/yagso_test_root/yagso.yaml')
        manager = ManifestManager()
        manifest = manager.load_manifest(pathYaml)
        new_manifest = copy.deepcopy(manifest)
        manager.update_submodule_field(new_manifest, 'lib3/bis', 'commit', 'develop/YAGSO')

        # Write modified manifest back
        manager.save_manifest(new_manifest, pathYaml)

        try:
            controller = CLIController()

            result = controller.run(['configure', '--root-path', 'tests/sample1/yagso_test_root'])
            self.assertEqual(result, 0)
        finally:
            manager.save_manifest(manifest, pathYaml)

    def test_configure_command_name_change(self):
        """Test that configure command works with name change to innerLib3Test.\n"""
        # Modify yagso.yaml to change name of lib2/lib3 repo to innerLib3Test
        pathYaml = Path('tests/sample1/yagso_test_root/yagso.yaml')
        manager = ManifestManager()
        manifest = manager.load_manifest(pathYaml)
        new_manifest = copy.deepcopy(manifest)
        manager.update_submodule_field(new_manifest, 'lib2/lib3', 'name', 'innerLib3Test')

        # Write modified manifest back
        manager.save_manifest(new_manifest, pathYaml)

        try:
            controller = CLIController()

            result = controller.run(['configure', '--root-path', 'tests/sample1/yagso_test_root'])
            self.assertEqual(result, 0)

        finally:
            manager.save_manifest(manifest, pathYaml)

    def test_configure_command_url_change(self):
        """Test that configure command works with url change to ssh"""
        # Modify yagso.yaml to change lib1 url to ssh
        pathYaml = Path('tests/sample1/yagso_test_root/yagso.yaml')
        manager = ManifestManager()
        manifest = manager.load_manifest(pathYaml)
        new_manifest = copy.deepcopy(manifest)
        manager.update_submodule_field(
            new_manifest,
            'lib1',
            'url',
            'git@github.com:Didifred/yagso_test_repo_1.git')

        # Write modified manifest back
        manager.save_manifest(new_manifest, pathYaml)

        try:
            controller = CLIController()

            result = controller.run(['configure', '--root-path', 'tests/sample1/yagso_test_root'])
            self.assertEqual(result, 0)

        finally:
            manager.save_manifest(manifest, pathYaml)


if __name__ == "__main__":
    unittest.main()
