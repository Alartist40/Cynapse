#!/bin/bash
# install.sh - Setup the Pi for Off-Grid Voice Wallet

if [ "$EUID" -ne 0 ]; then
  echo "Please run as root"
  exit
fi

echo "[*] Installing dependencies..."
apt-get update
# arecord is in alsa-utils, usually installed. pip for python libs.
apt-get install -y alsa-utils python3-pip python3-dev i2c-tools

echo "[*] Installing Python libraries..."
# adafruit-circuitpython-ssd1306 for OLED
# qrcode configuration
# Pillow for image manipulation
pip3 install adafruit-circuitpython-ssd1306 adafruit-blinka qrcode[pil]

echo "[*] Configuring I2S Microphone (Overlays)..."
# This often requires specific /boot/config.txt changes not easily automatable blindly
# but we can append common overlay configs if they don't exist
if ! grep -q "googlevoicehat-soundcard" /boot/config.txt; then
    echo "dtparam=i2s=on" >> /boot/config.txt
    echo "dtoverlay=googlevoicehat-soundcard" >> /boot/config.txt # Common trick for INMP441 or similar I2S
    # OR simpler generic I2S
    # echo "dtoverlay=i2s-mmap" >> /boot/config.txt
    echo "[!] Added I2S overlays to /boot/config.txt. Please verify specific pinout for INMP441."
fi

echo "[*] Configuring I2C for OLED..."
if ! grep -q "dtparam=i2c_arm=on" /boot/config.txt; then
    echo "dtparam=i2c_arm=on" >> /boot/config.txt
fi

echo "[*] Setting up service..."
# Copy files to /boot/voice-wallet for persistence if making Read-Only SD
TRACK_DIR="/boot/voice-wallet"
mkdir -p $TRACK_DIR
cp wallet.py $TRACK_DIR/
cp boot.sh $TRACK_DIR/
cp bip39.txt $TRACK_DIR/ 2>/dev/null
cp whisper_tiny* $TRACK_DIR/ 2>/dev/null

chmod +x $TRACK_DIR/boot.sh
chmod +x $TRACK_DIR/wallet.py

# Add to rc.local for simple boot
if ! grep -q "boot.sh" /etc/rc.local; then
    sed -i -e '$i \/boot\/voice-wallet\/boot.sh &\n' /etc/rc.local
    echo "[*] Added to /etc/rc.local"
fi

echo "[*] Installation Complete. Please Reboot."
