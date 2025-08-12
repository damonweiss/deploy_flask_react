#!/usr/bin/env python3
"""
Simple Folder Structure Bootloader
Just creates the project folder structure - no dependencies, no installs

Order of Operations:
1. GitHub clone (handled by VelaOS)
2. Create folder structure only
"""

import os
import sys
import json
import argparse
import logging
from pathlib import Path
from typing import Dict, Any

# --- stdout safety ---
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# --- logging first (so class methods can log immediately) ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("folder_bootloader.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("folder_bootloader")


def safe_write(path: Path, content: str, make_executable: bool = False) -> bool:
    """Write file only if it does not already exist. Returns True if created."""
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    if make_executable and os.name != "nt":
        try:
            os.chmod(path, 0o755)
        except Exception:
            pass
    return True


def write_unified_scripts(project_root: Path) -> list[str]:
    """Create start_server.py and stop_servers.py if missing."""
    start_py = project_root / "start_server.py"
    stop_py = project_root / "stop_servers.py"

    START_CONTENT = r'''#!/usr/bin/env python3
import os, sys, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
VENV = BACKEND / ".venv"
PID_DIR = ROOT / ".pids"
PID_DIR.mkdir(exist_ok=True)

def venv_python() -> str:
    return str(VENV / ("Scripts/python.exe" if os.name=="nt" else "bin/python"))

def detect_target(py: str) -> str | None:
    code = (
        "import importlib; m=importlib.import_module('app.main'); "
        "print('CREATE' if hasattr(m,'create_app') else ('APP' if hasattr(m,'app') else 'NONE'))"
    )
    try:
        out = subprocess.check_output([py, "-c", code], cwd=str(BACKEND), text=True).strip()
        if out == "CREATE": return "app.main:create_app"
        if out == "APP":    return "app.main:app"
        return None
    except Exception:
        return None

def run_flask(py: str, target: str):
    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("PYTHONUTF8", "1")
    cmd = [py, "-m", "flask", "--app", target, "run", "--debug", "--port", "5000"]
    proc = subprocess.Popen(cmd, cwd=str(BACKEND), env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    (PID_DIR / "flask.pid").write_text(str(proc.pid), encoding="utf-8")
    print(f"[start] Flask dev server starting pid={proc.pid} -> http://127.0.0.1:5000")
    try:
        assert proc.stdout is not None
        for line in proc.stdout:
            sys.stdout.write(line)
    finally:
        try: proc.wait()
        except Exception: pass

def main():
    py = venv_python()
    if not Path(py).exists():
        print("[start] venv python not found:", py)
        print("        Run Step 2 to create backend/.venv")
        sys.exit(1)
    target = detect_target(py)
    if not target:
        print("[start] Could not find create_app() or app in backend/app/main.py")
        sys.exit(1)
    run_flask(py, target)

if __name__ == "__main__":
    main()
'''

    STOP_CONTENT = r'''#!/usr/bin/env python3
import os, signal
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PID_DIR = ROOT / ".pids"

def kill_pidfile(name: str):
    p = PID_DIR / name
    if not p.exists():
        return False
    try:
        pid = int(p.read_text().strip())
    except Exception:
        p.unlink(missing_ok=True)
        return False
    try:
        if os.name == "nt":
            os.system(f"taskkill /PID {pid} /T /F >nul 2>&1")
        else:
            os.kill(pid, signal.SIGTERM)
        print(f"[stop] killed {name} pid={pid}")
    except Exception as e:
        print(f"[stop] could not kill {name} pid={pid}: {e}")
    finally:
        p.unlink(missing_ok=True)
    return True

def main():
    any_killed = False
    any_killed |= kill_pidfile("flask.pid")
    any_killed |= kill_pidfile("vite.pid")
    if not any_killed:
        print("[stop] no pid files found")
    else:
        print("[stop] done")

if __name__ == "__main__":
    main()
'''

    created = []
    if safe_write(start_py, START_CONTENT, make_executable=True):
        created.append("start_server.py")
    if safe_write(stop_py, STOP_CONTENT, make_executable=True):
        created.append("stop_servers.py")
    return created


