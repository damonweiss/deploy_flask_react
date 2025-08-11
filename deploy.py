#!/usr/bin/env python3
"""
Deploy Step 1 (+ optional Step 2)
---------------------------------
Step 1: Create folder structure by calling folder_bootloader.py
Step 2: (optional) Create Python env by calling python_env_bootloader.py if present

Designed to be called by VelaOS right after repo clone.

Usage:
  python deploy_step_1.py                 # Auto-deploy (runs Step 1, and Step 2 if available)
  python deploy_step_1.py --deploy        # Same as above
  python deploy_step_1.py --skip-env      # Force Step 1 only
  python deploy_step_1.py --help-only     # Show help only
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import subprocess
from datetime import datetime
from pathlib import Path

# ---- Early, visible boot trace (after imports to avoid NameError) ----
print("[DEPLOY] Script starting…")
print(f"[DEPLOY] Python: {sys.version.split()[0]}")
print(f"[DEPLOY] CWD: {os.getcwd()}")
print(f"[DEPLOY] Script: {Path(__file__).resolve()}")

# ---- Logging setup ----
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s - %(message)s',
    handlers=[logging.FileHandler('deployment.log'), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)


# ---------- Helpers ----------
def check_requirements() -> bool:
    """Basic preflight checks."""
    logger.info("Checking system requirements…")
    if sys.version_info < (3, 8):
        logger.error("Python 3.8+ required")
        return False

    try:
        probe = Path.cwd() / ".write_probe__remove_me"
        probe.mkdir(exist_ok=True)
        probe.rmdir()
    except PermissionError:
        logger.error("No write permission in current directory")
        return False

    logger.info("System requirements OK")
    return True


def have_file(fname: str) -> bool:
    return Path(fname).exists()


def check_local_files(require_env: bool) -> bool:
    """
    Ensure expected files exist in the same directory as this script.
    require_env=True also requires python_env_bootloader.py.
    """
    base_required = ["folder_bootloader.py", "bootloader_config.json"]
    env_required = ["python_env_bootloader.py"] if require_env else []

    missing = [f for f in (base_required + env_required) if not have_file(f)]
    for f in (base_required + env_required):
        if f in missing:
            logger.error(f"[MISSING] {f}")
        else:
            logger.info(f"[OK] Found {f}")

    if missing:
        return False
    return True


def run_step(step_name: str, cmd: list[str]) -> None:
    """Run a subprocess step with nice logging and error surfacing."""
    logger.info("=" * 60)
    logger.info(f"{step_name} - starting")
    logger.info(f"Command: {' '.join(cmd)}")
    try:
        res = subprocess.run(cmd, check=True, capture_output=True, text=True)
        if res.stdout:
            logger.info(f"{step_name} STDOUT:")
            for line in res.stdout.strip().splitlines():
                if line.strip():
                    logger.info(f"  {line}")
        if res.stderr:
            logger.warning(f"{step_name} STDERR:")
            for line in res.stderr.strip().splitlines():
                if line.strip():
                    logger.warning(f"  {line}")
        logger.info(f"{step_name} - success")
    except subprocess.CalledProcessError as e:
        logger.error(f"{step_name} - FAILED (exit {e.returncode})")
        if e.stdout:
            logger.error(f"{step_name} STDOUT:")
            for line in e.stdout.strip().splitlines():
                if line.strip():
                    logger.error(f"  {line}")
        if e.stderr:
            logger.error(f"{step_name} STDERR:")
            for line in e.stderr.strip().splitlines():
                if line.strip():
                    logger.error(f"  {line}")
        raise
    except KeyboardInterrupt:
        logger.error(f"{step_name} - interrupted by user")
        raise


# ---------- Main ----------
def main(skip_env: bool = False) -> None:
    logger.info("=" * 60)
    logger.info("DEPLOY: Step 1 (+ optional Step 2)")
    logger.info("=" * 60)
    logger.info(f"Start time: {datetime.now().isoformat(timespec='seconds')}")
    logger.info(f"Python exe: {sys.executable}")
    logger.info(f"Working dir: {os.getcwd()}")
    logger.info(f"Script path: {Path(__file__).resolve()}")

    # Helpful for diagnostics in VelaOS environments
    vela_core_dir = os.environ.get("VELA_CORE_DIR")
    if vela_core_dir:
        logger.info(f"VELA_CORE_DIR={vela_core_dir}")
    else:
        logger.info("VELA_CORE_DIR not set (local mode)")

    if not check_requirements():
        print("\n[ERROR] System requirements not met.")
        sys.exit(1)

    # Decide whether we *require* Step 2 assets
    step2_present = have_file("python_env_bootloader.py")
    require_env_assets = (not skip_env) and step2_present

    if not check_local_files(require_env=require_env_assets):
        print("\n[ERROR] Required bootloader files are missing.")
        if not step2_present and not skip_env:
            print("Tip: 'python_env_bootloader.py' not found; run with --skip-env or add the file.")
        sys.exit(1)

    # ---- Step 1: Folder Structure ----
    try:
        run_step("Step 1: Folder Structure Creation", [sys.executable, "folder_bootloader.py", "--deploy"])
    except Exception:
        print("\n[ERROR] Step 1 failed. See deployment.log for details.")
        sys.exit(1)

    # ---- Step 2: Python Env (optional) ----
    if not skip_env:
        if step2_present:
            try:
                run_step("Step 2: Python Environment Setup", [sys.executable, "python_env_bootloader.py", "--deploy"])
            except Exception:
                print("\n[FAILED] Step 2 failed. Step 1 completed successfully.")
                sys.exit(1)
        else:
            logger.info("Step 2 skipped (python_env_bootloader.py not found).")
            print("\n[NOTICE] Step 2 skipped (python_env_bootloader.py not found).")

    # ---- Done ----
    print("\n" + "=" * 60)
    print("DEPLOYMENT COMPLETE")
    print("=" * 60)
    print("✓ Step 1: Folder structure created")
    if not skip_env and step2_present:
        print("✓ Step 2: Python environment setup")
    elif skip_env:
        print("⏭ Step 2: Skipped by flag (--skip-env)")
    else:
        print("⏭ Step 2: Skipped (python_env_bootloader.py not found)")

    print("\nNext steps:")
    print("- Step 3: Backend TOML generation")
    print("- Step 4: Frontend setup (npm)")
    print("\nCheck deployment.log for a full transcript.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Deploy Step 1 (+ optional Step 2)")
    parser.add_argument("--deploy", action="store_true", help="Execute deployment (default behavior)")
    parser.add_argument("--skip-env", action="store_true", help="Run Step 1 only (skip Python env)")
    parser.add_argument("--help-only", action="store_true", help="Show help only (no deploy)")
    args = parser.parse_args()

    if args.help_only:
        print(__doc__)
        sys.exit(0)

    # Default behavior: auto-deploy
    try:
        main(skip_env=args.skip_env)
    except KeyboardInterrupt:
        print("\n[ABORTED] Interrupted by user.")
        sys.exit(1)
