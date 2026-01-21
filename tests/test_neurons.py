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
    """Discover all neurons in the neurons/ directory."""
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
    """Creates a test case for a single neuron."""

    def test_neuron(self):
        """Generic test for a single neuron."""
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
