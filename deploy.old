#!/usr/bin/env python3
"""
Flask + Vite Repository Deployment Script
Direct execution for VelaOS bootloader system (no downloads needed)

This script assumes all files are already cloned locally by VelaOS:
- vite_flask_bootloader.py (in same directory)
- bootloader_config.json (in same directory)
"""

import os
import sys
import subprocess
from pathlib import Path


def check_local_files():
    """Check that required files are present locally."""
    print("Checking for local bootloader files...")
    
    required_files = ['vite_flask_bootloader.py', 'bootloader_config.json']
    missing_files = []
    
    for filename in required_files:
        if not Path(filename).exists():
            missing_files.append(filename)
        else:
            print(f"[OK] Found {filename}")
    
    if missing_files:
        print(f"[ERROR] Missing files: {', '.join(missing_files)}")
        print("These files should be in the same directory as deploy.py")
        return False
    
    return True


def check_requirements():
    """Check system requirements."""
    print("Checking system requirements...")
    
    # Check Python version
    if sys.version_info < (3, 8):
        print("[ERROR] Python 3.8+ required")
        return False
    print("[OK] Python version OK")
    
    # Check for uv (preferred) or pip
    try:
        subprocess.run(['uv', '--version'], capture_output=True, check=True)
        print("[OK] uv package manager available")
    except (subprocess.CalledProcessError, FileNotFoundError):
        try:
            subprocess.run([sys.executable, '-m', 'pip', '--version'], 
                         capture_output=True, check=True)
            print("[OK] pip package manager available")
        except subprocess.CalledProcessError:
            print("[ERROR] No Python package manager found")
            return False
    
    # Check for Node.js and npm
    try:
        subprocess.run(['node', '--version'], capture_output=True, check=True)
        subprocess.run(['npm', '--version'], capture_output=True, check=True)
        print("[OK] Node.js and npm available")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("[ERROR] Node.js and npm required")
        return False
    
    return True


def main():
    """Main deployment entry point."""
    print("=" * 60)
    print("FLASK + VITE REPOSITORY DEPLOYMENT")
    print("=" * 60)
    
    # Check system requirements
    if not check_requirements():
        print("\nSystem requirements not met. Please install:")
        print("- Python 3.8+")
        print("- uv (preferred) or pip")
        print("- Node.js and npm")
        sys.exit(1)
    
    # Check for local bootloader files (should be cloned by VelaOS)
    if not check_local_files():
        print("\nBootloader files not found in current directory.")
        print("This script expects to run in a repository with:")
        print("- vite_flask_bootloader.py")
        print("- bootloader_config.json")
        sys.exit(1)
    
    # Execute the bootloader directly (no downloads needed)
    print("\nStarting Flask + Vite bootloader...")
    try:
        subprocess.run([sys.executable, 'vite_flask_bootloader.py', '--deploy'], 
                      check=True)
        print("\n[SUCCESS] Flask + Vite deployment completed!")
    except subprocess.CalledProcessError as e:
        print(f"\n[ERROR] Deployment failed: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nDeployment interrupted by user")
        subprocess.run([sys.executable, 'vite_flask_bootloader.py', '--stop'])
        sys.exit(0)


if __name__ == '__main__':
    main()
