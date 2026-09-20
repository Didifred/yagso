"""Integration test of yagso cli commands """
import unittest
import copy
from io import StringIO
from pathlib import Path
from unittest.mock import patch
from git import Repo
from rich.console import Console

from yagso.cli.formatter import OutputFormatter, get_output_formatter
from yagso.core.handlers import GenerateHandler
from yagso.core.orchestrator import SubmoduleOrchestrator
from yagso.infrastructure.git_ops import GitOperations
from yagso.cli.controller import CLIController
from yagso.infrastructure.manifest_manager import ManifestManager
from yagso.domain.submodule import SubmoduleDefinition
from tests.common import BaseGitTest


class TestFormatter(unittest.TestCase):
    """Unit tests for OutputFormatter and related functionality."""

    def test_instance_returns_same_formatter(self):
        """The formatter getter returns one shared instance."""
        self.assertIs(OutputFormatter.instance(), OutputFormatter.instance())

    def test_public_formatter_getter_returns_shared_instance(self):
        """The public accessor returns the shared formatter."""
        self.assertIs(get_output_formatter(), OutputFormatter.instance())

    def test_core_accepts_injected_output(self):
        """Core services retain the injected output port."""
        output = object()
        orchestrator = SubmoduleOrchestrator(Path('.'), output)
        handler = GenerateHandler(orchestrator, output)

        self.assertIs(orchestrator.output, output)
        self.assertIs(orchestrator.manifest_manager.output, output)
        self.assertIs(handler.output, output)

    def test_output_formatter_apis_use_rich_console(self):
        """The formatter exposes the expected Rich-backed output APIs."""
        stream = StringIO()
        console = Console(file=stream, color_system=None, force_terminal=True)

        with patch("yagso.cli.formatter.Console", return_value=console):
            formatter = OutputFormatter()

            formatter.success("Saved")
            formatter.info("Ready")
            formatter.error("Failed")
            formatter.progress(2, 3, "Syncing")

        output = stream.getvalue()
        self.assertIn("Saved", output)
        self.assertIn("Ready", output)
        self.assertIn("Failed", output)
        self.assertIn("Syncing", output)

    def test_error_stops_progress_and_uses_red(self):
        """An error stops active progress and is rendered in red."""
        stream = StringIO()
        console = Console(file=stream, color_system="standard", force_terminal=True)

        with patch("yagso.cli.formatter.Console", return_value=console):
            formatter = OutputFormatter()
            formatter.progress(1, 2, "Syncing")
            progress = formatter._progress
            bar_column = formatter._bar_column

            with patch.object(progress, "stop", wraps=progress.stop) as stop:
                formatter.error("Failed")

        stop.assert_called_once_with()
        self.assertEqual(bar_column.complete_style, "red")
        self.assertEqual(bar_column.finished_style, "red")
        self.assertIsNone(formatter._progress)
        self.assertIsNone(formatter._task_id)
        self.assertIn("\x1b[31m", stream.getvalue())
        self.assertIn("Failed", stream.getvalue())

    def test_progress_updates_total(self):
        """Progress reflects a larger total reported after task creation."""
        console = Console(file=StringIO(), color_system=None, force_terminal=True)

        with patch("yagso.cli.formatter.Console", return_value=console):
            formatter = OutputFormatter()
            formatter.progress(1, 2, "Syncing")
            formatter.progress(2, 5, "Syncing more")

        self.assertEqual(formatter._progress.tasks[0].total, 5)
        self.assertEqual(formatter._progress.tasks[0].completed, 2)


