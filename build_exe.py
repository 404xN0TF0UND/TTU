#!/usr/bin/env python3
"""
Build script to create a standalone executable for TTU Notes
This creates a single .exe file that includes Python and all dependencies
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def install_pyinstaller():
    """Install PyInstaller if not already installed"""
    try:
        import PyInstaller
        print("✅ PyInstaller already installed")
    except ImportError:
        print("📦 Installing PyInstaller...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
        print("✅ PyInstaller installed successfully")

def build_executable():
    """Build the standalone executable"""
    print("🔨 Building TTU Notes executable...")
    
    # PyInstaller command
    cmd = [
        "pyinstaller",
        "--onefile",                    # Single executable file
        "--windowed",                   # No console window (Windows)
        "--name=TTU_Notes",             # Executable name
        "--icon=static/favicon.ico",    # Icon (if available)
        "--add-data=templates;templates",  # Include templates
        "--add-data=static;static",     # Include static files
        "--hidden-import=netmiko",
        "--hidden-import=jinja2",
        "--hidden-import=flask",
        "app.py"
    ]
    
    # Run PyInstaller
    subprocess.check_call(cmd)
    
    print("✅ Executable built successfully!")
    print("📁 Location: dist/TTU_Notes.exe")

def create_installer():
    """Create a simple installer script"""
    installer_content = """@echo off
echo Installing TTU Notes...
echo.

REM Create application directory
if not exist "%APPDATA%\\TTU_Notes" mkdir "%APPDATA%\\TTU_Notes"

REM Copy executable
copy "TTU_Notes.exe" "%APPDATA%\\TTU_Notes\\"

REM Create desktop shortcut
echo Creating desktop shortcut...
powershell "$WshShell = New-Object -comObject WScript.Shell; $Shortcut = $WshShell.CreateShortcut('%USERPROFILE%\\Desktop\\TTU Notes.lnk'); $Shortcut.TargetPath = '%APPDATA%\\TTU_Notes\\TTU_Notes.exe'; $Shortcut.Save()"

echo.
echo ✅ TTU Notes installed successfully!
echo 🚀 You can now run TTU Notes from your desktop or Start menu
pause
"""
    
    with open("install_TTU_Notes.bat", "w") as f:
        f.write(installer_content)
    
    print("✅ Installer script created: install_TTU_Notes.bat")

def main():
    print("🚀 TTU Notes Distribution Builder")
    print("=" * 40)
    
    # Install PyInstaller
    install_pyinstaller()
    
    # Build executable
    build_executable()
    
    # Create installer
    create_installer()
    
    print("\n🎉 Distribution package ready!")
    print("📦 Files created:")
    print("   - dist/TTU_Notes.exe (standalone executable)")
    print("   - install_TTU_Notes.bat (installer script)")
    print("\n📋 Distribution instructions:")
    print("   1. Copy both files to a USB drive or shared folder")
    print("   2. Users run install_TTU_Notes.bat to install")
    print("   3. Application will be available on desktop and Start menu")

if __name__ == "__main__":
    main()