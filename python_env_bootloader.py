#!/usr/bin/env python3
"""
Python Env Bootloader (STEP 2)
- Ensures backend with a minimal Flask app (/api/health)
- Creates backend/.venv using a target Python (default 3.12)
- Writes backend/requirements.txt (Flask + deps incl. MarkupSafe)
- Installs via uv or pip
- Verifies imports; remediates MarkupSafe on Win/Py3.13
- Writes start/stop scripts; supports --start-now and --allow-build
"""

from __future__ import annotations
import os, sys, subprocess, shutil, argparse, textwrap, signal
from pathlib import Path

# ----------------- helpers -----------------

def resolve_deployment_root() -> Path:
    core_dir = os.environ.get("VELA_CORE_DIR")
    if core_dir:
        p = Path(core_dir).resolve()
        try:
            return p.parents[3]  # cores -> .vela -> data -> <root>
        except IndexError:
            pass
    return Path.cwd().resolve()

def ensure_backend(root: Path) -> Path:
    backend = root / "backend"
    app_dir = backend / "app"
    app_dir.mkdir(parents=True, exist_ok=True)

    init_py = app_dir / "__init__.py"
    if not init_py.exists():
        init_py.write_text("# Flask app package\n", encoding="utf-8")

    main_py = app_dir / "main.py"
    if not main_py.exists():
        main_py.write_text(textwrap.dedent("""\
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
        """), encoding="utf-8")
    return backend

BASE_REQS = [
    "Flask>=3.0,<4",
    "Werkzeug>=3.0,<4",
    "Click>=8.1,<9",
    "itsdangerous>=2.1,<3",
    "Jinja2>=3.1,<4",
    "MarkupSafe>=2.1,<3",
]

def write_requirements(requirements_path: Path) -> None:
    if requirements_path.exists():
        return
    requirements_path.parent.mkdir(parents=True, exist_ok=True)
    reqs = [
        "flask>=3.0,<4",
        "blinker>=1.7,<2",
        "werkzeug>=3.0,<4",
        "Jinja2>=3.1,<4",
        "itsdangerous>=2.2,<3",
        "click>=8.1,<9",
        # "python-dotenv>=1.0,<2",  # optional
    ]
    requirements_path.write_text("\n".join(reqs) + "\n", encoding="utf-8")

def ensure_minimum_stack(requirements_path: Path) -> None:
    needed = {
        "blinker": "blinker>=1.7,<2",
        "werkzeug": "werkzeug>=3.0,<4",
        "jinja2": "Jinja2>=3.1,<4",
        "itsdangerous": "itsdangerous>=2.2,<3",
        "click": "click>=8.1,<9",
    }
    try:
        lines = requirements_path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return
    have = {line.strip().split("==")[0].split(">=")[0].lower() for line in lines if line.strip() and not line.strip().startswith("#")}
    changed = False
    for k, v in needed.items():
        if k not in have:
            lines.append(v)
            changed = True
    if changed:
        requirements_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _detect_python_for_version(version: str) -> str | None:
    """
    Try to find an interpreter for the requested major.minor.
    - Windows: use 'py -X.Y'
    - POSIX: try 'pythonX.Y' on PATH
    - If 'version' looks like a path, use it directly.
    """
    if not version:
        return None
    # Explicit path?
    v = version.strip().strip('"').strip("'")
    if os.path.sep in v or (os.name == "nt" and ":" in v):
        return v  # treat as path
    if os.name == "nt":
        # We'll drive the 'py' launcher via create_venv; return sentinel
        return f"py:{v}"
    return shutil.which(f"python{v}") or shutil.which("python3")  # best effort

def _python_version_str(py: str) -> str:
    r = subprocess.run([py, "-c", "import sys;print(f'{sys.version_info[0]}.{sys.version_info[1]}')"],
                       capture_output=True, text=True)
    return (r.stdout or "").strip() if r.returncode == 0 else "unknown"

