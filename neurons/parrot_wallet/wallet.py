#!/usr/bin/env python3
import wave, tempfile, os, subprocess, hashlib, json, time, gc, sys
from pathlib import Path

# --- Configuration ---
BUTTON = 9
LED_GREEN = 8
LED_RED = 7
RECORD_SECS = 30
SAMPLE_RATE = 16000
CHANNELS = 1

# Paths
BASE_DIR = Path(__file__).parent.absolute()
MODEL_BIN = BASE_DIR / "whisper_tiny_int8.tflite" # Not used directly by this script if using external wrapper, but good reference
WHISPER_WRAPPER = BASE_DIR / "whisper_tiny" # The specialized binary wrapper
DICT_FILE = BASE_DIR / "bip39.txt"

# ---------- gpio helpers (no external deps) ----------
def export(pin, direction):
    try:
        if not Path(f"/sys/class/gpio/gpio{pin}").exists():
            Path("/sys/class/gpio/export").write_text(str(pin))
        Path(f"/sys/class/gpio/gpio{pin}/direction").write_text(direction)
    except Exception as e:
        print(f"[!] GPIO setup failed for {pin}: {e}")

def write(pin, v):
    try:
        Path(f"/sys/class/gpio/gpio{pin}/value").write_text(str(v))
    except Exception:
        pass # Ignore errors during shutdown/cleanup

def read(pin):
    try:
        return int(Path(f"/sys/class/gpio/gpio{pin}/value").read_text())
    except Exception:
        return 1 # Assume high if fail (pull-up)

def setup():
    print("[*] Setting up GPIO...")
    for p in (BUTTON, LED_GREEN, LED_RED):
        export(p, "out" if p != BUTTON else "in")
    write(LED_GREEN, 1) # Green ON = Ready
    write(LED_RED, 0)

# ---------- record ----------
def record():
    print(f"[*] Recording for {RECORD_SECS} s ...")
    write(LED_RED, 1)
    write(LED_GREEN, 0)
    
    # Use tempfile in /tmp (usually RAM on Pi if configured as tmpfs, or SD)
    # PRD recommends tmpfs for security.
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.close() # Close so arecord can write to it
    
    try:
        # arecord -D plughw:1 ... (Assuming mic is on card 1, need to verify)
        # Using specific params from PRD
        cmd = [
            "arecord", 
            "-D", "plughw:1", 
            "-f", "S16_LE", 
            "-r", str(SAMPLE_RATE), 
            "-c", str(CHANNELS), 
            "-d", str(RECORD_SECS), 
            tmp.name
        ]
        subprocess.run(cmd, check=True)
    except Exception as e:
        print(f"[!] Recording failed: {e}")
        write(LED_RED, 0)
        write(LED_GREEN, 1) # Back to ready
        return None

    write(LED_RED, 0)
    return tmp.name

# ---------- whisper ----------
def transcribe(wav_path):
    print("[*] Whispering...")
    if not WHISPER_WRAPPER.exists():
        print(f"[!] Whisper wrapper not found at {WHISPER_WRAPPER}")
        return ""
        
    try:
        # Call the external tiny binary wrapper
        # Assuming the wrapper takes wav file as arg and outputs text to stdout
        output = subprocess.check_output([str(WHISPER_WRAPPER), wav_path], text=True, stderr=subprocess.DEVNULL)
        return output.strip()
    except Exception as e:
        print(f"[!] Transcription failed: {e}")
        return ""

# ---------- seed ----------
def bip39_list():
    if not DICT_FILE.exists():
        print(f"[!] BIP39 dictionary not found at {DICT_FILE}")
        return []
    return DICT_FILE.read_text().splitlines()

def first24_valid(words):
    b39_words = bip39_list()
    if not b39_words:
        return []
    b39_set = set(b39_words)
    
    valid = [w for w in words if w in b39_set]
    return valid[:24]

def seed_from_words(words):
    # BIP39: words -> entropy -> seed via PBKDF2
    from hashlib import pbkdf2_hmac
    sentence = " ".join(words)
    # Mocking entropy check for MVP, strictly following "words -> seed"
    # standard PBKDF2 for BIP39
    salt = b"mnemonic" # + passphrase if any (none here)
    seed = pbkdf2_hmac("sha512", sentence.encode("utf-8"), salt, 2048, 64)
    return seed

