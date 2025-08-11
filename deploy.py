#!/usr/bin/env python3
"""
Deploy Orchestrator (VelaOS entry point)
----------------------------------------
Step 1: Create folder structure via folder_bootloader.py
Step 2: (optional) Create Python env via python_env_bootloader.py (if present)

Usage:
  python deploy.py                   # Auto-deploy (Step 1, then Step 2 if available)
  python deploy.py --skip-env        # Force Step 1 only
  python deploy.py --help-only       # Show help
  python deploy.py --verbose         # DEBUG logging
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import subprocess
import traceback
from datetime import datetime
from pathlib import Path

# --- Establish repo root & chdir early (avoid relative-path issues) ---
SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parent
os.chdir(REPO_ROOT)

# --- Early visible boot trace (after imports so sys/os exist) ---
print("[DEPLOY] starting…")
print(f"[DEPLOY] python: {sys.version.split()[0]}")
print(f"[DEPLOY] cwd: {os.getcwd()}")
print(f"[DEPLOY] script: {SCRIPT_PATH}")

# --- Logging setup ---
def setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='[%(asctime)s] %(levelname)s - %(message)s',
        handlers=[logging.FileHandler('deployment.log', encoding='utf-8'), logging.StreamHandler()]
    )

logger = logging.getLogger(__name__)


# ---------- Helpers ----------
def check_requirements() -> bool:
    logger.info("Checking system requirements…")
    if sys.version_info < (3, 8):
        logger.error("Python 3.8+ required")
        return False
    # write permission probe
    try:
        p = REPO_ROOT / ".write_probe__remove_me"
        p.mkdir(exist_ok=True)
        p.rmdir()
    except PermissionError:
        logger.error("No write permission in repo directory")
        return False
    logger.info("System requirements OK")
    return True


def have_file(name: str) -> bool:
    return (REPO_ROOT / name).exists()


def check_local_files(require_env: bool) -> bool:
    base = ["folder_bootloader.py", "bootloader_config.json"]
    env = ["python_env_bootloader.py"] if require_env else []
    missing = [f for f in (base + env) if not have_file(f)]

    logger.info("Top-level files: %s", [p.name for p in REPO_ROOT.iterdir() if p.is_file() or p.is_dir()])
    for f in (base + env):
        if f in missing:
            logger.error("[MISSING] %s", f)
        else:
            logger.info("[OK] %s", f)

    return not missing


def run_step(title: str, cmd: list[str]) -> None:
    logger.info("=" * 60)
    logger.info("%s - starting", title)
    logger.info("Command: %s", " ".join(cmd))
    try:
        res = subprocess.run(cmd, check=True, capture_output=True, text=True)
        if res.stdout:
            logger.info("%s STDOUT:", title)
            for line in res.stdout.strip().splitlines():
                if line.strip():
                    logger.info("  %s", line)
        if res.stderr:
            logger.warning("%s STDERR:", title)
            for line in res.stderr.strip().splitlines():
                if line.strip():
                    logger.warning("  %s", line)
        logger.info("%s - success", title)
    except subprocess.CalledProcessError as e:
        logger.error("%s - FAILED (exit %s)", title, e.returncode)
        if e.stdout:
            logger.error("%s STDOUT:", title)
            for line in e.stdout.strip().splitlines():
                if line.strip():
                    logger.error("  %s", line)
        if e.stderr:
            logger.error("%s STDERR:", title)
            for line in e.stderr.strip().splitlines():
                if line.strip():
                    logger.error("  %s", line)
        raise
    except KeyboardInterrupt:
        logger.error("%s - interrupted by user", title)
        raise
    except Exception:
        logger.exception("%s - unexpected exception", title)
        raise


def main(skip_env: bool, verbose: bool) -> None:
    setup_logging(verbose)
    logger.info("=" * 60)
    logger.info("DEPLOY orchestrator (Step 1 + optional Step 2)")
    logger.info("=" * 60)
    logger.info("Start: %s", datetime.now().isoformat(timespec="seconds"))
    logger.info("Python exe: %s", sys.executable)
    logger.info("Repo root: %s", REPO_ROOT)

    vela_core_dir = os.environ.get("VELA_CORE_DIR")
    if vela_core_dir:
        logger.info("VELA_CORE_DIR=%s", vela_core_dir)
    else:
        logger.info("VELA_CORE_DIR not set (local mode)")

    if not check_requirements():
        print("\n[ERROR] System requirements not met. See deployment.log")
        sys.exit(1)

    step2_present = have_file("python_env_bootloader.py")
    require_env_assets = (not skip_env) and step2_present

    if not check_local_files(require_env=require_env_assets):
        print("\n[ERROR] Required bootloader files are missing. See deployment.log")
        if not step2_present and not skip_env:
            print("Tip: 'python_env_bootloader.py' not found; rerun with --skip-env or add the file.")
        sys.exit(1)

    # Step 1
    try:
        run_step("Step 1: Folder Structure Creation", [sys.executable, "folder_bootloader.py", "--deploy"])
    except Exception:
        print("\n[ERROR] Step 1 failed. See deployment.log for details.")
        sys.exit(1)

    # Step 2 (optional)
    if not skip_env:
        if step2_present:
            try:
              run_step(
                  "Step 2: Python Environment Setup",
                  [sys.executable, str(REPO_ROOT / "python_env_bootloader.py"), "--deploy", "--verbose"]
              )
            except Exception:
                print("\n[FAILED] Step 2 failed. Step 1 completed successfully. See deployment.log")
                sys.exit(1)
        else:
            logger.info("Step 2 skipped (python_env_bootloader.py not found).")
            print("\n[NOTICE] Step 2 skipped (python_env_bootloader.py not found).")

    # Done
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
    print("\nSee deployment.log for full transcript.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="VelaOS Deploy Orchestrator")
    parser.add_argument("--deploy", action="store_true", help="Execute deployment (default)")
    parser.add_argument("--skip-env", action="store_true", help="Run Step 1 only (skip Python env)")
    parser.add_argument("--help-only", action="store_true", help="Show help only (no deploy)")
    parser.add_argument("--verbose", action="store_true", help="DEBUG logging")
    args = parser.parse_args()

    if args.help_only:
        print(__doc__)
        sys.exit(0)

    try:
        main(skip_env=args.skip_env, verbose=args.verbose)
    except KeyboardInterrupt:
        print("\n[ABORTED] Interrupted by user.")
        sys.exit(1)
    except SystemExit as e:
        raise
    except Exception:
        # Ensure non-zero exit and a traceback for the bootloader
        traceback.print_exc()
        sys.exit(1)