def create_venv(venv_dir: Path, desired_python: str | None) -> tuple[Path, str]:
    """
    Create venv with target Python when possible.
    - If uv is available, use: uv venv --python <ver|path> venv_dir
    - Else:
      * Windows: if desired 'py:X.Y', call: py -X.Y -m venv venv_dir
      * POSIX:   if we found an interpreter path, call: <path> -m venv venv_dir
      * Fallback: sys.executable -m venv venv_dir
    """
    venv_dir.mkdir(parents=True, exist_ok=True)
    uv = shutil.which("uv")

    # Resolve desired interpreter hint
    py_hint = _detect_python_for_version(desired_python) if desired_python else None

    if uv:
        cmd = ["uv", "venv"]
        if desired_python:
            cmd += ["--python", desired_python]
        cmd += [str(venv_dir)]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode:
            sys.stdout.write(r.stdout or ""); sys.stderr.write(r.stderr or "")
            raise SystemError("uv venv failed")
    else:
        if os.name == "nt" and isinstance(py_hint, str) and py_hint.startswith("py:"):
            ver = py_hint.split(":", 1)[1]
            r = subprocess.run(["py", f"-{ver}", "-m", "venv", str(venv_dir)],
                               capture_output=True, text=True)
            if r.returncode:
                sys.stdout.write(r.stdout or ""); sys.stderr.write(r.stderr or "")
                # Fallback to current interpreter
                r2 = subprocess.run([sys.executable, "-m", "venv", str(venv_dir)],
                                    capture_output=True, text=True)
                if r2.returncode:
                    sys.stdout.write(r2.stdout or ""); sys.stderr.write(r2.stderr or "")
                    raise SystemError("venv creation failed")
        elif py_hint and os.path.exists(py_hint):
            r = subprocess.run([py_hint, "-m", "venv", str(venv_dir)], capture_output=True, text=True)
            if r.returncode:
                sys.stdout.write(r.stdout or ""); sys.stderr.write(r.stderr or "")
                # Fallback
                r2 = subprocess.run([sys.executable, "-m", "venv", str(venv_dir)],
                                    capture_output=True, text=True)
                if r2.returncode:
                    sys.stdout.write(r2.stdout or ""); sys.stderr.write(r2.stderr or "")
                    raise SystemError("venv creation failed")
        elif py_hint:
            # e.g. 'python3.12' found on PATH
            r = subprocess.run([py_hint, "-m", "venv", str(venv_dir)], capture_output=True, text=True)
            if r.returncode:
                sys.stdout.write(r.stdout or ""); sys.stderr.write(r.stderr or "")
                # Fallback
                r2 = subprocess.run([sys.executable, "-m", "venv", str(venv_dir)],
                                    capture_output=True, text=True)
                if r2.returncode:
                    sys.stdout.write(r2.stdout or ""); sys.stderr.write(r2.stderr or "")
                    raise SystemError("venv creation failed")
        else:
            r = subprocess.run([sys.executable, "-m", "venv", str(venv_dir)],
                               capture_output=True, text=True)
            if r.returncode:
                sys.stdout.write(r.stdout or ""); sys.stderr.write(r.stderr or "")
                raise SystemError("venv creation failed")

    python_exe = str(venv_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python"))
    # Report the interpreter actually inside the venv
    try:
        actual = _python_version_str(python_exe)
        print(f"[STEP2] venv python={actual} (requested={desired_python or 'current'})")
    except Exception:
        pass
    return venv_dir, python_exe

def ensure_pip(py: str) -> None:
    chk = subprocess.run([py, "-m", "pip", "--version"], capture_output=True, text=True)
    if chk.returncode == 0:
        return
    ep = subprocess.run([py, "-m", "ensurepip", "--upgrade"], capture_output=True, text=True)
    sys.stdout.write(ep.stdout or ""); sys.stderr.write(ep.stderr or "")
    chk = subprocess.run([py, "-m", "pip", "--version"], capture_output=True, text=True)
    if chk.returncode != 0:
        raise SystemError("pip not available in venv")

def _pip(py: str, args: list[str], cwd: Path | None = None) -> None:
    r = subprocess.run([py, "-m", "pip", *args], capture_output=True, text=True, cwd=str(cwd) if cwd else None)
    sys.stdout.write(r.stdout or "")
    if r.returncode:
        sys.stderr.write(r.stderr or "")
        raise SystemError("pip command failed")

def install_requirements(py: str, reqs_path: Path) -> None:
    uv = shutil.which("uv")
    if reqs_path.exists():
        if uv:
            r = subprocess.run([uv, "pip", "sync", str(reqs_path)],
                               capture_output=True, text=True, cwd=str(reqs_path.parent))
            sys.stdout.write(r.stdout or "")
            if r.returncode:
                sys.stderr.write(r.stderr or ""); raise SystemError("uv pip sync failed")
        else:
            _pip(py, ["install", "-r", str(reqs_path)], cwd=reqs_path.parent)
    else:
        if uv:
            r = subprocess.run([uv, "pip", "install", *BASE_REQS], capture_output=True, text=True)
            sys.stdout.write(r.stdout or "")
            if r.returncode:
                sys.stderr.write(r.stderr or ""); raise SystemError("uv pip install failed")
        else:
            _pip(py, ["install", *BASE_REQS])

def verify_runtime(py: str, allow_build: bool) -> None:
    """Verify flask stack; remediate MarkupSafe if missing (Windows + Py3.13 common)."""
    code = "import flask, jinja2, markupsafe, werkzeug; print('OK')"
    r = subprocess.run([py, "-c", code], capture_output=True, text=True)
    if r.returncode == 0:
        sys.stdout.write("[STEP2] Verified Flask/Jinja2/MarkupSafe/Werkzeug import\n")
        return

    err = (r.stderr or "").lower()
    if "markupsafe" in err:
        # 1) Try stable wheels only
        try:
            _pip(py, ["install", "--only-binary=:all:", "MarkupSafe>=2.1,<3"])
            r2 = subprocess.run([py, "-c", code], capture_output=True, text=True)
            if r2.returncode == 0:
                sys.stdout.write("[STEP2] Auto-installed MarkupSafe (stable wheel)\n")
                return
        except Exception:
            pass

        # 2) Try pre-release wheel
        try:
            _pip(py, ["install", "--pre", "--only-binary=:all:", "MarkupSafe>=2.1,<3"])
            r3 = subprocess.run([py, "-c", code], capture_output=True, text=True)
            if r3.returncode == 0:
                sys.stdout.write("[STEP2] Auto-installed MarkupSafe (pre-release wheel)\n")
                return
        except Exception:
            pass

        # 3) Optional source build (needs build tools)
        if allow_build:
            try:
                _pip(py, ["install", "--no-binary=:all:", "MarkupSafe>=2.1,<3"])
                r4 = subprocess.run([py, "-c", code], capture_output=True, text=True)
                if r4.returncode == 0:
                    sys.stdout.write("[STEP2] Built MarkupSafe from source\n")
                    return
            except Exception:
                pass

        raise SystemError(
            "[STEP2] ERROR: MarkupSafe wheel not available for this Python. "
            "Easiest fix: run Step 2 under Python 3.12. "
            "Alternatively pass --allow-build (requires C build tools) or rerun later once wheels publish."
        )

    # Different error
    sys.stderr.write(r.stderr or "")
    raise SystemError("Flask stack failed to import")

def write_backend_run_script(backend: Path, venv: Path) -> None:
    run_sh = backend / ("run_dev.bat" if os.name == "nt" else "run_dev.sh")
    if run_sh.exists():
        return
    if os.name == "nt":
        run_sh.write_text(
            "@echo off\n"
            f'call "{venv}\\Scripts\\activate"\n'
            "python -m flask --app app.main:create_app run --debug --port 5000\n",
            encoding="utf-8"
        )
    else:
        run_sh.write_text(
            "#!/usr/bin/env bash\n"
            f'source "{venv}/bin/activate"\n'
            "python -m flask --app app.main:create_app run --debug --port 5000\n",
            encoding="utf-8"
        )
        run_sh.chmod(0o755)

def verify_stack(python_exe: str) -> None:
    code = (
        "mods=['flask','werkzeug','jinja2','click','itsdangerous','blinker'];"
        "missing=[]\n"
        "import importlib\n"
        "for m in mods:\n"
        "    try: importlib.import_module(m)\n"
        "    except Exception as e: missing.append((m,str(e)))\n"
        "import sys\n"
        "print('OK' if not missing else 'MISSING:'+str(missing))"
    )
    res = subprocess.run([python_exe, "-c", code], capture_output=True, text=True)
    out = (res.stdout or '').strip()
    if not out.startswith("OK"):
        raise SystemError(f"Flask stack failed to import: {out}")


def write_control_scripts(root: Path, backend: Path) -> None:
    run_dir = root / ".vela-run"; run_dir.mkdir(exist_ok=True)
    pid_file = run_dir / "flask.pid"
    start_py = root / "start_server.py"
    stop_py = root / "stop_servers.py"

    start_py.write_text(textwrap.dedent("""\
        #!/usr/bin/env python3
        import os, sys, subprocess
        from pathlib import Path

        def pid_alive(pid: int) -> bool:
            try:
                if os.name == "nt":
                    out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}"], capture_output=True, text=True)
                    return str(pid) in out.stdout
                else:
                    os.kill(pid, 0); return True
            except Exception:
                return False

        def main():
            root = Path(__file__).resolve().parent
            backend = root / "backend"
            run_dir = root / ".vela-run"; run_dir.mkdir(exist_ok=True)
            pid_file = run_dir / "flask.pid"

            if pid_file.exists():
                try: old = int(pid_file.read_text().strip())
                except Exception: old = None
                if old and not pid_alive(old): pid_file.unlink(missing_ok=True)
                elif old:
                    print(f"[start] Flask already appears to be running (pid={old}).")
                    print("Use: python stop_servers.py"); return 0

            venv = backend / ".venv"
            python_exe = venv / ("Scripts/python.exe" if os.name=="nt" else "bin/python")
            if not python_exe.exists(): python_exe = Path(sys.executable)

            env = os.environ.copy()
            env["FLASK_APP"] = "app.main:create_app"
            env["PYTHONPATH"] = str(backend)
            env.setdefault("FLASK_RUN_HOST", "127.0.0.1")
            env.setdefault("FLASK_RUN_PORT", "5000")

            cmd = [str(python_exe), "-m", "flask", "run", "--debug",
                   "--host", env["FLASK_RUN_HOST"], "--port", env["FLASK_RUN_PORT"]]
            proc = subprocess.Popen(cmd, cwd=str(backend), env=env,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            pid_file.write_text(str(proc.pid), encoding="utf-8")
            print(f"[start] Flask dev server starting (pid={proc.pid}) at http://{env['FLASK_RUN_HOST']}:{env['FLASK_RUN_PORT']}")
            try:
                for _ in range(30):
                    line = proc.stdout.readline()
                    if not line: break
                    sys.stdout.write(line); sys.stdout.flush()
            except KeyboardInterrupt:
                pass
            return 0

        if __name__ == "__main__":
            sys.exit(main())
    """), encoding="utf-8")

    stop_py.write_text(textwrap.dedent("""\
        #!/usr/bin/env python3
        import os, sys, time, signal, subprocess
        from pathlib import Path

        def kill_tree_windows(pid: int) -> None:
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, text=True)

        def main():
            root = Path(__file__).resolve().parent
            pid_file = root / ".vela-run" / "flask.pid"
            if not pid_file.exists():
                print("[stop] No pid file found. Nothing to stop."); return 0
            try: pid = int(pid_file.read_text().strip())
            except Exception:
                print("[stop] Invalid pid file."); pid_file.unlink(missing_ok=True); return 0
            print(f"[stop] Stopping Flask server pid={pid}...")
            if os.name=="nt": kill_tree_windows(pid)
            else:
                try: os.kill(pid, signal.SIGTERM)
                except ProcessLookupError: pass
            time.sleep(0.5); pid_file.unlink(missing_ok=True)
            print("[stop] Stopped."); return 0

        if __name__ == "__main__":
            sys.exit(main())
    """), encoding="utf-8")

# ----------------- main -----------------

def main() -> int:
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--deploy", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--venv-dir", default="backend/.venv")
    ap.add_argument("--requirements", default="backend/requirements.txt")
    ap.add_argument("--strict-reqs", action="store_true")
    ap.add_argument("--config")
    ap.add_argument("--start-now", action="store_true")
    ap.add_argument("--allow-build", action="store_true",
                    help="Allow building MarkupSafe from source if no wheels (requires C build tools)")
    ap.add_argument(
        "--python",
        default=os.environ.get("VELA_PYTHON", "3.13"),
        help="Target Python for the venv (major.minor, a path, or leave default 3.12)."
    )
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
            if args.strict_reqs and args.requirements != "backend/requirements.txt":
                print(f"[STEP2] --strict-reqs set and requirements file missing: {reqs_path}")
                return 2
            write_requirements(reqs_path)
        else:
            ensure_minimum_stack(reqs_path)


        venv_path, py = create_venv(venv_dir, args.python)
        ensure_pip(py)

        if args.verbose:
            print(f"[STEP2] venv={venv_path}")
            print(f"[STEP2] python={py}")
            print(f"[STEP2] requirements={reqs_path}")

        install_requirements(py, reqs_path)
        verify_stack(python_exe)
        verify_runtime(py, allow_build=args.allow_build)

        write_backend_run_script(backend, venv_path)
        write_control_scripts(root, backend)

        if args.start_now:
            subprocess.run([sys.executable, str(root / "start_server.py")], check=False)

        print(f"[STEP2] Backend venv ready: {venv_path}")
        print(f"[STEP2] Requirements installed from: {reqs_path if reqs_path.exists() else 'explicit list'}")
        print("[STEP2] Python Env Bootloader: SUCCESS")
        return 0

    except KeyboardInterrupt:
        print("[STEP2] Interrupted"); return 130
    except Exception as e:
        print(f"[STEP2] ERROR: {e}"); return 1

if __name__ == "__main__":
    sys.exit(main())
