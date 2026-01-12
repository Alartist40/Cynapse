#!/usr/bin/env python3
import sys

# Mock Elara TTS
# In the future this would hook into a real TTS API or library
# For now it just speaks to the console!

def main():
    message = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Alert"
    print(f"\n[VOICE ALERT] (Mock TTS): \"{message}\"\n")
    
    # Optional: could use terminal bell
    print("\a") 

if __name__ == "__main__":
    main()
