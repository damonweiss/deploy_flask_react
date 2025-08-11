#!/usr/bin/env python3
"""
Deploy Orchestrator (VelaOS entry point)
----------------------------------------
Step 1: Create folder structure via folder_bootloader.py
Step 2: (optional) Python env via python_env_bootloader.py (if present)
Step 3: (optional) Vite/React & proxy via vite_bootloader.py (if present)

Usage:
  python deploy.py                    # Step 1, then Step 2/3 if available
  python deploy.py --skip-env         # Skip Step 2
  python deploy.py --skip-frontend    # Skip Step 3
  python deploy.py --help-only        # Show help
  python deploy.py --verbose          # DEBUG logging
"""

from __future__ import annotations
import argparse, logging, os, sys, subprocess, traceback
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
        handlers=[logging.FileHandler('deployment.log', encoding='utf-8'),
                  logging.StreamHandler()]
    )

logger = logging.getLogger(__name__)

# ---------- Helpers ----------
def check_requirements() -> bool:
    logger.info("Checking system requirements…")
    if sys.version_info < (3, 8):
        logger.error("Python 3.8+ required")
        return False
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
    # Step 3 is optional; don't require vite_bootloader.py here
    missing = [f for f in (base + env) if not have_file(f)]
    logger.info("Top-level files: %s", [p.name for p in REPO_ROOT.iterdir()])
    for f in (base + env):
        if f in missing:
            logger.error("[MISSING] %s", f)
        else:
            logger.info("[OK] %s", f)
    return not missing

def _log_stream(title: str, text: str, level: str) -> None:
    if not text:
        return
    for line in text.strip().splitlines():
        if not line.strip():
            continue
        if level == "info":
            logger.info("  %s", line)
        elif level == "warn":
            logger.warning("  %s", line)
        else:
            logger.error("  %s", line)

def run_step(title: str, cmd: list[str]) -> None:
    logger.info("=" * 60)
    logger.info("%s - starting", title)
    logger.info("Command: %s", " ".join(cmd))
    try:
        res = subprocess.run(cmd, check=True, capture_output=True, text=True)
        _log_stream(f"{title} STDOUT:", res.stdout, "info")
        _log_stream(f"{title} STDERR:", res.stderr, "warn")
        logger.info("%s - success", title)
    except subprocess.CalledProcessError as e:
        logger.error("%s - FAILED (exit %s)", title, e.returncode)
        _log_stream(f"{title} STDOUT:", e.stdout, "error")
        _log_stream(f"{title} STDERR:", e.stderr, "error")
        raise
    except KeyboardInterrupt:
        logger.error("%s - interrupted by user", title)
        raise
    except Exception:
        logger.exception("%s - unexpected exception", title)
        raise

def run_step_soft(title: str, cmd: list[str]) -> bool:
    logger.info("=" * 60)
    logger.info("%s - starting (soft)", title)
    logger.info("Command: %s", " ".join(cmd))
    try:
        res = subprocess.run(cmd, check=True, capture_output=True, text=True)
        _log_stream(f"{title} STDOUT:", res.stdout, "info")
        _log_stream(f"{title} STDERR:", res.stderr, "warn")
        logger.info("%s - success", title)
        return True
    except Exception:
        logger.exception("%s - FAILED (soft)", title)
        return False

