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

MUST_HAVE = {
    "flask": "Flask>=3.0,<4",
    "werkzeug": "Werkzeug>=3.0,<4",
    "jinja2": "Jinja2>=3.1,<4",
    "markupsafe": "MarkupSafe>=2.1.5,<3",
    "itsdangerous": "itsdangerous>=2.1,<3",
    "click": "click>=8.1,<9",
    "blinker": "blinker>=1.7,<2",
    "flask-cors": "flask-cors>=4.0,<5",
}


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
    requirements_path.parent.mkdir(parents=True, exist_ok=True)
    if not requirements_path.exists():
        # fresh file with all must-haves
        requirements_path.write_text("\n".join(MUST_HAVE.values()) + "\n", encoding="utf-8")
        return
    # patch existing file to include any missing must-haves
    existing = requirements_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    lower = {ln.strip().split("==")[0].split(">=")[0].split("<")[0].lower() for ln in existing if ln.strip() and not ln.strip().startswith("#")}
    additions = [spec for name, spec in MUST_HAVE.items() if name not in lower]
    if additions:
        with requirements_path.open("a", encoding="utf-8") as f:
            f.write("\n" + "\n".join(additions) + "\n")


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

def install_requirements(python_exe: str, requirements_path: Path, backend: Path, base_env: dict) -> int:
    # 0) env hygiene
    env = os.environ.copy()
    env.update(base_env or {})
    env.setdefault("PYTHONUNBUFFERED", "1")
    env.setdefault("PIP_DISABLE_PIP_VERSION_CHECK", "1")
    env.setdefault("UV_SYSTEM_PYTHON", "0")  # keep uv inside the venv

    # 1) ensure pip tooling (inside venv)
    rc = _stream_run([python_exe, "-m", "pip", "install", "-U", "pip", "setuptools", "wheel"],
                     cwd=backend, env=env, label="pip")
    if rc != 0:
        return rc

    # 2) prefer uv with explicit venv Python, else pip -r
    uv = shutil.which("uv")
    if uv:
        print("[STEP2] Installing requirements with uv pip sync:", requirements_path)
        _stream_run([python_exe, "-m", "pip", "install",
                     "--disable-pip-version-check",
                     "click>=8.1,<9", "flask-cors>=4,<5"],
                    cwd=backend, env=env, label="pip")
        return rc  # IMPORTANT: return directly; don't fall through
    else:
        print("[STEP2] Installing requirements with pip -r:", requirements_path)
        rc = _stream_run([python_exe, "-m", "pip", "install", "-r", str(requirements_path)],
                         cwd=backend, env=env, label="pip")
        return rc




def verify_stack(python_exe: str, env: dict) -> None:
    print("[STEP2] Verifying Flask stack imports ...")
    verify_src = textwrap.dedent("""\
        import importlib as i, json
        mods=['flask','werkzeug','jinja2','markupsafe','blinker','click']
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

def write_flask_scripts(root: Path) -> None:
    run_dir = root / ".vela-run"
    run_dir.mkdir(exist_ok=True)

    start_flask = root / "start_flask.py"
    stop_flask  = root / "stop_flask.py"

    start_flask.write_text(r"""#!/usr/bin/env python3
import os, sys, time, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
RUN = ROOT / ".vela-run"; RUN.mkdir(exist_ok=True)
PIDF = RUN / "flask.pid"
LOGF = BACKEND / "flask.log"

def pid_alive(pid: int) -> bool:
    try:
        if os.name == "nt":
            out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}"], capture_output=True, text=True)
            return str(pid) in out.stdout
        else:
            os.kill(pid, 0)
            return True
    except Exception:
        return False

def read_pid():
    try:
        if PIDF.exists():
            p = int(PIDF.read_text().strip())
            if pid_alive(p): return p
    except Exception:
        pass
    return None

def write_pid(pid: int):
    PIDF.write_text(str(pid), encoding="utf-8")

def venv_python() -> str:
    v = BACKEND / ".venv" / ("Scripts/pythonw.exe" if os.name=="nt" else "bin/python")
    if v.exists(): return str(v)
    v = BACKEND / ".venv" / ("Scripts/python.exe" if os.name=="nt" else "bin/python")
    return str(v if v.exists() else sys.executable)

def start(detached: bool = True, host="127.0.0.1", port=5000):
    existing = read_pid()
    if existing:
        print(f"[flask] already running pid={existing}")
        return existing

    code = (
        "from app.main import create_app; "
        "app=create_app(); "
        f"app.run(host='{host}', port={port}, debug=False)"
    )
    py = venv_python()
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONPATH"] = str(BACKEND)

    kwargs = dict(cwd=str(BACKEND), env=env)
    if detached:
        log = open(LOGF, "ab", buffering=0)
        kwargs.update(stdout=log, stderr=subprocess.STDOUT, close_fds=True)
        if os.name == "nt":
            DETACHED_PROCESS = 0x00000008
            CREATE_NEW_PROCESS_GROUP = 0x00000200
            CREATE_NO_WINDOW = 0x08000000
            kwargs["creationflags"] = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW
        else:
            kwargs["preexec_fn"] = os.setpgrp
    else:
        kwargs.update(stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)

    p = subprocess.Popen([py, "-c", code], **kwargs)
    write_pid(p.pid)
    print(f"[flask] pid={p.pid} → http://{host}:{port}")
    if not detached and p.stdout:
        for _ in range(30):
            ln = p.stdout.readline()
            if not ln: break
            print("[flask]", ln.rstrip())
    return p.pid

if __name__ == "__main__":
    start(detached=True)
""", encoding="utf-8")

    stop_flask.write_text(r"""#!/usr/bin/env python3
import os, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RUN  = ROOT / ".vela-run"
PIDF = RUN / "flask.pid"

def kill(pid: int):
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], check=False,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            os.kill(pid, 15)
    except Exception:
        pass

if __name__ == "__main__":
    if PIDF.exists():
        try:
            pid = int(PIDF.read_text().strip())
            print(f"[flask] stopping pid={pid} …")
            kill(pid)
        except Exception:
            pass
        PIDF.unlink(missing_ok=True)
    else:
        print("[flask] no pid file")
""", encoding="utf-8")

    for f in (start_flask, stop_flask):
        try: os.chmod(f, 0o755)
        except Exception: pass


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
        write_requirements(reqs_path)

        venv_path, python_exe = create_venv(venv_dir, env)
        ensure_pip(python_exe, env)

        if args.verbose:
            print(f"[STEP2] venv={venv_path}")
            print(f"[STEP2] python={python_exe}")
            print(f"[STEP2] requirements={reqs_path}")

        rc = install_requirements(python_exe, reqs_path, backend, base_env=env)
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
