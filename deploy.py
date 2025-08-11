#!/usr/bin/env python3
"""
Deploy: Step 1 (structure) + Step 2 (python env + Flask) + Step 4 (Vite)
- Step 1: create folder structure (folder_bootloader.py)
- Step 2: create backend venv + install Flask + write start/stop scripts
- Step 4: install React/Vite, proxy to Flask, upgrade start/stop to manage both

Usage:
  python deploy.py                 # Run steps 1,2 (+ start Flask), then 4 if npm is available
  python deploy.py --no-start      # Do not start servers automatically
  python deploy.py --skip-vite     # Skip Vite step even if npm exists
  python deploy.py --skip-step1    # Skip folder structure step
  python deploy.py --skip-step2    # Skip Python env step
  python deploy.py --force-vite    # Run Vite step even if npm isn't detected
  python deploy.py --python 3.12   # Choose venv Python (default 3.12; or set VELA_PYTHON)
  python deploy.py --allow-build   # Allow building MarkupSafe from source if needed
  python deploy.py --help-only
"""

from __future__ import annotations
import os
import sys
import subprocess
from pathlib import Path
import argparse
import shutil

THIS_DIR = Path(__file__).resolve().parent

# ---------- utils ----------

def have_npm() -> bool:
    try:
        subprocess.run(["npm", "--version"], capture_output=True, text=True, check=True)
        return True
    except Exception:
        return False

def run_cmd(cmd: list[str], cwd: Path | None = None) -> int:
    """Run a command, stream stdout/stderr live, return exit code."""
    proc = subprocess.Popen(
        cmd,
        cwd=str(cwd) if cwd else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        shell=False,  # keep False; cross-platform and safe
    )
    try:
        assert proc.stdout is not None
        for line in proc.stdout:
            sys.stdout.write(line)
        proc.wait()
        return proc.returncode or 0
    except KeyboardInterrupt:
        try:
            proc.terminate()
        except Exception:
            pass
        return 130

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

def check_local_files(skip1: bool, skip2: bool, skip_vite: bool) -> bool:
    missing = []
    if not skip1 and not (THIS_DIR / "folder_bootloader.py").exists():
        missing.append("folder_bootloader.py")
    if not skip2 and not (THIS_DIR / "python_env_bootloader.py").exists():
        missing.append("python_env_bootloader.py")
    # vite_bootloader.py is optional unless forced
    if missing:
        print(f"[ERROR] Missing required file(s): {', '.join(missing)}")
        return False
    if not (THIS_DIR / "bootloader_config.json").exists():
        print("[INFO] bootloader_config.json not found — Step 1 will use defaults")
    return True

def resolve_deployment_root() -> Path:
    core_dir = os.environ.get("VELA_CORE_DIR")
    if core_dir:
        p = Path(core_dir).resolve()
        try:
            return p.parents[3]  # cores -> .vela -> data -> <deployment_root>
        except IndexError:
            pass
    return THIS_DIR

# ---------- steps ----------

def run_step_1() -> bool:
    print("\n=== STEP 1: Folder Structure Creation ===")
    cmd = [sys.executable, str(THIS_DIR / "folder_bootloader.py"), "--deploy"]
    rc = run_cmd(cmd, cwd=THIS_DIR)
    if rc != 0:
        print(f"[ERROR] Step 1 failed (exit {rc})")
        return False
    print("[OK] Step 1 complete")
    return True

def run_step_2(start_now: bool, python_target: str, allow_build: bool) -> bool:
    print("\n=== STEP 2: Python Env Setup (backend) ===")
    cmd = [
        sys.executable,
        str(THIS_DIR / "python_env_bootloader.py"),
        "--deploy",
        "--venv-dir", "backend/.venv",
        "--requirements", "backend/requirements.txt",
        "--python", python_target,
        "--verbose",
    ]
    if start_now:
        cmd.append("--start-now")
    if allow_build:
        cmd.append("--allow-build")

    rc = run_cmd(cmd, cwd=THIS_DIR)
    if rc != 0:
        print(f"[ERROR] Step 2 failed (exit {rc})")
        return False
    print("[OK] Step 2 complete")
    return True

