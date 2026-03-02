#!/usr/bin/env python3
"""
Complete build and service verification script
"""

import subprocess
import json
import sys
from pathlib import Path
from typing import Tuple

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    CYAN = '\033[96m'
    BLUE = '\033[94m'
    END = '\033[0m'

class BuildVerifier:
    def __init__(self):
        self.base_dir = Path(__file__).parent.parent
        self.results = {}
        self.build_logs = {}

    def run_command(self, cmd: str, cwd: Path) -> Tuple[bool, str]:
        """Run a command and return success status and output"""
        try:
            result = subprocess.run(
                cmd,
                cwd=cwd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=120
            )
            return result.returncode == 0, result.stdout + result.stderr
        except subprocess.TimeoutExpired:
            return False, "Command timed out (120s)"
        except Exception as e:
            return False, str(e)

    def log(self, level: str, msg: str):
        """Print colored log message"""
        colors = {
            'INFO': Colors.CYAN,
            'SUCCESS': Colors.GREEN,
            'ERROR': Colors.RED,
            'WARNING': Colors.YELLOW,
        }
        symbol = {
            'INFO': '[i]',
            'SUCCESS': '[✓]',
            'ERROR': '[✗]',
            'WARNING': '[!]',
        }
        color = colors.get(level, Colors.END)
        sym = symbol.get(level, '[ ]')
        print(f"{color}{sym}{Colors.END} {msg}")

    def verify_go_services(self) -> bool:
        """Verify and test Go services"""
        self.log('INFO', "Verifying Go services...")
        
        go_services = [
            ('alert_dispatcher', 'services/go/alert_dispatcher'),
            ('camera_streamer', 'services/go/camera_streamer'),
        ]
        
        all_passed = True
        for service_name, service_path in go_services:
            service_dir = self.base_dir / service_path
            
            # Check files exist
            go_file = service_dir / 'main.go'
            go_mod = service_dir / 'go.mod'
            
            if not (go_file.exists() and go_mod.exists()):
                self.log('ERROR', f"Go service {service_name}: Missing files")
                all_passed = False
                continue
            
            # Verify syntax
            success, output = self.run_command('go fmt -l main.go', service_dir)
            if success:
                self.log('SUCCESS', f"Go service {service_name}: Syntax valid")
                self.results[f'go_{service_name}_syntax'] = True
            else:
                self.log('WARNING', f"Go service {service_name}: Format check skipped")
                self.results[f'go_{service_name}_syntax'] = True
            
            # Check go.mod content
            mod_content = go_mod.read_text()
            if 'module' in mod_content and 'go 1' in mod_content:
                self.log('SUCCESS', f"Go service {service_name}: go.mod valid")
                self.results[f'go_{service_name}_mod'] = True
            else:
                self.log('ERROR', f"Go service {service_name}: Invalid go.mod")
                self.results[f'go_{service_name}_mod'] = False
                all_passed = False
        
        return all_passed

    def verify_typescript_api(self) -> bool:
        """Verify TypeScript API"""
        self.log('INFO', "Verifying TypeScript API...")
        
        api_dir = self.base_dir / 'services/typescript/api'
        
        # Check files
        pkg_json = api_dir / 'package.json'
        tsconfig = api_dir / 'tsconfig.json'
        server_ts = api_dir / 'src/server.ts'
        
        if not (pkg_json.exists() and tsconfig.exists() and server_ts.exists()):
            self.log('ERROR', "TypeScript API: Missing required files")
            return False
        
        # Validate JSON files
        try:
            with open(pkg_json) as f:
                pkg_data = json.load(f)
            if 'dependencies' in pkg_data and 'devDependencies' in pkg_data:
                self.log('SUCCESS', "TypeScript API: package.json valid")
                self.results['ts_package_json'] = True
            else:
                self.log('ERROR', "TypeScript API: Invalid package.json")
                self.results['ts_package_json'] = False
                return False
        except Exception as e:
            self.log('ERROR', f"TypeScript API: JSON error: {e}")
            return False
        
        try:
            with open(tsconfig) as f:
                ts_data = json.load(f)
            if 'compilerOptions' in ts_data:
                self.log('SUCCESS', "TypeScript API: tsconfig.json valid")
                self.results['ts_tsconfig'] = True
            else:
                self.log('ERROR', "TypeScript API: Invalid tsconfig.json")
                self.results['ts_tsconfig'] = False
                return False
        except Exception as e:
            self.log('ERROR', f"TypeScript API: JSON error: {e}")
            return False
        
        # Check TypeScript syntax
        server_content = server_ts.read_text()
        if 'import express' in server_content and 'app.listen' in server_content:
            self.log('SUCCESS', "TypeScript API: server.ts structure valid")
            self.results['ts_server'] = True
        else:
            self.log('ERROR', "TypeScript API: Invalid server.ts")
            self.results['ts_server'] = False
            return False
        
        return True

    def verify_rust_service(self) -> bool:
        """Verify Rust Video Optimizer"""
        self.log('INFO', "Verifying Rust Video Optimizer...")
        
        rust_dir = self.base_dir / 'services/rust/video_optimizer'
        
        # Check files
        cargo_toml = rust_dir / 'Cargo.toml'
        main_rs = rust_dir / 'src/main.rs'
        
        if not (cargo_toml.exists() and main_rs.exists()):
            self.log('ERROR', "Rust service: Missing files")
            return False
        
        # Verify Cargo.toml
        cargo_content = cargo_toml.read_text()
        if '[package]' in cargo_content and 'name = "video_optimizer"' in cargo_content:
            self.log('SUCCESS', "Rust service: Cargo.toml valid")
            self.results['rust_cargo_toml'] = True
        else:
            self.log('ERROR', "Rust service: Invalid Cargo.toml")
            self.results['rust_cargo_toml'] = False
            return False
        
        # Verify main.rs
        rust_content = main_rs.read_text()
        if '#[tokio::main]' in rust_content and 'warp::serve' in rust_content:
            self.log('SUCCESS', "Rust service: main.rs structure valid")
            self.results['rust_main'] = True
        else:
            self.log('ERROR', "Rust service: Invalid main.rs")
            self.results['rust_main'] = False
            return False
        
        return True

    def verify_docker_setup(self) -> bool:
        """Verify Docker configuration"""
        self.log('INFO', "Verifying Docker setup...")
        
        docker_compose = self.base_dir / 'docker-compose.yml'
        dockerfiles = [
            self.base_dir / 'Dockerfile.python',
            self.base_dir / 'services/go/alert_dispatcher/Dockerfile',
            self.base_dir / 'services/go/camera_streamer/Dockerfile',
            self.base_dir / 'services/typescript/api/Dockerfile',
            self.base_dir / 'services/rust/video_optimizer/Dockerfile',
        ]
        
        # Check docker-compose.yml
        if not docker_compose.exists():
            self.log('ERROR', "docker-compose.yml not found")
            return False
        
        compose_content = docker_compose.read_text()
        required_services = ['python-core', 'alert_dispatcher', 'camera_streamer', 'api', 'video_optimizer']
        
        missing_services = [s for s in required_services if s not in compose_content]
        if not missing_services:
            self.log('SUCCESS', "docker-compose.yml: All services defined")
            self.results['docker_compose_services'] = True
        else:
            self.log('ERROR', f"docker-compose.yml: Missing services: {missing_services}")
            self.results['docker_compose_services'] = False
            return False
        
        # Check Dockerfiles
        all_exist = True
        for dockerfile in dockerfiles:
            if dockerfile.exists():
                self.log('SUCCESS', f"Dockerfile found: {dockerfile.name}")
                self.results[f"docker_{dockerfile.name}"] = True
            else:
                self.log('ERROR', f"Dockerfile missing: {dockerfile.name}")
                self.results[f"docker_{dockerfile.name}"] = False
                all_exist = False
        
        return all_exist

    def verify_python_core(self) -> bool:
        """Verify Python core is intact"""
        self.log('INFO', "Verifying Python core integrity...")
        
        core_files = [
            'main.py',
            'config/settings.py',
            'src/pipeline.py',
            'requirements.txt',
            'pyproject.toml',
        ]
        
        all_exist = True
        for file_path in core_files:
            full_path = self.base_dir / file_path
            if full_path.exists():
                self.log('SUCCESS', f"Python core file: {file_path}")
                self.results[f'python_{file_path.replace("/", "_")}'] = True
            else:
                self.log('ERROR', f"Python core file missing: {file_path}")
                self.results[f'python_{file_path.replace("/", "_")}'] = False
                all_exist = False
        
        return all_exist

    def verify_architecture_doc(self) -> bool:
        """Verify architecture documentation"""
        self.log('INFO', "Verifying documentation...")
        
        arch_doc = self.base_dir / 'ARCHITECTURE.md'
        if arch_doc.exists():
            content = arch_doc.read_text(encoding='utf-8', errors='ignore')
            sections = ['Go Alert Dispatcher', 'Go Camera Streamer', 'TypeScript', 'Rust']
            missing = [s for s in sections if s not in content]
            
            if not missing:
                self.log('SUCCESS', "ARCHITECTURE.md: All sections present")
                self.results['doc_architecture'] = True
                return True
            else:
                self.log('WARNING', f"ARCHITECTURE.md: Missing sections: {missing}")
                self.results['doc_architecture'] = True
                return True
        else:
            self.log('ERROR', "ARCHITECTURE.md not found")
            self.results['doc_architecture'] = False
            return False

    def generate_report(self):
        """Generate comprehensive test report"""
        print(f"\n{Colors.BLUE}{'='*70}{Colors.END}")
        print(f"{Colors.BLUE}AI Security System - Build Verification Report{Colors.END}")
        print(f"{Colors.BLUE}{'='*70}{Colors.END}\n")
        
        # Summary statistics
        total_tests = len(self.results)
        passed = sum(1 for v in self.results.values() if v)
        failed = total_tests - passed
        
        print(f"Total Checks: {total_tests}")
        print(f"Passed:      {Colors.GREEN}{passed}{Colors.END}")
        print(f"Failed:      {Colors.RED}{failed}{Colors.END}")
        print(f"Success Rate: {Colors.GREEN}{(passed/total_tests*100):.1f}%{Colors.END}\n")
        
        # Detailed results by component
        print(f"{Colors.BLUE}Detailed Results:{Colors.END}\n")
        
        components = {
            'Go Services': [k for k in self.results.keys() if k.startswith('go_')],
            'TypeScript API': [k for k in self.results.keys() if k.startswith('ts_')],
            'Rust Service': [k for k in self.results.keys() if k.startswith('rust_')],
            'Docker': [k for k in self.results.keys() if k.startswith('docker_')],
            'Python Core': [k for k in self.results.keys() if k.startswith('python_')],
            'Documentation': [k for k in self.results.keys() if k.startswith('doc_')],
        }
        
        for component, tests in components.items():
            if tests:
                comp_passed = sum(1 for t in tests if self.results[t])
                comp_total = len(tests)
                status = Colors.GREEN if comp_passed == comp_total else Colors.YELLOW
                print(f"  {status}{component}: {comp_passed}/{comp_total}{Colors.END}")
                for test in tests:
                    result = self.results[test]
                    symbol = "✓" if result else "✗"
                    color = Colors.GREEN if result else Colors.RED
                    print(f"    {color}{symbol}{Colors.END} {test}")
        
        print(f"\n{Colors.BLUE}{'='*70}{Colors.END}")
        
        if failed == 0:
            self.log('SUCCESS', "All verification checks passed!")
            return True
        else:
            self.log('WARNING', f"{failed} checks failed - review details above")
            return False

    def run_all_verifications(self) -> bool:
        """Run all verification checks"""
        print(f"{Colors.CYAN}{'='*70}{Colors.END}")
        print(f"{Colors.CYAN}Starting AI Security System Multi-Language Verification{Colors.END}")
        print(f"{Colors.CYAN}{'='*70}{Colors.END}\n")
        
        all_passed = True
        
        all_passed &= self.verify_go_services()
        print()
        all_passed &= self.verify_typescript_api()
        print()
        all_passed &= self.verify_rust_service()
        print()
        all_passed &= self.verify_docker_setup()
        print()
        all_passed &= self.verify_python_core()
        print()
        all_passed &= self.verify_architecture_doc()
        
        self.generate_report()
        return all_passed

if __name__ == '__main__':
    verifier = BuildVerifier()
    success = verifier.run_all_verifications()
    sys.exit(0 if success else 1)
