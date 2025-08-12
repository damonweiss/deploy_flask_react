#!/usr/bin/env python3
"""
Vite Bootloader (STEP 4)
- Resolves deployment root from VELA_CORE_DIR (or cwd)
- Ensures frontend/ with React+Vite scaffold
- Writes vite.config.js with proxy to Flask on 127.0.0.1:5000
- Runs npm install in frontend/ (streams output; no "hang")
- Upgrades start_server.py / stop_servers.py to manage BOTH Flask and Vite
- (Optional) Installs Node.js on Windows if missing (winget/choco/scoop)
- (Optional) --start-now to launch Flask+Vite immediately (detached)

Usage:
  python vite_bootloader.py --deploy
  python vite_bootloader.py --deploy --auto-install-node
  python vite_bootloader.py --deploy --auto-install-node --pm winget   # or choco/scoop
  python vite_bootloader.py --deploy --start-now
"""

from __future__ import annotations
import os, sys, subprocess, shutil, argparse, json, textwrap, time
from pathlib import Path
from typing import Optional

# -------------------- paths --------------------

def resolve_deployment_root() -> Path:
    core_dir = os.environ.get("VELA_CORE_DIR")
    if core_dir:
        p = Path(core_dir).resolve()
        try:
            # …/data/.vela/cores/<vh> → deployment root
            return p.parents[3]
        except IndexError:
            pass
    return Path.cwd().resolve()

# -------------------- npm / Node helpers --------------------

def which(cmd: str) -> Optional[str]:
    p = shutil.which(cmd)
    return str(Path(p).resolve()) if p else None

def find_npm_command() -> Optional[str]:
    """Best-effort locate npm on all platforms."""
    npm = which("npm")
    if npm:
        return npm

    if os.name == "nt":
        candidates = [
            Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "nodejs" / "npm.cmd",
            Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "nodejs" / "npm.cmd",
            Path(os.environ.get("LocalAppData", r"C:\Users\%USERNAME%\AppData\Local")) / "Programs" / "node" / "npm.cmd",
        ]
        nvm_home = os.environ.get("NVM_HOME")
        if nvm_home:
            candidates.append(Path(nvm_home) / "npm.cmd")
        for c in candidates:
            if c.exists():
                return str(c)
    else:
        for c in ("/opt/homebrew/bin/npm", "/usr/local/bin/npm", "/usr/bin/npm"):
            if Path(c).exists():
                return c
    return None

def _quiet_run(pm_cmd: list[str]) -> bool:
    try:
        flags = 0
        if os.name == "nt":
            CREATE_NEW_PROCESS_GROUP = 0x00000200
            CREATE_NO_WINDOW = 0x08000000
            flags = CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW
        res = subprocess.run(pm_cmd, text=True, capture_output=True, creationflags=flags if os.name=="nt" else 0)
        return res.returncode == 0
    except Exception:
        return False

def install_node_windows(preferred_pm: Optional[str] = None) -> bool:
    """Try to install Node.js LTS on Windows using winget, choco, or scoop."""
    order = []
    if preferred_pm: order.append(preferred_pm.lower())
    order += ["winget", "choco", "scoop"]
    seen = set(); order = [x for x in order if not (x in seen or seen.add(x))]

    for pm in order:
        if pm == "winget" and which("winget"):
            if _quiet_run(["winget", "install", "-e", "--id", "OpenJS.NodeJS.LTS",
                           "--source", "winget", "--accept-source-agreements", "--accept-package-agreements"]):
                return True
        elif pm == "choco" and which("choco"):
            if _quiet_run(["choco", "install", "-y", "nodejs-lts"]):
                return True
        elif pm == "scoop" and which("scoop"):
            _quiet_run(["scoop", "bucket", "add", "main"])
            if _quiet_run(["scoop", "install", "nodejs-lts"]):
                return True
    return False

def ensure_npm(auto_install: bool, preferred_pm: Optional[str]) -> Optional[str]:
    npm_cmd = find_npm_command()
    if npm_cmd:
        return npm_cmd

    if os.name == "nt" and auto_install:
        print("[VITE] npm not found. Attempting to install Node.js LTS (Windows).")
        if install_node_windows(preferred_pm):
            npm_cmd = find_npm_command()
            if npm_cmd:
                print(f"[VITE] Node.js installed. Found npm at: {npm_cmd}")
                return npm_cmd
            print("[VITE] Node.js installer finished but npm not yet visible on PATH. "
                  "Close/reopen terminal or reboot may be required.")
            return None

        print("[VITE] Automatic Node.js install failed or not available. "
              "Please install Node.js LTS manually: https://nodejs.org")
        return None

    print("[VITE] npm not found. Install Node.js to enable frontend.")
    return None

