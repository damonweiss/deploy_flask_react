#!/usr/bin/env python3
"""
Deploy Step 1: Folder Structure Creation
First step in the ordered deployment process - just creates folders

This script is designed to be called by VelaOS after GitHub repository clone.
It focuses solely on creating the project folder structure without any dependencies.

Usage:
    python deploy_step_1.py                 # Auto-deploy (VelaOS compatible)
    python deploy_step_1.py --deploy        # Explicit deploy
    python deploy_step_1.py --help-only     # Show help only
"""

import os
import sys
import subprocess
from pathlib import Path
import argparse
import logging


def check_local_files():
    """Check that required files are present locally."""
    print("Checking for local bootloader files...")
    
    required_files = ['folder_bootloader.py', 'python_env_bootloader.py', 'bootloader_config.json']
    missing_files = []
    
    for filename in required_files:
        if not Path(filename).exists():
            missing_files.append(filename)
        else:
            print(f"[OK] Found {filename}")
    
    if missing_files:
        print(f"[ERROR] Missing files: {', '.join(missing_files)}")
        print("These files should be in the same directory as deploy script")
        return False
    
    return True


def check_requirements():
    """Check basic system requirements for folder creation."""
    print("Checking system requirements...")
    
    # Check Python version
    if sys.version_info < (3, 8):
        print("[ERROR] Python 3.8+ required")
        return False
    print("[OK] Python version OK")
    
    # Check write permissions
    try:
        test_dir = Path.cwd() / "test_write_permission"
        test_dir.mkdir(exist_ok=True)
        test_dir.rmdir()
        print("[OK] Write permissions OK")
    except PermissionError:
        print("[ERROR] No write permissions in current directory")
        return False
    
    return True


def main():
    """Main deployment entry point for Step 1."""
    print("=" * 60)
    print("DEPLOY STEP 1: FOLDER STRUCTURE CREATION")
    print("=" * 60)
    
    # Check system requirements
    if not check_requirements():
        print("\nSystem requirements not met.")
        sys.exit(1)
    
    # Check for local bootloader files (should be cloned by VelaOS)
    if not check_local_files():
        print("\nBootloader files not found in current directory.")
        print("This script expects to run in a repository with:")
        print("- folder_bootloader.py")
        print("- python_env_bootloader.py")
        print("- bootloader_config.json")
        sys.exit(1)
    
    # Execute the folder bootloader directly (no downloads needed)
    print("\nStarting Step 1: Folder Structure Creation...")
    try:
        result = subprocess.run([sys.executable, 'folder_bootloader.py', '--deploy'], 
                              check=True, capture_output=True, text=True)
        
        # Show the output from folder bootloader
        if result.stdout:
            print(result.stdout)
        
        print("\n[SUCCESS] Step 1: Folder structure created successfully!")
        
    except subprocess.CalledProcessError as e:
        print(f"\n[ERROR] Step 1 failed: {e}")
        if e.stdout:
            print("STDOUT:", e.stdout)
        if e.stderr:
            print("STDERR:", e.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nStep 1 interrupted by user")
        sys.exit(1)
    
    # Step 2: Python Environment Setup
    print("\nStarting Step 2: Python Environment Setup...")
    try:
        result = subprocess.run([sys.executable, 'python_env_bootloader.py', '--deploy'], 
                              check=True, capture_output=True, text=True)
        
        # Show the output from python env bootloader
        if result.stdout:
            print(result.stdout)
        
        print("\n[SUCCESS] Step 2: Python environment setup completed!")
        
    except subprocess.CalledProcessError as e:
        print(f"\n[ERROR] Step 2 failed: {e}")
        if e.stdout:
            print("STDOUT:", e.stdout)
        if e.stderr:
            print("STDERR:", e.stderr)
        print("\n[PARTIAL SUCCESS] Step 1 completed successfully")
        print("[FAILED] Step 2 failed - check logs above")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nStep 2 interrupted by user")
        print("\n[PARTIAL SUCCESS] Step 1 completed successfully")
        sys.exit(1)
    
    # Final success message
    print("\n" + "="*60)
    print("🎉 DEPLOYMENT SUCCESSFUL!")
    print("="*60)
    print("✅ Step 1: Folder structure created")
    print("✅ Step 2: Python environment setup")
    print("\n🚀 Your Flask + Vite project is ready for development!")
    
    print("\n📋 What was created:")
    print("- Project folder structure (backend/, frontend/, tests/, etc.)")
    print("- Python virtual environment (.venv)")
    print("- Basic Flask application files")
    print("- Comprehensive .gitignore")
    
    print("\n💡 Next steps:")
    print("- Activate virtual environment")
    print("- Install additional dependencies as needed")
    print("- Start developing your Flask + Vite application")


if __name__ == '__main__':
    # Parse arguments - but default to deploy=True for VelaOS compatibility
    parser = argparse.ArgumentParser(description="Deploy Step 1: Folder Structure Creation")
    parser.add_argument("--deploy", action="store_true", help="Execute folder structure creation")
    parser.add_argument("--help-only", action="store_true", help="Show help only (don't auto-deploy)")
    
    args = parser.parse_args()
    
    # Auto-deploy unless explicitly asked for help only
    if args.help_only:
        print("Deploy Step 1 - Use --deploy to create folder structure")
        print("\nThis is the first step in the ordered deployment process:")
        print("1. [THIS STEP] Create folder structure")
        print("2. Setup Python environment (uv, .venv)")
        print("3. Generate backend TOML")
        print("4. Setup frontend (npm)")
    else:
        # Default behavior: auto-deploy (VelaOS compatibility)
        main()
