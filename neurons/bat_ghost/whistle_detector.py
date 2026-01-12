#!/usr/bin/env python3
"""
Whistle Detector for Ghost Shell
Detects 18 kHz ultrasonic whistle to wake up the Ghost Shell system.

Uses PyAudio for audio capture and NumPy for FFT analysis.
"""

import sys
import argparse
import time

try:
    import pyaudio
    import numpy as np
    AUDIO_AVAILABLE = True
except ImportError:
    AUDIO_AVAILABLE = False
    print("Warning: PyAudio or NumPy not installed. Install with: pip install pyaudio numpy")


# Configuration
CHUNK = 1024
RATE = 48000
TARGET_FREQ = 18000  # 18 kHz
TOLERANCE = 500  # Hz tolerance around target
THRESHOLD = 1e6  # Energy threshold for detection
DETECTION_WINDOW = 3  # Number of consecutive detections required


def detect_whistle(continuous: bool = True, timeout: float = None) -> bool:
    """
    Listen for 18 kHz ultrasonic whistle.
    
    Args:
        continuous: If True, keep listening until whistle detected. 
                   If False, check once and return.
        timeout: Maximum seconds to listen (None = indefinite)
    
    Returns:
        bool: True if whistle detected, False otherwise
    """
    if not AUDIO_AVAILABLE:
        print("Error: Audio libraries not available")
        return False
    
    try:
        p = pyaudio.PyAudio()
        
        # Find input device
        device_index = None
        for i in range(p.get_device_count()):
            info = p.get_device_info_by_index(i)
            if info['maxInputChannels'] > 0:
                device_index = i
                break
        
        if device_index is None:
            print("Error: No audio input device found")
            p.terminate()
            return False
        
        stream = p.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=RATE,
            input=True,
            input_device_index=device_index,
            frames_per_buffer=CHUNK
        )
        
        start_time = time.time()
        consecutive_detections = 0
        
        print(f"Listening for {TARGET_FREQ} Hz whistle...")
        
        while True:
            # Check timeout
            if timeout and (time.time() - start_time) > timeout:
                print("Timeout reached")
                break
            
            # Read audio data
            try:
                data = stream.read(CHUNK, exception_on_overflow=False)
            except Exception as e:
                print(f"Audio read error: {e}")
                continue
            
            # Convert to numpy array
            samples = np.frombuffer(data, dtype=np.int16).astype(np.float32)
            
            # Apply Hanning window for better frequency resolution
            window = np.hanning(len(samples))
            samples = samples * window
            
            # Compute FFT
            fft = np.fft.fft(samples)
            freqs = np.fft.fftfreq(len(fft), 1.0 / RATE)
            
            # Get magnitude spectrum (positive frequencies only)
            magnitude = np.abs(fft[:len(fft)//2])
            pos_freqs = freqs[:len(freqs)//2]
            
            # Find energy in target frequency band
            freq_mask = (pos_freqs >= TARGET_FREQ - TOLERANCE) & (pos_freqs <= TARGET_FREQ + TOLERANCE)
            target_energy = np.sum(magnitude[freq_mask])
            
            # Compare to total energy to reduce false positives
            total_energy = np.sum(magnitude)
            if total_energy > 0:
                energy_ratio = target_energy / total_energy
            else:
                energy_ratio = 0
            
            # Check if whistle detected
            if target_energy > THRESHOLD and energy_ratio > 0.1:
                consecutive_detections += 1
                if consecutive_detections >= DETECTION_WINDOW:
                    print("WHISTLE_DETECTED")
                    stream.stop_stream()
                    stream.close()
                    p.terminate()
                    return True
            else:
                consecutive_detections = 0
            
            if not continuous:
                break
        
        stream.stop_stream()
        stream.close()
        p.terminate()
        return False
        
    except Exception as e:
        print(f"Error: {e}")
        return False


def generate_test_tone(frequency: int = 18000, duration: float = 1.0):
    """
    Generate a test tone file for testing the detector.
    Requires scipy for wave file generation.
    """
    try:
        from scipy.io import wavfile
        
        sample_rate = 48000
        t = np.linspace(0, duration, int(sample_rate * duration), False)
        tone = np.sin(2 * np.pi * frequency * t)
        
        # Normalize and convert to 16-bit
        audio = (tone * 32767).astype(np.int16)
        
        wavfile.write(f'test_tone_{frequency}hz.wav', sample_rate, audio)
        print(f"Generated test_tone_{frequency}hz.wav")
        
    except ImportError:
        print("scipy required for tone generation: pip install scipy")


def main():
    parser = argparse.ArgumentParser(description='Ghost Shell Whistle Detector')
    parser.add_argument('--detect-once', action='store_true',
                       help='Check once and exit')
    parser.add_argument('--timeout', type=float, default=None,
                       help='Maximum seconds to listen')
    parser.add_argument('--generate-test', action='store_true',
                       help='Generate test tone file')
    parser.add_argument('--frequency', type=int, default=18000,
                       help='Target frequency in Hz (default: 18000)')
    parser.add_argument('--threshold', type=float, default=1e6,
                       help='Energy threshold for detection')
    
    args = parser.parse_args()
    
    global TARGET_FREQ, THRESHOLD
    TARGET_FREQ = args.frequency
    THRESHOLD = args.threshold
    
    if args.generate_test:
        generate_test_tone(args.frequency)
        return
    
    if args.detect_once:
        detected = detect_whistle(continuous=False, timeout=args.timeout or 1.0)
    else:
        detected = detect_whistle(continuous=True, timeout=args.timeout)
    
    sys.exit(0 if detected else 1)


if __name__ == "__main__":
    main()
