#!/usr/bin/env python3
"""
Python Env Bootloader (STEP 2)
- Finds deployment root from VELA_CORE_DIR (or cwd)
- Ensures backend/ with minimal Flask app (/api/health)
- Creates backend/.venv
- Ensures backend/requirements.txt (writes defaults if missing)
- Upgrades pip tooling, installs requirements (uv if present → pip fallback)
- Verifies imports (flask, werkzeug, jinja2, markupsafe, blinker) via temp script
- Writes start_server.py / stop_servers.py at repo root
- Optional --start-now to launch Flask
"""

from __future__ import annotations
import os, sys, subprocess, shutil, tempfile
from pathlib import Path
import argparse, textwrap, json

# ---------- helpers ----------

def resolve_deployment_root() -> Path:
    core_dir = os.environ.get("VELA_CORE_DIR")
    if core_dir:
        p = Path(core_dir).resolve()
        try:
            return p.parents[3]  # …/data/.vela/cores/<vh> -> deployment root
        except IndexError:
            pass
    return Path.cwd().resolve()

def ensure_backend(root: Path) -> Path:
    backend = root / "backend"
    (backend / "app" / "routes").mkdir(parents=True, exist_ok=True)
    (backend / "app" / "models").mkdir(parents=True, exist_ok=True)
    (backend / "app" / "utils").mkdir(parents=True, exist_ok=True)

    (backend / "app" / "__init__.py").write_text("# Flask app init\n", encoding="utf-8") if not (backend / "app" / "__init__.py").exists() else None
    main_py = backend / "app" / "main.py"
    if not main_py.exists():
        main_py.write_text(textwrap.dedent("""\
            from flask import Flask, jsonify
            from flask_cors import CORS

            def create_app():
                app = Flask(__name__)
                CORS(app, resources={r"/api/*": {"origins": "*"}})

                @app.get("/api/health")
                def health():
                    import time
                    return jsonify({"status": "ok", "service": "backend", "ts": time.time()})

                return app

            if __name__ == "__main__":
                app = create_app()
                app.run(host="127.0.0.1", port=5000, debug=True)
        """), encoding="utf-8")
    return backend

def write_requirements(requirements_path: Path) -> None:
    if requirements_path.exists():
        return
    requirements_path.parent.mkdir(parents=True, exist_ok=True)
    reqs = [
        "Flask>=3.0,<4",
        "Werkzeug>=3.0,<4",
        "Jinja2>=3.1,<4",
        "MarkupSafe>=2.1.5,<3",
        "itsdangerous>=2.1,<3",
        "click>=8.1,<9",
        "blinker>=1.7,<2",
        "flask-cors>=4.0,<5",
    ]
    requirements_path.write_text("\n".join(reqs) + "\n", encoding="utf-8")

