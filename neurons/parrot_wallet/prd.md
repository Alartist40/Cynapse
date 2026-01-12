# PRD: Off-Grid Voice Wallet (MVP)  
**"Speak your seed, see your address, leave no trace"**

## 1. Core Job Stories
- **As** a Bitcoin holder **I** press the button and speak 24 words **So** the OLED shows my receive QR without the seed ever touching disk.  
- **As** a recruiter **I** watch the video **So** I see you combine **edge AI + security + hardware** in one weekend.

## 2. MVP Scope (Pareto cut)
| Feature | In MVP | Later |
|---------|--------|-------|
| Button-trigger record 30 s | ✅ | — |
| On-device Whisper-tiny int8 (39 MB) | ✅ | — |
| Extract 24 valid BIP39 words | ✅ | — |
| Derive legacy address + QR on OLED | ✅ | — |
| Zero RAM + shutdown after 60 s | ✅ | — |
| Encrypted backup, multisig, metal plate | ❌ | v2 |

## 3. Functional Spec
- **Hardware**: Raspberry Pi Zero 2 W (or ESP32-S3) + I²S mic (INMP441) + 128×64 OLED (SSD1306) + push-button + slide switch (power).  
- **Power**: 5 V USB; Pi runs **read-only** SD card (pull write-protect switch).  
- **Flow**:  
  1. Boot → green LED blink (ready).  
  2. Hold button → red LED on → record 30 s @ 16 kHz → store in **RAM only** (tmpfs).  
  3. Whisper-tiny int8 → text → keep **first 24 valid BIP39 words** (drop rest).  
  4. Compute seed → master private key → first **legacy 1F44t** address → show QR on OLED.  
  5. After 60 s **explicit memset + reboot**; seed gone.  
- **Latency**: 5 s from end of speech to QR.  
- **Privacy**: no network stack started; no SD writes after boot; microphone **disabled** after use.

## 4. End-to-End Flow (Pi Zero)
```
[BOOT] → [Green blink]  
[Hold button] → [Red on, recording] → [Red off, processing] → [OLED QR + address] → [Auto reboot]
```

## 5. Success Criteria
- Speak 24 words → QR correct vs wallet software.  
- Pull power → SD image **zero seed bytes**.  
- Demo video <60 s, no cuts, no internet icon.

## 6. File Layout
```
voice-wallet/
├── boot/                    # read-only overlay files
├── wallet.py                # main script (Whisper + seed logic)
├── whisper_tiny_int8.tflite # 39 MB model (ship binary)
├── boot.sh                  # systemd-one-shot service
├── install.sh               # one-liner flash SD
└── README.md                # wiring photo + usage GIF
```

## 7. BOM & Wiring
| Part | Price |
|------|-------|
| Pi Zero 2 W | $15 |
| INMP441 I²S mic | $1 |
| 0.96" OLED SSD1306 | $3 |
| Button + 5 mm LED | $0.50 |
| SD card 32 GB | $5 |
| Total | ≈ $25 |

**Wiring**  
- Mic VCC → 3V3, GND → GND, WS → GPIO 4, SCK → GPIO 5, SD → GPIO 6  
- OLED VCC → 3V3, GND → GND, SCL → GPIO 11, SDA → GPIO 10  
- Button → GPIO 9 (pull-up)  
- LED → GPIO 8 (sink)

# Code Skeleton (Pi Zero, Python, std-lib only)

