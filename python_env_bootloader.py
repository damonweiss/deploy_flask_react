#!/usr/bin/env python3
"""
Python Environment Bootloader - Step 2
Sets up Python virtual environment using uv

Order of Operations:
1. [DONE] Create folder structure (Step 1)
2. [THIS STEP] Install uv and create .venv
3. [NEXT] Generate backend TOML
4. [NEXT] Setup frontend (npm)
"""

import os
import sys
import json
import argparse
import logging
import subprocess
import shutil
from pathlib import Path
from typing import Dict, Any
from datetime import datetime

# Setup comprehensive logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('python_env_bootloader.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class PythonEnvBootloader:
    """Bootloader that sets up Python virtual environment using uv."""
    
    def __init__(self, config_path: str = None):
        logger.info("=" * 60)
        logger.info("PYTHON ENVIRONMENT BOOTLOADER - STEP 2")
        logger.info("=" * 60)
        logger.info(f"Initializing PythonEnvBootloader at {datetime.now()}")
        logger.info(f"Python version: {sys.version}")
        logger.info(f"Current working directory: {os.getcwd()}")
        
        self.config_path = config_path or "bootloader_config.json"
        logger.info(f"Config path: {self.config_path}")
        self.config = self._load_config()
        
        # Use VELA_CORE_DIR if available (VelaOS deployment), otherwise current directory
        vela_target = os.environ.get("VELA_CORE_DIR")
        if vela_target:
            logger.info(f"VELA_CORE_DIR detected: {vela_target}")
            # VELA_CORE_DIR points to deep internal directory like:
            # C:\...\vela_install_20250810_193432\data\.vela\cores\1.0.0-e34b2e4c
            # We want the deployment root: C:\...\vela_install_20250810_193432
            core_path = Path(vela_target)
            logger.info(f"Core path: {core_path}")
            # Go up: cores -> .vela -> data -> deployment_root
            deployment_root = core_path.parent.parent.parent
            logger.info(f"Calculated deployment root: {deployment_root}")
            self.project_root = deployment_root
            logger.info(f"[VelaOS] Core directory: {core_path}")
            logger.info(f"[VelaOS] Using deployment root: {self.project_root}")
        else:
            logger.info("VELA_CORE_DIR not set - using current directory as project root")
            deployment_root = Path.cwd()
            self.project_root = deployment_root
            logger.info(f"[Local] Using current directory: {self.project_root}")
            
        self.app_name = self.config["application"]["name"]
        logger.info(f"Application name: {self.app_name}")
    
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
        """Default configuration."""
        return {
            "application": {
                "name": "flask-vite-app",
                "description": "Flask + Vite application"
            },
            "python": {
                "version": ">=3.8",
                "dependencies": [
                    "flask>=2.0.0",
                    "flask-cors>=4.0.0"
                ]
            }
        }
    
    def check_uv_installed(self) -> bool:
        """Check if uv is installed and accessible."""
        logger.info("Checking if uv is installed...")
        try:
            result = subprocess.run(['uv', '--version'], 
                                  capture_output=True, text=True, check=True)
            logger.info(f"✅ uv is installed: {result.stdout.strip()}")
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.warning("❌ uv is not installed or not in PATH")
            return False
    
    def install_uv(self) -> bool:
        """Install uv using pip."""
        try:
            logger.info("Installing uv...")
            subprocess.run([sys.executable, '-m', 'pip', 'install', 'uv'], 
                          check=True, capture_output=True, text=True)
            logger.info("✅ uv installed successfully")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ Failed to install uv: {e}")
            if e.stdout:
                logger.error(f"STDOUT: {e.stdout}")
            if e.stderr:
                logger.error(f"STDERR: {e.stderr}")
            return False
    
    def create_virtual_environment(self) -> bool:
        """Create Python virtual environment using uv."""
        venv_path = self.project_root / ".venv"
        
        if venv_path.exists():
            self.logger.info(f"✅ Virtual environment already exists: {venv_path}")
            return True
        
        try:
            self.logger.info(f"Creating virtual environment at: {venv_path}")
            
            # Change to project root for uv venv creation
            original_cwd = os.getcwd()
            os.chdir(self.project_root)
            
            try:
                # Create virtual environment with uv
                result = subprocess.run(['uv', 'venv', '.venv'], 
                                      capture_output=True, text=True, check=True)
                self.logger.info("✅ Virtual environment created successfully")
                if result.stdout:
                    self.logger.info(f"uv output: {result.stdout.strip()}")
                return True
            finally:
                os.chdir(original_cwd)
                
        except subprocess.CalledProcessError as e:
            self.logger.error(f"❌ Failed to create virtual environment: {e}")
            if e.stdout:
                self.logger.error(f"STDOUT: {e.stdout}")
            if e.stderr:
                self.logger.error(f"STDERR: {e.stderr}")
            return False
    
    def create_basic_python_files(self) -> bool:
        """Create basic Python project files."""
        files_to_create = [
            # Basic Python files
            ("backend/app/__init__.py", "# Flask application package\n"),
            ("backend/app/main.py", '''#!/usr/bin/env python3
"""
Main Flask application entry point.
"""

from flask import Flask
from flask_cors import CORS

def create_app():
    """Create and configure Flask application."""
    app = Flask(__name__)
    CORS(app)
    
    @app.route('/')
    def hello():
        return {"message": "Hello from Flask + Vite!"}
    
    @app.route('/api/health')
    def health():
        return {"status": "healthy", "service": "flask-backend"}
    
    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=5000)
'''),
            
            # Requirements placeholder (will be replaced by pyproject.toml)
            ("requirements.txt", "# This file is managed by uv and pyproject.toml\n# Use 'uv sync' to install dependencies\n"),
            
            # Python gitignore additions
            (".gitignore", '''# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
share/python-wheels/
*.egg-info/
.installed.cfg
*.egg
MANIFEST

# Virtual environments
.venv/
venv/
ENV/
env/

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Logs
*.log
logs/

# Environment variables
.env
.env.local
.env.development.local
.env.test.local
.env.production.local
'''),
        ]
        
        created_files = []
        for file_path, content in files_to_create:
            full_path = self.project_root / file_path
            
            # Only create if doesn't exist
            if not full_path.exists():
                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.write_text(content)
                created_files.append(file_path)
                self.logger.info(f"Created file: {file_path}")
            else:
                self.logger.info(f"File already exists: {file_path}")
        
        self.logger.info(f"Created {len(created_files)} Python files")
        return True
    
    def deploy(self):
        """Deploy - set up Python environment."""
        self.logger.info("Starting Python environment setup...")
        
        try:
            # Check if uv is installed
            if not self.check_uv_installed():
                self.logger.info("uv not found, attempting to install...")
                if not self.install_uv():
                    self.logger.error("❌ Failed to install uv - continuing without virtual environment")
                    return False
            
            # Create virtual environment
            if not self.create_virtual_environment():
                self.logger.error("❌ Failed to create virtual environment")
                return False
            
            # Create basic Python files
            if not self.create_basic_python_files():
                self.logger.error("❌ Failed to create Python files")
                return False
            
            self.logger.info("✅ Python environment setup completed successfully!")
            self.logger.info("🐍 Virtual environment is ready for development")
            
            # Show next steps
            self._show_next_steps()
            
        except Exception as e:
            self.logger.error(f"❌ Python environment setup failed: {e}")
            raise
    
    def _show_next_steps(self):
        """Show next steps for the user."""
        venv_path = self.project_root / ".venv"
        
        self.logger.info("\n" + "="*60)
        self.logger.info("🚀 PYTHON ENVIRONMENT READY")
        self.logger.info("="*60)
        self.logger.info(f"📁 Project root: {self.project_root}")
        self.logger.info(f"🐍 Virtual environment: {venv_path}")
        self.logger.info("\n📋 Next Steps:")
        self.logger.info("   1. ✅ Folder structure created")
        self.logger.info("   2. ✅ Python environment setup")
        self.logger.info("   3. 🔄 Generate backend TOML (Step 3)")
        self.logger.info("   4. 🔄 Setup frontend (Step 4)")
        
        # Activation instructions
        if os.name == 'nt':
            activate_cmd = f"{venv_path}\\Scripts\\activate"
        else:
            activate_cmd = f"source {venv_path}/bin/activate"
            
        self.logger.info(f"\n💡 To activate virtual environment:")
        self.logger.info(f"   {activate_cmd}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Python Environment Bootloader - Step 2")
    parser.add_argument("--deploy", action="store_true", help="Set up Python environment")
    parser.add_argument("--config", default="bootloader_config.json", help="Config file path")
    
    args = parser.parse_args()
    
    bootloader = PythonEnvBootloader(config_path=args.config)
    
    if args.deploy:
        bootloader.deploy()
    else:
        print("Python Environment Bootloader - Step 2")
        print("Use --deploy to set up Python environment")
        print("\nThis step will:")
        print("- Install uv (if not present)")
        print("- Create Python virtual environment (.venv)")
        print("- Create basic Python project files")


if __name__ == "__main__":
    main()
