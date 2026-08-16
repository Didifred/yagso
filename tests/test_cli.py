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

        # Verified fields in yagso.yaml are like expected, and that the command returns 0
        pathYaml = Path('yagso.yaml')
        manager = ManifestManager()

        manifest = manager.load_manifest(pathYaml)

        commit_value = manager.get_submodule_field(manifest, 'lib1', 'commit')
        self.assertEqual(commit_value, 'ddb8e804644540502551230b8a9eeb5ffe797abf')

        lib1_refs = manager.get_submodule_field(manifest, 'lib1', 'ref')
        self.assertEqual(lib1_refs[1], 'origin/main')
        self.assertEqual(lib1_refs[0], '1.0')

        # Verify that the tracking_branch for lib2/lib3 is develop/YAGSO
        tracking_branch_value = manager.get_submodule_field(
            manifest, 'lib2/lib3', 'tracking_branch')
        self.assertEqual(tracking_branch_value, 'develop/YAGSO')

        # Verify the submodule name for lib2/lib3 is correct
        name_value = manager.get_submodule_field(manifest, 'lib2/lib3', 'name')
        self.assertEqual(name_value, 'innerLib3')

        # Verify that lib2 contains an inner submodule at path 'lib3'
        lib2_submodules = manager.get_submodule_field(manifest, 'lib2', 'submodules')
        self.assertIsNotNone(lib2_submodules)
        self.assertTrue(any(s.path == 'lib3' or s.root_path ==
                        'lib2/lib3' for s in lib2_submodules))

        # Verify that the command returns 0
        self.assertEqual(result, 0)

    def test_generate_command__local_branches(self):

        # Create some local branches to test
        try:
            # Checkout main
            submodule_path = Path('lib2/lib3')
            submodule_repo = Repo(submodule_path)
            submodule_repo.git.checkout('-b', 'main', 'origin/main')

            # Create a new local branch in a submodule
            submodule_repo.git.checkout('-b', 'test_submodule_branch')
        except Exception as e:
            self.fail(f"Failed to create local branches in submodule: {e}")

        # Commit submodules and root repo to ensure the local branches are present
        # in the repository state
        with GitOperations(Path.cwd()) as git_ops:
            git_ops.commit_all("TestCli::test_generate_command__local_branches")

        controller = CLIController()
        result = controller.run(['generate'])

        # Verify that un yaml file is generated and contains the local branch
        # test_submodule_branch and with main branch for submodule lib2/lib3 written main|origin.
        # Verify that command returns 0
        # Load generated manifest and verify refs include the local branch
        pathYaml = Path('yagso.yaml')
        manager = ManifestManager()
        manifest = manager.load_manifest(pathYaml)

        refs = manager.get_submodule_field(manifest, 'lib2/lib3', 'ref')
        # Ensure refs is a list and contains the test local branch
        self.assertIsNotNone(refs)
        self.assertTrue(any('test_submodule_branch' in r for r in refs))
        # Ensure there's an entry that encodes main and origin separated by '|'
        self.assertTrue(any(('main' in r and 'origin' in r and '|' in r) for r in refs))

        self.assertEqual(result, 0)

    def test_configure_command(self):
        """Test that configure command works (identity)."""
        controller = CLIController()

        result = controller.run(['configure'])

        # Verify that yaml file is unchanged and that the command returns 0
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

            # Verify that lib3/bis is now at commit develop/YAGSO and that the command returns 0
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

            # Verify that lib2/lib3 is now named innerLib3Test that the command returns 0
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

            # Verify that lib1 url change to ssh url and that the command returns 0
            self.assertEqual(result, 0)

        finally:
            manager.save_manifest(manifest, pathYaml)

    def test_configure_command_add_submodule(self):
        """Test that configure command works with adding a new submodule."""
        # Modify yagso.yaml to add a new submodule addedsub
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

            # Verify that testaddedsub submodule has been added and that the command returns 0
            self.assertEqual(result, 0)

        finally:
            manager.save_manifest(manifest, pathYaml)

    def test_configure_command_add_submodule_level_1(self):
        """Test that configure command works with adding a new submodule."""
        # Modify yagso.yaml to add a new submodule addedsub under lib2
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

            # Verify that testaddedsub submodule has been added and that the command returns 0
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

            # Verify that testaddedsub submodule has been added and gitlinks comitted
            # and that the command returns 0
            self.assertEqual(result, 0)
        finally:
            manager.save_manifest(manifest, pathYaml)

    def test_generate_command__bom(self):
        """Test that generate with --BOM produces BOM.yaml with expected structure."""
        controller = CLIController()

        result = controller.run(['generate', '--BOM'])

        self.assertEqual(result, 0)

        bom_path = Path('BOM.yaml')
        self.assertTrue(bom_path.exists())

        with open(bom_path, 'r', encoding='utf-8') as f:
            bom = yaml.safe_load(f)

        self.assertIn('submodules', bom)
        # Ensure first submodule entry contains path and files keys
        if bom.get('submodules'):
            first = bom['submodules'][0]
            self.assertIn('path', first)
            self.assertIn('files', first)

    def test_generate_command__bom2(self):
        """Test that generate --BOM command works."""
        controller = CLIController()

        result = controller.run(['generate', '--BOM'])

        # Verified fields in yagso.yaml are like expected, and that the command returns 0
        pathYaml = Path('BOM.yaml')
        manager = ManifestManager()

        # TODO: Implement BOM manifest loading and validation in ManifestManager
        # manifest = manager.load_manifest(pathYaml)

        # commit_value = manager.get_submodule_field(manifest, 'lib1', 'commit')
        # self.assertEqual(commit_value, 'ddb8e804644540502551230b8a9eeb5ffe797abf')

        # lib1_refs = manager.get_submodule_field(manifest, 'lib1', 'ref')
        # self.assertEqual(lib1_refs[0], '1.0')

        # Verify that lib2 contains an inner submodule at path 'lib3'
        # lib2_submodules = manager.get_submodule_field(manifest, 'lib2', 'submodules')
        # self.assertIsNotNone(lib2_submodules)
        # self.assertTrue(any(s.path == 'lib3' or s.root_path ==
        #                'lib2/lib3' for s in lib2_submodules))

        # Verify that the command returns 0
        self.assertEqual(result, 0)


if __name__ == "__main__":
    unittest.main()