def run_step_4_vite(force_vite: bool) -> bool:
    print("\n=== STEP 4: Frontend (Vite + React) ===")
    vite_py = THIS_DIR / "vite_bootloader.py"
    if not vite_py.exists():
        print("[INFO] vite_bootloader.py not found — skipping Vite step.")
        return True if not force_vite else False

    if not have_npm() and not force_vite:
        print("[INFO] npm not detected — skipping Vite step. (Use --force-vite to try anyway.)")
        return True

    cmd = [sys.executable, str(vite_py), "--deploy"]
    rc = run_cmd(cmd, cwd=THIS_DIR)
    if rc != 0:
        print(f"[ERROR] Step 4 (Vite) failed (exit {rc})")
        return False
    print("[OK] Step 4 complete")
    return True

def stop_existing_if_any(root: Path) -> None:
    """Best-effort: stop previously running servers to avoid port/PID conflicts."""
    stop_py = root / "stop_servers.py"
    if stop_py.exists():
        print("\n[INFO] Stopping any existing servers...")
        run_cmd([sys.executable, str(stop_py)], cwd=root)

def final_hint(root: Path, started: bool, ran_vite: bool) -> None:
    print("\n[SUCCESS] Deploy finished.")
    print(f"- Root: {root}")
    print("- Backend venv: backend/.venv")
    print("- Flask: http://127.0.0.1:5000  (health: /api/health)")
    if ran_vite:
        print("- Vite:  http://127.0.0.1:5173  (proxy /api → Flask)")
    print("- Start both later:  python start_server.py")
    print("- Stop both:         python stop_servers.py")
    if not started:
        print("\n[NOTE] You used --no-start. Run `python start_server.py` when ready.")

# ---------- entry ----------

def main() -> int:
    ap = argparse.ArgumentParser(description="Deploy Steps 1 + 2 (+ 4 Vite)")
    ap.add_argument("--help-only", action="store_true", help="Show help and exit")
    ap.add_argument("--no-start", action="store_true", help="Do not start servers automatically")
    ap.add_argument("--skip-vite", action="store_true", help="Skip Step 4 (Vite) even if npm is available")
    ap.add_argument("--skip-step1", action="store_true", help="Skip Step 1 (folder structure)")
    ap.add_argument("--skip-step2", action="store_true", help="Skip Step 2 (python env)")
    ap.add_argument("--force-vite", action="store_true", help="Run Vite step even if npm not detected")
    ap.add_argument("--python", default=os.environ.get("VELA_PYTHON", "3.12"),
                    help="Target Python for the venv (major.minor or full path). Defaults to env VELA_PYTHON or 3.12.")
    ap.add_argument("--allow-build", action="store_true",
                    help="Allow building MarkupSafe from source if no wheels (needs C build tools).")
    args, _ = ap.parse_known_args()

    if args.help_only:
        print(__doc__.strip())
        return 0

    if not check_requirements():
        return 1
    if not check_local_files(args.skip_step1, args.skip_step2, args.skip_vite):
        return 1

    root = resolve_deployment_root()

    # Avoid duplicate instances from a previous run
    stop_existing_if_any(root)

    # Step 1
    if not args.skip_step1 and not run_step_1():
        return 2

    # Step 2
    started = not args.no_start
    if not args.skip_step2 and not run_step_2(start_now=started, python_target=args.python, allow_build=args.allow_build):
        return 3

    # Step 4 (Vite)
    ran_vite = False
    if not args.skip_vite:
        ok = run_step_4_vite(force_vite=args.force_vite)
        if not ok:
            if args.force_vite:
                return 4
            print("[WARN] Vite step skipped/failed; backend is still ready.")
        else:
            ran_vite = True

    # If we started Flask and we also ran Vite, re-run unified starter
    if started and ran_vite:
        print("\n[INFO] Starting unified dev servers (Flask + Vite)...")
        run_cmd([sys.executable, str(root / "start_server.py")], cwd=root)

    final_hint(root, started, ran_vite)
    return 0

if __name__ == "__main__":
    sys.exit(main())
