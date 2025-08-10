#!/usr/bin/env python3
"""
Flask + Vite Deployment Script
One-command deployment for VelaOS bootloader system

This script can be served from GitHub and executed directly:
    curl -sSL https://raw.githubusercontent.com/damonweiss/deploy_flask_react/main/deploy.py | python3

Or downloaded and run locally:
    python3 deploy.py
"""

import os
import sys
import subprocess
import urllib.request
from pathlib import Path


def download_bootloader():
    """Download the main bootloader script."""
    bootloader_url = "https://raw.githubusercontent.com/damonweiss/deploy_flask_react/main/flask_vite_bootloader.py"
    config_url = "https://raw.githubusercontent.com/damonweiss/deploy_flask_react/main/bootloader_config.json"
    
    print("Downloading Flask + Vite bootloader...")
    
    try:
        # Download bootloader script
        with urllib.request.urlopen(bootloader_url) as response:
            bootloader_content = response.read().decode('utf-8')
        
        with open('flask_vite_bootloader.py', 'w') as f:
            f.write(bootloader_content)
        
        # Make executable
        os.chmod('flask_vite_bootloader.py', 0o755)
        print("[OK] Downloaded flask_vite_bootloader.py")
        
        # Download config
        with urllib.request.urlopen(config_url) as response:
            config_content = response.read().decode('utf-8')
        
        with open('bootloader_config.json', 'w') as f:
            f.write(config_content)
        
        print("[OK] Downloaded bootloader_config.json")
        
    except Exception as e:
        print(f"[ERROR] Download failed: {e}")
        print("Falling back to local execution...")
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
    print("FLASK + VITE BOOTLOADER DEPLOYMENT")
    print("=" * 60)
    
    # Check system requirements
    if not check_requirements():
        print("\nSystem requirements not met. Please install:")
        print("- Python 3.8+")
        print("- uv (preferred) or pip")
        print("- Node.js and npm")
        sys.exit(1)
    
    # Download bootloader if not running locally
    if not Path('flask_vite_bootloader.py').exists():
        if not download_bootloader():
            print("Could not download bootloader files")
            sys.exit(1)
    
    # Execute the bootloader
    print("\nStarting Flask + Vite bootloader...")
    try:
        subprocess.run([sys.executable, 'flask_vite_bootloader.py', '--deploy'], 
                      check=True)
    except subprocess.CalledProcessError as e:
        print(f"Deployment failed: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nDeployment interrupted by user")
        subprocess.run([sys.executable, 'flask_vite_bootloader.py', '--stop'])
        sys.exit(0)


if __name__ == '__main__':
    main()
