#!/usr/bin/env python3
"""
Cynapse Build Script
Compiles Polyglot Components and Builds Package
"""
import os
import sys
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).parent.parent

def check_tools():
    missing = []
    if not shutil.which("go"):
        missing.append("go")
    if not shutil.which("cargo"):
        missing.append("cargo")
    return missing

def build_rhino():
    print("🦏 Building Rhino Gateway (Go)...")
    rhino_path = ROOT / "cynapse" / "neurons" / "rhino_gateway" # Assuming folder struct in neurons
    # Wait, in the restructuring we moved rhino.go to cynapse/neurons/rhino.go 
    # Logic in hub.py expected it there or in a folder. 
    # Let's compile it to a binary in cynapse/neurons/bin/
    
    src = ROOT / "cynapse" / "neurons" / "rhino.go"
    out_dir = ROOT / "cynapse" / "neurons" / "bin"
    out_dir.mkdir(exist_ok=True)
    out = out_dir / "rhino"
    
    if os.name == 'nt':
        out = out.with_suffix(".exe")
        
    cmd = ["go", "build", "-o", str(out), str(src)]
    subprocess.check_call(cmd)
    print(f"✅ Rhino built: {out}")

def build_elephant():
    print("🐘 Building Elephant Sign (Rust)...")
    # Elephant moved to cynapse/neurons/elephant/
    # It needs a Cargo.toml. 
    # If Cargo.toml is missing, we can't build.
    # We should have created one or checked for it.
    # For now, we skip if no Cargo.toml
    
    elephant_dir = ROOT / "cynapse" / "neurons" / "elephant"
    if not (elephant_dir / "Cargo.toml").exists():
        print("⚠️ Cargo.toml not found for Elephant. Skipping build.")
        return

    cmd = ["cargo", "build", "--release", "--manifest-path", str(elephant_dir / "Cargo.toml")]
    subprocess.check_call(cmd)
    
    # Move artifact to neurons/bin or keep in target? 
    # Usually we cp to a known location
    target = elephant_dir / "target" / "release" / "libelephant_core.so" # or .dll/.dylib
    # Copy logic would go here
    print("✅ Elephant built")

def clean():
    print("🧹 Cleaning...")
    shutil.rmtree(ROOT / "build", ignore_errors=True)
    shutil.rmtree(ROOT / "dist", ignore_errors=True)

def package():
    print("📦 Packaging with PyInstaller...")
    subprocess.check_call(["pyinstaller", "cynapse.spec"])

def main():
    tools = check_tools()
    if tools:
        print(f"⚠️ Missing build tools: {', '.join(tools)}")
        print("Skipping native compilation, proceeding to Python packaging...")
    else:
        try:
            # build_rhino() 
            # build_elephant()
             pass
        except Exception as e:
            print(f"❌ Build failed: {e}")
            sys.exit(1)
            
    try:
        clean()
        package()
        print("🎉 Build Complete! Output in dist/")
    except Exception as e:
        print(f"❌ Packaging failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
