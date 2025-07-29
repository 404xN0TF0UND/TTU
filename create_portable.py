#!/usr/bin/env python3
"""
Create a portable package for TTU Notes
This includes Python runtime and all dependencies in a single folder
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

def create_portable_package():
    """Create a portable package"""
    print("📦 Creating portable TTU Notes package...")
    
    # PyInstaller command for portable package
    cmd = [
        "pyinstaller",
        "--onedir",                     # Directory mode (portable)
        "--windowed",                   # No console window
        "--name=TTU_Notes_Portable",    # Package name
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
    
    # Create launcher script
    launcher_content = """@echo off
echo Starting TTU Notes...
cd /d "%~dp0"
TTU_Notes_Portable.exe
"""
    
    launcher_path = Path("dist/TTU_Notes_Portable/Start_TTU_Notes.bat")
    with open(launcher_path, "w") as f:
        f.write(launcher_content)
    
    # Create README for portable package
    readme_content = """# TTU Notes - Portable Version

## 🚀 Quick Start
1. Double-click "Start_TTU_Notes.bat" to launch the application
2. The application will open in your default web browser
3. No installation required - this is a portable package

## 📁 What's Included
- TTU_Notes_Portable.exe - Main application
- Start_TTU_Notes.bat - Easy launcher script
- All required dependencies and templates

## 🔧 System Requirements
- Windows 10 or later
- Web browser (Chrome, Firefox, Edge, Safari)
- Network access to your devices

## 📝 Usage
1. Run Start_TTU_Notes.bat
2. Open your web browser to http://127.0.0.1:5000
3. Start managing your network devices!

## 🗂️ Data Storage
Your notes and device configurations are stored locally in the same folder.
You can copy this entire folder to another computer to transfer your data.

---
Built for Network Engineers, by Network Engineers 🛠️
"""
    
    readme_path = Path("dist/TTU_Notes_Portable/README.txt")
    with open(readme_path, "w") as f:
        f.write(readme_content)
    
    print("✅ Portable package created successfully!")
    print("📁 Location: dist/TTU_Notes_Portable/")

def create_zip_package():
    """Create a zip file for easy distribution"""
    import zipfile
    
    print("📦 Creating zip package...")
    
    portable_dir = Path("dist/TTU_Notes_Portable")
    zip_path = Path("dist/TTU_Notes_Portable.zip")
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file_path in portable_dir.rglob('*'):
            if file_path.is_file():
                arcname = file_path.relative_to(portable_dir)
                zipf.write(file_path, arcname)
    
    print(f"✅ Zip package created: {zip_path}")

def main():
    print("🚀 TTU Notes Portable Package Builder")
    print("=" * 45)
    
    # Install PyInstaller
    install_pyinstaller()
    
    # Create portable package
    create_portable_package()
    
    # Create zip package
    create_zip_package()
    
    print("\n🎉 Portable package ready!")
    print("📦 Files created:")
    print("   - dist/TTU_Notes_Portable/ (portable folder)")
    print("   - dist/TTU_Notes_Portable.zip (compressed package)")
    print("\n📋 Distribution instructions:")
    print("   1. Share the zip file with users")
    print("   2. Users extract and run Start_TTU_Notes.bat")
    print("   3. No installation required - completely portable")

if __name__ == "__main__":
    main()