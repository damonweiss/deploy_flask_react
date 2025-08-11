#!/usr/bin/env python3
"""
Python Env Bootloader (STEP 2)
- Resolves deployment root from VELA_CORE_DIR (or cwd)
- Ensures backend/ exists
- Creates backend/.venv (or given --venv-dir)
- Writes backend/requirements.txt (if missing)
- Installs requirements via uv (preferred) or pip (bootstraps pip if missing)
"""

from __future__ import annotations
import os
import sys
import subprocess
import shutil
from pathlib import Path
import argparse
import textwrap

def resolve_deployment_root() -> Path:
    core_dir = os.environ.get("VELA_CORE_DIR")
    if core_dir:
        p = Path(core_dir).resolve()
        # cores -> .vela -> data -> <deployment_root>
        try:
            return p.parents[3]
        except IndexError:
            pass
    return Path.cwd().resolve()

def ensure_backend(root: Path) -> Path:
    backend = root / "backend"
    (backend / "app").mkdir(parents=True, exist_ok=True)
    init_py = backend / "app" / "__init__.py"
    main_py = backend / "app" / "main.py"
    if not init_py.exists():
        init_py.write_text("# Flask app init\n", encoding="utf-8")
    if not main_py.exists():
        main_py.write_text(
            textwrap.dedent(
                """\
                from flask import Flask, jsonify

                def create_app():
                    app = Flask(__name__)

                    @app.get("/api/health")
                    def health():
                        return jsonify({"status": "ok"})

                    return app

                if __name__ == "__main__":
                    app = create_app()
                    app.run(host="127.0.0.1", port=5000, debug=True)
                """
            ),
            encoding="utf-8",
        )
    return backend

def write_requirements(backend: Path, requirements_path: Path) -> None:
    if requirements_path.exists():
        return
    requirements_path.parent.mkdir(parents=True, exist_ok=True)
    reqs = [
        "flask>=3.0,<4",
        # "python-dotenv>=1.0,<2",
    ]
    requirements_path.write_text("\n".join(reqs) + "\n", encoding="utf-8")

def create_venv(venv_dir: Path) -> tuple[Path, str]:
    venv_dir.mkdir(parents=True, exist_ok=True)
    uv = shutil.which("uv")
    if uv:
        res = subprocess.run([uv, "venv", str(venv_dir)], capture_output=True, text=True)
        if res.returncode != 0:
            print(res.stdout, end="")
            print(res.stderr, end="")
            raise SystemError("uv venv failed")
        python_exe = str(venv_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python"))
        return venv_dir, python_exe

    res = subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], capture_output=True, text=True)
    if res.returncode != 0:
        print(res.stdout, end="")
        print(res.stderr, end="")
        raise SystemError("venv creation failed")
    python_exe = str(venv_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python"))
    return venv_dir, python_exe

def ensure_pip(python_exe: str) -> None:
    chk = subprocess.run([python_exe, "-m", "pip", "--version"], capture_output=True, text=True)
    if chk.returncode == 0:
        return
    ep = subprocess.run([python_exe, "-m", "ensurepip", "--upgrade"], capture_output=True, text=True)
    print(ep.stdout, end="")
    print(ep.stderr, end="")
    chk = subprocess.run([python_exe, "-m", "pip", "--version"], capture_output=True, text=True)
    if chk.returncode != 0:
        raise SystemError("pip is unavailable in the virtual environment")

def install_requirements(python_exe: str, requirements_path: Path) -> None:
    uv = shutil.which("uv")
    if uv:
        res = subprocess.run([uv, "pip", "sync", str(requirements_path)],
                             capture_output=True, text=True, cwd=str(requirements_path.parent))
        print(res.stdout, end="")
        if res.returncode != 0:
            print(res.stderr, end="")
            raise SystemError("uv pip sync failed")
        return

    res = subprocess.run([python_exe, "-m", "pip", "install", "-r", str(requirements_path)],
                         capture_output=True, text=True, cwd=str(requirements_path.parent))
    print(res.stdout, end="")
    if res.returncode != 0:
        print(res.stderr, end="")
        raise SystemError("pip install failed")

def main() -> int:
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--deploy", action="store_true", help="Run env setup")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--venv-dir", default="backend/.venv")
    ap.add_argument("--requirements", default="backend/requirements.txt")
    ap.add_argument("--strict-reqs", action="store_true", help="Fail if requirements missing")
    ap.add_argument("--config")
    args, _ = ap.parse_known_args()

    root = resolve_deployment_root()
    if args.verbose:
        print(f"[STEP2] VELA_CORE_DIR={os.environ.get('VELA_CORE_DIR')}")
        print(f"[STEP2] deployment_root={root}")
        print(f"[STEP2] argv={sys.argv}")

    backend = ensure_backend(root)
    venv_dir = (root / args.venv_dir).resolve() if not Path(args.venv_dir).is_absolute() else Path(args.venv_dir)
    reqs_path = (root / args.requirements).resolve() if not Path(args.requirements).is_absolute() else Path(args.requirements)

    try:
        if not reqs_path.exists():
            # For first run, auto-create requirements unless user explicitly asked for strict
            if args.strict_reqs and args.requirements != "backend/requirements.txt":
                print(f"[STEP2] --strict-reqs set and requirements file missing: {reqs_path}")
                return 2
            write_requirements(backend, reqs_path)

        venv_path, python_exe = create_venv(venv_dir)
        ensure_pip(python_exe)

        if args.verbose:
            print(f"[STEP2] venv={venv_path}")
            print(f"[STEP2] python={python_exe}")
            print(f"[STEP2] requirements={reqs_path}")

        install_requirements(python_exe, reqs_path)

        # Convenience run script
        run_sh = backend / ("run_dev.bat" if os.name == "nt" else "run_dev.sh")
        if not run_sh.exists():
            if os.name == "nt":
                content = (
                    "@echo off\n"
                    'call "{}\\Scripts\\activate"\n'
                    "python -m flask --app app.main:create_app run --debug --port 5000\n"
                ).format(venv_path)
                run_sh.write_text(content, encoding="utf-8")
            else:
                content = (
                    "#!/usr/bin/env bash\n"
                    'source "{}/bin/activate"\n'
                    "python -m flask --app app.main:create_app run --debug --port 5000\n"
                ).format(venv_path)
                run_sh.write_text(content, encoding="utf-8")
                run_sh.chmod(0o755)