# -------------------- scaffolding --------------------

def ensure_frontend(root: Path) -> Path:
    fe = root / "frontend"
    (fe / "src").mkdir(parents=True, exist_ok=True)
    (fe / "public").mkdir(parents=True, exist_ok=True)

    pkg = fe / "package.json"
    if not pkg.exists():
        pkg.write_text(json.dumps({
            "name": "vela-frontend",
            "version": "0.1.0",
            "private": True,
            "type": "module",
            "scripts": {
                "dev": "vite",
                "build": "vite build",
                "preview": "vite preview"
            },
            "dependencies": {
                "react": "^18.2.0",
                "react-dom": "^18.2.0"
            },
            "devDependencies": {
                "@vitejs/plugin-react": "^4.2.0",
                "vite": "^5.3.0"
            }
        }, indent=2), encoding="utf-8")

    # Branded root HTML with a visible preflight health check (before React)
    index_html = fe / "index.html"
    if not index_html.exists():
        index_html.write_text(
            textwrap.dedent("""\
                <!doctype html>
                <html>
                  <head>
                    <meta charset="UTF-8" />
                    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
                    <title>VelaOS • Frontend</title>
                    <style>
                      :root { color-scheme: light dark; }
                      body { font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; margin: 0; }
                      .banner { padding: 16px 20px; background: #0a0a0a; color: #fff; }
                      .container { padding: 24px; }
                      .health { font-size: 14px; opacity: .85; }
                      code { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
                    </style>
                  </head>
                  <body>
                    <div class="banner">
                      <strong>VelaOS</strong> • React + Vite (proxy → Flask @ <code>http://127.0.0.1:5000</code>)
                    </div>
                    <div class="container">
                      <div id="health-preflight" class="health">preflight: checking <code>/api/health</code>…</div>
                      <div id="root" style="margin-top:14px;"></div>
                    </div>

                    <script>
                      (async () => {
                        const el = document.getElementById('health-preflight');
                        try {
                          const r = await fetch('/api/health', {headers:{'Accept':'application/json'}});
                          const j = await r.json();
                          el.textContent = 'preflight: ' + JSON.stringify(j);
                        } catch (e) {
                          el.textContent = 'preflight: unreachable';
                        }
                      })();
                    </script>

                    <script type="module" src="/src/main.jsx"></script>
                  </body>
                </html>
            """),
            encoding="utf-8",
        )

    main_jsx = fe / "src" / "main.jsx"
    if not main_jsx.exists():
        main_jsx.write_text(
            textwrap.dedent("""\
                import React from "react";
                import { createRoot } from "react-dom/client";
                import App from "./App.jsx";

                const root = createRoot(document.getElementById("root"));
                root.render(<App />);
            """),
            encoding="utf-8",
        )

    app_jsx = fe / "src" / "App.jsx"
    if not app_jsx.exists():
        app_jsx.write_text(
            textwrap.dedent("""\
                import React, { useEffect, useState } from "react";

                export default function App() {
                  const [health, setHealth] = useState(null);
                  useEffect(() => {
                    fetch("/api/health")
                      .then(r => r.json())
                      .then(setHealth)
                      .catch(() => setHealth({ status: "unreachable" }));
                  }, []);
                  return (
                    <div>
                      <h1 style={{margin:"8px 0"}}>Vite + Flask</h1>
                      <p>React fetch: {health ? JSON.stringify(health) : "loading..."}</p>
                    </div>
                  );
                }
            """),
            encoding="utf-8",
        )

    vite_cfg = fe / "vite.config.js"
    if not vite_cfg.exists():
        vite_cfg.write_text(
            textwrap.dedent("""\
                import { defineConfig } from "vite";
                import react from "@vitejs/plugin-react";

                export default defineConfig({
                  plugins: [react()],
                  server: {
                    host: "127.0.0.1",
                    port: 5173,
                    proxy: {
                      "/api": {
                        target: "http://127.0.0.1:5000",
                        changeOrigin: true
                      }
                    }
                  }
                });
            """),
            encoding="utf-8",
        )
    return fe

# -------------------- install & start --------------------

