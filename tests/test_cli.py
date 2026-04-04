import unittest
import sys
from io import StringIO
from yagso.cli.controller import CLIController

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

if __name__ == "__main__":
    unittest.main()