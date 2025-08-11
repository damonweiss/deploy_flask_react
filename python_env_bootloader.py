#!/usr/bin/env python3
"""
Python Env Bootloader (STEP 2)
- Resolves deployment root from VELA_CORE_DIR (or cwd)
- Ensures backend/ exists
- Creates backend/.venv (or given --venv-dir)
- Writes backend/requirements.txt (if missing)
- Installs requirements via uv (preferred) or pip
"""

from __future__ import annotations
import os, sys, subprocess, shutil
from pathlib import Path
import argparse
import textwrap

def resolve_deployment_root() -> Path:
    core_dir = os.environ.get("VELA_CORE_DIR")
    if core_dir:
        p = Path(core_dir).resolve()
        # Expect: cores -> .vela -> data -> <deployment_root>
        # Walk up 4 levels safely; fallback to cwd if not enough parents
        try:
            root = p.parents[3]
            return root
        except IndexError:
            pass
    return Path.cwd().resolve()

def ensure_backend(root: Path) -> Path:
    backend = root / "backend"
    backend.mkdir(parents=True, exist_ok=True)
    (backend / "app").mkdir(parents=True, exist_ok=True)
    # Seed minimal Flask app if not present
    init_py = backend / "app" / "__init__.py"
    main_py = backend / "app" / "main.py"
    if not init_py.exists():
        init_py.write_text("# Flask app init\n", encoding="utf-8")
    if not main_py.exists():
        main_py.write_text(
            textwrap.dedent("""\
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
            """),
            encoding="utf-8",
        )
    return backend

def write_requirements(backend: Path, requirements_path: Path, strict: bool) -> None:
    if requirements_path.exists():
        return
    # Keep it minimal; you can expand later
    reqs = [
        "flask>=3.0,<4",
        # "python-dotenv>=1.0,<2",  # uncomment if you want .env support
    ]
    requirements_path.write_text("\n".join(reqs) + "\n", encoding="utf-8")

def create_venv(venv_dir: Path) -> tuple[Path, str]:
    venv_dir.mkdir(parents=True, exist_ok=True)
    # Try uv first
    uv = shutil.which("uv")
    if uv:
        # uv venv creates if missing; no-op if exists
        cmd = [uv, "venv", str(venv_dir)]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            print(res.stdout, end="")
            print(res.stderr, end="")
            raise SystemError("uv venv failed")
        py = str(venv_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python"))
        return venv_dir, py

    # Fallback: python -m venv
    res = subprocess.run([sys.executable, "-m", "venv", str(venv_dir)],
                         capture_output=True, text=True)
    if res.returncode != 0:
        print(res.stdout, end="")
        print(res.stderr, end="")
        raise SystemError("venv creation failed")
    py = str(venv_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python"))
    return venv_dir, py

def install_requirements(python_exe: str, requirements_path: Path) -> None:
    uv = shutil.which("uv")
    if uv:
        cmd = [uv, "pip", "sync", str(requirements_path)]
        res = subprocess.run(cmd, capture_output=True, text=True, cwd=str(requirements_path.parent))
        print(res.stdout, end="")
        if res.returncode != 0:
            print(res.stderr, end="")
            raise SystemError("uv pip sync failed")
        return

    # Fallback to pip
    cmd = [python_exe, "-m", "pip", "install", "-r", str(requirements_path)]
    res = subprocess.run(cmd, capture_output=True, text=True, cwd=str(requirements_path.parent))
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
    ap.add_argument("--config")  # reserved
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
            # Only fail strict if user provided a non-default path explicitly
            default_req = (args.requirements == "backend/requirements.txt")
            if args.strict_reqs and not default_req:
             print(f"[STEP2] --strict-reqs set and requirements file missing: {reqs_path}")
             return 2
         write_requirements(backend, reqs_path, strict=args.strict_reqs)

        venv_path, python_exe = create_venv(venv_dir)
        if args.verbose:
            print(f"[STEP2] venv={venv_path}")
            print(f"[STEP2] python={python_exe}")
            print(f"[STEP2] requirements={reqs_path}")

        install_requirements(python_exe, reqs_path)

        # Create a tiny run script for convenience
        run_sh = backend / ("run_dev.bat" if os.name == "nt" else "run_dev.sh")
        if not run_sh.exists():
            if os.name == "nt":
                run_sh.write_text(
                    textwrap.dedent(f"""\
                    @echo off
                    call "{venv_path}\\Scripts\\activate"
                    python -m flask --app app.main:create_app run --debug --port 5000
                    """),
                    encoding="utf-8",
                )
            else:
                run_sh.write_text(
                    textwrap.dedent(f"""\
                    #!/usr/bin/env bash
                    source "{venv_path}/bin/activate"
                    python -m flask --app app.main:create_app run --debug --port 5000
                    """),
                    encoding="utf-8",
                )
                run_sh.chmod(0o755)

        print(f"[STEP2] Backend venv ready: {venv_path}")
        print(f"[STEP2] Requirements installed from: {reqs_path}")
        print("[STEP2] Python Env Bootloader: SUCCESS")
        return 0

    except KeyboardInterrupt:
        print("[STEP2] Interrupted")
        return 130
    except Exception as e:
        print(f"[STEP2] ERROR: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
