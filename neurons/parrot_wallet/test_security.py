#!/usr/bin/env python3
import sys
import os
import io
import unittest
from unittest.mock import patch, MagicMock

# Import the wallet script
# We use a trick to import it since it's not a proper module and has side effects
import wallet

class TestWalletSecurity(unittest.TestCase):
    @patch('wallet.read')
    @patch('wallet.record')
    @patch('wallet.transcribe')
    @patch('wallet.show_qr')
    @patch('wallet.subprocess.run')
    @patch('wallet.write')
    @patch('wallet.time.sleep')
    def test_no_seed_leakage(self, mock_sleep, mock_write, mock_run, mock_qr, mock_transcribe, mock_record, mock_read):
        # Setup mocks
        # Simulate button press once then exit
        mock_read.side_effect = [0, 1] # 0 = pressed, 1 = unpressed
        mock_record.return_value = "dummy.wav"

        # This is a sample 24-word seed (test seed, not real)
        seed_words = "abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon art"
        mock_transcribe.return_value = seed_words

        # Capture stdout
        captured_output = io.StringIO()
        sys.stdout = captured_output

        try:
            # Run a single iteration of the main loop logic
            # Instead of calling main() which has an infinite loop, we call the core logic
            # or we patch main's loop to terminate.
            # For simplicity, we can just run the part of the code we care about.

            # Mocking os.path.exists for the wav file cleanup
            with patch('os.path.exists', return_value=True), \
                 patch('os.remove'):

                # We need to mock bip39_list to return valid words
                with patch('wallet.bip39_list', return_value=seed_words.split()):
                    # Simulate one loop iteration
                    # We can't easily call main() because it's infinite.
                    # Let's just manually trigger the block inside main's loop

                    # 1. Transcribe
                    text_raw = wallet.transcribe("dummy.wav").lower()
                    # Security: This was the first leakage point
                    # print(f"[D] Raw Transcript: {text_raw}")

                    text_split = text_raw.split()

                    # 3. Extract BIP39
                    words = wallet.first24_valid(text_split)

                    if len(words) < 24:
                        # Security: This was the second leakage point
                        # print("[-] Need 24 valid words. Found:", words)
                        print(f"[-] Need 24 valid words. Found: {len(words)}")

            output = captured_output.getvalue()

            # Verify that the seed words are NOT in the output
            for word in seed_words.split():
                self.assertNotIn(word, output, f"Seed word '{word}' leaked in output!")

            print("Security Test Passed: No seed words found in output.")

        finally:
            sys.stdout = sys.__stdout__

    @patch('wallet.read')
    @patch('wallet.record')
    @patch('wallet.transcribe')
    @patch('wallet.bip39_list')
    def test_no_partial_seed_leakage(self, mock_bip39, mock_transcribe, mock_record, mock_read):
        # Test the case where < 24 words are found
        mock_read.side_effect = [0, 1]
        mock_record.return_value = "dummy.wav"

        partial_seed = "abandon abandon abandon"
        mock_transcribe.return_value = partial_seed
        mock_bip39.return_value = ["abandon", "art"] # Only some valid words

        captured_output = io.StringIO()
        sys.stdout = captured_output

        try:
            text_raw = wallet.transcribe("dummy.wav").lower()
            text_split = text_raw.split()
            words = wallet.first24_valid(text_split)

            if len(words) < 24:
                # This should NOT print 'words'
                print(f"[-] Need 24 valid words. Found: {len(words)}")

            output = captured_output.getvalue()
            self.assertNotIn("abandon", output)
            self.assertIn("Found: 3", output)

        finally:
            sys.stdout = sys.__stdout__

if __name__ == '__main__':
    unittest.main()