def main(skip_env: bool, skip_frontend: bool, verbose: bool) -> None:
    setup_logging(verbose)
    logger.info("=" * 60)
    logger.info("DEPLOY orchestrator (Step 1 + optional Step 2/3)")
    logger.info("=" * 60)
    logger.info("Start: %s", datetime.now().isoformat(timespec="seconds"))
    logger.info("Python exe: %s", sys.executable)
    logger.info("Repo root: %s", REPO_ROOT)

    vela_core_dir = os.environ.get("VELA_CORE_DIR")
    logger.info("VELA_CORE_DIR=%s", vela_core_dir if vela_core_dir else "(not set)")

    if not check_requirements():
        print("\n[ERROR] System requirements not met. See deployment.log")
        sys.exit(1)

    step2_present = have_file("python_env_bootloader.py")
    step3_present = have_file("vite_bootloader.py")
    require_env_assets = (not skip_env) and step2_present

    if not check_local_files(require_env=require_env_assets):
        print("\n[ERROR] Required bootloader files are missing. See deployment.log")
        if not step2_present and not skip_env:
            print("Tip: 'python_env_bootloader.py' not found; rerun with --skip-env or add the file.")
        sys.exit(1)

    # Step 1 (hard)
    try:
        run_step("Step 1: Folder Structure Creation",
                 [sys.executable, "-u", str(REPO_ROOT / "folder_bootloader.py"), "--deploy"])
    except Exception:
        print("\n[ERROR] Step 1 failed. See deployment.log for details.")
        sys.exit(1)

    # Step 2 (soft; stub always returns 0 anyway)
    if not skip_env and step2_present:
        ok2 = run_step_soft("Step 2: Python Environment Setup",
                            [sys.executable, "-u", str(REPO_ROOT / "python_env_bootloader.py"),
                             "--deploy", "--verbose"])
        if not ok2:
            print("\n[WARNING] Step 2 failed. Continuing. See deployment.log")
    elif skip_env:
        logger.info("Step 2 skipped by flag (--skip-env)")
        print("\n[NOTICE] Step 2 skipped by flag (--skip-env)")
    else:
        logger.info("Step 2 skipped (python_env_bootloader.py not found)")
        print("\n[NOTICE] Step 2 skipped (python_env_bootloader.py not found)")

    # Step 3 (soft; stub always returns 0 anyway)
    if not skip_frontend and step3_present:
        ok3 = run_step_soft("Step 3: Frontend (Vite/React & proxy)",
                            [sys.executable, "-u", str(REPO_ROOT / "vite_bootloader.py"),
                             "--deploy", "--verbose"])
        if not ok3:
            print("\n[WARNING] Step 3 failed. Continuing. See deployment.log")
    elif skip_frontend:
        logger.info("Step 3 skipped by flag (--skip-frontend)")
        print("\n[NOTICE] Step 3 skipped by flag (--skip-frontend)")
    else:
        logger.info("Step 3 skipped (vite_bootloader.py not found)")
        print("\n[NOTICE] Step 3 skipped (vite_bootloader.py not found)")

    # Done
    print("\n" + "=" * 60)
    print("DEPLOYMENT COMPLETE")
    print("=" * 60)
    print("✓ Step 1: Folder structure created")
    print("✓ Step 2: Python environment (soft) —", "executed" if (not skip_env and step2_present) else "skipped")
    print("✓ Step 3: Frontend (soft) —", "executed" if (not skip_frontend and step3_present) else "skipped")
    print("\nNext steps:")
    print("- Step 3/4 (real): swap stubs with real installers when ready")
    print("\nSee deployment.log for full transcript.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="VelaOS Deploy Orchestrator")
    parser.add_argument("--deploy", action="store_true", help="Execute deployment (default)")
    parser.add_argument("--skip-env", action="store_true", help="Run Step 1 only (skip Python env)")
    parser.add_argument("--skip-frontend", action="store_true", help="Skip Vite/React & proxy step")
    parser.add_argument("--help-only", action="store_true", help="Show help only (no deploy)")
    parser.add_argument("--verbose", action="store_true", help="DEBUG logging")
    args = parser.parse_args()

    if args.help_only:
        print(__doc__)
        sys.exit(0)

    try:
        main(skip_env=args.skip_env, skip_frontend=args.skip_frontend, verbose=args.verbose)
    except KeyboardInterrupt:
        print("\n[ABORTED] Interrupted by user.")
        sys.exit(1)
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        sys.exit(1)
