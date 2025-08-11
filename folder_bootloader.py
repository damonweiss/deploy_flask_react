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


class FolderBootloader:
    """Simple bootloader that just creates folder structure."""
    
    def __init__(self, config_path: str = None):
        self.config_path = config_path or "bootloader_config.json"
        self.config = self._load_config()
        
        # Use VELA_CORE_DIR if available (VelaOS deployment), otherwise current directory
        vela_target = os.environ.get("VELA_CORE_DIR")
        if vela_target:
            # VELA_CORE_DIR points to deep internal directory like:
            # C:\...\vela_install_20250810_193432\data\.vela\cores\1.0.0-e34b2e4c
            # We want the deployment root: C:\...\vela_install_20250810_193432
            core_path = Path(vela_target)
            # Go up: cores -> .vela -> data -> deployment_root
            deployment_root = core_path.parent.parent.parent.parent
            self.project_root = deployment_root
            print(f"[VelaOS] Core directory: {core_path}")
            print(f"[VelaOS] Using deployment root: {self.project_root}")
        else:
            self.project_root = Path.cwd()
            print(f"[Local] Using current directory: {self.project_root}")
            
        self.app_name = self.config["application"]["name"]
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('folder_bootloader.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
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
                "description": "Flask + Vite application"
            },
            "structure": {
                "backend_dir": "backend",
                "frontend_dir": "frontend",
                "tests_dir": "tests",
                "docs_dir": "docs",
                "scripts_dir": "scripts"
            }
        }
    
    def create_folder_structure(self):
        """Create the project folder structure."""
        self.logger.info("Creating project folder structure...")
        
        # Get folder names from config
        structure = self.config.get("structure", {})
        
        # Define the folder structure
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
            "logs"
        ]
        
        # Create each folder
        created_folders = []
        for folder in folders:
            folder_path = self.project_root / folder
            if not folder_path.exists():
                folder_path.mkdir(parents=True, exist_ok=True)
                created_folders.append(folder)
                self.logger.info(f"Created: {folder}")
            else:
                self.logger.info(f"Exists: {folder}")
        
        # Create basic files
        self._create_basic_files()
        
        self.logger.info(f"Folder structure creation completed!")
        self.logger.info(f"Created {len(created_folders)} new folders")
        
        return created_folders
    
    def _create_basic_files(self):
        """Create basic placeholder files."""
        files_to_create = [
            # Backend files
            ("backend/app/__init__.py", "# Flask app initialization\n"),
            ("backend/app/main.py", "# Main Flask application\nfrom flask import Flask\n\napp = Flask(__name__)\n\n@app.route('/')\ndef hello():\n    return {'message': 'Hello from Flask!'}\n"),
            ("backend/app/routes/__init__.py", "# Routes module\n"),
            ("backend/app/models/__init__.py", "# Models module\n"),
            ("backend/app/utils/__init__.py", "# Utils module\n"),
            
            # Frontend files
            ("frontend/src/main.jsx", "// Main React entry point\nimport React from 'react'\nimport ReactDOM from 'react-dom/client'\nimport App from './App.jsx'\n\nReactDOM.createRoot(document.getElementById('root')).render(\n  <React.StrictMode>\n    <App />\n  </React.StrictMode>,\n)\n"),
            ("frontend/src/App.jsx", "// Main App component\nimport React from 'react'\n\nfunction App() {\n  return (\n    <div>\n      <h1>Flask + Vite App</h1>\n      <p>Welcome to your new application!</p>\n    </div>\n  )\n}\n\nexport default App\n"),
            ("frontend/public/index.html", "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n    <meta charset=\"UTF-8\">\n    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n    <title>Flask + Vite App</title>\n</head>\n<body>\n    <div id=\"root\"></div>\n    <script type=\"module\" src=\"/src/main.jsx\"></script>\n</body>\n</html>\n"),
            
            # Test files
            ("tests/backend/__init__.py", "# Backend tests\n"),
            ("tests/frontend/__init__.py", "# Frontend tests\n"),
            ("tests/test_example.py", "# Example test file\ndef test_example():\n    assert True\n"),
            
            # Config files
            ("config/.env.example", "# Environment variables example\nFLASK_ENV=development\nFLASK_PORT=5000\nVITE_PORT=5173\n"),
            
            # Documentation
            ("docs/README.md", f"# {self.app_name} Documentation\n\nProject documentation goes here.\n"),
            
            # Scripts
            ("scripts/dev.py", "#!/usr/bin/env python3\n# Development scripts\nprint('Development script placeholder')\n"),
            
            # Logs placeholder
            ("logs/.gitkeep", "# Keep logs directory in git\n")
        ]
        
        created_files = []
        for file_path, content in files_to_create:
            full_path = self.project_root / file_path
            if not full_path.exists():
                full_path.write_text(content)
                created_files.append(file_path)
                self.logger.info(f"Created file: {file_path}")
        
        self.logger.info(f"Created {len(created_files)} basic files")
        return created_files
    
    def deploy(self):
        """Deploy - just create folder structure."""
        self.logger.info("Starting folder structure deployment...")
        
        try:
            created_folders = self.create_folder_structure()
            
            self.logger.info("Folder structure deployment completed successfully!")
            self.logger.info("Project structure is ready for development")
            
            # Show structure
            self._show_structure()
            
        except Exception as e:
            self.logger.error(f"[X] Deployment failed: {e}")
            raise
    
    def _show_structure(self):
        """Show the created project structure."""
        self.logger.info("\nProject Structure Created:")
        self.logger.info("├── backend/")
        self.logger.info("│   └── app/")
        self.logger.info("│       ├── routes/")
        self.logger.info("│       ├── models/")
        self.logger.info("│       └── utils/")
        self.logger.info("├── frontend/")
        self.logger.info("│   ├── src/")
        self.logger.info("│   │   ├── components/")
        self.logger.info("│   │   ├── pages/")
        self.logger.info("│   │   ├── hooks/")
        self.logger.info("│   │   └── utils/")
        self.logger.info("│   └── public/")
        self.logger.info("├── tests/")
        self.logger.info("│   ├── backend/")
        self.logger.info("│   └── frontend/")
        self.logger.info("├── docs/")
        self.logger.info("├── scripts/")
        self.logger.info("├── config/")
        self.logger.info("└── logs/")


def main():
    """Main entry point."""
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
