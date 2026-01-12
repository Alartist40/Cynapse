# AI Canarytoken (MVP)

A lightweight "Canarytoken" that drops a folder of fake treasures (AWS keys, model weights, cookies) on your machine. The instant someone opens, copies, or edits one of them, you get an immediate voice alert and a JSON log entry.

**Vision**: Detect lateral movement and unauthorized file access in < 1 second using deception.

## Features

- **Fake Baits**: Generates realistic-looking `aws_credentials.json`, `model_weights.onnx` (fake header + garbage), and `Cookies.json`.
- **Real-time Watcher**: Monitors the bait directory using OS-native APIs (`ReadDirectoryChangesW` on Windows, `inotify` on Linux/Mac).
- **Voice Alert**: Uses a local TTS script (`elara_tts.py`) to annouce intrusions out loud.
- **JSON Logging**: Detailed logs of every event (monitor start, file access) in `canary.log`.

## Setup Instructions

### Prerequisites
- Python 3.x installed and added to PATH.

### Installation

1. Clone this repository (or download the files).
   ```bash
   git clone https://github.com/Alartist40/AI-Canarytoken.git
   cd AI-Canarytoken
   ```

2. **Generate Baits**
   Run the generator script to create the `Canary` folder and populate it with fake sensitive files.
   ```bash
   python bait_gen.py
   ```
   *Output: `[+] Baits created in .../Canary`*

3. **Start the Watcher**
   Run the main canary script. Keep this terminal open (or run in background).
   ```bash
   python canary.py
   ```
   *Output: `[*] Canary watching .../Canary`*

## Usage

Once `canary.py` is running:

1. **Trigger an Alert**: Open standard file explorer and navigate into the `Canary` folder, or try to open `aws_credentials.json` with a text editor.
2. **Observe Response**:
   - You will hear a voice alert: *"Canary tripped on READ/WRITE/ACCESS"*.
   - A new line is appended to `canary.log`.
   - The terminal running `canary.py` will display the alert details:
     ```json
     [ALERT] {'time': '...', 'user': '...', 'bait_file': 'Canary/', 'event': 'READ/WRITE/ACCESS'}
     ```

3. **Stop**: Press `Ctrl+C` in the terminal to stop the watcher.

## Technical Details

- **`bait_gen.py`**: Creates the `Canary` directory and writes fake data. It uses standard `json` and `os` libraries. The ONNX file has a valid header but random data to simulate a large model file without taking up actual space.
- **`canary.py`**: The core monitoring engine.
    - **Windows**: Uses `ctypes` to call `ReadDirectoryChangesW` from `kernel32.dll`. This allows monitoring directory events without external dependencies like `pywin32`.
    - **Linux/macOS**: Uses `ctypes` to interface with `inotify` syscalls directly.
    - **Alerting**: On any detected event, it writes a JSON record to `canary.log` and executes `elara_tts.py` via a subprocess call.
- **`elara_tts.py`**: A mock TTS handler for this MVP. It receives the alert message and prints it to stdout (simulating a voice response). In a full version, this would integrate with a real local TTS engine like Kokoro.

## Disclaimer
This tool is for educational and defensive testing purposes only. Do not use it on systems you do not own or have permission to monitor.