def derive_address(seed):
    # BIP32/BIP44 is complex to implement with stdlib only.
    # PRD "Functional Spec" Item 4 says: "Derive legacy address"
    # PRD Code Skeleton Item 136 says: "mock: first legacy address (1...) from seed"
    # We will implement the mock as requested in the PRD skeleton to avoid 
    # huge dependencies like bip32utils for this MVP.
    
    # Simple deterministic derivation for demo purposes:
    # Sha256(seed) -> Ripemd160 -> Address Checksum calculation
    
    # 1. SHA256 of seed (taking first 32 bytes to simulate private key)
    priv_key = seed[:32] 
    
    # 2. Public Key generation (Mocking - usually EC multiplication)
    # We'll just hash the private key content to get "public key data" for the mock
    pub_key_mock = hashlib.sha256(priv_key).digest()
    
    # 3. SHA256 of PubKey
    s1 = hashlib.sha256(pub_key_mock).digest()
    
    # 4. RIPEMD160 of SHA256 (This is the HASH160)
    # Python's hashlib might not have ripemd160 depending on OpenSSL config
    try:
        h = hashlib.new("ripemd160", s1).digest()
    except ValueError:
        # Fallback if ripemd160 not available
        h = hashlib.new("sha1", s1).digest() 
        
    # 5. Add network byte (0x00 for Mainnet)
    vh160 = b"\x00" + h
    
    # 6. Checksum (Double SHA256)
    checksum = hashlib.sha256(hashlib.sha256(vh160).digest()).digest()[:4]
    
    # 7. Concatenate
    addr_bin = vh160 + checksum
    
    # 8. Base58 Encode (Manual implementation to avoid imports)
    alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    num = int.from_bytes(addr_bin, "big")
    b58 = ""
    while num > 0:
        num, mod = divmod(num, 58)
        b58 = alphabet[mod] + b58
    
    # Add leading '1's for leading null bytes
    for b in addr_bin:
        if b == 0:
            b58 = "1" + b58
        else:
            break
            
    return b58

# ---------- OLED ----------
def show_qr(text):
    print(f"[=] Showing QR for: {text}")
    try:
        # Attempt to import shipped libraries
        sys.path.append(str(BASE_DIR))
        import ssd1306
        import board # This usually requires adafruit-blinka
        import busio
        from PIL import Image, ImageDraw
        import qrcode
    except ImportError as e:
        print(f"[!] OLED/QR libraries missing: {e}")
        return

    try:
        i2c = busio.I2C(board.SCL, board.SDA)
        disp = ssd1306.SSD1306_I2C(128, 64, i2c)
        disp.fill(0)
        disp.show()

        qr = qrcode.QRCode(box_size=2, border=2)
        qr.add_data(text)
        qr.make(fit=True)
        img = qr.make_image(fill_color="white", back_color="black").convert("1")
        
        # Center the QR code
        # OLED is 128x64. QR might be ~50x50.
        pos_x = (128 - img.width) // 2
        pos_y = (64 - img.height) // 2
        
        # Create canvas
        image = Image.new("1", (128, 64))
        image.paste(img, (pos_x, pos_y))
        
        disp.image(image)
        disp.show()
    except Exception as e:
        print(f"[!] Failed to show QR: {e}")

# ---------- main ----------
def main():
    setup()
    print("[*] Voice Wallet Ready. Press button to start.")
    
    # Ensure cleanup on exit
    try:
        while True:
            # Button is pull-up (1=unpressed, 0=pressed)
            if read(BUTTON) == 0: 
                print("[!] Button Pressed!")
                
                # 1. Record
                wav = record()
                if not wav:
                    continue
                
                # 2. Transcribe
                text_raw = transcribe(wav).lower()
                # Security: Removed raw transcript print to prevent seed leakage in logs/console
                text_split = text_raw.split()
                
                # Clean up audio file immediately
                if os.path.exists(wav):
                    os.remove(wav)
                
                # 3. Extract BIP39
                words = first24_valid(text_split)
                print(f"[D] Valid words found: {len(words)}")
                
                if len(words) < 24:
                    # Security: Do not print the words themselves, only the count
                    print(f"[-] Need 24 valid words. Found: {len(words)}")
                    # Blink output red to indicate failure
                    for _ in range(3):
                        write(LED_RED, 1); time.sleep(0.2); write(LED_RED, 0); time.sleep(0.2)
                    write(LED_GREEN, 1)
                    continue
                
                # 4. Derive
                seed = seed_from_words(words)
                addr = derive_address(seed)
                print(f"[+] Address: {addr}")
                
                # 5. Show QR
                show_qr(addr)
                
                # 6. Scrub & Reboot
                print("[!] Wiping RAM and Rebooting in 60s...")
                # Overwrite sensitive variables
                words = ["x"] * 24
                seed = b"\x00" * 64
                text_raw = "x" * 100
                del words, seed, text_raw
                gc.collect()
                
                time.sleep(60)
                subprocess.run(["sudo", "reboot"])
                
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\n[!] Exiting...")
        write(LED_GREEN, 0)
        write(LED_RED, 0)

if __name__ == "__main__":
    main()
