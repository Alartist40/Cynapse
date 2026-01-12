#!/usr/bin/env python3
"""
Voice input handling module
Records audio and transcribes using Whisper
"""

import os
import sys
import tempfile
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class VoiceHandler:
    """Handles voice recording and transcription"""
    
    def __init__(self, config: dict):
        """
        Initialize voice handler
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.duration = config.get("voice", {}).get("duration", 5)
        self.sample_rate = config.get("voice", {}).get("sample_rate", 16000)
        self.model_name = config.get("voice", {}).get("whisper_model", "tiny")
        
        # Try to import required libraries
        self._check_dependencies()
        
    def _check_dependencies(self):
        """Check if required dependencies are installed"""
        try:
            import sounddevice
            import soundfile
            self.sounddevice = sounddevice
            self.soundfile = soundfile
        except ImportError:
            logger.warning(
                "sounddevice or soundfile not installed. "
                "Voice input will not work without them. "
                "Install with: pip install sounddevice soundfile"
            )
            self.sounddevice = None
            self.soundfile = None
        
        try:
            import whisper
            self.whisper = whisper
            self.model = None  # Lazy load
        except ImportError:
            logger.warning(
                "whisper not installed. Voice input will not work. "
                "Install with: pip install openai-whisper"
            )
            self.whisper = None
    
    def _load_whisper_model(self):
        """Lazy load Whisper model"""
        if self.model is None and self.whisper is not None:
            logger.info(f"[*] Loading Whisper model '{self.model_name}'...")
            self.model = self.whisper.load_model(self.model_name)
            logger.info("[+] Whisper model loaded")
    
    def record_audio(self, output_path: Optional[str] = None) -> str:
        """
        Record audio from microphone
        
        Args:
            output_path: Path to save audio file (temp file if None)
            
        Returns:
            Path to recorded audio file
        """
        if self.sounddevice is None or self.soundfile is None:
            raise RuntimeError(
                "Audio recording dependencies not installed. "
                "Install with: pip install sounddevice soundfile"
            )
        
        if output_path is None:
            fd, output_path = tempfile.mkstemp(suffix=".wav")
            os.close(fd)
        
        print(f"[*] Recording for {self.duration} seconds...")
        print("[*] Speak now!")
        
        try:
            # Record audio
            recording = self.sounddevice.rec(
                int(self.duration * self.sample_rate),
                samplerate=self.sample_rate,
                channels=1,
                dtype='int16'
            )
            self.sounddevice.wait()
            
            # Save to file
            self.soundfile.write(output_path, recording, self.sample_rate)
            print("[+] Recording complete")
            
            return output_path
            
        except Exception as e:
            logger.error(f"Recording failed: {e}")
            raise
    
    def transcribe_audio(self, audio_path: str) -> str:
        """
        Transcribe audio file using Whisper
        
        Args:
            audio_path: Path to audio file
            
        Returns:
            Transcribed text
        """
        if self.whisper is None:
            raise RuntimeError(
                "Whisper not installed. "
                "Install with: pip install openai-whisper"
            )
        
        self._load_whisper_model()
        
        logger.info(f"[*] Transcribing audio from {audio_path}...")
        
        try:
            result = self.model.transcribe(audio_path)
            text = result["text"].strip()
            logger.info(f"[+] Transcription: {text}")
            return text
            
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            raise
    
    def record_and_transcribe(self) -> str:
        """
        Record audio and transcribe in one step
        
        Returns:
            Transcribed text
        """
        temp_audio = None
        try:
            # Record
            temp_audio = self.record_audio()
            
            # Transcribe
            text = self.transcribe_audio(temp_audio)
            
            return text
            
        finally:
            # Clean up temp file
            if temp_audio and os.path.exists(temp_audio):
                try:
                    os.remove(temp_audio)
                except:
                    pass


# Fallback implementation without dependencies
class VoiceHandlerFallback:
    """Fallback handler when dependencies are not available"""
    
    def __init__(self, config: dict):
        pass
    
    def record_and_transcribe(self) -> str:
        raise RuntimeError(
            "Voice input not available. Please install required dependencies:\n"
            "  pip install sounddevice soundfile openai-whisper\n"
            "Or use text input instead."
        )
