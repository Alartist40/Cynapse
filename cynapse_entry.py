#!/usr/bin/env python3
"""
Cynapse - Ghost Shell Hub
Entry Point
"""
import sys
import argparse
from cynapse.core.hub import CynapseHub

def main():
    parser = argparse.ArgumentParser(description="Cynapse Security Hub")
    parser.add_argument("--tui", action="store_true", help="Launch Synaptic Fortress TUI")
    parser.add_argument("--cli", action="store_true", help="Run in CLI mode")
    parser.add_argument("--test", action="store_true", help="Run self-tests")
    
    args = parser.parse_args()
    
    hub = CynapseHub()
    
    if args.tui:
        print("Initializing Synaptic Fortress...")
        from cynapse.tui.main import SynapticFortress
        app = SynapticFortress()
        app.run()
    elif args.test:
        print("Running system diagnostics...")
        # hub.run_diagnostics()
    else:
        # Default to CLI or Help
        parser.print_help()

if __name__ == "__main__":
    main()