class FolderBootloader:
    """Simple bootloader that just creates folder structure."""

    def __init__(self, config_path: str | None = None):
        self.config_path = config_path or "bootloader_config.json"

        # Determine project root (VelaOS → ascend to deployment root; else CWD)
        vela_target = os.environ.get("VELA_CORE_DIR")
        if vela_target:
            core_path = Path(vela_target)
            # cores -> .vela -> data -> deployment_root
            deployment_root = core_path.parent.parent.parent.parent
            self.project_root = deployment_root
            print(f"[VelaOS] Core directory: {core_path}")
            print(f"[VelaOS] Using deployment root: {self.project_root}")
        else:
            self.project_root = Path.cwd()
            print(f"[Local] Using current directory: {self.project_root}")

        # Now safe to load config + log
        self.config = self._load_config()
        self.app_name = self.config["application"]["name"]
        self.logger = log

    def _load_config(self) -> Dict[str, Any]:
        """Load bootloader configuration."""
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            log.warning(f"Config file {self.config_path} not found, using defaults")
            return self._default_config()
        except json.JSONDecodeError as e:
            log.error(f"Invalid JSON in config file: {e}")
            return self._default_config()

    def _default_config(self) -> Dict[str, Any]:
        """Return default configuration."""
        return {
            "application": {
                "name": "Flask-Vite-App",
                "version": "1.0.0",
                "description": "Flask + Vite application",
            },
            "structure": {
                "backend_dir": "backend",
                "frontend_dir": "frontend",
                "tests_dir": "tests",
                "docs_dir": "docs",
                "scripts_dir": "scripts",
            },
        }

    def create_folder_structure(self):
        """Create the project folder structure."""
        self.logger.info("Creating project folder structure...")
        structure = self.config.get("structure", {})

        folders = [
            structure.get("backend_dir", "backend"),
            structure.get("frontend_dir", "frontend"),
            f"{structure.get('frontend_dir', 'frontend')}/src",
            f"{structure.get('frontend_dir', 'frontend')}/src/components",
            f"{structure.get('frontend_dir', 'frontend')}/src/pages",
            f"{structure.get('frontend_dir', 'frontend')}/src/hooks",
            f"{structure.get('frontend_dir', 'frontend')}/src/utils",
            f"{structure.get('frontend_dir', 'frontend')}/public",
            f"{structure.get('backend_dir', 'backend')}/app",
            f"{structure.get('backend_dir', 'backend')}/app/routes",
            f"{structure.get('backend_dir', 'backend')}/app/models",
            f"{structure.get('backend_dir', 'backend')}/app/utils",
            structure.get("tests_dir", "tests"),
            f"{structure.get('tests_dir', 'tests')}/backend",
            f"{structure.get('tests_dir', 'tests')}/frontend",
            structure.get("docs_dir", "docs"),
            structure.get("scripts_dir", "scripts"),
            "config",
            "logs",
        ]

        created_folders = []
        for folder in folders:
            folder_path = self.project_root / folder
            if not folder_path.exists():
                folder_path.mkdir(parents=True, exist_ok=True)
                created_folders.append(folder)
                self.logger.info(f"Created: {folder}")
            else:
                self.logger.info(f"Exists: {folder}")

        self._create_basic_files()

        # Always provide unified start/stop scripts
        created_scripts = write_unified_scripts(self.project_root)
        for f in created_scripts:
            self.logger.info(f"Created file: {f}")

        self.logger.info("Folder structure creation completed!")
        self.logger.info(f"Created {len(created_folders)} new folders")
        return created_folders

    def _create_basic_files(self):
        """Create basic placeholder files (non-destructive: only if missing)."""
        files_to_create = [
            # Backend files
            (
                "backend/app/__init__.py",
                "# Flask app init package\n",
            ),
            (
                "backend/app/main.py",
                # App factory with /api/health and root
                "from flask import Flask, jsonify\n\n"
                "def create_app():\n"
                "    app = Flask(__name__)\n\n"
                "    @app.get('/api/health')\n"
                "    def health():\n"
                "        return jsonify({'status': 'ok'})\n\n"
                "    @app.get('/')\n"
                "    def hello():\n"
                "        return jsonify({'message': 'Hello from Flask!'})\n\n"
                "    return app\n\n"
                "# Expose `app` for servers that import module:app\n"
                "app = create_app()\n",
            ),
            ("backend/app/routes/__init__.py", "# Routes module\n"),
            ("backend/app/models/__init__.py", "# Models module\n"),
            ("backend/app/utils/__init__.py", "# Utils module\n"),
            # Frontend files
            (
                "frontend/src/main.jsx",
                "// Main React entry point\n"
                "import React from 'react'\n"
                "import ReactDOM from 'react-dom/client'\n"
                "import App from './App.jsx'\n\n"
                "ReactDOM.createRoot(document.getElementById('root')).render(\n"
                "  <React.StrictMode>\n"
                "    <App />\n"
                "  </React.StrictMode>,\n"
                ")\n",
            ),
            (
                "frontend/src/App.jsx",
                "// Main App component\n"
                "import React from 'react'\n\n"
                "function App() {\n"
                "  return (\n"
                "    <div>\n"
                "      <h1>Flask + Vite App</h1>\n"
                "      <p>Welcome to your new application!</p>\n"
                "    </div>\n"
                "  )\n"
                "}\n\n"
                "export default App\n",
            ),
            (
                "frontend/public/index.html",
                "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n"
                "  <meta charset=\"UTF-8\" />\n"
                "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />\n"
                "  <title>Flask + Vite App</title>\n"
                "</head>\n<body>\n"
                "  <div id=\"root\"></div>\n"
                "  <script type=\"module\" src=\"/src/main.jsx\"></script>\n"
                "</body>\n</html>\n",
            ),
            # Tests
            ("tests/backend/__init__.py", "# Backend tests\n"),
            ("tests/frontend/__init__.py", "# Frontend tests\n"),
            (
                "tests/test_example.py",
                "# Example test file\n"
                "def test_example():\n"
                "    assert True\n",
            ),
            # Config
            (
                "config/.env.example",
                "# Environment variables example\n"
                "FLASK_ENV=development\nFLASK_PORT=5000\nVITE_PORT=5173\n",
            ),
            # Docs & scripts & logs
            ("docs/README.md", f"# {self.config['application']['name']} Documentation\n\n"),
            ("scripts/dev.py", "#!/usr/bin/env python3\nprint('Development script placeholder')\n"),
            ("logs/.gitkeep", "# Keep logs directory in git\n"),
        ]

        created_files = []
        for rel, content in files_to_create:
            full = self.project_root / rel
            if safe_write(full, content, make_executable=rel.endswith(".py") and "scripts/" in rel):
                created_files.append(rel)
                self.logger.info(f"Created file: {rel}")

        # Seed a requirements.txt if missing (helps Step 2 succeed)
        reqs = self.project_root / "backend" / "requirements.txt"
        default_reqs = (
            "flask>=3.0,<4\n"
            "werkzeug>=3.0,<4\n"
            "jinja2>=3.1,<4\n"
            "markupsafe>=2.1,<3\n"
            "blinker>=1.7,<2\n"
            "itsdangerous>=2.1,<3\n"
        )
        if safe_write(reqs, default_reqs):
            self.logger.info("Created file: backend/requirements.txt")

        self.logger.info(f"Created {len(created_files)} basic files")
        return created_files

    def deploy(self):
        """Deploy - just create folder structure."""
        self.logger.info("Starting folder structure deployment...")
        try:
            self.create_folder_structure()
            self.logger.info("Folder structure deployment completed successfully!")
            self.logger.info("Project structure is ready for development")
            self._show_structure()
        except Exception as e:
            self.logger.error(f"[X] Deployment failed: {e}")
            raise

    def _show_structure(self):
        self.logger.info("")
        self.logger.info("Project Structure Created:")
        self.logger.info("|-- backend/")
        self.logger.info("|   `-- app/")
        self.logger.info("|       |-- routes/")
        self.logger.info("|       |-- models/")
        self.logger.info("|       `-- utils/")
        self.logger.info("|-- frontend/")
        self.logger.info("|   |-- src/")
        self.logger.info("|   |   |-- components/")
        self.logger.info("|   |   |-- pages/")
        self.logger.info("|   |   |-- hooks/")
        self.logger.info("|   |   `-- utils/")
        self.logger.info("|   `-- public/")
        self.logger.info("|-- tests/")
        self.logger.info("|   |-- backend/")
        self.logger.info("|   `-- frontend/")
        self.logger.info("|-- docs/")
        self.logger.info("|-- scripts/")
        self.logger.info("|-- config/")
        self.logger.info("`-- logs/")


def main():
    parser = argparse.ArgumentParser(description="Simple Folder Structure Bootloader")
    parser.add_argument("--deploy", action="store_true", help="Create folder structure")
    parser.add_argument("--config", default="bootloader_config.json", help="Config file path")
    args = parser.parse_args()

    bootloader = FolderBootloader(config_path=args.config)

    if args.deploy:
        bootloader.deploy()
    else:
        print("Folder Bootloader - Use --deploy to create folder structure")


if __name__ == "__main__":
    main()
