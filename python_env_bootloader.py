#!/usr/bin/env python3
"""
Python Env Bootloader (STEP 2)
- Finds deployment root from VELA_CORE_DIR (or cwd)
- Ensures backend/ with minimal Flask app (/api/health)
- Creates backend/.venv
- Ensures backend/requirements.txt (writes defaults if missing)
- Upgrades pip tooling, installs requirements (uv if present → pip fallback)
- Verifies imports (flask, werkzeug, jinja2, markupsafe, blinker)
- Writes start_server.py / stop_servers.py at repo root
- Optional --start-now to launch Flask (detached)
"""

from __future__ import annotations
import os, sys, subprocess, shutil, tempfile, time
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

    ini = backend / "app" / "__init__.py"
    if not ini.exists():
        ini.write_text("# Flask app init\n", encoding="utf-8")

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

def create_venv(venv_dir: Path, env: dict) -> tuple[Path, str]:
    venv_dir.mkdir(parents=True, exist_ok=True)
    uv = shutil.which("uv")
    if uv:
        res = subprocess.run([uv, "venv", str(venv_dir)], capture_output=True, text=True, env=env)
        if res.returncode != 0:
            sys.stdout.write(res.stdout or ""); sys.stderr.write(res.stderr or "")
            raise SystemError("uv venv failed")
    else:
        res = subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], capture_output=True, text=True, env=env)
        if res.returncode != 0:
            sys.stdout.write(res.stdout or ""); sys.stderr.write(res.stderr or "")
            raise SystemError("venv creation failed")
    python_exe = str(venv_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python"))
    return venv_dir, python_exe

def ensure_pip(python_exe: str, env: dict) -> None:
    chk = subprocess.run([python_exe, "-m", "pip", "--version"], capture_output=True, text=True, env=env)
    if chk.returncode == 0:
        return
    print("[STEP2] Bootstrapping pip via ensurepip ...")
    ep = subprocess.run([python_exe, "-m", "ensurepip", "--upgrade"], capture_output=True, text=True, env=env)
    sys.stdout.write(ep.stdout or ""); sys.stderr.write(ep.stderr or "")
    chk = subprocess.run([python_exe, "-m", "pip", "--version"], capture_output=True, text=True, env=env)
    if chk.returncode != 0:
        raise SystemError("pip is unavailable in the virtual environment")

def _stream_run(cmd, cwd=None, env=None, label=""):
    """Run a command and stream stdout to our stdout (line-by-line)."""
    lbl = f"[{label}] " if label else ""
    print(f"{lbl}exec: {' '.join(map(str, cmd))} (cwd={cwd or os.getcwd()})", flush=True)

    creationflags = 0
    if os.name == "nt":
        DETACHED_PROCESS = 0x00000008
        CREATE_NEW_PROCESS_GROUP = 0x00000200
        CREATE_NO_WINDOW = 0x08000000
        creationflags = CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW  # we want a console for installs, but no new window

    p = subprocess.Popen(
        cmd,
        cwd=str(cwd) if cwd else None,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        creationflags=creationflags
    )
    assert p.stdout is not None
    try:
        for line in iter(p.stdout.readline, ""):
            print(f"{lbl}{line.rstrip()}", flush=True)
    finally:
        p.stdout.close()
    rc = p.wait()
    print(f"{lbl}exit code: {rc}", flush=True)
    return rc

def install_requirements(python_exe: str, requirements_path: Path, backend: Path, env: dict) -> int:
    # 1) Upgrade bootstrappers
    rc = _stream_run([str(python_exe), "-m", "pip", "install", "-U", "pip", "setuptools", "wheel"],
                     cwd=backend, env=env, label="pip")
    if rc != 0:
        return rc

    # 2) Prefer uv if available, else pip -r
    uv = shutil.which("uv")
    if uv:
        print("[STEP2] Installing requirements with uv pip sync:", requirements_path)
        rc = _stream_run([uv, "pip", "sync", str(requirements_path)], cwd=backend, env=env, label="uv")
    else:
        print("[STEP2] Installing requirements with pip -r:", requirements_path)
        rc = _stream_run([str(python_exe), "-m", "pip", "install", "-r", str(requirements_path)],
                         cwd=backend, env=env, label="pip")
    return rc

def verify_stack(python_exe: str, env: dict) -> None:
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
        res = subprocess.run([python_exe, tf_path], capture_output=True, text=True, env=env)
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
        start_py.write_text(textwrap.dedent("""\
            import os, sys, subprocess, time, json
            from pathlib import Path

            ROOT = Path(__file__).parent
            VENV = ROOT / "backend" / ".venv"
            PY   = VENV / ("Scripts/pythonw.exe" if os.name == "nt" else "bin/python")
            PIDF = ROOT / ".pids.json"

            def _record_pid(kind, pid):
                P = {}
                if PIDF.exists():
                    try: P = json.loads(PIDF.read_text())
                    except Exception: P = {}
                P[kind] = pid
                PIDF.write_text(json.dumps(P), encoding="utf-8")

            def _already_running(kind):
                if not PIDF.exists(): return None
                try:
                    P = json.loads(PIDF.read_text())
                    return P.get(kind)
                except Exception:
                    return None

            def run_direct():
                code = (
                    "from app.main import create_app\\n"
                    "app = create_app()\\n"
                    "app.run(host='127.0.0.1', port=5000, debug=True)\\n"
                )
                env = os.environ.copy()
                env.setdefault("PYTHONIOENCODING","utf-8")
                env.setdefault("PYTHONUNBUFFERED","1")
                p = subprocess.Popen(
                    [str(PY), "-c", code],
                    cwd=str(ROOT / "backend"),
                    env=env,
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
                )
                print(f"[start] Flask dev server (direct) starting pid={p.pid} \u2192 http://127.0.0.1:5000")
                _record_pid("flask_pid", p.pid)
                t_end = time.time() + 3
                try:
                    while time.time() < t_end:
                        line = p.stdout.readline()
                        if not line: break
                        print(line.rstrip())
                except Exception:
                    pass

            if __name__ == "__main__":
                running = _already_running("flask_pid")
                if running:
                    print(f"[start] Flask already appears to be running (pid={running}).")
                    sys.exit(0)
                run_direct()
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
                        P.pop(key, None); count += 1
                PIDF.write_text(json.dumps(P), encoding="utf-8")
                if count == 0:
                    print("[stop] nothing to stop")
        """), encoding="utf-8")

def start_flask_detached(backend: Path, venv_path: Path, env: dict, host="127.0.0.1", port=5000):
    # prefer pythonw.exe on Windows to avoid console window
    if os.name == "nt":
        pyw = venv_path / "Scripts" / "pythonw.exe"
        python_exe = str(pyw if pyw.exists() else venv_path / "Scripts" / "python.exe")
    else:
        python_exe = str(venv_path / "bin" / "python")

    log_file = backend / "flask.log"
    pid_file = backend / "flask.pid"

    code = (
        "from app.main import create_app; "
        "app=create_app(); "
        f"app.run(host='{host}', port={port}, debug=False)"
    )
    cmd = [python_exe, "-c", code]

    lf = open(log_file, "ab", buffering=0)
    kwargs = dict(cwd=str(backend), stdout=lf, stderr=subprocess.STDOUT, close_fds=True, env=env)

    if os.name == "nt":
        DETACHED_PROCESS = 0x00000008
        CREATE_NEW_PROCESS_GROUP = 0x00000200
        CREATE_NO_WINDOW = 0x08000000
        kwargs["creationflags"] = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW
    else:
        kwargs["preexec_fn"] = os.setpgrp

    proc = subprocess.Popen(cmd, **kwargs)
    pid_file.write_text(str(proc.pid), encoding="utf-8")
    print(f"[start] Flask dev server (detached) pid={proc.pid} -> http://{host}:{port}")
    print(f"[start] Logs: {log_file}")
    return proc.pid

def stop_flask_if_any(backend_dir: Path):
    pid_file = backend_dir / "flask.pid"
    if not pid_file.exists():
        return
    try:
        pid = int(pid_file.read_text().strip())
    except Exception:
        return
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], check=False)
        else:
            os.kill(pid, 15)
    finally:
        try: pid_file.unlink(missing_ok=True)
        except Exception: pass

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

    # one env for all children (unbuffered + saner pip/uv)
    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("PYTHONUNBUFFERED", "1")
    env.setdefault("PIP_DISABLE_PIP_VERSION_CHECK", "1")
    env.setdefault("UV_SYSTEM_PYTHON", "1")

    backend = ensure_backend(root)

    venv_dir = (root / args.venv_dir).resolve() if not Path(args.venv_dir).is_absolute() else Path(args.venv_dir)
    reqs_path = (root / args.requirements).resolve() if not Path(args.requirements).is_absolute() else Path(args.requirements)

    try:
        if not reqs_path.exists():
            print("[STEP2] requirements.txt missing — writing defaults …")
            write_requirements(reqs_path)

        venv_path, python_exe = create_venv(venv_dir, env)
        ensure_pip(python_exe, env)

        if args.verbose:
            print(f"[STEP2] venv={venv_path}")
            print(f"[STEP2] python={python_exe}")
            print(f"[STEP2] requirements={reqs_path}")

        rc = install_requirements(python_exe, reqs_path, backend, env)
        if rc != 0:
            print("[STEP2] ERROR: dependency install failed")
            return 1

        verify_stack(python_exe, env)
        write_start_stop_scripts(root)

        print(f"[STEP2] Backend venv ready: {venv_path}")
        print(f"[STEP2] Requirements installed from: {reqs_path}")

        if args.start_now:
            start_flask_detached(backend, venv_path, env, host="127.0.0.1", port=5000)

        print("[STEP2] Python Env Bootloader: SUCCESS")
        return 0

    except KeyboardInterrupt:
        print("[STEP2] Interrupted"); return 130
    except Exception as e:
        print(f"[STEP2] ERROR: {e}"); return 1

if __name__ == "__main__":
    sys.exit(main())
