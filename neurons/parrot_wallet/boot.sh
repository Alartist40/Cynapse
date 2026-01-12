#!/bin/bash
# boot.sh - Launches the Voice Wallet
# Add this to /boot/rc.local or systemd

echo "[VoiceWallet] Starting..."
cd /boot/voice-wallet || exit 1

# Provide visible feedback that we are starting
# (If we controlled the LED here directly, we would)

# Run the wallet script
# Using sys.executable logic if needed, but standard python3 is expected
/usr/bin/python3 wallet.py >> wallet.log 2>&1 &