def npm_install(fe_dir: Path, npm_cmd: Optional[str]) -> None:
    if not npm_cmd:
        print("[VITE] Skipping npm install (npm not available).")
        return

    env = os.environ.copy()
    # keep output flowing
    env.setdefault("npm_config_loglevel", "info")
    env.setdefault("npm_config_progress", "true")
    env.setdefault("npm_config_fund", "false")
    env.setdefault("npm_config_audit", "false")

    label = "npm"
    print(f"[{label}] exec: {npm_cmd} install (cwd={fe_dir})", flush=True)

    creationflags = 0
    if os.name == "nt":
        # New group + no extra window. Intentionally NOT detached (we want streaming IO).
        CREATE_NEW_PROCESS_GROUP = 0x00000200
        CREATE_NO_WINDOW = 0x08000000
        creationflags = CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW

    p = subprocess.Popen(
        [npm_cmd, "install"],
        cwd=str(fe_dir),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        shell=False,
        creationflags=creationflags
    )
    assert p.stdout is not None
    try:
        for line in iter(p.stdout.readline, ""):
            print(f"[{label}] {line.rstrip()}", flush=True)
    finally:
        p.stdout.close()
    rc = p.wait()
    print(f"[{label}] exit code: {rc}", flush=True)
    if rc != 0:
        raise SystemError("npm install failed")

def write_combined_start_stop(root: Path) -> None:
    run_dir = root / ".vela-run"; run_dir.mkdir(exist_ok=True)
    start_py = root / "start_server.py"
    stop_py  = root / "stop_servers.py"

    start_py.write_text(
        textwrap.dedent("""\
            #!/usr/bin/env python3
            import os, sys, subprocess, time, shutil
            from pathlib import Path

            def pid_alive(pid: int) -> bool:
                try:
                    if os.name == "nt":
                        out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}"],
                                             capture_output=True, text=True)
                        return str(pid) in out.stdout
                    else:
                        os.kill(pid, 0)
                        return True
                except Exception:
                    return False

            def find_npm() -> str | None:
                p = shutil.which("npm")
                if p: return p
                if os.name == "nt":
                    candidates = [
                        Path(os.environ.get("ProgramFiles", r"C:\\Program Files")) / "nodejs" / "npm.cmd",
                        Path(os.environ.get("ProgramFiles(x86)", r"C:\\Program Files (x86)")) / "nodejs" / "npm.cmd",
                        Path(os.environ.get("LocalAppData", r"C:\\Users\\%USERNAME%\\AppData\\Local")) / "Programs" / "node" / "npm.cmd",
                    ]
                    nvm_home = os.environ.get("NVM_HOME")
                    if nvm_home:
                        candidates.append(Path(nvm_home) / "npm.cmd")
                    for c in candidates:
                        if c.exists():
                            return str(c)
                else:
                    for c in ("/opt/homebrew/bin/npm", "/usr/local/bin/npm", "/usr/bin/npm"):
                        if Path(c).exists():
                            return c
                return None

            def start_flask(root: Path) -> int:
                backend = root / "backend"
                run_dir = root / ".vela-run"; run_dir.mkdir(exist_ok=True)
                pid_file = run_dir / "flask.pid"

                if pid_file.exists():
                    try:
                        old = int(pid_file.read_text().strip())
                    except Exception:
                        old = None
                    if old and not pid_alive(old):
                        pid_file.unlink(missing_ok=True)
                    elif old:
                        print(f"[start] Flask already running (pid={old})"); return old

                venv = backend / ".venv"
                python_exe = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
                if not python_exe.exists():
                    python_exe = Path(sys.executable)

                env = os.environ.copy()
                env["FLASK_APP"] = "app.main:create_app"
                env["PYTHONPATH"] = str(backend)
                env.setdefault("FLASK_RUN_HOST", "127.0.0.1")
                env.setdefault("FLASK_RUN_PORT", "5000")

                cmd = [str(python_exe), "-m", "flask", "run",
                       "--host", env["FLASK_RUN_HOST"], "--port", env["FLASK_RUN_PORT"]]

                kwargs = dict(cwd=str(backend), env=env,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                if os.name == "nt":
                    CREATE_NEW_PROCESS_GROUP = 0x00000200
                    CREATE_NO_WINDOW = 0x08000000
                    kwargs["creationflags"] = CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW
                else:
                    kwargs["preexec_fn"] = os.setpgrp

                proc = subprocess.Popen(cmd, **kwargs)
                pid_file.write_text(str(proc.pid), encoding="utf-8")
                print(f"[start] Flask (pid={proc.pid}) http://{env['FLASK_RUN_HOST']}:{env['FLASK_RUN_PORT']}")
                try:
                    for _ in range(10):
                        line = proc.stdout.readline()
                        if not line: break
                        sys.stdout.write(line); sys.stdout.flush()
                except KeyboardInterrupt:
                    pass
                return proc.pid

            def start_vite(root: Path) -> int | None:
                fe = root / "frontend"
                if not (fe / "package.json").exists():
                    return None
                run_dir = root / ".vela-run"
                pid_file = run_dir / "vite.pid"

                if pid_file.exists():
                    try:
                        old = int(pid_file.read_text().strip())
                    except Exception:
                        old = None
                    if old and not pid_alive(old):
                        pid_file.unlink(missing_ok=True)
                    elif old:
                        print(f"[start] Vite already running (pid={old})"); return old

                npm_cmd = find_npm()
                if not npm_cmd:
                    print("[start] npm not found; skipping Vite.")
                    return None

                cmd = [npm_cmd, "run", "dev"]
                kwargs = dict(cwd=str(fe),
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                if os.name == "nt":
                    CREATE_NEW_PROCESS_GROUP = 0x00000200
                    CREATE_NO_WINDOW = 0x08000000
                    kwargs["creationflags"] = CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW
                else:
                    kwargs["preexec_fn"] = os.setpgrp

                proc = subprocess.Popen(cmd, **kwargs)
                pid_file.write_text(str(proc.pid), encoding="utf-8")
                print(f"[start] Vite (pid={proc.pid}) http://127.0.0.1:5173")
                try:
                    for _ in range(10):
                        line = proc.stdout.readline()
                        if not line: break
                        sys.stdout.write(line); sys.stdout.flush()
                except KeyboardInterrupt:
                    pass
                return proc.pid

            def main():
                root = Path(__file__).resolve().parent
                fp = start_flask(root)
                vp = start_vite(root)
                print("[start] Done.")
                return 0

            if __name__ == "__main__":
                sys.exit(main())
        """),
        encoding="utf-8",
    )

    stop_py.write_text(
        textwrap.dedent("""\
            #!/usr/bin/env python3
            import os, sys, time, signal, subprocess
            from pathlib import Path

            def kill_tree_windows(pid: int) -> None:
                subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                               capture_output=True, text=True)

            def stop_pid(pid_file: Path, label: str) -> None:
                if not pid_file.exists():
                    print(f"[stop] No {label} pid file.")
                    return
                try:
                    pid = int(pid_file.read_text().strip())
                except Exception:
                    print(f"[stop] Invalid {label} pid file.")
                    pid_file.unlink(missing_ok=True)
                    return
                print(f"[stop] Stopping {label} pid={pid}...")
                if os.name == "nt":
                    kill_tree_windows(pid)
                else:
                    try:
                        os.kill(pid, signal.SIGTERM)
                    except ProcessLookupError:
                        pass
                time.sleep(0.5)
                pid_file.unlink(missing_ok=True)
                print(f"[stop] {label} stopped.")

            def main():
                root = Path(__file__).resolve().parent
                run_dir = root / ".vela-run"
                stop_pid(run_dir / "vite.pid", "Vite")
                stop_pid(run_dir / "flask.pid", "Flask")
                print("[stop] Done.")
                return 0

            if __name__ == "__main__":
                sys.exit(main())
        """),
        encoding="utf-8",
    )

