#!/usr/bin/env python3
"""
Cynapse Neuron Test Suite
Dynamically discovers and tests all neurons.
"""

import os
import sys
import json
import unittest
import subprocess
import time
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from cynapse import Neuron

class TestAllNeurons(unittest.TestCase):
    """Dynamically tests all neurons in the neurons/ directory."""
    pass

def discover_neurons():
    """
    Locate neuron project directories under the repository's `neurons/` folder.
    
    Searches the sibling `neurons/` directory for subdirectories that contain a `manifest.json` file and returns their paths. Directories whose names start with an underscore are ignored. If the `neurons/` directory does not exist, an empty list is returned.
    
    Returns:
        list[pathlib.Path]: Paths to neuron directories that include a `manifest.json`.
    """
    neurons_dir = Path(__file__).parent.parent / "neurons"
    if not neurons_dir.exists():
        return []

    neuron_paths = []
    for path in neurons_dir.iterdir():
        if not path.is_dir() or path.name.startswith('_'):
            continue

        manifest_file = path / "manifest.json"
        if not manifest_file.exists():
            continue

        neuron_paths.append(path)
    return neuron_paths

def create_neuron_test(neuron_path):
    """
    Create and return a unittest-compatible test function that performs smoke tests for a neuron located at the given path.
    
    Parameters:
        neuron_path (pathlib.Path): Path to the neuron's project directory (must contain a manifest.json).
    
    Returns:
        test_neuron (callable): A test function suitable for attaching to a unittest.TestCase; when invoked it will validate the neuron's manifest, report declared dependencies, and perform a smoke test (interactive neurons are launched briefly, non-interactive neurons are invoked with `--help`).
    """
    """
    Run smoke checks for a single neuron: verify manifest, report dependencies, and exercise the neuron's executable.
    
    This test verifies that the neuron's manifest is present and that the manifest name matches the directory name, prints any declared dependencies, and then performs a smoke test:
    - For known interactive neurons, attempts to start the neuron's binary and ensures it does not exit immediately.
    - For other neurons, runs the neuron with `--help` and accepts return codes 0 or 1.
    
    On any unexpected condition (missing manifest, missing binary for interactive neurons, non-acceptable return code, timeout, or other exceptions) the test will fail with a descriptive message.
    """

    def test_neuron(self):
        """
        Run a smoke test for the neuron located at `neuron_path`.
        
        Verifies the neuron has a loaded manifest whose name appears in the path, prints any declared dependencies, and exercises the neuron:
        - For interactive neurons ('canary_token', 'parrot_wallet'): ensures a runnable binary exists, launches it, expects it to remain running for 2 seconds, then terminates it.
        - For non-interactive neurons: runs the neuron with `--help` and expects an exit code of `0` or `1`.
        The test fails if the manifest is missing or mismatched, an expected binary is absent, the help invocation returns an unexpected code, the help invocation times out, or any other exception occurs.
        """
        try:
            neuron = Neuron(neuron_path)

            # 1. Verify manifest
            self.assertIsNotNone(neuron.manifest, "Manifest should be loaded")
            self.assertIn(neuron.manifest.name.lower(), str(neuron_path).lower())

            # 2. Install dependencies (if any)
            if neuron.manifest.dependencies:
                # For now, just print the dependencies. A more robust solution would be to install them.
                print(f"Dependencies for {neuron.manifest.name}: {neuron.manifest.dependencies}")

            # 3. Execute with a generic command (e.g., --help) or smoke test for interactive neurons
            print(f"Testing neuron: {neuron.manifest.name}")
            interactive_neurons = ['canary_token', 'parrot_wallet']
            if neuron.manifest.name in interactive_neurons:
                # Smoke test for interactive neurons
                if not neuron.binary or not neuron.binary.exists():
                    self.fail(f"Binary not found for interactive neuron: {neuron.manifest.name}")

                cmd = []
                if neuron.binary.suffix == '.py':
                    cmd = [sys.executable, str(neuron.binary)]
                else:
                    self.fail(f"Don't know how to run interactive neuron {neuron.manifest.name}")

                process = subprocess.Popen(cmd, cwd=str(neuron.path), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                time.sleep(2)
                if process.poll() is not None:
                    stderr = process.stderr.read().decode()
                    self.fail(f"Neuron {neuron.manifest.name} exited unexpectedly with code {process.returncode}. Stderr: {stderr}")

                process.terminate()
                process.wait()
            else:
                # This is a basic test to see if the neuron can be executed.
                try:
                    result = neuron.execute('--help', timeout=30)
                    # Some programs return 1 on --help, so we accept 0 or 1
                    self.assertIn(result.returncode, [0, 1], f"Neuron {neuron.manifest.name} failed to execute with --help. Stderr: {result.stderr}")
                except subprocess.TimeoutExpired:
                    self.fail(f"Neuron {neuron.manifest.name} timed out when run with --help")
        except Exception as e:
            self.fail(f"Failed to test neuron {neuron_path.name}: {e}")

    return test_neuron

# Dynamically add a test for each neuron
neuron_paths = discover_neurons()
skipped_neurons = ['elephant_sign', 'tinyml_anomaly', 'rhino_gateway']
for neuron_path in neuron_paths:
    neuron_name = neuron_path.name
    test_name = f"test_{neuron_name}"

    if neuron_name in skipped_neurons:
        @unittest.skip(f"Skipping {neuron_name} due to compilation requirements.")
        def test_skipped(self):
            pass
        setattr(TestAllNeurons, test_name, test_skipped)
    else:
        test = create_neuron_test(neuron_path)
        setattr(TestAllNeurons, test_name, test)

if __name__ == "__main__":
    unittest.main(verbosity=2)