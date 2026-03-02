#!/usr/bin/env python3
"""
Comprehensive integration test for all services
"""

import subprocess
import time
import requests
import json
import sys
from pathlib import Path

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    CYAN = '\033[96m'
    END = '\033[0m'

def log_info(msg):
    print(f"{Colors.CYAN}[INFO]{Colors.END} {msg}")

def log_success(msg):
    print(f"{Colors.GREEN}[✓]{Colors.END} {msg}")

def log_error(msg):
    print(f"{Colors.RED}[✗]{Colors.END} {msg}")

def log_warning(msg):
    print(f"{Colors.YELLOW}[!]{Colors.END} {msg}")

class ServiceTester:
    def __init__(self):
        self.results = {}
        self.base_dir = Path(__file__).parent.parent
    
    def test_go_alert_dispatcher(self):
        """Test Go Alert Dispatcher service"""
        log_info("Testing Go Alert Dispatcher...")
        try:
            # Check if Go is installed
            result = subprocess.run(['go', 'version'], capture_output=True, text=True)
            if result.returncode == 0:
                log_success("Go is installed")
                self.results['go_installed'] = True
            else:
                log_warning("Go is not installed")
                self.results['go_installed'] = False
            
            # Check if go.mod exists
            go_mod = self.base_dir / 'services' / 'go' / 'alert_dispatcher' / 'go.mod'
            if go_mod.exists():
                log_success(f"go.mod found: {go_mod}")
                self.results['go_mod_alert'] = True
            else:
                log_error(f"go.mod not found")
                self.results['go_mod_alert'] = False
                
            return True
        except Exception as e:
            log_error(f"Error testing Go: {e}")
            return False
    
    def test_typescript_api(self):
        """Test TypeScript API service"""
        log_info("Testing TypeScript API...")
        try:
            # Check if Node is installed
            result = subprocess.run(['node', '--version'], capture_output=True, text=True)
            if result.returncode == 0:
                log_success(f"Node.js is installed: {result.stdout.strip()}")
                self.results['node_installed'] = True
            else:
                log_warning("Node.js is not installed")
                self.results['node_installed'] = False
            
            # Check package.json
            pkg_json = self.base_dir / 'services' / 'typescript' / 'api' / 'package.json'
            if pkg_json.exists():
                log_success(f"package.json found: {pkg_json}")
                self.results['typescript_pkg'] = True
            else:
                log_error(f"package.json not found")
                self.results['typescript_pkg'] = False
                
            return True
        except Exception as e:
            log_error(f"Error testing TypeScript: {e}")
            return False
    
    def test_rust_optimizer(self):
        """Test Rust Video Optimizer"""
        log_info("Testing Rust Video Optimizer...")
        try:
            # Check if Rust is installed
            result = subprocess.run(['rustc', '--version'], capture_output=True, text=True)
            if result.returncode == 0:
                log_success(f"Rust is installed: {result.stdout.strip()}")
                self.results['rust_installed'] = True
            else:
                log_warning("Rust is not installed")
                self.results['rust_installed'] = False
            
            # Check Cargo.toml
            cargo_toml = self.base_dir / 'services' / 'rust' / 'video_optimizer' / 'Cargo.toml'
            if cargo_toml.exists():
                log_success(f"Cargo.toml found: {cargo_toml}")
                self.results['rust_cargo'] = True
            else:
                log_error(f"Cargo.toml not found")
                self.results['rust_cargo'] = False
                
            return True
        except Exception as e:
            log_error(f"Error testing Rust: {e}")
            return False
    
    def test_docker(self):
        """Test Docker setup"""
        log_info("Testing Docker setup...")
        try:
            # Check if Docker is installed
            result = subprocess.run(['docker', '--version'], capture_output=True, text=True)
            if result.returncode == 0:
                log_success(f"Docker is installed: {result.stdout.strip()}")
                self.results['docker_installed'] = True
            else:
                log_warning("Docker is not installed")
                self.results['docker_installed'] = False
            
            # Check docker-compose.yml
            docker_compose = self.base_dir / 'docker-compose.yml'
            if docker_compose.exists():
                log_success(f"docker-compose.yml found: {docker_compose}")
                self.results['docker_compose'] = True
            else:
                log_error(f"docker-compose.yml not found")
                self.results['docker_compose'] = False
            
            # Check Dockerfiles
            dockerfiles = [
                self.base_dir / 'Dockerfile.python',
                self.base_dir / 'services' / 'go' / 'alert_dispatcher' / 'Dockerfile',
                self.base_dir / 'services' / 'typescript' / 'api' / 'Dockerfile',
                self.base_dir / 'services' / 'rust' / 'video_optimizer' / 'Dockerfile',
            ]
            
            all_exist = True
            for dockerfile in dockerfiles:
                if dockerfile.exists():
                    log_success(f"Dockerfile found: {dockerfile.name}")
                else:
                    log_error(f"Dockerfile not found: {dockerfile.name}")
                    all_exist = False
            
            self.results['dockerfiles'] = all_exist
            return True
        except Exception as e:
            log_error(f"Error testing Docker: {e}")
            return False
    
    def test_file_structure(self):
        """Test overall file structure"""
        log_info("Testing file structure...")
        
        required_files = {
            'services/go/alert_dispatcher/main.go': 'Go Alert Dispatcher',
            'services/go/alert_dispatcher/go.mod': 'Go Alert Dispatcher Module',
            'services/go/camera_streamer/main.go': 'Go Camera Streamer',
            'services/go/camera_streamer/go.mod': 'Go Camera Streamer Module',
            'services/typescript/api/package.json': 'TypeScript API',
            'services/typescript/api/tsconfig.json': 'TypeScript Config',
            'services/typescript/api/src/server.ts': 'TypeScript Server',
            'services/rust/video_optimizer/Cargo.toml': 'Rust Video Optimizer',
            'services/rust/video_optimizer/src/main.rs': 'Rust Main',
            'docker-compose.yml': 'Docker Compose',
        }
        
        all_exist = True
        for file_path, description in required_files.items():
            full_path = self.base_dir / file_path
            if full_path.exists():
                log_success(f"{description}: {file_path}")
            else:
                log_error(f"{description} not found: {file_path}")
                all_exist = False
        
        self.results['file_structure'] = all_exist
        return all_exist
    
    def test_python_core(self):
        """Test Python core is still intact"""
        log_info("Testing Python core...")
        
        python_files = [
            'main.py',
            'config/settings.py',
            'src/pipeline.py',
            'requirements.txt',
        ]
        
        all_exist = True
        for file_path in python_files:
            full_path = self.base_dir / file_path
            if full_path.exists():
                log_success(f"Python core file: {file_path}")
            else:
                log_error(f"Python core file not found: {file_path}")
                all_exist = False
        
        self.results['python_intact'] = all_exist
        return all_exist
    
    def run_all_tests(self):
        """Run all tests"""
        print(f"{Colors.CYAN}{'='*60}{Colors.END}")
        print(f"{Colors.CYAN}AI Security System - Multi-Language Integration Tests{Colors.END}")
        print(f"{Colors.CYAN}{'='*60}{Colors.END}\n")
        
        self.test_file_structure()
        print()
        self.test_go_alert_dispatcher()
        print()
        self.test_typescript_api()
        print()
        self.test_rust_optimizer()
        print()
        self.test_docker()
        print()
        self.test_python_core()
        
        return self.generate_report()
    
    def generate_report(self):
        """Generate test report"""
        print(f"\n{Colors.CYAN}{'='*60}{Colors.END}")
        print(f"{Colors.CYAN}Test Report{Colors.END}")
        print(f"{Colors.CYAN}{'='*60}{Colors.END}\n")
        
        passed = sum(1 for v in self.results.values() if v)
        total = len(self.results)
        
        print(f"Total Tests: {total}")
        print(f"Passed: {Colors.GREEN}{passed}{Colors.END}")
        print(f"Failed: {Colors.RED}{total - passed}{Colors.END}\n")
        
        print("Details:")
        for test_name, result in self.results.items():
            status = f"{Colors.GREEN}✓{Colors.END}" if result else f"{Colors.RED}✗{Colors.END}"
            print(f"  {status} {test_name}")
        
        success_rate = (passed / total * 100) if total > 0 else 0
        print(f"\nSuccess Rate: {Colors.GREEN}{success_rate:.1f}%{Colors.END}")
        
        return passed == total

if __name__ == '__main__':
    tester = ServiceTester()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)
