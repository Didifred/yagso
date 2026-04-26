import unittest
import sys
import yaml
import copy
from io import StringIO
from pathlib import Path
from yagso.cli.controller import CLIController
from yagso.infrastructure.manifest_manager import ManifestManager


class TestCli(unittest.TestCase):
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
        # Capture output
        captured_output = StringIO()
        sys.stdout = captured_output

        result = controller.run(['generate', '--root-path', 'tests/sample1/yagso_test_root'])
        self.assertEqual(result, 0)
        output = captured_output.getvalue()
        self.assertIn("Generated manifest", output)

        # Restore stdout
        sys.stdout = sys.__stdout__

    def test_configure_command(self):
        """Test that configure command works (identity)."""
        controller = CLIController()
        # Capture output
        captured_output = StringIO()
        sys.stdout = captured_output

        result = controller.run(['configure', '--root-path', 'tests/sample1/yagso_test_root'])
        self.assertEqual(result, 0)
        output = captured_output.getvalue()
        self.assertIn("Repository configured according to manifest", output)

        # Restore stdout
        sys.stdout = sys.__stdout__

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
            # Capture output
            captured_output = StringIO()
            sys.stdout = captured_output

            result = controller.run(['configure', '--root-path', 'tests/sample1/yagso_test_root'])
            self.assertEqual(result, 0)
            output = captured_output.getvalue()
            self.assertIn("Repository configured according to manifest", output)

            # Restore stdout
            sys.stdout = sys.__stdout__
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
            # Capture output
            # captured_output = StringIO()
            # sys.stdout = captured_output

            result = controller.run(['configure', '--root-path', 'tests/sample1/yagso_test_root'])
            self.assertEqual(result, 0)
            # output = captured_output.getvalue()
            # self.assertIn("Repository configured according to manifest", output)

            # Restore stdout
            # sys.stdout = sys.__stdout__
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
            # Capture output
            captured_output = StringIO()
            sys.stdout = captured_output

            result = controller.run(['configure', '--root-path', 'tests/sample1/yagso_test_root'])
            self.assertEqual(result, 0)
            output = captured_output.getvalue()
            self.assertIn("Repository configured according to manifest", output)

            # Restore stdout
            sys.stdout = sys.__stdout__
        finally:
            manager.save_manifest(manifest, pathYaml)


if __name__ == "__main__":
    unittest.main()
