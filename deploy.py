#!/usr/bin/env python3
"""
Simple VelaOS Deploy Script
Runs Steps 1 and 2 in sequence without complex orchestration

This script is designed to be called by VelaOS after GitHub repository clone.
It runs the essential deployment steps to get a Flask + Vite project started.

Usage:
    python deploy.py                    # Auto-deploy (VelaOS compatible)
    python deploy.py --help-only        # Show help only
"""

import os
import sys
import subprocess
from pathlib import Path
import argparse


def check_system_requirements():
    """Check basic system requirements."""
    print("Checking system requirements...")
    
    # Check Python version
    if sys.version_info < (3, 8):
        print("❌ Python 3.8+ required")
        return False
    print("✅ Python version OK")
    
    # Check write permissions
    try:
        test_dir = Path.cwd() / "test_write_permission"
        test_dir.mkdir(exist_ok=True)
        test_dir.rmdir()
        print("✅ Write permissions OK")
    except PermissionError:
        print("❌ No write permissions in current directory")
        return False
    
    return True


def check_required_files():
    """Check that required bootloader files are present."""
    print("Checking for required files...")
    
    required_files = [
        'folder_bootloader.py',
        'python_env_bootloader.py', 
        'bootloader_config.json'
    ]
    
    missing_files = []
    for filename in required_files:
        if Path(filename).exists():
            print(f"✅ Found {filename}")
        else:
            missing_files.append(filename)
    
    if missing_files:
        print(f"❌ Missing files: {', '.join(missing_files)}")
        return False
    
    return True


def run_step(step_num, step_name, script_name):
    """Run a deployment step."""
    print(f"\n{'='*60}")
    print(f"🚀 STEP {step_num}: {step_name.upper()}")
    print(f"{'='*60}")
    
    try:
        print(f"▶️  Executing: {script_name}")
        result = subprocess.run(
            [sys.executable, script_name, '--deploy'], 
            check=True, 
            capture_output=True, 
            text=True,
            timeout=300
        )
        
        # Show output
        if result.stdout:
            print("📄 Output:")
            for line in result.stdout.strip().split('\n'):
                if line.strip():
                    print(f"   {line}")
        
        if result.stderr:
            print("⚠️  Warnings:")
            for line in result.stderr.strip().split('\n'):
                if line.strip():
                    print(f"   {line}")
        
        print(f"✅ Step {step_num} completed successfully!")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Step {step_num} failed with exit code {e.returncode}")
        if e.stdout:
            print("STDOUT:")
            for line in e.stdout.strip().split('\n'):
                if line.strip():
                    print(f"   {line}")
        if e.stderr:
            print("STDERR:")
            for line in e.stderr.strip().split('\n'):
                if line.strip():
                    print(f"   {line}")
        return False
        
    except subprocess.TimeoutExpired:
        print(f"❌ Step {step_num} timed out after 5 minutes")
        return False
        
    except Exception as e:
        print(f"❌ Step {step_num} failed: {e}")
        return False


def main():
    """Main deployment entry point."""
    print("=" * 60)
    print("🚀 VELA OS FLASK + VITE DEPLOYMENT")
    print("=" * 60)
    
    # Check system requirements
    if not check_system_requirements():
        print("\n❌ System requirements not met.")
        sys.exit(1)
    
    # Check required files
    if not check_required_files():
        print("\n❌ Required bootloader files not found.")
        print("This script expects to run in a repository with:")
        print("- folder_bootloader.py")
        print("- python_env_bootloader.py")
        print("- bootloader_config.json")
        sys.exit(1)
    
    print(f"\n🎯 DEPLOYMENT PLAN: Running Steps 1-2")
    
    # Step 1: Folder Structure
    if not run_step(1, "Folder Structure Creation", "folder_bootloader.py"):
        print("\n💥 DEPLOYMENT FAILED at Step 1")
        sys.exit(1)
    
    # Step 2: Python Environment
    if not run_step(2, "Python Environment Setup", "python_env_bootloader.py"):
        print("\n💥 DEPLOYMENT FAILED at Step 2")
        print("✅ Step 1 completed successfully")
        print("❌ Step 2 failed - check logs above")
        sys.exit(1)
    
    # Success!
    print(f"\n🎉 DEPLOYMENT SUCCESSFUL!")
    print("✅ Step 1: Folder structure created")
    print("✅ Step 2: Python environment setup")
    print("\n🚀 Your Flask + Vite project is ready for development!")
    
    print(f"\n📋 What was created:")
    print("- Project folder structure (backend/, frontend/, tests/, etc.)")
    print("- Python virtual environment (.venv)")
    print("- Basic Flask application files")
    print("- Comprehensive .gitignore")
    
    print(f"\n💡 Next steps:")
    print("- Activate virtual environment")
    print("- Install additional dependencies as needed")
    print("- Start developing your Flask + Vite application")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Simple VelaOS Deploy Script")
    parser.add_argument("--help-only", action="store_true", help="Show help only")
    
    args = parser.parse_args()
    
    if args.help_only:
        print("Simple VelaOS Deploy Script")
        print("\nThis script runs essential deployment steps:")
        print("1. Folder Structure Creation")
        print("2. Python Environment Setup")
        print("\nIt creates a ready-to-use Flask + Vite project structure.")
    else:
        # Default behavior: auto-deploy (VelaOS compatibility)
        main()
