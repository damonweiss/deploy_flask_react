#!/usr/bin/env python3
"""
Flask + Vite Bootloader Deployment Script
VelaOS Compatible Bootloader for Flask/Vite Stack

This script is designed to be served from GitHub and executed by the VelaOS bootloader
to deploy and manage Flask + Vite applications in production environments.

Usage (via VelaOS bootloader):
    curl -sSL https://raw.githubusercontent.com/user/repo/main/flask_vite_bootloader.py | python3

Direct usage:
    python3 flask_vite_bootloader.py --deploy
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


class FlaskViteBootloader:
    """VelaOS compatible bootloader for Flask + Vite applications."""
    
    def __init__(self, config_path: str = None):
        self.config_path = config_path or "bootloader_config.json"
        self.config = self._load_config()
        self.processes = {}
        self.running = False
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('bootloader.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _load_config(self):
        """Load bootloader configuration."""
        if not Path(self.config_path).exists():
            self.logger.error(f"Configuration file not found: {self.config_path}")
            raise FileNotFoundError(f"Required configuration file missing: {self.config_path}")
        
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)
                self.logger.info(f"Loaded configuration from {self.config_path}")
                return config
        except Exception as e:
            self.logger.error(f"Failed to load configuration: {e}")
            raise
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        self.logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        self.stop()
        sys.exit(0)
    
    def deploy(self):
        """Deploy the Flask + Vite application."""
        self.logger.info("Starting Flask + Vite deployment...")
        
        try:
            # Create necessary directories
            self._create_directories()
            
            # Install dependencies
            if self.config['deployment']['auto_install']:
                self._install_dependencies()
            
            # Build frontend for production
            self._build_frontend()
            
            # Start services
            if self.config['deployment']['auto_start']:
                self._start_services()
            
            # Setup health monitoring
            if self.config['deployment']['health_check_enabled']:
                self._start_health_monitor()
            
            self.logger.info("Deployment completed successfully")
            
        except Exception as e:
            self.logger.error(f"Deployment failed: {e}")
            raise
    
    def _create_directories(self):
        """Create necessary directories for deployment."""
        # Runtime directories
        runtime_dirs = [
            self.config['paths']['logs_dir'],
            self.config['paths']['pid_dir']
        ]
        
        # Enhanced project structure directories
        project_dirs = [
            # Backend structure
            self.config['paths']['backend_dir'],
            f"{self.config['paths']['backend_dir']}/api",
            f"{self.config['paths']['backend_dir']}/config",
            
            # Frontend structure
            self.config['paths']['frontend_dir'],
            f"{self.config['paths']['frontend_dir']}/src",
            f"{self.config['paths']['frontend_dir']}/public",
            
            # Test structure
            "./backend-tests",
            "./frontend-tests",
            
            # Project Brain structure
            "./.Project Brain",
            "./.Project Brain/00 - LLM-Human Collaboration",
        ]
        
        all_dirs = runtime_dirs + project_dirs
        
        for dir_path in all_dirs:
            Path(dir_path).mkdir(parents=True, exist_ok=True)
            self.logger.info(f"Created directory: {dir_path}")
    
    def _install_dependencies(self):
        """Install backend and frontend dependencies."""
        self.logger.info("Installing dependencies...")
        
        # Install backend dependencies with uv (fallback to pip)
        backend_dir = Path(self.config['paths']['backend_dir'])
        if backend_dir.exists():
            self.logger.info("Installing backend dependencies...")
            
            # Try uv first
            try:
                result = subprocess.run(
                    ['uv', 'sync', '--frozen'],
                    cwd=backend_dir,
                    capture_output=True,
                    text=True,
                    timeout=300
                )
                
                if result.returncode == 0:
                    self.logger.info("Backend dependencies installed with uv")
                else:
                    raise subprocess.CalledProcessError(result.returncode, 'uv sync')
                    
            except (subprocess.CalledProcessError, FileNotFoundError):
                self.logger.warning("uv failed, falling back to pip...")
                
                # Create requirements.txt from config
                requirements = '\n'.join(self.config['backend']['dependencies'])
                req_file = backend_dir / 'requirements.txt'
                req_file.write_text(requirements)
                
                subprocess.run(
                    [sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'],
                    cwd=backend_dir,
                    check=True,
                    timeout=300
                )
                self.logger.info("Backend dependencies installed with pip")
        
        # Install frontend dependencies
        frontend_dir = Path(self.config['paths']['frontend_dir'])
        if frontend_dir.exists():
            self.logger.info("Installing frontend dependencies...")
            
            subprocess.run(
                ['npm', 'ci'],  # Use ci for production installs
                cwd=frontend_dir,
                check=True,
                timeout=300
            )
            self.logger.info("Frontend dependencies installed with npm")
    
    def _build_frontend(self):
        """Build frontend for production."""
        frontend_dir = Path(self.config['paths']['frontend_dir'])
        if not frontend_dir.exists():
            self.logger.warning("Frontend directory not found, skipping build")
            return
        
        self.logger.info("Building frontend for production...")
        
        build_cmd = self.config['frontend']['build_command'].split()
        subprocess.run(
            build_cmd,
            cwd=frontend_dir,
            check=True,
            timeout=600
        )
        
        self.logger.info("Frontend build completed")
    
    def _start_services(self):
        """Start backend and frontend services."""
        self.logger.info("Starting services...")
        self.running = True
        
        # Start backend with Gunicorn
        self._start_backend()
        
        # Start frontend server
        self._start_frontend()
        
        self.logger.info("All services started successfully")
    
    def _start_backend(self):
        """Start Flask backend with Gunicorn."""
        backend_dir = Path(self.config['paths']['backend_dir'])
        if not backend_dir.exists():
            self.logger.warning("Backend directory not found, skipping backend start")
            return
        
        backend_config = self.config['backend']
        
        # Gunicorn command
        cmd = [
            'gunicorn',
            '--bind', f"{backend_config['host']}:{backend_config['port']}",
            '--workers', str(backend_config['workers']),
            '--timeout', str(backend_config['timeout']),
            '--access-logfile', f"{self.config['paths']['logs_dir']}/backend_access.log",
            '--error-logfile', f"{self.config['paths']['logs_dir']}/backend_error.log",
            '--pid', f"{self.config['paths']['pid_dir']}/backend.pid",
            '--daemon',
            'app:app'  # Assumes app.py with app variable
        ]
        
        self.logger.info(f"Starting backend: {' '.join(cmd)}")
        
        process = subprocess.Popen(
            cmd,
            cwd=backend_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        self.processes['backend'] = process
        self.logger.info(f"Backend started with PID: {process.pid}")
    
    def _start_frontend(self):
        """Start frontend server."""
        frontend_dir = Path(self.config['paths']['frontend_dir'])
        if not frontend_dir.exists():
            self.logger.warning("Frontend directory not found, skipping frontend start")
            return
        
        frontend_config = self.config['frontend']
        
        # Use preview mode for production (serves built files)
        cmd = frontend_config['serve_command'].split()
        
        # Set environment variables
        env = os.environ.copy()
        env.update({
            'HOST': frontend_config['host'],
            'PORT': str(frontend_config['port'])
        })
        
        self.logger.info(f"Starting frontend: {' '.join(cmd)}")
        
        process = subprocess.Popen(
            cmd,
            cwd=frontend_dir,
            env=env,
            stdout=open(f"{self.config['paths']['logs_dir']}/frontend.log", 'w'),
            stderr=subprocess.STDOUT
        )
        
        self.processes['frontend'] = process
        
        # Write PID file
        pid_file = Path(self.config['paths']['pid_dir']) / 'frontend.pid'
        pid_file.write_text(str(process.pid))
        
        self.logger.info(f"Frontend started with PID: {process.pid}")
    
    def _start_health_monitor(self):
        """Start health monitoring in a separate thread."""
        def health_check():
            while self.running:
                try:
                    self._check_service_health()
                    time.sleep(self.config['deployment']['health_check_interval'])
                except Exception as e:
                    self.logger.error(f"Health check failed: {e}")
        
        health_thread = threading.Thread(target=health_check, daemon=True)
        health_thread.start()
        self.logger.info("Health monitoring started")
    
    def _check_service_health(self):
        """Check health of running services."""
        import urllib.request
        import urllib.error
        
        backend_port = self.config['backend']['port']
        frontend_port = self.config['frontend']['port']
        
        # Check backend health
        try:
            urllib.request.urlopen(f"http://localhost:{backend_port}/api/health", timeout=5)
            self.logger.debug("Backend health check: OK")
        except urllib.error.URLError:
            self.logger.warning("Backend health check failed")
            if self.config['deployment']['restart_on_failure']:
                self._restart_service('backend')
        
        # Check frontend health
        try:
            urllib.request.urlopen(f"http://localhost:{frontend_port}", timeout=5)
            self.logger.debug("Frontend health check: OK")
        except urllib.error.URLError:
            self.logger.warning("Frontend health check failed")
            if self.config['deployment']['restart_on_failure']:
                self._restart_service('frontend')
    
    def _restart_service(self, service_name):
        """Restart a specific service."""
        self.logger.info(f"Restarting {service_name} service...")
        
        if service_name in self.processes:
            process = self.processes[service_name]
            process.terminate()
            process.wait(timeout=10)
            del self.processes[service_name]
        
        if service_name == 'backend':
            self._start_backend()
        elif service_name == 'frontend':
            self._start_frontend()
    
    def stop(self):
        """Stop all services gracefully."""
        self.logger.info("Stopping all services...")
        self.running = False
        
        for service_name, process in self.processes.items():
            self.logger.info(f"Stopping {service_name}...")
            process.terminate()
            
            try:
                process.wait(timeout=10)
                self.logger.info(f"{service_name} stopped gracefully")
            except subprocess.TimeoutExpired:
                self.logger.warning(f"Force killing {service_name}...")
                process.kill()
                process.wait()
        
        self.processes.clear()
        self.logger.info("All services stopped")
    
    def status(self):
        """Get status of all services."""
        status_info = {
            'timestamp': datetime.now().isoformat(),
            'application': self.config['application'],
            'services': {}
        }
        
        for service_name, process in self.processes.items():
            if process.poll() is None:
                status_info['services'][service_name] = {
                    'status': 'running',
                    'pid': process.pid
                }
            else:
                status_info['services'][service_name] = {
                    'status': 'stopped',
                    'exit_code': process.returncode
                }
        
        return status_info


def main():
    """Main entry point for the bootloader."""
    parser = argparse.ArgumentParser(
        description='Flask + Vite Bootloader for VelaOS'
    )
    parser.add_argument('--deploy', action='store_true',
                       help='Deploy and start the application')
    parser.add_argument('--stop', action='store_true',
                       help='Stop all services')
    parser.add_argument('--status', action='store_true',
                       help='Show service status')
    parser.add_argument('--config', default='bootloader_config.json',
                       help='Configuration file path')
    
    args = parser.parse_args()
    
    try:
        bootloader = FlaskViteBootloader(config_path=args.config)
        
        if args.deploy:
            bootloader.deploy()
            
            # Keep running for health monitoring
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                bootloader.stop()
                
        elif args.stop:
            bootloader.stop()
            
        elif args.status:
            status = bootloader.status()
            print(json.dumps(status, indent=2))
            
        else:
            parser.print_help()
            
    except Exception as e:
        logging.error(f"Bootloader failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
