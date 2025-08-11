#!/usr/bin/env python3
"""
Python Env Bootloader (STEP 2)
- Resolves deployment root from VELA_CORE_DIR (or cwd)
- Ensures backend/ exists
- Creates backend/.venv
- Ensures/patches backend/requirements.txt with full Flask stack
- Installs via pip (or uv if available)
- Verifies imports
- Writes start/stop scripts (if missing)
"""

from __future__ import annotations
import os, sys, subprocess, shutil, argparse, textwrap
from pathlib import Path

# ---------- helpers ----------

def resolve_deployment_root() -> Path:
    core_dir = os.environ.get("VELA_CORE_DIR")
    if core_dir:
        p = Path(core_dir).resolve()
        try:
            return p.parents[3]  # cores -> .vela -> data -> <deployment_root>
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

def write_requirements(requirements_path: Path) -> None:
    ...
    lines = [
        "flask>=3.0,<4",
        "blinker>=1.7,<2",
        "werkzeug>=3.0,<4",
        "Jinja2>=3.1,<4",
        "itsdangerous>=2.2,<3",
        "click>=8.1,<9",
        "MarkupSafe>=2.1.5,<3",   # <-- add this
    ]


def ensure_minimum_stack(requirements_path: Path) -> None:
    needed = {
        "flask": "flask>=3.0,<4",
        "blinker": "blinker>=1.7,<2",
        "werkzeug": "werkzeug>=3.0,<4",
        "jinja2": "Jinja2>=3.1,<4",
        "itsdangerous": "itsdangerous>=2.2,<3",
        "click": "click>=8.1,<9",
        "markupsafe": "MarkupSafe>=2.1.5,<3",  # <-- add this
    }
    
    try:
        lines = requirements_path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return
    have = {
        l.strip().split("==")[0].split(">=")[0].split("<")[0].lower()
        for l in lines if l.strip() and not l.strip().startswith("#")
    }
    changed = False
    for k, v in needed.items():
        if k not in have:
            lines.append(v)
            changed = True
    if changed:
        requirements_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

def create_venv(venv_dir: Path) -> tuple[Path, str]:
    venv_dir.mkdir(parents=True, exist_ok=True)
    # Prefer uv if present
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
    ep = subprocess.run([python_exe, "-m", "ensurepip", "--upgrade"], capture_output=True, text=True)
    sys.stdout.write(ep.stdout or ""); sys.stderr.write(ep.stderr or "")
    chk = subprocess.run([python_exe, "-m", "pip", "--version"], capture_output=True, text=True)
    if chk.returncode != 0:
        raise SystemError("pip is unavailable in the virtual environment")

def install_requirements(python_exe: str, requirements_path: Path) -> None:
    uv = shutil.which("uv")
    if uv:
        res = subprocess.run([uv, "pip", "sync", str(requirements_path)],
                             capture_output=True, text=True, cwd=str(requirements_path.parent))
        sys.stdout.write(res.stdout or "")
        if res.returncode != 0:
            sys.stderr.write(res.stderr or "")
            raise SystemError("uv pip sync failed")
        return
    res = subprocess.run([python_exe, "-m", "pip", "install", "-r", str(requirements_path)],
                         capture_output=True, text=True, cwd=str(requirements_path.parent))
    sys.stdout.write(res.stdout or "")
    if res.returncode != 0:
        sys.stderr.write(res.stderr or "")
        raise SystemError("pip install failed")

