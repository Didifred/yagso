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
from yagso.domain.submodule import SubmoduleDefinition
from tests.common import BaseGitTest


class TestCli(BaseGitTest):

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

        result = controller.run(['generate'])
        self.assertEqual(result, 0)

    def test_configure_command(self):
        """Test that configure command works (identity)."""
        controller = CLIController()

        result = controller.run(['configure'])
        self.assertEqual(result, 0)

    def test_configure_command_commit_change(self):
        """Test that configure command works with commit change to develop/YAGSO."""
        # Modify yagso.yaml to change lib3/bis commit to develop/YAGSO
        pathYaml = Path('yagso.yaml')
        manager = ManifestManager()
        manifest = manager.load_manifest(pathYaml)
        new_manifest = copy.deepcopy(manifest)
        manager.update_submodule_field(new_manifest, 'lib3/bis', 'commit', 'develop/YAGSO')

        # Write modified manifest back
        manager.save_manifest(new_manifest, pathYaml)

        try:
            controller = CLIController()

            result = controller.run(['configure'])
            self.assertEqual(result, 0)
        finally:
            manager.save_manifest(manifest, pathYaml)

    def test_configure_command_name_change(self):
        """Test that configure command works with name change to innerLib3Test.\n"""
        # Modify yagso.yaml to change name of lib2/lib3 repo to innerLib3Test
        pathYaml = Path('yagso.yaml')
        manager = ManifestManager()
        manifest = manager.load_manifest(pathYaml)
        new_manifest = copy.deepcopy(manifest)
        manager.update_submodule_field(new_manifest, 'lib2/lib3', 'name', 'innerLib3Test')

        # Write modified manifest back
        manager.save_manifest(new_manifest, pathYaml)

        try:
            controller = CLIController()

            result = controller.run(['configure'])
            self.assertEqual(result, 0)

        finally:
            manager.save_manifest(manifest, pathYaml)

    def test_configure_command_url_change(self):
        """Test that configure command works with url change to ssh"""
        # Modify yagso.yaml to change lib1 url to ssh
        pathYaml = Path('yagso.yaml')
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

            result = controller.run(['configure'])
            self.assertEqual(result, 0)

        finally:
            manager.save_manifest(manifest, pathYaml)

    def test_configure_command_add_submodule(self):
        """Test that configure command works with adding a new submodule."""
        # Modify yagso.yaml to add a new submodule lib4
        pathYaml = Path('yagso.yaml')
        manager = ManifestManager()
        manifest = manager.load_manifest(pathYaml)
        new_manifest = copy.deepcopy(manifest)

        sub_def = SubmoduleDefinition(
            root_path='libs/addedsub',
            name='testaddedsub',
            path='libs/addedsub',
            url='https://github.com/Didifred/yagso_test_repo_3.git',
            commit='HEAD'
        )
        manager.add_submodule_definition(new_manifest, sub_def)

        # Write modified manifest back
        manager.save_manifest(new_manifest, pathYaml)

        try:
            controller = CLIController()

            result = controller.run(['configure'])
            self.assertEqual(result, 0)

        finally:
            manager.save_manifest(manifest, pathYaml)

    def test_configure_command_add_submodule_level_1(self):
        """Test that configure command works with adding a new submodule."""
        # Modify yagso.yaml to add a new submodule lib4
        pathYaml = Path('yagso.yaml')
        manager = ManifestManager()
        manifest = manager.load_manifest(pathYaml)
        new_manifest = copy.deepcopy(manifest)

        sub_def = SubmoduleDefinition(
            root_path='lib2',  # Root path where to insert the submodule
            name='testaddedsub',
            path='addedsub',
            url='https://github.com/Didifred/yagso_test_repo_3.git',
            commit='HEAD'
        )
        manager.add_submodule_definition(new_manifest, sub_def)

        # Write modified manifest back
        manager.save_manifest(new_manifest, pathYaml)

        try:
            controller = CLIController()

            result = controller.run(['configure'])
            self.assertEqual(result, 0)

            # TODO : stage upper level submodules ?
        finally:
            manager.save_manifest(manifest, pathYaml)

    def test_commit_command_add_submodule_level_1(self):
        """Test that commit command works."""

        # Modify yagso.yaml to add a new submodule lib4
        pathYaml = Path('yagso.yaml')
        manager = ManifestManager()
        manifest = manager.load_manifest(pathYaml)
        new_manifest = copy.deepcopy(manifest)

        sub_def = SubmoduleDefinition(
            root_path='lib2',  # Root path where to insert the submodule
            name='testaddedsub',
            path='addedsub',
            url='https://github.com/Didifred/yagso_test_repo_3.git',
            commit='HEAD'
        )
        manager.add_submodule_definition(new_manifest, sub_def)

        # Write modified manifest back
        manager.save_manifest(new_manifest, pathYaml)

        try:
            controller = CLIController()

            result = controller.run(['configure'])
            self.assertEqual(result, 0)

            result = controller.run(['commit', '--message', 'Test commit from CLI'])
            self.assertEqual(result, 0)
        finally:
            manager.save_manifest(manifest, pathYaml)


if __name__ == "__main__":
    unittest.main()
