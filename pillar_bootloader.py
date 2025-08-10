#!/usr/bin/env python3
"""
Modular TOML-Based Pillar Bootloader
VelaOS Compatible Bootloader with Pillar Architecture

This enhanced bootloader supports:
- Pillar-based TOML configuration generation
- TOML merging and dependency management
- uv virtual environment setup
- npm frontend dependency installation
"""

import os
import sys
import json
import subprocess
import signal
import time
import threading
from pathlib import Path
from datetime import datetime
import argparse
import logging
import toml
from typing import Dict, List, Any, Optional


class PillarConfig:
    """Represents a single pillar configuration."""
    
    def __init__(self, name: str, pillar_type: str):
        self.name = name
        self.pillar_type = pillar_type
        self.dependencies = []
        self.dev_dependencies = []
        self.scripts = {}
        self.config = {}
    
    def add_dependency(self, package: str, version: str = "*"):
        """Add a Python dependency."""
        self.dependencies.append(f"{package}{version if version != '*' else ''}")
    
    def add_dev_dependency(self, package: str, version: str = "*"):
        """Add a development dependency."""
        self.dev_dependencies.append(f"{package}{version if version != '*' else ''}")
    
    def add_script(self, name: str, command: str):
        """Add a script command."""
        self.scripts[name] = command
    
    def to_toml_dict(self) -> Dict[str, Any]:
        """Convert pillar config to TOML dictionary."""
        toml_dict = {
            "project": {
                "name": self.name,
                "version": "0.1.0",
                "description": f"{self.pillar_type} pillar for {self.name}",
                "requires-python": ">=3.8"
            }
        }
        
        if self.dependencies:
            toml_dict["project"]["dependencies"] = self.dependencies
        
        if self.dev_dependencies:
            toml_dict["project"]["optional-dependencies"] = {
                "dev": self.dev_dependencies
            }
        
        if self.scripts:
            toml_dict["project"]["scripts"] = self.scripts
        
        # Add pillar-specific configuration
        toml_dict["tool"] = {
            "pillar": {
                "type": self.pillar_type,
                "name": self.name,
                **self.config
            }
        }
        
        return toml_dict


class FlaskPillar(PillarConfig):
    """Flask backend pillar configuration."""
    
    def __init__(self, name: str = "flask-backend"):
        super().__init__(name, "flask")
        
        # Flask core dependencies
        self.add_dependency("flask", ">=3.0.0")
        self.add_dependency("gunicorn", ">=21.0.0")
        self.add_dependency("flask-cors", ">=4.0.0")
        
        # Development dependencies
        self.add_dev_dependency("pytest", ">=7.0.0")
        self.add_dev_dependency("black", ">=23.0.0")
        self.add_dev_dependency("flake8", ">=6.0.0")
        
        # Scripts
        self.add_script("dev", "flask --app app run --debug --port 5000")
        self.add_script("prod", "gunicorn -w 4 -b 0.0.0.0:5000 app:app")
        self.add_script("test", "pytest tests/")
        
        # Flask-specific config
        self.config = {
            "port": 5000,
            "debug": False,
            "cors_origins": ["http://localhost:5173", "http://127.0.0.1:5173"]
        }


class VitePillar(PillarConfig):
    """Vite frontend pillar configuration."""
    
    def __init__(self, name: str = "vite-frontend"):
        super().__init__(name, "vite")
        
        # No Python dependencies for Vite pillar
        self.dependencies = []
        
        # Vite-specific config
        self.config = {
            "port": 5173,
            "proxy_target": "http://localhost:5000",
            "build_dir": "dist",
            "public_dir": "public"
        }


