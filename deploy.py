#!/usr/bin/env python3
"""
Deploy: Step 1 (structure) + Step 2 (python env)
- Step 1: create folder structure (folder_bootloader.py)
- Step 2: create backend venv + install Python deps
"""

from __future__ import annotations
import os, sys, subprocess
from pathlib import Path
import argparse

THIS_DIR = Path(__file__).resolve().parent

def check_requirements() -> bool:
    if sys.version_info < (3, 8):
        print("[ERROR] Python 3.8+ required")
        return False
    try:
        t = THIS_DIR / ".perm_test"
        t.write_text("ok", encoding="utf-8")
        t.unlink(missing_ok=True)
    except Exception as e:
        print(f"[ERROR] Write permission check failed: {e}")
        return False
    return True

def check_local_files() -> bool:
    missing = []
    for fname in ("folder_bootloader.py",):
        if not (THIS_DIR / fname).exists():
            missing.append(fname)
    if missing:
        print(f"[ERROR] Missing required file(s): {', '.join(missing)}")
        return False

    # Optional config: bootloader_config.json
    if not (THIS_DIR / "bootloader_config.json").exists():
        print("[INFO] bootloader_config.json not found — defaults will be used by Step 1")
    return True

def run_step_1() -> bool:
    print("\n=== STEP 1: Folder Structure Creation ===")
    cmd = [sys.executable, str(THIS_DIR / "folder_bootloader.py"), "--deploy"]
    try:
        res = subprocess.run(cmd, check=False, capture_output=True, text=True)
        if res.stdout: print(res.stdout, end="")
        if res.stderr: print(res.stderr, end="")
        if res.returncode != 0:
            print(f"[ERROR] Step 1 failed (exit {res.returncode})")
            return False
        print("[OK] Step 1 complete")
        return True
    except Exception as e:
        print(f"[ERROR] Step 1 error: {e}")
        return False

def run_step_2() -> bool:
    print("\n=== STEP 2: Python Env Setup (backend) ===")
    # Target venv + requirements locations in the deployment root backend/
    # Step 2 resolves deployment root via VELA_CORE_DIR (or falls back to cwd)
    cmd = [
        sys.executable,
        str(THIS_DIR / "python_env_bootloader.py"),
        "--deploy",
        "--venv-dir", "backend/.venv",
        "--requirements", "backend/requirements.txt",
        "--strict-reqs",
        "--verbose",
    ]
    try:
        res = subprocess.run(cmd, check=False, capture_output=True, text=True)
        if res.stdout: print(res.stdout, end="")
        if res.stderr: print(res.stderr, end="")
        if res.returncode != 0:
            print(f"[ERROR] Step 2 failed (exit {res.returncode})")
            return False
        print("[OK] Step 2 complete")
        return True
    except Exception as e:
        print(f"[ERROR] Step 2 error: {e}")
        return False

def main() -> int:
    ap = argparse.ArgumentParser(description="Deploy Steps 1+2")
    ap.add_argument("--help-only", action="store_true", help="Show help and exit")
    args, _ = ap.parse_known_args()

    if args.help_only:
        print("Run with no args to perform Step 1 + Step 2.")
        return 0

    if not check_requirements() or not check_local_files():
        return 1

    if not run_step_1():
        return 2

    if not run_step_2():
        return 3

    print("\n[SUCCESS] Steps 1 & 2 finished.")
    print("- Backend Python venv ready at backend/.venv")
    print("- Next: Step 3 (backend TOML/config) & Step 4 (frontend/Vite + proxy)")
    return 0

if __name__ == "__main__":
    sys.exit(main())
