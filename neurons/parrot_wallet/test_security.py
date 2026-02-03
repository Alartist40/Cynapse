#!/usr/bin/env python3
import sys
import os
import io
import unittest
from unittest.mock import patch, MagicMock

# Import the wallet script
import wallet

class TestWalletSecurity(unittest.TestCase):
    @patch('wallet.transcribe')
    @patch('wallet.first24_valid')
    @patch('wallet.seed_from_words')
    @patch('wallet.derive_address')
    @patch('os.path.exists')
    @patch('os.remove')
    def test_no_seed_leakage(self, mock_remove, mock_exists, mock_derive, mock_seed, mock_first24, mock_transcribe):
        # Setup mocks
        seed_words = "abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon art"
        mock_transcribe.return_value = seed_words
        mock_first24.return_value = seed_words.split()
        mock_seed.return_value = b"dummy_seed"
        mock_derive.return_value = "1MockAddress"
        mock_exists.return_value = True

        # Capture stdout
        captured_output = io.StringIO()
        sys.stdout = captured_output

        try:
            # Call the real code path
            addr = wallet.process_recording("dummy.wav")

            output = captured_output.getvalue()

            # Verify that the seed words are NOT in the output
            for word in seed_words.split():
                self.assertNotIn(word, output, f"Seed word '{word}' leaked in output!")

            # Verify address was derived
            self.assertEqual(addr, "1MockAddress")

            # Verify functions were called
            mock_transcribe.assert_called_once_with("dummy.wav")
            mock_first24.assert_called_once()
            mock_seed.assert_called_once()
            mock_derive.assert_called_once()

        finally:
            sys.stdout = sys.__stdout__

        print("Security Test Passed: No seed words found in output and functions were correctly mocked.")

    @patch('wallet.transcribe')
    @patch('wallet.first24_valid')
    @patch('os.path.exists')
    @patch('os.remove')
    def test_no_partial_seed_leakage(self, mock_remove, mock_exists, mock_first24, mock_transcribe):
        # Test the case where < 24 words are found
        partial_seed = "abandon abandon abandon"
        mock_transcribe.return_value = partial_seed
        mock_first24.return_value = ["abandon", "abandon", "abandon"]
        mock_exists.return_value = True

        captured_output = io.StringIO()
        sys.stdout = captured_output

        try:
            # Call the real code path
            addr = wallet.process_recording("dummy.wav")

            output = captured_output.getvalue()

            # Verify that seed words are NOT in the output
            self.assertNotIn("abandon", output)
            self.assertIn("Found: 3", output)

            # Verify address was NOT derived
            self.assertIsNone(addr)

        finally:
            sys.stdout = sys.__stdout__

        print("Security Test Passed: No partial seed words found in output.")

if __name__ == '__main__':
    unittest.main()
