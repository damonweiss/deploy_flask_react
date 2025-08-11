#!/usr/bin/env python3
"""
Python Env Bootloader (STEP 2)
- Resolves deployment root from VELA_CORE_DIR (or cwd)
- Ensures backend/ exists with a minimal Flask app
- Creates backend/.venv (or --venv-dir)
- Writes backend/requirements.txt (if missing) with Flask
- Installs requirements via uv (preferred) or pip (bootstraps pip if missing)
- Writes start_server.py and stop_servers.py at deployment root
- Optionally starts the Flask dev server now (--start-now)
"""

from __future__ import annotations
import os
import sys
import subprocess
import shutil
from pathlib import Path
import argparse
import textwrap

# ---------- helpers ----------

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

def write_requirements(requirements_path: Path) -> None:
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
            sys.stdout.write(res.stdout or "")
            sys.stderr.write(res.stderr or "")
            raise SystemError("uv venv failed")
        python_exe = str(venv_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python"))
        return venv_dir, python_exe

    res = subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], capture_output=True, text=True)
    if res.returncode != 0:
        sys.stdout.write(res.stdout or "")
        sys.stderr.write(res.stderr or "")
        raise SystemError("venv creation failed")
    python_exe = str(venv_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python"))
    return venv_dir, python_exe

def ensure_pip(python_exe: str) -> None:
    chk = subprocess.run([python_exe, "-m", "pip", "--version"], capture_output=True, text=True)
    if chk.returncode == 0:
        return
    ep = subprocess.run([python_exe, "-m", "ensurepip", "--upgrade"], capture_output=True, text=True)
    sys.stdout.write(ep.stdout or "")
    sys.stderr.write(ep.stderr or "")
    chk = subprocess.run([python_exe, "-m", "pip", "--version"], capture_output=True, text=True)
    if chk.returncode != 0:
        raise SystemError("pip is unavailable in the virtual environment")

def install_requirements(python_exe: str, requirements_path: Path) -> None:
    uv = shutil.which("uv")
    if uv:
        res = subprocess.run(
            [uv, "pip", "sync", str(requirements_path)],
            capture_output=True, text=True, cwd=str(requirements_path.parent)
        )
        sys.stdout.write(res.stdout or "")
        if res.returncode != 0:
            sys.stderr.write(res.stderr or "")
            raise SystemError("uv pip sync failed")
        return

    res = subprocess.run(
        [python_exe, "-m", "pip", "install", "-r", str(requirements_path)],
        capture_output=True, text=True, cwd=str(requirements_path.parent)
    )
    sys.stdout.write(res.stdout or "")
    if res.returncode != 0:
        sys.stderr.write(res.stderr or "")
        raise SystemError("pip install failed")

def write_run_scripts(root: Path, backend: Path, venv_path: Path) -> None:
    # Python control scripts at deployment root
    vela_run = root / ".vela-run"
    vela_run.mkdir(exist_ok=True)

    pid_dir = vela_run
    pid_file = pid_dir / "flask.pid"

    start_py = root / "start_server.py"
    stop_py = root / "stop_servers.py"

    if not start_py.exists():
        start_py.write_text(
            textwrap.dedent(
                """\
                #!/usr/bin/env python3
                import os, sys, subprocess, time
                from pathlib import Path

                def main():
                    root = Path(__file__).resolve().parent
                    backend = root / "backend"
                    venv = backend / ".venv"
                    pid_dir = root / ".vela-run"
                    pid_dir.mkdir(exist_ok=True)
                    pid_file = pid_dir / "flask.pid"

                    if pid_file.exists():
                        try:
                            old_pid = int(pid_file.read_text().strip())
                        except Exception:
                            old_pid = None
                        if old_pid:
                            print(f"[start] Flask already appears to be running (pid={old_pid}).")
                            print("Use: python stop_servers.py")
                            return 0

                    python_exe = str(venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python"))
                    if not Path(python_exe).exists():
                        python_exe = sys.executable

                    env = os.environ.copy()
                    env["FLASK_APP"] = "app.main:create_app"
                    env["PYTHONPATH"] = str(backend)
                    env.setdefault("FLASK_RUN_HOST", "127.0.0.1")
                    env.setdefault("FLASK_RUN_PORT", "5000")

                    cmd = [python_exe, "-m", "flask", "run", "--debug",
                           "--host", env["FLASK_RUN_HOST"], "--port", env["FLASK_RUN_PORT"]]

                    proc = subprocess.Popen(
                        cmd, cwd=str(backend), env=env,
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
                    )
                    with pid_file.open("w", encoding="utf-8") as f:
                        f.write(str(proc.pid))

                    print(f"[start] Flask dev server starting (pid={proc.pid}) at http://{env['FLASK_RUN_HOST']}:{env['FLASK_RUN_PORT']}")
                    print("[start] Tailing first few lines (Ctrl+C to detach)...")
                    try:
                        for _ in range(30):
                            line = proc.stdout.readline()
                            if not line:
                                break
                            sys.stdout.write(line)
                            sys.stdout.flush()
                    except KeyboardInterrupt:
                        pass
                    return 0

                if __name__ == "__main__":
                    sys.exit(main())
                """
            ),
            encoding="utf-8",
        )

    if not stop_py.exists():
        stop_py.write_text(
            textwrap.dedent(
                """\
                #!/usr/bin/env python3
                import os, sys, time, signal, subprocess
                from pathlib import Path

                def kill_tree_windows(pid: int) -> None:
                    # /T kills process tree, /F forces
                    subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                                   capture_output=True, text=True)

                def main():
                    root = Path(__file__).resolve().parent
                    pid_file = root / ".vela-run" / "flask.pid"
                    if not pid_file.exists():
                        print("[stop] No pid file found. Nothing to stop.")
                        return 0
                    try:
                        pid = int(pid_file.read_text().strip())
                    except Exception:
                        print("[stop] Invalid pid file.")
                        pid_file.unlink(missing_ok=True)
                        return 0

                    print(f"[stop] Stopping Flask server pid={pid}...")
                    if os.name == "nt":
                        kill_tree_windows(pid)
                    else:
                        try:
                            os.kill(pid, signal.SIGTERM)
                        except ProcessLookupError:
                            pass

                    # Small grace period
                    time.sleep(0.5)
                    pid_file.unlink(missing_ok=True)
                    print("[stop] Stopped.")
                    return 0

                if __name__ == "__main__":
                    sys.exit(main())
                """
            ),
            encoding="utf-8",
        )

    # Optional convenience wrapper for Windows users
    run_bat = root / "run_dev.bat"
    if os.name == "nt" and not run_bat.exists():
        run_bat.write_text(
            "@echo off\r\n"
            "python start_server.py\r\n",
            encoding="utf-8",
        )

def start_now(root: Path) -> None:
    # Start immediately by invoking start_server.py
    start_py = root / "start_server.py"
    if not start_py.exists():
        return
    subprocess.run([sys.executable, str(start_py)], check=False)

# ---------- main ----------

def main() -> int:
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--deploy", action="store_true", help="Run env setup")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--venv-dir", default="backend/.venv")
    ap.add_argument("--requirements", default="backend/requirements.txt")
    ap.add_argument("--strict-reqs", action="store_true", help="Fail if requirements missing")
    ap.add_argument("--config")
    ap.add_argument("--start-now", action="store_true", help="Start Flask immediately after install")
    args, _ = ap.parse_known_args()

    root = resolve_deployment_root()
    if args.verbose:
        print(f"[STEP2] VELA_CORE_DIR={os.environ.get('VELA_CORE_DIR')}")
        print(f"[STEP2] deployment_root={root}")
        print(f"[STEP2] argv={sys.argv}")

    backend = ensure_backend(root)

    venv_dir = Path(args.venv_dir)
    if not venv_dir.is_absolute():
        venv_dir = (root / venv_dir).resolve()

    reqs_path = Path(args.requirements)
    if not reqs_path.is_absolute():
        reqs_path = (root / reqs_path).resolve()

    try:
        if not reqs_path.exists():
            # First run: auto-create default requirements unless user explicitly asked strict for a custom path
            if args.strict_reqs and args.requirements != "backend/requirements.txt":
                print(f"[STEP2] --strict-reqs set and requirements file missing: {reqs_path}")
                return 2
            write_requirements(reqs_path)

        venv_path, python_exe = create_venv(venv_dir)
        ensure_pip(python_exe)

        if args.verbose:
            print(f"[STEP2] venv={venv_path}")
            p
