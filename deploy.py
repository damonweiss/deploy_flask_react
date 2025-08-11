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

# IMMEDIATE DEBUG OUTPUT - before any imports that might fail
print("[DEPLOY_STEP_1_FIXED] Script starting...")
print(f"[DEPLOY_STEP_1_FIXED] Python version: {sys.version}")
print(f"[DEPLOY_STEP_1_FIXED] Current directory: {os.getcwd()}")
print(f"[DEPLOY_STEP_1_FIXED] Script file: {__file__}")

import os
import sys
import subprocess
from pathlib import Path
import argparse
import logging
from datetime import datetime

print("[DEPLOY_STEP_1_FIXED] All imports successful")


# Setup comprehensive logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('deployment.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


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
    """Main deployment entry point."""
    logger.info("=" * 60)
    logger.info("DEPLOY STEP 1+2: FOLDER STRUCTURE + PYTHON ENV")
    logger.info("=" * 60)
    logger.info(f"Starting deployment at {datetime.now()}")
    logger.info(f"Python version: {sys.version}")
    logger.info(f"Current working directory: {os.getcwd()}")
    logger.info(f"Script path: {__file__}")
    
    # Log environment variables
    vela_core_dir = os.environ.get("VELA_CORE_DIR")
    if vela_core_dir:
        logger.info(f"VELA_CORE_DIR detected: {vela_core_dir}")
    else:
        logger.info("VELA_CORE_DIR not set - running in local mode")
    
    # Check if we have the required files locally
    logger.info("Checking for required bootloader files...")
    if not check_local_files():
        logger.error("Bootloader files not found in current directory.")
        logger.error("This script expects to run in a repository with:")
        logger.error("- folder_bootloader.py")
        logger.error("- python_env_bootloader.py")
        logger.error("- bootloader_config.json")
        sys.exit(1)
    
    # Execute the folder bootloader directly (no downloads needed)
    logger.info("Starting Step 1: Folder Structure Creation...")
    logger.info(f"Executing command: {sys.executable} folder_bootloader.py --deploy")
    try:
        result = subprocess.run([sys.executable, 'folder_bootloader.py', '--deploy'], 
                              check=True, capture_output=True, text=True)
        
        logger.info("Step 1 subprocess completed successfully")
        # Show the output from folder bootloader
        if result.stdout:
            logger.info("Step 1 STDOUT:")
            for line in result.stdout.strip().split('\n'):
                if line.strip():
                    logger.info(f"  {line}")
        
        if result.stderr:
            logger.warning("Step 1 STDERR:")
            for line in result.stderr.strip().split('\n'):
                if line.strip():
                    logger.warning(f"  {line}")
        
        logger.info("[SUCCESS] Step 1: Folder structure created successfully!")
        
    except subprocess.CalledProcessError as e:
        logger.error(f"[ERROR] Step 1 failed with exit code {e.returncode}")
        if e.stdout:
            logger.error("Step 1 STDOUT:")
            for line in e.stdout.strip().split('\n'):
                if line.strip():
                    logger.error(f"  {line}")
        if e.stderr:
            logger.error("Step 1 STDERR:")
            for line in e.stderr.strip().split('\n'):
                if line.strip():
                    logger.error(f"  {line}")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.error("Step 1 interrupted by user")
        sys.exit(1)
    
    # Step 2: Python Environment Setup
    logger.info("Starting Step 2: Python Environment Setup...")
    logger.info(f"Executing command: {sys.executable} python_env_bootloader.py --deploy")
    try:
        result = subprocess.run([sys.executable, 'python_env_bootloader.py', '--deploy'], 
                              check=True, capture_output=True, text=True)
        
        logger.info("Step 2 subprocess completed successfully")
        # Show the output from python env bootloader
        if result.stdout:
            logger.info("Step 2 STDOUT:")
            for line in result.stdout.strip().split('\n'):
                if line.strip():
                    logger.info(f"  {line}")
        
        if result.stderr:
            logger.warning("Step 2 STDERR:")
            for line in result.stderr.strip().split('\n'):
                if line.strip():
                    logger.warning(f"  {line}")
        
        logger.info("[SUCCESS] Step 2: Python environment setup completed!")
        
    except subprocess.CalledProcessError as e:
        logger.error(f"[ERROR] Step 2 failed with exit code {e.returncode}")
        if e.stdout:
            logger.error("Step 2 STDOUT:")
            for line in e.stdout.strip().split('\n'):
                if line.strip():
                    logger.error(f"  {line}")
        if e.stderr:
            logger.error("Step 2 STDERR:")
            for line in e.stderr.strip().split('\n'):
                if line.strip():
                    logger.error(f"  {line}")
        logger.error("[PARTIAL SUCCESS] Step 1 completed successfully")
        logger.error("[FAILED] Step 2 failed - check logs above")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.error("Step 2 interrupted by user")
        logger.error("[PARTIAL SUCCESS] Step 1 completed successfully")
        sys.exit(1)
    
    # Final success message
    print("\n" + "="*60)
    print("DEPLOYMENT SUCCESSFUL!")
    print("="*60)
    print("Step 1: Folder structure created")
    print("Step 2: Python environment setup")
    print("\nYour Flask + Vite project is ready for development!")
    
    print("\nWhat was created:")
    print("- Project folder structure (backend/, frontend/, tests/, etc.)")
    print("- Python virtual environment (.venv)")
    print("- Basic Flask application files")
    print("- Comprehensive .gitignore")
    
    print("\nNext steps:")
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
