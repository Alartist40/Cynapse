#!/usr/bin/env python3
import urllib.request
import os

FILES = {
    "bip39.txt": "https://raw.githubusercontent.com/bitcoin/bips/master/bip-0039/english.txt",
    "ssd1306.py": "https://raw.githubusercontent.com/adafruit/Adafruit_CircuitPython_SSD1306/main/adafruit_ssd1306.py",
    # We might need a simpler qrcode lib or assume install. 
    # For MVP we will try to grab a single file version or rely on pip in install.sh
    # But for a strictly offline "ship binaries" approach, downloading a pure python qrcode lib is best.
    # The 'qrcode' package on PyPI is multi-file.
    # Using a micro-qrcode port or similar would be better for single file, 
    # but strictly sticking to standard 'qrcode' package via pip is safer for reliability unless we find a good single file ref.
}

def download(url, filename):
    print(f"Downloading {filename}...")
    try:
        urllib.request.urlretrieve(url, filename)
        print(f"-> Saved {filename}")
    except Exception as e:
        print(f"-> Error downloading {filename}: {e}")

def main():
    print("Fetching assets for Off-Grid Voice Wallet...")
    
    for filename, url in FILES.items():
        if not os.path.exists(filename):
            download(url, filename)
        else:
            print(f"Skipping {filename} (already exists)")
            
    print("\n[NOTE] 'whisper_tiny' binary and 'whisper_tiny_int8.tflite' model must be manually placed here.")
    print("       See: https://github.com/usefultransformers/openai-whisper-tiny-tflite for model")
    # In a real scenario, we would download the model here too if we had a direct link to a raw tflite file.

if __name__ == "__main__":
    main()
