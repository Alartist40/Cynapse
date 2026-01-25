#!/usr/bin/env python3
"""
Cynapse Security Test Suite
Tests the security features of the Cynapse ecosystem.
"""

import os
import sys
import unittest
import subprocess
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from cynapse import CynapseHub

class TestSecurity(unittest.TestCase):
    """Tests the security features of the Cynapse ecosystem."""

    def test_signature_verification(self):
        """
        Checks neuron signature verification by tampering with and restoring a neuron's binary.
        
        Searches for a neuron whose manifest.requires_signature is True and skips the test if none is found. Overwrites the neuron's binary with tampered bytes and asserts that verify() returns `False`, then restores the original binary and asserts that verify() returns `True`.
        """
        hub = CynapseHub()

        # Find a neuron that requires a signature
        neuron_to_test = None
        for neuron in hub.neurons.values():
            if neuron.manifest.requires_signature:
                neuron_to_test = neuron
                break

        if not neuron_to_test:
            self.skipTest("No neurons found that require a signature.")

        # Tamper with the neuron's binary
        original_binary = neuron_to_test.binary.read_bytes()
        try:
            neuron_to_test.binary.write_bytes(b"tampered")

            # Verify that the signature check fails
            self.assertFalse(neuron_to_test.verify(), "Signature verification should fail for a tampered neuron.")

        finally:
            # Restore the original binary
            neuron_to_test.binary.write_bytes(original_binary)

        # Verify that the signature check passes for the original neuron
        self.assertTrue(neuron_to_test.verify(), "Signature verification should pass for the original neuron.")

if __name__ == "__main__":
    unittest.main(verbosity=2)