def verify_stack(python_exe: str) -> None:
    code = (
        "mods=['flask','werkzeug','jinja2','click','itsdangerous','blinker','markupsafe'];"
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

def write_run_scripts(root: Path, venv_path: Path) -> None:
    # write unified start/stop at the deployment root
    start_py = root / "start_server.py"
    stop_py  = root / "stop_servers.py"

    if not start_py.exists():
        start_py.write_text(textwrap.dedent(f"""\
            import os, subprocess, sys, json, time
            from pathlib import Path

            ROOT = Path(__file__).resolve().parent
            VENV = ROOT / "backend" / ".venv"
            PY   = VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
            PIDS = ROOT / ".pids.json"

            def run_detached(cmd, cwd=None):
                flags = 0
                popen_kwargs = dict(cwd=str(cwd) if cwd else None,
                                    stdout=subprocess.DEVNULL,
                                    stderr=subprocess.STDOUT)
                if os.name == "nt":
                    flags = 0x00000008  # CREATE_NO_WINDOW
                    popen_kwargs["creationflags"] = flags
                return subprocess.Popen(cmd, **popen_kwargs)

            def main():
                # Flask
                flask = run_detached([str(PY), "-m", "flask", "--app", "backend/app/main.py", "run", "--debug", "--port", "5000"], cwd=ROOT)
                pids = {{"flask": flask.pid}}
                PIDS.write_text(json.dumps(pids, indent=2), encoding="utf-8")
                print(f"[start] Flask dev server starting (pid={{flask.pid}}) at http://127.0.0.1:5000")
            if __name__ == "__main__":
                main()
        """), encoding="utf-8")

    if not stop_py.exists():
        stop_py.write_text(textwrap.dedent("""\
            import os, json, signal
            from pathlib import Path

            ROOT = Path(__file__).resolve().parent
            PIDS = ROOT / ".pids.json"

            def kill(pid):
                try:
                    if os.name == "nt":
                        os.kill(pid, signal.SIGTERM)
                    else:
                        os.kill(pid, signal.SIGTERM)
                except Exception:
                    pass

            def main():
                if not PIDS.exists():
                    print("[stop] no running servers recorded")
                    return
                data = json.loads(PIDS.read_text(encoding="utf-8"))
                for name, pid in data.items():
                    kill(int(pid))
                    print(f"[stop] {name} stopped (pid={pid})")
                try: PIDS.unlink()
                except Exception: pass
            if __name__ == "__main__":
                main()
        """), encoding="utf-8")

def maybe_start(start_now: bool, root: Path) -> None:
    if not start_now:
        return
    proc = subprocess.Popen([sys.executable, str(root / "start_server.py")],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        # print first line for feedback
        print(proc.stdout.readline().rstrip())
    except Exception:
        pass

# ---------- main ----------

def main() -> int:
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--deploy", action="store_true", help="Run env setup")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--venv-dir", default="backend/.venv")
    ap.add_argument("--requirements", default="backend/requirements.txt")
    ap.add_argument("--strict-reqs", action="store_true", help="Fail if requirements missing")
    ap.add_argument("--start-now", action="store_true", help="Start Flask immediately")
    args, _ = ap.parse_known_args()

    root = resolve_deployment_root()
    if args.verbose:
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

        venv_path, python_exe = create_venv(venv_dir)
        ensure_pip(python_exe)

        if args.verbose:
            print(f"[STEP2] venv={venv_path}")
            print(f"[STEP2] python={python_exe}")
            print(f"[STEP2] requirements={reqs_path}")

        install_requirements(python_exe, reqs_path)
        
        # Hotfix: if markupsafe still missing, try installing a wheel explicitly
        probe = subprocess.run([python_exe, "-c", "import markupsafe"], capture_output=True, text=True)
        if probe.returncode != 0:
            fix = subprocess.run(
                [python_exe, "-m", "pip", "install", "--only-binary=:all:", "MarkupSafe>=2.1.5,<3"],
                capture_output=True, text=True
            )
            sys.stdout.write(fix.stdout or "")
            if fix.returncode != 0:
                sys.stderr.write(fix.stderr or "")
                raise SystemError("MarkupSafe wheel install failed; ensure Python 3.12 and internet access.")
        
        verify_stack(python_exe)
        write_run_scripts(root, venv_path)

        print(f"[STEP2] Backend venv ready: {venv_path}")
        print(f"[STEP2] Requirements installed from: {reqs_path}")
        print("[STEP2] Python Env Bootloader: SUCCESS")

        maybe_start(args.start_now, root)
        return 0

    except KeyboardInterrupt:
        print("[STEP2] Interrupted"); return 130
    except Exception as e:
        print(f"[STEP2] ERROR: {e}"); return 1

if __name__ == "__main__":
    sys.exit(main())
