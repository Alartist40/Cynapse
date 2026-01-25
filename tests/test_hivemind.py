#!/usr/bin/env python3
"""
Cynapse HiveMind Test Suite
Tests the HiveMind AI ecosystem.
"""

import os
import sys
import unittest
import subprocess
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

class TestHiveMind(unittest.TestCase):
    """Tests the HiveMind AI ecosystem."""

    def test_hivemind_script_execution_with_help(self):
        """
        Verify hivemind.py executes with the --help flag.
        
        Asserts the script exists, runs it with the current Python interpreter, and verifies the process exits with code 0 or 1. Fails the test if execution times out or any unexpected exception occurs.
        """
        hivemind_script = Path(__file__).parent.parent / "hivemind.py"
        self.assertTrue(hivemind_script.exists(), "hivemind.py should exist")

        try:
            # Execute the script with the --help command to check if it runs
            result = subprocess.run(
                [sys.executable, str(hivemind_script), '--help'],
                capture_output=True,
                text=True,
                timeout=30
            )
            self.assertIn(result.returncode, [0, 1], f"hivemind.py failed to execute with --help. Stderr: {result.stderr}")
        except subprocess.TimeoutExpired:
            self.fail("hivemind.py timed out when run with --help")
        except Exception as e:
            self.fail(f"Failed to test hivemind.py: {e}")

    def test_hivemind_script_execution_with_invalid_command(self):
        """Test that the hivemind.py script returns a non-zero exit code with an invalid command."""
        hivemind_script = Path(__file__).parent.parent / "hivemind.py"
        self.assertTrue(hivemind_script.exists(), "hivemind.py should exist")

        try:
            # Execute the script with an invalid command
            result = subprocess.run(
                [sys.executable, str(hivemind_script), 'invalid_command'],
                capture_output=True,
                text=True,
                timeout=30
            )
            self.assertNotEqual(result.returncode, 0, f"hivemind.py should have returned a non-zero exit code with an invalid command.")
        except subprocess.TimeoutExpired:
            self.fail("hivemind.py timed out when run with an invalid command")
        except Exception as e:
            self.fail(f"Failed to test hivemind.py: {e}")

if __name__ == "__main__":
    unittest.main(verbosity=2)