#!/usr/bin/env python3
"""
Vite Bootloader (STEP 4)
- Resolves deployment root from VELA_CORE_DIR (or cwd)
- Ensures frontend/ with React+Vite scaffold
- Writes vite.config.js with proxy to Flask on 127.0.0.1:5000
- Runs npm install in frontend/
- Upgrades start_server.py / stop_servers.py to manage BOTH Flask and Vite
"""

from __future__ import annotations
import os
import sys
import subprocess
from pathlib import Path
import argparse
import json
import textwrap

def resolve_deployment_root() -> Path:
    core_dir = os.environ.get("VELA_CORE_DIR")
    if core_dir:
        p = Path(core_dir).resolve()
        try:
            return p.parents[3]
        except IndexError:
            pass
    return Path.cwd().resolve()

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

    index_html = fe / "index.html"
    if not index_html.exists():
        index_html.write_text(
            textwrap.dedent(
                """\
                <!doctype html>
                <html>
                  <head>
                    <meta charset="UTF-8" />
                    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
                    <title>Vela Vite</title>
                  </head>
                  <body>
                    <div id="root"></div>
                    <script type="module" src="/src/main.jsx"></script>
                  </body>
                </html>
                """
            ),
            encoding="utf-8",
        )

    main_jsx = fe / "src" / "main.jsx"
    if not main_jsx.exists():
        main_jsx.write_text(
            textwrap.dedent(
                """\
                import React from "react";
                import { createRoot } from "react-dom/client";
                import App from "./App.jsx";

                const root = createRoot(document.getElementById("root"));
                root.render(<App />);
                """
            ),
            encoding="utf-8",
        )

    app_jsx = fe / "src" / "App.jsx"
    if not app_jsx.exists():
        app_jsx.write_text(
            textwrap.dedent(
                """\
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
                    <div style={{fontFamily: "sans-serif", padding: 24}}>
                      <h1>Vite + Flask</h1>
                      <p>Backend health: {health ? JSON.stringify(health) : "loading..."}</p>
                    </div>
                  );
                }
                """
            ),
            encoding="utf-8",
        )

    vite_cfg = fe / "vite.config.js"
    if not vite_cfg.exists():
        vite_cfg.write_text(
            textwrap.dedent(
                """\
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
                """
            ),
            encoding="utf-8",
        )

    return fe

def npm_install(fe_dir: Path) -> None:
    try:
        subprocess.run(["npm", "--version"], capture_output=True, check=True)
    except Exception:
        print("[VITE] npm not found. Install Node.js to enable frontend.")
        return
    res = subprocess.run(["npm", "install"], cwd=str(fe_dir), text=True)
    if res.returncode != 0:
        raise SystemError("npm install failed")

def write_combined_start_stop(root: Path) -> None:
    run_dir = root / ".vela-run"; run_dir.mkdir(exist_ok=True)
    start_py = root / "start_server.py"
    stop_py = root / "stop_servers.py"

    start_py.write_text(
        textwrap.dedent(
            """\
            #!/usr/bin/env python3
            import os, sys, subprocess, time
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

                cmd = [str(python_exe), "-m", "flask", "run", "--debug",
                       "--host", env["FLASK_RUN_HOST"], "--port", env["FLASK_RUN_PORT"]]
                proc = subprocess.Popen(
                    cmd, cwd=str(backend), env=env,
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
                )
                pid_file.write_text(str(proc.pid), encoding="utf-8")
                print(f"[start] Flask (pid={proc.pid}) http://{env['FLASK_RUN_HOST']}:{env['FLASK_RUN_PORT']}")
                # tail a few lines
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

                try:
                    subprocess.run(["npm", "--version"], capture_output=True, check=True)
                except Exception:
                    print("[start] npm not found; skipping Vite.")
                    return None

                # Use npm run dev
                cmd = ["npm", "run", "dev"]
                proc = subprocess.Popen(
                    cmd, cwd=str(fe),
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, shell=(os.name=="nt")
                )
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
            """
        ),
        encoding="utf-8",
    )

    stop_py.write_text(
        textwrap.dedent(
            """\
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
            """
        ),
        encoding="utf-8",
    )

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--deploy", action="store_true", help="Install Vite/React and configure proxy")
    args, _ = ap.parse_known_args()

    root = resolve_deployment_root()
    fe = ensure_frontend(root)
    npm_install(fe)
    write_combined_start_stop(root)
    print("[VITE] Frontend ready. Use: python start_server.py (starts Flask + Vite).")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