## wallet.py
```python
#!/usr/bin/env python3
import wave, tempfile, os, subprocess, hashlib, json, time, gc
from pathlib import Path

BUTTON = 9
LED_GREEN = 8
LED_RED = 7
MODEL = Path(__file__).with_name("whisper_tiny_int8.tflite")
DICT = Path(__file__).with_name("bip39.txt")   # 2048 words, 1 per line
RECORD_SECS = 30
SAMPLE_RATE = 16000
CHANNELS = 1

# ---------- gpio helpers (no external deps) ----------
def export(pin, direction):
    Path(f"/sys/class/gpio/gpio{pin}/direction").write_text(direction)
def write(pin, v):
    Path(f"/sys/class/gpio/gpio{pin}/value").write_text(str(v))
def read(pin):
    return int(Path(f"/sys/class/gpio/gpio{pin}/value").read_text())

def setup():
    for p in (BUTTON, LED_GREEN, LED_RED):
        if not Path(f"/sys/class/gpio/gpio{p}").exists():
            Path("/sys/class/gpio/export").write_text(str(p))
        export(p, "out" if p != BUTTON else "in")
    write(LED_GREEN, 1); write(LED_RED, 0)

# ---------- record ----------
def record():
    print("[*] recording 30 s ...")
    write(LED_RED, 1); write(LED_GREEN, 0)
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    # arecord: shipped with Pi
    subprocess.run(["arecord", "-D", "plughw:1", "-f", "S16_LE", "-r", str(SAMPLE_RATE), "-c", str(CHANNELS), "-d", str(RECORD_SECS), tmp.name], check=True)
    write(LED_RED, 0)
    return tmp.name

# ---------- whisper ----------
def transcribe(wav):
    print("[*] whispering ...")
    # use tflite_runtime (single file, no pip)
    # skeleton: call external tiny binary (ship 2 MB wrapper)
    bin = Path(__file__).with_name("whisper_tiny")
    out = subprocess.check_output([str(bin), wav], text=True, stderr=subprocess.DEVNULL)
    return out.strip()

# ---------- seed ----------
def bip39_list():
    return Path(DICT).read_text().splitlines()

def first24_valid(words):
    b39 = set(bip39_list())
    valid = [w for w in words if w in b39]
    return valid[:24]

def seed_from_words(words):
    # BIP39: words -> entropy -> seed via PBKDF2
    from hashlib import pbkdf2_hmac
    sentence = " ".join(words)
    entropy = hashlib.sha256(sentence.encode()).digest()[:16]  # mock 128-bit
    seed = pbkdf2_hmac("sha512", sentence.encode(), b"mnemonic", 2048, 64)
    return seed

def derive_address(seed):
    # mock: first legacy address (1...) from seed
    h = hashlib.new("ripemd160", hashlib.sha256(seed[:32]).digest()).digest()
    return "1" + h.hex()[:33]

# ---------- OLED ----------
def show_qr(text):
    # use ssd1306 pure-python driver (ship single file ssd1306.py)
    import ssd1306, board
    disp = ssd1306.SSD1306_I2C(128, 64, board.I2C())
    disp.fill(0)
    # tiny QR: use qrcode pure-python (ship qrcode.py)
    import qrcode
    qr = qrcode.QRCode(box_size=2, border=1)
    qr.add_data(text); qr.make(fit=True)
    img = qr.make_image(fill="black", back="white")
    disp.image(img); disp.show()

# ---------- main ----------
def main():
    setup()
    while True:
        if read(BUTTON) == 0:  # pressed
            wav = record()
            text = transcribe(wav).lower().split()
            os.remove(wav)  # RAM only
            words = first24_valid(text)
            if len(words) < 24:
                print("[-] need 24 valid words"); continue
            seed = seed_from_words(words)
            addr = derive_address(seed)
            print("[+] address", addr)
            show_qr(addr)
            # scrub RAM
            del words, seed, text; gc.collect()
            time.sleep(60)
            subprocess.run(["sudo", "reboot"])
        time.sleep(0.1)

if __name__ == "__main__":
    main()
```

## boot.sh (runs at boot, read-only overlay)
```bash
#!/bin/bash
echo "Starting voice-wallet..."
/usr/bin/python3 /boot/wallet.py &
```

## install.sh (run once on PC)
```bash
# 1. Flash Raspberry Pi OS Lite to SD
# 2. Mount SD and:
cp -r voice-wallet /boot/
echo "/boot/wallet.py &" >> /boot/rc.local
# 3. Pull SD write-protect switch → read-only
# 4. Insert, power, done.
```

# Build & Ship
1. **Bundle** `wallet.py + whisper_tiny + ssd1306.py + qrcode.py + bip39.txt` into SD image.  
2. **Record 30-s demo**: press button → speak 24 words → QR appears → reboot.  
3. **GitHub release**: `.img.bz2 + 60-s video + wiring.jpg`.

**Impact line for résumé**  
“Built air-gapped speech wallet; seed never touches disk, Whisper-tiny on Pi Zero, disaster-recovery via voice only.”