def start_now_detached(root: Path) -> None:
    """Launch start_server.py detached so the bootloader can finish."""
    start_py = root / "start_server.py"
    py = sys.executable
    kwargs = dict(cwd=str(root),
                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if os.name == "nt":
        CREATE_NEW_PROCESS_GROUP = 0x00000200
        CREATE_NO_WINDOW = 0x08000000
        kwargs["creationflags"] = CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW
    else:
        kwargs["preexec_fn"] = os.setpgrp
    try:
        subprocess.Popen([py, str(start_py)], **kwargs)
        print("[VITE] start_server.py launched (detached).")
    except Exception as e:
        print(f"[VITE] WARN: could not start servers automatically: {e}")

# -------------------- entry --------------------

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--deploy", action="store_true", help="Install Vite/React and configure proxy")
    ap.add_argument("--auto-install-node", action="store_true", help="Attempt to install Node.js if npm is missing (Windows only)")
    ap.add_argument("--pm", choices=["winget","choco","scoop"], help="Package manager to use for Node.js install (Windows)")
    ap.add_argument("--start-now", action="store_true", help="Start Flask + Vite immediately (detached)")
    args, _ = ap.parse_known_args()

    root = resolve_deployment_root()
    fe = ensure_frontend(root)

    npm_cmd = ensure_npm(auto_install=args.auto_install_node, preferred_pm=args.pm)
    npm_install(fe, npm_cmd)
    write_combined_start_stop(root)

    if args.start_now:
        start_now_detached(root)

    print("[VITE] Frontend ready. Use: python start_server.py (starts Flask + Vite).")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
