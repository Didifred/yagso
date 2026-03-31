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

if __name__ == "__main__":
    unittest.main()