#!/usr/bin/env python3
"""
VelaOS Step-by-Step Deployment Chain
Orchestrates multiple bootloader steps in the correct order

This script is designed to be called by VelaOS after GitHub repository clone.
It runs bootloader steps in sequence, with proper error handling and rollback.

Usage:
    python deploy_step_chain.py                    # Auto-deploy all steps (VelaOS compatible)
    python deploy_step_chain.py --step 1           # Run specific step only
    python deploy_step_chain.py --steps 1,2        # Run specific steps
    python deploy_step_chain.py --help-only        # Show help only
"""

import os
import sys
import subprocess
import argparse
import logging
from pathlib import Path
from typing import List, Dict, Any


class DeploymentOrchestrator:
    """Orchestrates step-by-step deployment process."""
    
    def __init__(self):
        self.steps = [
            {
                "id": 1,
                "name": "Folder Structure Creation",
                "script": "folder_bootloader.py",
                "description": "Create project folder structure and basic files",
                "required_files": ["folder_bootloader.py", "bootloader_config.json"]
            },
            {
                "id": 2,
                "name": "Python Environment Setup",
                "script": "python_env_bootloader.py",
                "description": "Install uv, create .venv, setup Python files",
                "required_files": ["python_env_bootloader.py", "bootloader_config.json"]
            },
            # Future steps can be added here
            # {
            #     "id": 3,
            #     "name": "Backend TOML Generation",
            #     "script": "backend_toml_bootloader.py",
            #     "description": "Generate pyproject.toml and install dependencies",
            #     "required_files": ["backend_toml_bootloader.py", "bootloader_config.json"]
            # },
            # {
            #     "id": 4,
            #     "name": "Frontend Setup",
            #     "script": "frontend_bootloader.py", 
            #     "description": "Create package.json and install npm dependencies",
            #     "required_files": ["frontend_bootloader.py", "bootloader_config.json"]
            # }
        ]
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('deployment_orchestrator.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def check_system_requirements(self) -> bool:
        """Check basic system requirements."""
        self.logger.info("Checking system requirements...")
        
        # Check Python version
        if sys.version_info < (3, 8):
            self.logger.error("❌ Python 3.8+ required")
            return False
        self.logger.info("✅ Python version OK")
        
        # Check write permissions
        try:
            test_dir = Path.cwd() / "test_write_permission"
            test_dir.mkdir(exist_ok=True)
            test_dir.rmdir()
            self.logger.info("✅ Write permissions OK")
        except PermissionError:
            self.logger.error("❌ No write permissions in current directory")
            return False
        
        return True
    
    def check_step_requirements(self, step: Dict[str, Any]) -> bool:
        """Check if required files exist for a step."""
        self.logger.info(f"Checking requirements for Step {step['id']}: {step['name']}")
        
        missing_files = []
        for filename in step["required_files"]:
            if not Path(filename).exists():
                missing_files.append(filename)
            else:
                self.logger.info(f"✅ Found {filename}")
        
        if missing_files:
            self.logger.error(f"❌ Missing files for Step {step['id']}: {', '.join(missing_files)}")
            return False
        
        return True
    
    def run_step(self, step: Dict[str, Any]) -> bool:
        """Run a single deployment step."""
        self.logger.info(f"\n{'='*60}")
        self.logger.info(f"🚀 STEP {step['id']}: {step['name'].upper()}")
        self.logger.info(f"{'='*60}")
        self.logger.info(f"📝 Description: {step['description']}")
        
        # Check step requirements
        if not self.check_step_requirements(step):
            return False
        
        # Execute step script
        try:
            self.logger.info(f"▶️  Executing: {step['script']}")
            result = subprocess.run(
                [sys.executable, step['script'], '--deploy'], 
                check=True, 
                capture_output=True, 
                text=True,
                timeout=300  # 5 minute timeout per step
            )
            
            # Show output
            if result.stdout:
                self.logger.info(f"📄 Step {step['id']} Output:")
                for line in result.stdout.strip().split('\n'):
                    self.logger.info(f"   {line}")
            
            if result.stderr:
                self.logger.warning(f"⚠️  Step {step['id']} Warnings:")
                for line in result.stderr.strip().split('\n'):
                    self.logger.warning(f"   {line}")
            
            self.logger.info(f"✅ Step {step['id']} completed successfully!")
            return True
            
        except subprocess.CalledProcessError as e:
            self.logger.error(f"❌ Step {step['id']} failed with exit code {e.returncode}")
            if e.stdout:
                self.logger.error("STDOUT:")
                for line in e.stdout.strip().split('\n'):
                    self.logger.error(f"   {line}")
            if e.stderr:
                self.logger.error("STDERR:")
                for line in e.stderr.strip().split('\n'):
                    self.logger.error(f"   {line}")
            return False
            
        except subprocess.TimeoutExpired:
            self.logger.error(f"❌ Step {step['id']} timed out after 5 minutes")
            return False
            
        except Exception as e:
            self.logger.error(f"❌ Step {step['id']} failed with error: {e}")
            return False
    
    def run_steps(self, step_ids: List[int] = None) -> bool:
        """Run deployment steps in sequence."""
        if step_ids is None:
            step_ids = [step["id"] for step in self.steps]
        
        self.logger.info(f"\n🎯 DEPLOYMENT PLAN: Running steps {step_ids}")
        
        # Validate step IDs
        available_ids = {step["id"] for step in self.steps}
        invalid_ids = set(step_ids) - available_ids
        if invalid_ids:
            self.logger.error(f"❌ Invalid step IDs: {invalid_ids}")
            self.logger.error(f"Available steps: {sorted(available_ids)}")
            return False
        
        # Run steps in order
        completed_steps = []
        for step_id in step_ids:
            step = next(s for s in self.steps if s["id"] == step_id)
            
            if self.run_step(step):
                completed_steps.append(step_id)
            else:
                self.logger.error(f"\n💥 DEPLOYMENT FAILED at Step {step_id}")
                self.logger.error(f"Completed steps: {completed_steps}")
                self.logger.error(f"Failed step: {step_id}")
                return False
        
        self.logger.info(f"\n🎉 ALL STEPS COMPLETED SUCCESSFULLY!")
        self.logger.info(f"✅ Completed steps: {completed_steps}")
        return True
    
    def show_available_steps(self):
        """Show available deployment steps."""
        self.logger.info("\n📋 AVAILABLE DEPLOYMENT STEPS:")
        self.logger.info("="*50)
        
        for step in self.steps:
            self.logger.info(f"Step {step['id']}: {step['name']}")
            self.logger.info(f"   📝 {step['description']}")
            self.logger.info(f"   📄 Script: {step['script']}")
            self.logger.info("")
    
    def deploy(self, step_ids: List[int] = None):
        """Main deployment entry point."""
        self.logger.info("="*60)
        self.logger.info("🚀 VELA OS STEP-BY-STEP DEPLOYMENT")
        self.logger.info("="*60)
        
        # Check system requirements
        if not self.check_system_requirements():
            self.logger.error("❌ System requirements not met")
            sys.exit(1)
        
        # Show deployment plan
        if step_ids:
            self.logger.info(f"🎯 Running specific steps: {step_ids}")
        else:
            self.logger.info("🎯 Running all available steps")
            
        self.show_available_steps()
        
        # Execute deployment
        success = self.run_steps(step_ids)
        
        if success:
            self.logger.info("\n🎉 DEPLOYMENT SUCCESSFUL!")
            self.logger.info("🚀 Your Flask + Vite project is ready for development!")
        else:
            self.logger.error("\n💥 DEPLOYMENT FAILED!")
            self.logger.error("Check the logs above for details")
            sys.exit(1)


def parse_step_list(step_str: str) -> List[int]:
    """Parse comma-separated step list."""
    try:
        return [int(s.strip()) for s in step_str.split(',')]
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"Invalid step list: {step_str}. Use comma-separated integers.")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="VelaOS Step-by-Step Deployment Chain",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python deploy_step_chain.py                    # Run all steps
  python deploy_step_chain.py --step 1           # Run step 1 only
  python deploy_step_chain.py --steps 1,2        # Run steps 1 and 2
  python deploy_step_chain.py --help-only        # Show help only
        """
    )
    
    parser.add_argument("--step", type=int, help="Run specific step only")
    parser.add_argument("--steps", type=parse_step_list, help="Run specific steps (comma-separated)")
    parser.add_argument("--help-only", action="store_true", help="Show help only (don't auto-deploy)")
    
    args = parser.parse_args()
    
    orchestrator = DeploymentOrchestrator()
    
    # Handle help-only mode
    if args.help_only:
        print("VelaOS Step-by-Step Deployment Chain")
        print("\nThis deployment system runs bootloader steps in sequence:")
        orchestrator.show_available_steps()
        return
    
    # Determine which steps to run
    step_ids = None
    if args.step:
        step_ids = [args.step]
    elif args.steps:
        step_ids = args.steps
    
    # Run deployment (auto-deploy by default for VelaOS compatibility)
    orchestrator.deploy(step_ids)


if __name__ == '__main__':
    main()
