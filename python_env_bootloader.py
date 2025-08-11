#!/usr/bin/env python3
"""
Python Env Bootloader (Step 2)
- Creates/repairs a .venv
- Upgrades pip/setuptools/wheel
- Optionally installs requirements.txt if present

Usage:
  python python_env_bootloader.py --deploy
  python python_env_bootloader.py --deploy --venv-dir .venv
  python python_env_bootloader.py --deploy --requirements requirements.txt
  python python_env_bootloader.py --verbose
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import subprocess
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEFAULT_VENV = ROOT / ".venv"
DEFAULT_REQS = ROOT / "requirements.txt"

def setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='[%(asctime)s] %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(ROOT / "deployment.log", encoding="utf-8"),
            logging.StreamHandler()
        ]
    )

log = logging.getLogger(__name__)

def run(cmd: list[str], title: str) -> None:
    """Run a command, log stdout/stderr nicely, raise on failure."""
    log.info("=" * 60)
    log.info("%s - starting", title)
    log.info("Command: %s", " ".join(cmd))
    try:
        res = subprocess.run(cmd, check=True, capture_output=True, text=True)
        if res.stdout:
            log.info("%s STDOUT:", title)
            for line in res.stdout.strip().splitlines():
                if line.strip():
                    log.info("  %s", line)
        if res.stderr:
            log.warning("%s STDERR:", title)
            for line in res.stderr.strip().splitlines():
                if line.strip():
                    log.warning("  %s", line)
        log.info("%s - success", title)
    except subprocess.CalledProcessError as e:
        log.error("%s - FAILED (exit %s)", title, e.returncode)
        if e.stdout:
            log.error("%s STDOUT:", title)
            for line in e.stdout.strip().splitlines():
                if line.strip():
                    log.error("  %s", line)
        if e.stderr:
            log.error("%s STDERR:", title)
            for line in e.stderr.strip().splitlines():
                if line.strip():
                    log.error("  %s", line)
        raise

def venv_bins(venv_dir: Path) -> tuple[Path, Path]:
    """Return (python_bin, pip_bin) inside the venv (Windows/Linux)."""
    if os.name == "nt":
        py = venv_dir / "Scripts" / "python.exe"
        pip = venv_dir / "Scripts" / "pip.exe"
    else:
        py = venv_dir / "bin" / "python"
        pip = venv_dir / "bin" / "pip"
    return py, pip

def ensure_venv(venv_dir: Path) -> None:
    """Create venv if missing; repair ensurepip/pip if needed."""
    if not venv_dir.exists():
        run([sys.executable, "-m", "venv", str(venv_dir)], "Create venv")
    else:
        log.info("Venv already exists at %s", venv_dir)

    py_bin, pip_bin = venv_bins(venv_dir)

    # Sometimes pip isn't present; ensurepip then upgrade
    if not pip_bin.exists():
        log.warning("pip not found in venv; running ensurepip")
        run([str(py_bin), "-m", "ensurepip", "--upgrade"], "ensurepip")

    # Upgrade core tooling
    run([str(py_bin), "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"], "Upgrade pip/setuptools/wheel")

def install_requirements(venv_dir: Path, reqs_file: Path) -> None:
    if not reqs_file.exists():
        log.info("No requirements file found at %s (skipping)", reqs_file)
        return
    py_bin, _ = venv_bins(venv_dir)
    run([str(py_bin), "-m", "pip", "install", "-r", str(reqs_file)], f"Install requirements from {reqs_file.name}")

def main() -> int:
    parser = argparse.ArgumentParser(description="Python Env Bootloader (Step 2)")
    parser.add_argument("--deploy", action="store_true", help="Execute environment setup")
    parser.add_argument("--venv-dir", type=str, default=str(DEFAULT_VENV), help="Venv directory (default: .venv)")
    parser.add_argument("--requirements", type=str, default=str(DEFAULT_REQS), help="Requirements file (default: requirements.txt)")
    parser.add_argument("--verbose", action="store_true", help="DEBUG logging")
    args = parser.parse_args()

    setup_logging(args.verbose)

    venv_dir = Path(args.venv_dir).resolve()
    reqs = Path(args.requirements).resolve()

    log.info("Step 2: Python Environment Setup")
    log.info("Python exe: %s", sys.executable)
    log.info("Repo root: %s", ROOT)
    log.info("Venv dir : %s", venv_dir)
    log.info("Reqs file: %s", reqs)

    if not args.deploy:
        log.info("Nothing to do (run with --deploy).")
        return 0

    # Create/repair venv
    ensure_venv(venv_dir)

    # Install requirements if present
    install_requirements(venv_dir, reqs)

    log.info("Step 2 complete.")
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        log = logging.getLogger(__name__)
        log.error("Interrupted by user")
        sys.exit(1)
    except Exception:
        # Force non-zero exit and let deploy.py surface the traceback summary
        import traceback
        traceback.print_exc()
        sys.exit(1)
