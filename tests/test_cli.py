import unittest
import sys
import yaml
import copy
from io import StringIO
from pathlib import Path
from git import Repo
from rich.console import Console

from yagso.cli.formatter import OutputFormatter
from yagso.infrastructure.git_ops import GitOperations
from yagso.cli.controller import CLIController
from yagso.infrastructure.manifest_manager import ManifestManager
from yagso.domain.submodule import SubmoduleDefinition
from tests.common import BaseGitTest


class TestFormatter(unittest.TestCase):

    def test_output_formatter_apis_use_rich_console(self):
        """The formatter exposes the expected Rich-backed output APIs."""
        stream = StringIO()
        console = Console(file=stream, force_terminal=False, color_system=None)
        formatter = OutputFormatter(console=console)

        formatter.success("Saved")
        formatter.info("Ready")
        formatter.error("Failed")
        formatter.progress(2, 3, "Syncing")

        output = stream.getvalue()
        self.assertIn("Saved", output)
        self.assertIn("Ready", output)
        self.assertIn("Failed", output)
        self.assertIn("Syncing", output)


class TestCli(BaseGitTest):

    def test_controller_creation(self):
        """Test that CLIController can be created"""
        controller = CLIController(True)
        self.assertIsNotNone(controller)

    def test_help_command(self):
        """Test that help command works."""
        controller = CLIController(True)
        result = controller.run(['--help'])
        # Should return 0 for help
        self.assertEqual(result, 0)

    def test_invalid_command(self):
        """Test that invalid command returns error"""
        controller = CLIController(True)
        result = controller.run(['invalid'])
        self.assertEqual(result, 1)

    def test_generate_command(self):
        """Test that generate command works"""
        controller = CLIController(True)

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
        self.assertTrue(any(s.path == 'lib3' and s.root_path ==
                        'lib2/lib3' for s in lib2_submodules))

        # Verify that the command returns 0
        self.assertEqual(result, 0)

    def test_generate_command__local_branches(self):
        """Test that generate command and local branches are included in the manifest"""
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

        controller = CLIController(True)
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
        """Test that configure command works (identity)"""
        controller = CLIController(True)

        result = controller.run(['configure'])

        # Verify that yaml file is unchanged and that the command returns 0
        self.assertEqual(result, 0)

    def test_configure_command_commit_change(self):
        """Test that configure command works with commit change to develop/YAGSO"""
        # Modify yagso.yaml to change lib3/bis commit to develop/YAGSO
        pathYaml = Path('yagso.yaml')
        manager = ManifestManager()
        manifest = manager.load_manifest(pathYaml)
        new_manifest = copy.deepcopy(manifest)
        manager.update_submodule_field(new_manifest, 'lib3/bis', 'commit', 'develop/YAGSO')

        # Write modified manifest back
        manager.save_manifest(new_manifest, pathYaml)

        try:
            controller = CLIController(True)

            result = controller.run(['configure'])

            # Verify that lib3/bis is now at commit develop/YAGSO and that the command returns 0
            self.assertEqual(result, 0)
        finally:
            manager.save_manifest(manifest, pathYaml)

    def test_configure_command_name_change(self):
        """Test that configure command works with name change to innerLib3Test"""
        # Modify yagso.yaml to change name of lib2/lib3 repo to innerLib3Test
        pathYaml = Path('yagso.yaml')
        manager = ManifestManager()
        manifest = manager.load_manifest(pathYaml)
        new_manifest = copy.deepcopy(manifest)
        manager.update_submodule_field(new_manifest, 'lib2/lib3', 'name', 'innerLib3Test')

        # Write modified manifest back
        manager.save_manifest(new_manifest, pathYaml)

        try:
            controller = CLIController(True)

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
            controller = CLIController(True)

            result = controller.run(['configure'])

            # Verify that lib1 url change to ssh url and that the command returns 0
            self.assertEqual(result, 0)

        finally:
            manager.save_manifest(manifest, pathYaml)

    def test_configure_command_tracking_change(self):
        """Test that configure command works with tracking branch"""
        # Modify yagso.yaml to change lib2/lib3 url to ssh
        pathYaml = Path('yagso.yaml')
        manager = ManifestManager()
        manifest = manager.load_manifest(pathYaml)
        new_manifest = copy.deepcopy(manifest)
        manager.update_submodule_field(
            new_manifest,
            'lib2/lib3',
            'tracking_branch',
            'main')

        # Write modified manifest back
        manager.save_manifest(new_manifest, pathYaml)

        try:
            controller = CLIController(True)

            result = controller.run(['configure'])

            # Verify that lib2/lib3 tracking branch change to main  and the command returns 0
            self.assertEqual(result, 0)

        finally:
            # Write original manifest back to yaml
            manager.save_manifest(manifest, pathYaml)

    def test_configure_command_add_submodule(self):
        """Test that configure command works with adding a new submodule"""
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
            controller = CLIController(True)

            result = controller.run(['configure'])

            # Verify that testaddedsub submodule has been added and that the command returns 0
            self.assertEqual(result, 0)

        finally:
            manager.save_manifest(manifest, pathYaml)

    def test_configure_command_add_submodule_level_1(self):
        """Test that configure command works with adding a new submodule"""
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
            controller = CLIController(True)

            result = controller.run(['configure'])

            # Verify that testaddedsub submodule has been added and that the command returns 0
            self.assertEqual(result, 0)

            # TODO : stage upper level submodules ?
        finally:
            manager.save_manifest(manifest, pathYaml)

    def test_configure_command_add_submodule_hierarchy(self):
        """Test that configure command works with adding a new submodule"""
        # Modify yagso.yaml to add a new submodule addedsub
        pathYaml = Path('yagso.yaml')
        manager = ManifestManager()
        manifest = manager.load_manifest(pathYaml)
        new_manifest = copy.deepcopy(manifest)

        sub_def = SubmoduleDefinition(
            root_path='lib4',
            name='testaddedsubdepth',
            path='lib4',
            url='https://github.com/Didifred/yagso_test_repo_4.git',
            commit='HEAD'
        )
        manager.add_submodule_definition(new_manifest, sub_def)

        # Write modified manifest back
        manager.save_manifest(new_manifest, pathYaml)

        try:
            controller = CLIController(True)

            result = controller.run(['configure'])

            # Verify that testaddedsubdepth submodule has been added and that the command returns 0
            # Verify that inner submodules has been discovered too in yagso.yaml !
            self.assertEqual(result, 0)

        finally:
            manager.save_manifest(manifest, pathYaml)

    def test_commit_command_add_submodule_level_1(self):
        """Test that commit command works"""

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
            controller = CLIController(True)

            result = controller.run(['configure'])
            self.assertEqual(result, 0)

            result = controller.run(['commit', '--message', 'Test commit from CLI'])

            # Verify that testaddedsub submodule has been added and gitlinks comitted
            # and that the command returns 0
            self.assertEqual(result, 0)
        finally:
            manager.save_manifest(manifest, pathYaml)

    def test_commit_command_none(self):
        """Test that commit command without changes returns information and does not fail"""

        # Modify yagso.yaml to add a new submodule lib4
        pathYaml = Path('yagso.yaml')
        manager = ManifestManager()
        manifest = manager.load_manifest(pathYaml)
        new_manifest = copy.deepcopy(manifest)

        # Write modified manifest back
        manager.save_manifest(new_manifest, pathYaml)

        try:
            controller = CLIController(True)

            result = controller.run(['commit', '--message', 'Nothing to commit'])

            self.assertEqual(result, 0)
        finally:
            manager.save_manifest(manifest, pathYaml)

    def test_generate_command__bom(self):
        """Test that generate --BOM command works"""
        controller = CLIController()

        result = controller.run(['generate', '--BOM'])

        # Verified fields in yagso.yaml are like expected, and that the command returns 0
        pathYaml = Path('BOM.yaml')
        manager = ManifestManager()

        bom = manager.load_bom(pathYaml)

        commit_value = manager.get_submodule_field(bom, 'lib1', 'commit')
        self.assertEqual(commit_value, 'ddb8e804644540502551230b8a9eeb5ffe797abf')

        lib1_refs = manager.get_submodule_field(bom, 'lib1', 'ref')
        self.assertEqual(lib1_refs, '1.0')

        # Verify that lib2 contains an inner submodule at path 'lib3'
        lib2_submodules = manager.get_submodule_field(bom, 'lib2', 'submodules')
        self.assertIsNotNone(lib2_submodules)
        self.assertTrue(any(s.path == 'lib3' and s.root_path ==
                            'lib2/lib3' for s in lib2_submodules))

        # Verify that submodule contains files field with at least one file
        lib1_files = manager.get_submodule_field(bom, 'lib1', 'files')
        self.assertIsNotNone(lib1_files)

        # Verify that the command returns 0
        self.assertEqual(result, 0)

    def test_generate_command__bom_files_filter(self):
        """Test that generate --BOM --files filters BOM files by regex"""
        controller = CLIController()

        result = controller.run(['generate', '--BOM', '--files', r'.*\.c$'])
        self.assertEqual(result, 0)

        bom = ManifestManager().load_bom(Path('BOM.yaml'))
        self.assertEqual(
            ManifestManager().get_submodule_field(bom, 'lib2', 'files'), ['source.c'])
        self.assertEqual(
            ManifestManager().get_submodule_field(bom, 'lib3/bis', 'files'), ['leaf.c'])

        result = controller.run(['generate', '--BOM', '--files', r'.*\.h$'])
        self.assertEqual(result, 0)

        bom = ManifestManager().load_bom(Path('BOM.yaml'))
        self.assertEqual(
            ManifestManager().get_submodule_field(bom, 'lib2', 'files'), ['include.h'])
        self.assertEqual(
            ManifestManager().get_submodule_field(bom, 'lib3/bis', 'files'), ['leaf.h'])

    def test_generate_command__files_requires_bom(self):
        """Test that --files cannot be used without --BOM."""
        result = CLIController().run(['generate', '--files', r'^README\.md$'])

        self.assertEqual(result, 1)


if __name__ == "__main__":
    unittest.main()
