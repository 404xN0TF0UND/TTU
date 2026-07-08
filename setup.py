#!/usr/bin/env python3
"""
Setup script for TTU Notes
Automates the installation process on new devices
"""

import os
import sys
import subprocess
import platform
from pathlib import Path

def check_python_version():
    """Check if Python version is compatible"""
    if sys.version_info < (3, 8):
        print("❌ Python 3.8 or higher is required")
        print(f"Current version: {sys.version}")
        return False
    print(f"✅ Python {sys.version.split()[0]} detected")
    return True

def install_dependencies():
    """Install required Python packages"""
    print("📦 Installing dependencies...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✅ Dependencies installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install dependencies: {e}")
        return False

def create_directories():
    """Create necessary directories"""
    print("📁 Creating directories...")
    directories = ["saved_notes", "scripts", "templates/generated_forms"]
    
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
        print(f"✅ Created: {directory}")

def create_startup_script():
    """Create a startup script for easy launching"""
    if platform.system() == "Windows":
        script_content = """@echo off
echo Starting TTU Notes...
cd /d "%~dp0"
python app.py
pause
"""
        script_name = "start_TTU_Notes.bat"
    else:
        script_content = """#!/bin/bash
echo "Starting TTU Notes..."
cd "$(dirname "$0")"
python3 app.py
"""
        script_name = "start_TTU_Notes.sh"
        # Make executable on Unix systems
        os.chmod(script_name, 0o755)
    
    with open(script_name, "w") as f:
        f.write(script_content)
    
    print(f"✅ Created startup script: {script_name}")

def create_desktop_shortcut():
    """Create desktop shortcut (Windows only)"""
    if platform.system() == "Windows":
        try:
            shortcut_content = f"""@echo off
cd /d "{os.getcwd()}"
python app.py
"""
            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
            shortcut_path = os.path.join(desktop, "TTU Notes.bat")
            
            with open(shortcut_path, "w") as f:
                f.write(shortcut_content)
            
            print("✅ Created desktop shortcut")
        except Exception as e:
            print(f"⚠️ Could not create desktop shortcut: {e}")

def main():
    print("🚀 TTU Notes Setup")
    print("=" * 30)
    
    # Check Python version
    if not check_python_version():
        sys.exit(1)
    
    # Install dependencies
    if not install_dependencies():
        sys.exit(1)
    
    # Create directories
    create_directories()
    
    # Create startup script
    create_startup_script()
    
    # Create desktop shortcut (Windows)
    create_desktop_shortcut()
    
    print("\n🎉 Setup completed successfully!")
    print("\n📋 Next steps:")
    print("1. Run the startup script to launch TTU Notes")
    print("2. Open your web browser to http://127.0.0.1:5000")
    print("3. Start adding your network devices!")
    
    if platform.system() == "Windows":
        print("\n🚀 Quick start:")
        print("   Double-click 'start_TTU_Notes.bat' or the desktop shortcut")
    else:
        print("\n🚀 Quick start:")
        print("   Run: ./start_TTU_Notes.sh")

if __name__ == "__main__":
    main()