def create_venv(venv_dir: Path) -> tuple[Path, str]:
    venv_dir.mkdir(parents=True, exist_ok=True)
    uv = shutil.which("uv")
    if uv:
        res = subprocess.run([uv, "venv", str(venv_dir)], capture_output=True, text=True)
        if res.returncode != 0:
            sys.stdout.write(res.stdout or ""); sys.stderr.write(res.stderr or "")
            raise SystemError("uv venv failed")
    else:
        res = subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], capture_output=True, text=True)
        if res.returncode != 0:
            sys.stdout.write(res.stdout or ""); sys.stderr.write(res.stderr or "")
            raise SystemError("venv creation failed")
    python_exe = str(venv_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python"))
    return venv_dir, python_exe

def ensure_pip(python_exe: str) -> None:
    chk = subprocess.run([python_exe, "-m", "pip", "--version"], capture_output=True, text=True)
    if chk.returncode == 0:
        return
    print("[STEP2] Bootstrapping pip via ensurepip ...")
    ep = subprocess.run([python_exe, "-m", "ensurepip", "--upgrade"], capture_output=True, text=True)
    sys.stdout.write(ep.stdout or ""); sys.stderr.write(ep.stderr or "")
    chk = subprocess.run([python_exe, "-m", "pip", "--version"], capture_output=True, text=True)
    if chk.returncode != 0:
        raise SystemError("pip is unavailable in the virtual environment")

def install_requirements(python_exe: str, requirements_path: Path) -> None:
    print("[STEP2] Upgrading pip/setuptools/wheel ...")
    up = subprocess.run([python_exe, "-m", "pip", "install", "-U", "pip", "setuptools", "wheel"], capture_output=True, text=True)
    sys.stdout.write(up.stdout or "")
    if up.returncode != 0:
        sys.stderr.write(up.stderr or "")
        print("[STEP2] WARN: upgrade pip tooling failed, continuing")

    uv = shutil.which("uv")
    if uv:
        print(f"[STEP2] Installing requirements with uv pip sync: {requirements_path}")
        res = subprocess.run([uv, "pip", "sync", str(requirements_path)], capture_output=True, text=True, cwd=str(requirements_path.parent))
        sys.stdout.write(res.stdout or "")
        if res.returncode == 0:
            return
        sys.stderr.write(res.stderr or "")
        print("[STEP2] WARN: uv pip sync failed; falling back to pip install -r")

    print(f"[STEP2] Installing requirements with pip: {requirements_path}")
    res = subprocess.run([python_exe, "-m", "pip", "install", "-r", str(requirements_path)], capture_output=True, text=True)
    sys.stdout.write(res.stdout or "")
    if res.returncode != 0:
        sys.stderr.write(res.stderr or "")
        raise SystemError("pip install failed")

def verify_stack(python_exe: str) -> None:
    print("[STEP2] Verifying Flask stack imports ...")
    verify_src = textwrap.dedent("""\
        import importlib as i, json
        mods=['flask','werkzeug','jinja2','markupsafe','blinker']
        missing=[]; vers={}
        for m in mods:
            try:
                mod=i.import_module(m)
                vers[m]=getattr(mod,'__version__','?')
            except Exception as e:
                missing.append((m,str(e)))
        print(json.dumps({'missing':missing,'versions':vers}))
    """)
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".py") as tf:
        tf.write(verify_src)
        tf_path = tf.name
    try:
        res = subprocess.run([python_exe, tf_path], capture_output=True, text=True)
        if res.stdout:
            print("[STEP2] Verify output:", res.stdout.strip())
        if res.returncode != 0:
            if res.stderr:
                print("[STEP2] Verify stderr:", res.stderr.strip())
            raise SystemError("import check failed")
        payload = json.loads(res.stdout.strip() or "{}")
        missing = payload.get("missing") or []
        vers = payload.get("versions") or {}
        print(f"[STEP2] Flask stack versions: {vers}")
        if missing:
            raise SystemError(f"Flask stack failed to import: MISSING:{missing}")
    finally:
        try: os.remove(tf_path)
        except Exception: pass

