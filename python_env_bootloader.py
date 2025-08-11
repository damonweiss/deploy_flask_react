#!/usr/bin/env python3
"""
Python Env Bootloader (Step 2, tolerant)
- Creates/repairs .venv (HARD-REQUIREMENT; only hard-fails here)
- Tries pip bootstrap/upgrade (non-fatal if it fails)
- Installs requirements.txt if present (non-fatal unless --strict-reqs)

Usage:
  python python_env_bootloader.py --deploy [--verbose]
  python python_env_bootloader.py --deploy --venv-dir .venv --requirements requirements.txt
  python python_env_bootloader.py --deploy --strict-reqs
"""

from __future__ import annotations
import argparse, logging, os, sys, subprocess, shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEFAULT_VENV = ROOT / ".venv"
DEFAULT_REQS = ROOT / "requirements.txt"

def setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='[%(asctime)s] %(levelname)s - %(message)s',
        handlers=[logging.FileHandler(ROOT / "deployment.log", encoding="utf-8"),
                  logging.StreamHandler()]
    )

log = logging.getLogger(__name__)

def run(cmd: list[str], title: str, fatal: bool) -> bool:
    """Run a command; if fatal=True, raise on failure; else warn and continue."""
    log.info("=" * 60)
    log.info("%s - starting", title)
    log.info("Command: %s", " ".join(cmd))
    try:
        res = subprocess.run(cmd, check=True, capture_output=True, text=True)
        if res.stdout:
            log.info("%s STDOUT:", title)
            for line in res.stdout.strip().splitlines():
                if line.strip(): log.info("  %s", line)
        if res.stderr:
            log.warning("%s STDERR:", title)
            for line in res.stderr.strip().splitlines():
                if line.strip(): log.warning("  %s", line)
        log.info("%s - success", title)
        return True
    except subprocess.CalledProcessError as e:
        log.error("%s - FAILED (exit %s)", title, e.returncode)
        if e.stdout:
            log.error("%s STDOUT:", title)
            for line in e.stdout.strip().splitlines():
                if line.strip(): log.error("  %s", line)
        if e.stderr:
            log.error("%s STDERR:", title)
            for line in e.stderr.strip().splitlines():
                if line.strip(): log.error("  %s", line)
        if fatal:
            raise
        else:
            log.warning("%s failed but continuing (non-fatal)", title)
            return False

def venv_bins(venv_dir: Path) -> tuple[Path, Path]:
    if os.name == "nt":
        py = venv_dir / "Scripts" / "python.exe"
        pip = venv_dir / "Scripts" / "pip.exe"
    else:
        py = venv_dir / "bin" / "python"
        pip = venv_dir / "bin" / "pip"
    return py, pip

def ensure_venv(venv_dir: Path) -> None:
    if not venv_dir.exists():
        run([sys.executable, "-m", "venv", str(venv_dir)], "Create venv", fatal=True)
    else:
        log.info("Venv already exists at %s", venv_dir)
    py_bin, pip_bin = venv_bins(venv_dir)
    # Try to ensure pip (non-fatal)
    if not pip_bin.exists():
        run([str(py_bin), "-m", "ensurepip", "--upgrade"], "ensurepip", fatal=False)
    # Try to upgrade tooling (non-fatal)
    run([str(py_bin), "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"],
        "Upgrade pip/setuptools/wheel", fatal=False)

def install_requirements(venv_dir: Path, reqs_file: Path, strict: bool) -> None:
    if not reqs_file.exists():
        log.info("No requirements file at %s (skipping)", reqs_file)
        return
    py_bin, _ = venv_bins(venv_dir)
    run([str(py_bin), "-m", "pip", "install", "-r", str(reqs_file)],
        f"Install requirements from {reqs_file.name}", fatal=strict)

def main() -> int:
    ap = argparse.ArgumentParser(description="Python Env Bootloader (Step 2, tolerant)")
    ap.add_argument("--deploy", action="store_true", help="Execute environment setup")
    ap.add_argument("--venv-dir", default=str(DEFAULT_VENV))
    ap.add_argument("--requirements", default=str(DEFAULT_REQS))
    ap.add_argument("--strict-reqs", action="store_true", help="Fail if requirements install fails")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    setup_logging(args.verbose)
    venv_dir = Path(args.venv_dir).resolve()
    reqs = Path(args.requirements).resolve()

    log.info("Step 2: Python Environment Setup")
    log.info("Python exe: %s", sys.executable)
    log.info("Repo root : %s", ROOT)
    log.info("Venv dir  : %s", venv_dir)
    log.info("Reqs file : %s", reqs)
    log.info("Strict reqs: %s", args.strict_reqs)

    if not args.deploy:
        log.info("Nothing to do (run with --deploy).")
        return 0

    # HARD requirement: venv creation
    ensure_venv(venv_dir)

    # Best-effort: requirements
    install_requirements(venv_dir, reqs, strict=args.strict_reqs)

    log.info("Step 2 complete (tolerant).")
    return 0

if __name__ == "__main__":
    log.info("Trying...")
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        logging.getLogger(__name__).error("Interrupted by user")
        sys.exit(1)
    except Exception:
        import traceback
        traceback.print_exc()
        sys.exit(1)