class PillarBootloader:
    """Enhanced bootloader with pillar architecture."""
    
    def __init__(self, config_path: str = None):
        self.config_path = config_path or "bootloader_config.json"
        self.config = self._load_config()
        self.pillars: List[PillarConfig] = []
        self.project_root = Path.cwd()
        self.processes = {}
        self.running = False
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('pillar_bootloader.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
        # Register signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _load_config(self) -> Dict[str, Any]:
        """Load bootloader configuration."""
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            self.logger.warning(f"Config file {self.config_path} not found, using defaults")
            return self._default_config()
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON in config file: {e}")
            return self._default_config()
    
    def _default_config(self) -> Dict[str, Any]:
        """Return default configuration."""
        return {
            "application": {
                "name": "Flask-Vite-App",
                "version": "1.0.0",
                "environment": "production"
            },
            "pillars": {
                "flask": {"enabled": True, "port": 5000},
                "vite": {"enabled": True, "port": 5173}
            },
            "deployment": {
                "auto_install": True,
                "health_check_interval": 30,
                "restart_on_failure": True
            }
        }
    
    def initialize_pillars(self):
        """Initialize pillar configurations based on config."""
        self.logger.info("Initializing pillars...")
        
        pillar_config = self.config.get("pillars", {})
        
        # Initialize Flask pillar if enabled
        if pillar_config.get("flask", {}).get("enabled", True):
            flask_pillar = FlaskPillar()
            flask_config = pillar_config.get("flask", {})
            if "port" in flask_config:
                flask_pillar.config["port"] = flask_config["port"]
            self.pillars.append(flask_pillar)
            self.logger.info("Flask pillar initialized")
        
        # Initialize Vite pillar if enabled
        if pillar_config.get("vite", {}).get("enabled", True):
            vite_pillar = VitePillar()
            vite_config = pillar_config.get("vite", {})
            if "port" in vite_config:
                vite_pillar.config["port"] = vite_config["port"]
            self.pillars.append(vite_pillar)
            self.logger.info("Vite pillar initialized")
    
    def generate_pillar_tomls(self):
        """Generate TOML files for each pillar."""
        self.logger.info("Generating pillar TOML configurations...")
        
        pillar_dir = self.project_root / "pillars"
        pillar_dir.mkdir(exist_ok=True)
        
        for pillar in self.pillars:
            toml_path = pillar_dir / f"{pillar.name}.toml"
            toml_dict = pillar.to_toml_dict()
            
            with open(toml_path, 'w') as f:
                toml.dump(toml_dict, f)
            
            self.logger.info(f"Generated {toml_path}")
    
    def merge_project_toml(self):
        """Merge pillar TOMLs into main project TOML."""
        self.logger.info("Merging pillar configurations into project TOML...")
        
        project_toml_path = self.project_root / "pyproject.toml"
        
        # Load existing project TOML or create new one
        if project_toml_path.exists():
            with open(project_toml_path, 'r') as f:
                project_toml = toml.load(f)
            self.logger.info("Loaded existing pyproject.toml")
        else:
            project_toml = {
                "project": {
                    "name": self.config["application"]["name"],
                    "version": self.config["application"]["version"],
                    "description": "Flask + Vite application with pillar architecture",
                    "requires-python": ">=3.8"
                }
            }
            self.logger.info("Created new pyproject.toml")
        
        # Merge dependencies from all pillars
        all_dependencies = set()
        all_dev_dependencies = set()
        all_scripts = {}
        
        for pillar in self.pillars:
            pillar_dict = pillar.to_toml_dict()
            
            # Merge dependencies
            if "dependencies" in pillar_dict["project"]:
                all_dependencies.update(pillar_dict["project"]["dependencies"])
            
            # Merge dev dependencies
            if "optional-dependencies" in pillar_dict["project"]:
                dev_deps = pillar_dict["project"]["optional-dependencies"].get("dev", [])
                all_dev_dependencies.update(dev_deps)
            
            # Merge scripts
            if "scripts" in pillar_dict["project"]:
                for script_name, script_cmd in pillar_dict["project"]["scripts"].items():
                    all_scripts[f"{pillar.name}-{script_name}"] = script_cmd
        
        # Update project TOML
        if all_dependencies:
            project_toml["project"]["dependencies"] = sorted(list(all_dependencies))
        
        if all_dev_dependencies:
            if "optional-dependencies" not in project_toml["project"]:
                project_toml["project"]["optional-dependencies"] = {}
            project_toml["project"]["optional-dependencies"]["dev"] = sorted(list(all_dev_dependencies))
        
        if all_scripts:
            project_toml["project"]["scripts"] = all_scripts
        
        # Add pillar configuration section
        if "tool" not in project_toml:
            project_toml["tool"] = {}
        
        project_toml["tool"]["pillars"] = {
            pillar.name: pillar.config for pillar in self.pillars
        }
        
        # Write merged TOML
        with open(project_toml_path, 'w') as f:
            toml.dump(project_toml, f)
        
        self.logger.info(f"Merged project TOML saved to {project_toml_path}")
    
    def setup_python_environment(self):
        """Setup Python virtual environment using uv."""
        self.logger.info("Setting up Python virtual environment with uv...")
        
        # Check if uv is available
        try:
            subprocess.run(['uv', '--version'], capture_output=True, check=True)
            self.logger.info("uv is available")
        except (subprocess.CalledProcessError, FileNotFoundError):
            self.logger.warning("uv is not installed. Skipping Python environment setup.")
            self.logger.info("To enable Python environment setup, install uv: curl -LsSf https://astral.sh/uv/install.sh | sh")
            return False
        
        # Create .venv if it doesn't exist
        venv_path = self.project_root / ".venv"
        if not venv_path.exists():
            self.logger.info("Creating virtual environment...")
            subprocess.run(['uv', 'venv'], cwd=self.project_root, check=True)
            self.logger.info("Virtual environment created")
        else:
            self.logger.info("Virtual environment already exists")
        
        # Install dependencies using uv sync
        self.logger.info("Installing Python dependencies...")
        subprocess.run(['uv', 'sync'], cwd=self.project_root, check=True)
        self.logger.info("Python dependencies installed")
        return True
    
    def setup_frontend_environment(self):
        """Setup frontend environment using npm."""
        self.logger.info("Setting up frontend environment with npm...")
        
        # Check if npm is available
        try:
            subprocess.run(['npm', '--version'], capture_output=True, check=True)
            self.logger.info("npm is available")
        except (subprocess.CalledProcessError, FileNotFoundError):
            self.logger.warning("npm is not installed. Skipping frontend environment setup.")
            self.logger.info("To enable frontend setup, install Node.js and npm")
            return False
        
        # Check if package.json exists
        package_json_path = self.project_root / "package.json"
        if not package_json_path.exists():
            self.logger.info("Creating package.json for Vite frontend...")
            self._create_package_json()
        
        # Run npm install
        self.logger.info("Installing frontend dependencies...")
        subprocess.run(['npm', 'install'], cwd=self.project_root, check=True)
        self.logger.info("Frontend dependencies installed")
        return True
    
    def _create_package_json(self):
        """Create a basic package.json for Vite."""
        package_json = {
            "name": self.config["application"]["name"].lower().replace(" ", "-"),
            "version": self.config["application"]["version"],
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
                "@types/react": "^18.2.0",
                "@types/react-dom": "^18.2.0",
                "@vitejs/plugin-react": "^4.0.0",
                "vite": "^5.0.0"
            }
        }
        
        package_json_path = self.project_root / "package.json"
        with open(package_json_path, 'w') as f:
            json.dump(package_json, f, indent=2)
        
        self.logger.info(f"Created {package_json_path}")
    
    def deploy(self):
        """Deploy the pillar-based application."""
        self.logger.info("Starting pillar-based deployment...")
        
        try:
            # Initialize pillars
            self.initialize_pillars()
            
            # Generate pillar TOMLs
            self.generate_pillar_tomls()
            
            # Merge into project TOML
            self.merge_project_toml()
            
            # Setup Python environment (optional)
            python_setup = self.setup_python_environment()
            
            # Setup frontend environment (optional)
            frontend_setup = self.setup_frontend_environment()
            
            # Report deployment status
            if python_setup and frontend_setup:
                self.logger.info("Pillar-based deployment completed successfully with full environment setup!")
            elif python_setup or frontend_setup:
                self.logger.info("Pillar-based deployment completed with partial environment setup!")
                if not python_setup:
                    self.logger.warning("Python environment setup skipped - install uv to enable")
                if not frontend_setup:
                    self.logger.warning("Frontend environment setup skipped - install Node.js/npm to enable")
            else:
                self.logger.info("Pillar-based deployment completed (TOML generation only)!")
                self.logger.warning("Environment setup skipped - install uv and Node.js/npm for full deployment")
            
        except Exception as e:
            self.logger.error(f"Deployment failed: {e}")
            raise
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        self.logger.info(f"Received signal {signum}, shutting down...")
        self.running = False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Pillar-based Flask + Vite Bootloader")
    parser.add_argument("--deploy", action="store_true", help="Deploy the application")
    parser.add_argument("--config", default="bootloader_config.json", help="Config file path")
    
    args = parser.parse_args()
    
    bootloader = PillarBootloader(config_path=args.config)
    
    if args.deploy:
        bootloader.deploy()
    else:
        print("Pillar Bootloader - Use --deploy to start deployment")


if __name__ == "__main__":
    main()