def write_start_stop_scripts(root: Path) -> None:
    start_py = root / "start_server.py"
    stop_py  = root / "stop_servers.py"

    if not start_py.exists():
        start_py.write_text(textwrap.dedent(f"""\
            import os, sys, subprocess, time, json
            from pathlib import Path

            ROOT = Path(__file__).parent
            VENV = ROOT / "backend" / ".venv"
            PY   = VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
            PIDF = ROOT / ".pids.json"

            def run():
                env = os.environ.copy()
                env["FLASK_APP"] = "app.main:create_app"
                env["FLASK_RUN_PORT"] = "5000"
                env["FLASK_ENV"] = "development"
                env["PYTHONUTF8"] = "1"
                p = subprocess.Popen(
                    [str(PY), "-m", "flask", "run", "--debug", "--host", "127.0.0.1", "--port", "5000"],
                    cwd=str(ROOT / "backend"),
                    env=env,
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
                )
                print(f"[start] Flask dev server starting (pid={{p.pid}}) at http://127.0.0.1:5000")
                P = {{}}
                if PIDF.exists():
                    try: P = json.loads(PIDF.read_text())
                    except Exception: P = {{}}
                P["flask_pid"] = p.pid
                PIDF.write_text(json.dumps(P), encoding="utf-8")
                t_end = time.time() + 3
                try:
                    while time.time() < t_end:
                        line = p.stdout.readline()
                        if not line: break
                        print(line.rstrip())
                except Exception:
                    pass

            if __name__ == "__main__":
                try:
                    P = json.loads((Path(".pids.json").read_text())) if PIDF.exists() else {{}}
                    pid = P.get("flask_pid")
                    if pid:
                        if os.name == "nt":
                            import ctypes
                            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
                            handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
                            if handle:
                                print(f"[start] Flask already appears to be running (pid={{pid}}).")
                                sys.exit(0)
                    run()
                except Exception as e:
                    print(f"[start] WARN: {{e}}"); run()
        """), encoding="utf-8")

    if not stop_py.exists():
        stop_py.write_text(textwrap.dedent("""\
            import os, sys, json, signal, subprocess
            from pathlib import Path

            ROOT = Path(__file__).parent
            PIDF = ROOT / ".pids.json"

            def kill(pid):
                try:
                    if os.name == "nt":
                        subprocess.run(["taskkill", "/F", "/PID", str(pid)],
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    else:
                        os.kill(int(pid), signal.SIGTERM)
                    return True
                except Exception:
                    return False

            if __name__ == "__main__":
                if not PIDF.exists():
                    print("[stop] no pidfile"); sys.exit(0)
                try:
                    P = json.loads(PIDF.read_text())
                except Exception:
                    P = {}
                count = 0
                for key in list(P.keys()):
                    pid = P.get(key)
                    if pid and kill(pid):
                        print(f"[stop] killed {key} pid={pid}")
                        P.pop(key, None)
                        count += 1
                PIDF.write_text(json.dumps(P), encoding="utf-8")
                if count == 0:
                    print("[stop] nothing to stop")
        """), encoding="utf-8")

def maybe_start_now(root: Path) -> None:
    try:
        subprocess.Popen([sys.executable, str(root / "start_server.py")], cwd=str(root))
    except Exception as e:
        print(f"[STEP2] WARN: could not start server automatically: {e}")

# ---------- main ----------

def main() -> int:
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--deploy", action="store_true", help="Run env setup")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--venv-dir", default="backend/.venv")
    ap.add_argument("--requirements", default="backend/requirements.txt")
    ap.add_argument("--start-now", action="store_true", help="Start Flask after install")
    args, _ = ap.parse_known_args()

    root = resolve_deployment_root()
    if args.verbose:
        print(f"[STEP2] deployment_root={root}")
        print(f"[STEP2] argv={sys.argv}")

    backend = ensure_backend(root)

    venv_dir = (root / args.venv_dir).resolve() if not Path(args.venv_dir).is_absolute() else Path(args.venv_dir)
    reqs_path = (root / args.requirements).resolve() if not Path(args.requirements).is_absolute() else Path(args.requirements)

    try:
        if not reqs_path.exists():
            print("[STEP2] requirements.txt missing — writing defaults …")
            write_requirements(reqs_path)

        venv_path, python_exe = create_venv(venv_dir)
        ensure_pip(python_exe)

        if args.verbose:
            print(f"[STEP2] venv={venv_path}")
            print(f"[STEP2] python={python_exe}")
            print(f"[STEP2] requirements={reqs_path}")

        install_requirements(python_exe, reqs_path)
        verify_stack(python_exe)
        write_start_stop_scripts(root)

        print(f"[STEP2] Backend venv ready: {venv_path}")
        print(f"[STEP2] Requirements installed from: {reqs_path}")

        if args.start_now:
            maybe_start_now(root)

        print("[STEP2] Python Env Bootloader: SUCCESS")
        return 0

    except KeyboardInterrupt:
        print("[STEP2] Interrupted"); return 130
    except Exception as e:
        print(f"[STEP2] ERROR: {e}"); return 1

if __name__ == "__main__":
    sys.exit(main())
