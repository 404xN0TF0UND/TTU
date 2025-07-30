#!/usr/bin/env python3
"""
Install dependencies for TTU Notes
"""

import subprocess
import sys

def install_dependencies():
    """Install all required dependencies"""
    print("📦 Installing TTU Notes dependencies...")
    
    # Install from requirements.txt
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✅ All dependencies installed successfully!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install dependencies: {e}")
        return False

def install_pyinstaller_only():
    """Install only PyInstaller"""
    print("📦 Installing PyInstaller...")
    
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
        print("✅ PyInstaller installed successfully!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install PyInstaller: {e}")
        return False

def main():
    print("🚀 TTU Notes Dependency Installer")
    print("=" * 35)
    
    if len(sys.argv) > 1 and sys.argv[1] == "--pyinstaller-only":
        install_pyinstaller_only()
    else:
        install_dependencies()
    
    print("\n💡 Next steps:")
    print("   1. Run 'python create_portable.py' to create portable package")
    print("   2. Or run 'python app.py' to start the application")

if __name__ == "__main__":
    main() 