class TestCli(BaseGitTest):
    """Integration tests for the CLIController and command handlers."""

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
        path_yaml = Path('yagso.yaml')
        manager = ManifestManager()

        manifest = manager.load_manifest(path_yaml)

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

        # Checkout main in root repo to ensure commit is made on main branch
        root_repo = Repo(Path.cwd())
        root_repo.git.checkout('main')

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
        path_yaml = Path('yagso.yaml')
        manager = ManifestManager()
        manifest = manager.load_manifest(path_yaml)

        refs = manager.get_submodule_field(manifest, 'lib2/lib3', 'ref')
        # Ensure refs is a list and contains the test local branch
        self.assertIsNotNone(refs)
        self.assertTrue(any('test_submodule_branch' in r for r in refs))
        # Ensure there's an entry that encodes main and origin separated by '|'
        self.assertTrue(any(('main' in r and 'origin' in r and '|' in r) for r in refs))

        self.assertEqual(result, 0)

    def test_configure_command(self):
        """Test that configure command works (identity)\n"""
        path_yaml = Path('yagso.yaml')
        original_manifest = path_yaml.read_bytes()
        controller = CLIController(True)

        result = controller.run(['status'])

        result = controller.run(['configure'])

        # Verify that the manifest is unchanged and that the command returns 0.
        self.assertEqual(path_yaml.read_bytes(), original_manifest)
        self.assertEqual(result, 0)

    def test_configure_command_commit_change(self):
        """Test that configure command works with commit change to develop/YAGSO"""
        # Modify yagso.yaml to change lib3/bis commit to develop/YAGSO
        path_yaml = Path('yagso.yaml')
        manager = ManifestManager()
        manifest = manager.load_manifest(path_yaml)
        new_manifest = copy.deepcopy(manifest)
        manager.update_submodule_field(new_manifest, 'lib3/bis', 'commit', 'develop/YAGSO')

        # Write modified manifest back
        manager.save_manifest(new_manifest, path_yaml)

        try:
            controller = CLIController(True)

            result = controller.run(['status'])

            result = controller.run(['configure'])

            # Verify that lib3/bis is now checked out on develop/YAGSO and that the
            # command returns 0.
            submodule_repo = Repo('lib3/bis')
            self.assertEqual(submodule_repo.head.reference.name, 'develop/YAGSO')
            self.assertEqual(result, 0)
        finally:
            manager.save_manifest(manifest, path_yaml)

    def test_configure_command_name_change(self):
        """Test that configure command works with name change to innerLib3Test"""
        # Modify yagso.yaml to change name of lib2/lib3 repo to innerLib3Test
        path_yaml = Path('yagso.yaml')
        manager = ManifestManager()
        manifest = manager.load_manifest(path_yaml)
        new_manifest = copy.deepcopy(manifest)
        manager.update_submodule_field(new_manifest, 'lib2/lib3', 'name', 'innerLib3Test')

        # Write modified manifest back
        manager.save_manifest(new_manifest, path_yaml)

        try:
            controller = CLIController(True)

            result = controller.run(['status'])

            result = controller.run(['configure'])

            # Verify that lib2/lib3 is now named innerLib3Test that the command returns 0
            self.assertEqual(result, 0)
            self.assertEqual(
                manager.get_submodule_field(
                    manager.load_manifest(path_yaml), 'lib2/lib3', 'name'),
                'innerLib3Test')

        finally:
            manager.save_manifest(manifest, path_yaml)

    def test_configure_command_url_change(self):
        """Test that configure command works with url change to ssh"""
        # Modify yagso.yaml to change lib1 url to ssh
        path_yaml = Path('yagso.yaml')
        manager = ManifestManager()
        manifest = manager.load_manifest(path_yaml)
        new_manifest = copy.deepcopy(manifest)
        manager.update_submodule_field(
            new_manifest,
            'lib1',
            'url',
            'git@github.com:Didifred/yagso_test_repo_1.git')

        # Write modified manifest back
        manager.save_manifest(new_manifest, path_yaml)

        try:
            controller = CLIController(True)

            result = controller.run(['status'])

            result = controller.run(['configure'])

            # Verify that lib1 url change to ssh url and that the command returns 0
            self.assertEqual(result, 0)

            updated_manifest = manager.load_manifest(path_yaml)
            updated_url = manager.get_submodule_field(updated_manifest, 'lib1', 'url')
            self.assertEqual(updated_url, 'git@github.com:Didifred/yagso_test_repo_1.git')

        finally:
            manager.save_manifest(manifest, path_yaml)

    def test_configure_command_bad_url_change(self):
        """Test that configure command failed with wrong url change"""
        # Modify yagso.yaml to change lib1 url to ssh
        path_yaml = Path('yagso.yaml')
        manager = ManifestManager()
        manifest = manager.load_manifest(path_yaml)
        new_manifest = copy.deepcopy(manifest)
        manager.update_submodule_field(
            new_manifest,
            'lib2',
            'url',
            'https://github.com/Didifred/yagso_test_oups.git')

        # Write modified manifest back
        manager.save_manifest(new_manifest, path_yaml)

        try:
            controller = CLIController(True)

            result = controller.run(['configure'])

            # Verify that command fails and that the command returns 1
            self.assertEqual(result, 1)

        finally:
            manager.save_manifest(manifest, path_yaml)

    def test_configure_command_tracking_change(self):
        """Test that configure command works with tracking branch"""
        # Modify yagso.yaml to change lib2/lib3 url to ssh
        path_yaml = Path('yagso.yaml')
        manager = ManifestManager()
        manifest = manager.load_manifest(path_yaml)
        new_manifest = copy.deepcopy(manifest)
        manager.update_submodule_field(
            new_manifest,
            'lib2/lib3',
            'tracking_branch',
            'main')

        # Write modified manifest back
        manager.save_manifest(new_manifest, path_yaml)

        try:
            controller = CLIController(True)

            result = controller.run(['status'])

            result = controller.run(['configure'])

            # Verify that the submodule tracking branch is configured to main in
            # .gitmodules and that the command returns 0.
            root_repo = Repo(Path.cwd())
            configured_branch = root_repo.git.config(
                '-f', '.gitmodules', '--get', 'submodule.lib2.branch')
            self.assertEqual(configured_branch, 'main')
            self.assertEqual(result, 0)

        finally:
            # Write original manifest back to yaml
            manager.save_manifest(manifest, path_yaml)

    def test_configure_command_add_submodule(self):
        """Test that configure command works with adding a new submodule"""
        # Modify yagso.yaml to add a new submodule addedsub
        path_yaml = Path('yagso.yaml')
        manager = ManifestManager()
        manifest = manager.load_manifest(path_yaml)
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
        manager.save_manifest(new_manifest, path_yaml)

        try:
            controller = CLIController(True)

            result = controller.run(['status'])

            result = controller.run(['configure'])

            # Verify that the new submodule exists on disk and that the command returns 0.
            added_submodule_path = Path('libs/addedsub')
            self.assertTrue(added_submodule_path.exists())
            self.assertTrue((added_submodule_path / '.git').exists())
            self.assertEqual(result, 0)

        finally:
            manager.save_manifest(manifest, path_yaml)

    def test_configure_command_add_submodule_level_1(self):
        """Test that configure command works with adding a new submodule"""
        # Modify yagso.yaml to add a new submodule addedsub under lib2
        path_yaml = Path('yagso.yaml')
        manager = ManifestManager()
        manifest = manager.load_manifest(path_yaml)
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
        manager.save_manifest(new_manifest, path_yaml)

        try:
            controller = CLIController(True)

            result = controller.run(['configure'])

            # Verify that the nested submodule is created under lib2 and that the
            # command returns 0.
            nested_submodule_path = Path('lib2/addedsub')
            self.assertTrue(nested_submodule_path.exists())
            self.assertTrue((nested_submodule_path / '.git').exists())
            self.assertEqual(result, 0)

            # TODO : stage upper level submodules ?
        finally:
            manager.save_manifest(manifest, path_yaml)

    def test_configure_command_add_submodule_hierarchy(self):
        """Test that configure command works with adding a new submodule"""
        # Modify yagso.yaml to add a new submodule addedsub
        path_yaml = Path('yagso.yaml')
        manager = ManifestManager()
        manifest = manager.load_manifest(path_yaml)
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
        manager.save_manifest(new_manifest, path_yaml)

        try:
            controller = CLIController(True)

            result = controller.run(['status'])

            result = controller.run(['configure'])

            # Verify that the hierarchy submodule exists on disk, has Git metadata,
            # and that the command returns 0.
            hierarchy_submodule_path = Path('lib4')
            self.assertTrue(hierarchy_submodule_path.exists())
            self.assertTrue((hierarchy_submodule_path / '.git').exists())

            nested_lib2_path = hierarchy_submodule_path / 'lib2'
            nested_lib3_path = nested_lib2_path / 'lib3'
            self.assertTrue(nested_lib2_path.exists())
            self.assertTrue((nested_lib2_path / '.git').exists())
            self.assertTrue(nested_lib3_path.exists())
            self.assertTrue((nested_lib3_path / '.git').exists())

            configured_manifest = manager.load_manifest(path_yaml)
            self.assertIsNotNone(
                manager.get_submodule_field(configured_manifest, 'lib4/lib2', 'submodules'))
            self.assertIsNotNone(
                manager.get_submodule_field(configured_manifest, 'lib4/lib2/lib3', 'url'))
            self.assertEqual(result, 0)

        finally:
            manager.save_manifest(manifest, path_yaml)

    def test_commit_command_add_submodule_level_1(self):
        """Test that commit command works"""

        # Modify yagso.yaml to add a new submodule lib4
        path_yaml = Path('yagso.yaml')
        manager = ManifestManager()
        manifest = manager.load_manifest(path_yaml)
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
        manager.save_manifest(new_manifest, path_yaml)

        try:
            controller = CLIController(True)

            result = controller.run(['configure'])
            self.assertEqual(result, 0)

            # Checkout main in root repo to ensure commit is made on main branch
            root_repo = Repo(Path.cwd())
            root_repo.git.checkout('main')

            result = controller.run(['commit', '--message', 'Test commit from CLI'])

            # Verify that the nested submodule exists and its gitlink was committed.
            added_submodule_path = Path('lib2/addedsub')
            self.assertTrue(added_submodule_path.exists())
            self.assertTrue((added_submodule_path / '.git').exists())

            lib2_repo = Repo('lib2')
            added_submodule_gitlink = lib2_repo.git.ls_tree('HEAD', 'addedsub')
            self.assertIn('160000 commit', added_submodule_gitlink)
            self.assertIn('addedsub', added_submodule_gitlink)
            self.assertFalse(lib2_repo.is_dirty())

            root_repo = Repo(Path.cwd())
            self.assertIn('Test commit from CLI', root_repo.head.commit.message)
            self.assertFalse(root_repo.is_dirty())
            self.assertEqual(result, 0)
        finally:
            manager.save_manifest(manifest, path_yaml)

    def test_configure_command_repopulate_subs(self):
        """Test that configure command works with repopulating submodules after a
        submodule has been removed from the repo and added back to the manifest"""
        # Modify yagso.yaml to add a new submodule addedsub
        path_yaml = Path('yagso.yaml')
        manager = ManifestManager()
        manifest = manager.load_manifest(path_yaml)
        new_manifest = copy.deepcopy(manifest)

        manager.update_submodule_field(new_manifest,
                                       'lib2', 'commit',
                                       'origin/feature/no_submodule')

        # Write modified manifest back
        manager.save_manifest(new_manifest, path_yaml)

        try:
            controller = CLIController(True)

            result = controller.run(['status'])

            result = controller.run(['configure'])

            # Verify that lib2 uses the requested commit and that its lib3
            # submodule has been repopulated.
            lib2_repo = Repo('lib2')
            self.assertEqual(
                lib2_repo.head.commit.hexsha,
                lib2_repo.commit('origin/feature/no_submodule').hexsha)

            lib3_submodule_path = Path('lib2/lib3')
            self.assertTrue(lib3_submodule_path.exists())
            self.assertTrue((lib3_submodule_path / '.git').exists())
            self.assertTrue(any(
                submodule.path == 'lib3' for submodule in lib2_repo.submodules))

            configured_manifest = manager.load_manifest(path_yaml)
            self.assertIsNotNone(
                manager.get_submodule_field(configured_manifest, 'lib2/lib3', 'url'))
            self.assertEqual(result, 0)

        finally:
            manager.save_manifest(manifest, path_yaml)

    def test_commit_command_none(self):
        """Test that commit command without changes returns information and does not fail"""

        # Modify yagso.yaml to add a new submodule lib4
        path_yaml = Path('yagso.yaml')
        manager = ManifestManager()
        manifest = manager.load_manifest(path_yaml)
        new_manifest = copy.deepcopy(manifest)

        # Write modified manifest back
        manager.save_manifest(new_manifest, path_yaml)

        try:
            controller = CLIController(True)

            result = controller.run(['commit', '--message', 'Nothing to commit'])

            self.assertEqual(result, 0)
        finally:
            manager.save_manifest(manifest, path_yaml)

    def test_generate_command__bom(self):
        """Test that generate --BOM command works"""
        controller = CLIController()

        result = controller.run(['generate', '--BOM'])

        # Verified fields in yagso.yaml are like expected, and that the command returns 0
        path_yaml = Path('BOM.yaml')
        manager = ManifestManager()

        bom = manager.load_bom(path_yaml)

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
