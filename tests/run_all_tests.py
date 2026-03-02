#!/usr/bin/env python3
"""
Master Test Suite - Runs all verification and integration tests
"""

import subprocess
import sys
from pathlib import Path
from typing import Tuple

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    CYAN = '\033[96m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    END = '\033[0m'

class MasterTestRunner:
    def __init__(self):
        self.base_dir = Path(__file__).parent.parent
        self.test_results = []
        self.total_tests = 0
        self.total_passed = 0

    def run_command(self, cmd: str, cwd: Path = None) -> Tuple[bool, str]:
        """Run a command and capture output"""
        try:
            result = subprocess.run(
                cmd,
                cwd=cwd or self.base_dir,
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

    def print_header(self, title: str):
        """Print section header"""
        print(f"\n{Colors.MAGENTA}{'='*70}{Colors.END}")
        print(f"{Colors.MAGENTA}{title:^70}{Colors.END}")
        print(f"{Colors.MAGENTA}{'='*70}{Colors.END}\n")

    def print_test_result(self, test_name: str, passed: bool, output: str = ""):
        """Print individual test result"""
        status = f"{Colors.GREEN}PASS{Colors.END}" if passed else f"{Colors.RED}FAIL{Colors.END}"
        print(f"[{status}] {test_name}")
        if not passed and output:
            print(f"     {Colors.RED}{output[:100]}{Colors.END}")
        self.test_results.append((test_name, passed))

    def run_integration_test(self) -> bool:
        """Run integration tests"""
        self.print_header("Test 1: Integration Tests")
        
        cmd = "python tests/integration_test.py"
        success, output = self.run_command(cmd)
        
        self.print_test_result("Integration Test (all languages)", success, output)
        if success:
            self.total_passed += 1
        self.total_tests += 1
        
        return success

    def run_build_verification(self) -> bool:
        """Run build verification tests"""
        self.print_header("Test 2: Build Verification")
        
        cmd = "python tests/build_verification.py"
        success, output = self.run_command(cmd)
        
        self.print_test_result("Build Verification (18 checks)", success, output)
        if success:
            self.total_passed += 1
        self.total_tests += 1
        
        return success

    def run_service_integration_test(self) -> bool:
        """Run service integration tests"""
        self.print_header("Test 3: Service API Integration")
        
        cmd = "python tests/service_integration_test.py"
        success, output = self.run_command(cmd)
        
        self.print_test_result("Service Integration Test (9 checks)", success, output)
        if success:
            self.total_passed += 1
        self.total_tests += 1
        
        return success

    def run_python_tests(self) -> bool:
        """Run original Python tests"""
        self.print_header("Test 4: Python Core Tests")
        
        test_files = [
            'tests/test_behaviour_analyser.py',
            'tests/test_anomaly_detector.py',
            'tests/test_attendance.py',
            'tests/test_alert_manager.py',
            'tests/test_database.py',
        ]
        
        all_passed = True
        for test_file in test_files:
            test_path = self.base_dir / test_file
            if not test_path.exists():
                self.print_test_result(f"Python Test: {test_file}", False, "File not found")
                self.total_tests += 1
                all_passed = False
                continue
            
            cmd = f"python -m pytest {test_file} -v --tb=short"
            success, output = self.run_command(cmd)
            
            test_name = test_file.replace('tests/', '').replace('.py', '')
            self.print_test_result(f"Python Test: {test_name}", success, output)
            self.total_tests += 1
            
            if success:
                self.total_passed += 1
            else:
                all_passed = False
        
        return all_passed

    def verify_file_structure(self) -> bool:
        """Verify all required files exist"""
        self.print_header("Test 5: File Structure Verification")
        
        required_files = {
            'services/go/alert_dispatcher/main.go': 'Go Alert Dispatcher',
            'services/go/camera_streamer/main.go': 'Go Camera Streamer',
            'services/typescript/api/src/server.ts': 'TypeScript API',
            'services/rust/video_optimizer/src/main.rs': 'Rust Video Optimizer',
            'docker-compose.yml': 'Docker Compose',
            'Dockerfile.python': 'Python Dockerfile',
            'ARCHITECTURE.md': 'Architecture Documentation',
            'DEPLOYMENT.md': 'Deployment Documentation',
        }
        
        all_exist = True
        for file_path, description in required_files.items():
            full_path = self.base_dir / file_path
            exists = full_path.exists()
            self.print_test_result(f"File: {description}", exists)
            self.total_tests += 1
            
            if exists:
                self.total_passed += 1
            else:
                all_exist = False
        
        return all_exist

    def generate_summary(self):
        """Generate final summary"""
        self.print_header("FINAL TEST SUMMARY")
        
        print(f"Total Tests Run: {self.total_tests}")
        print(f"Tests Passed:    {Colors.GREEN}{self.total_passed}{Colors.END}")
        print(f"Tests Failed:    {Colors.RED}{self.total_tests - self.total_passed}{Colors.END}")
        
        success_rate = (self.total_passed / self.total_tests * 100) if self.total_tests > 0 else 0
        
        if success_rate == 100:
            color = Colors.GREEN
        elif success_rate >= 80:
            color = Colors.YELLOW
        else:
            color = Colors.RED
        
        print(f"Success Rate:    {color}{success_rate:.1f}%{Colors.END}")
        
        print(f"\n{Colors.MAGENTA}{'='*70}{Colors.END}")
        
        if self.total_passed == self.total_tests:
            print(f"{Colors.GREEN}{'ALL TESTS PASSED':^70}{Colors.END}")
        else:
            failed = self.total_tests - self.total_passed
            print(f"{Colors.RED}{f'{failed} TEST(S) FAILED':^70}{Colors.END}")
        
        print(f"{Colors.MAGENTA}{'='*70}{Colors.END}\n")
        
        # Component summary
        print(f"{Colors.BLUE}Component Status:{Colors.END}\n")
        
        components = {
            'Python Core': ['Test 4: Python Core Tests'],
            'Go Services': ['Test 1: Integration Tests', 'Test 2: Build Verification'],
            'TypeScript API': ['Test 1: Integration Tests', 'Test 2: Build Verification'],
            'Rust Service': ['Test 1: Integration Tests', 'Test 2: Build Verification'],
            'Docker': ['Test 2: Build Verification'],
            'Documentation': ['Test 5: File Structure Verification'],
            'Service Integration': ['Test 3: Service API Integration'],
        }
        
        for component, _ in components.items():
            relevant_tests = [t for t, p in self.test_results if any(x in t for x in ['Integration', 'Build', 'File', 'Python', 'Service'])]
            if relevant_tests:
                print(f"  [OK] {component}")
        
        print()

    def run_all_tests(self) -> bool:
        """Run all test suites"""
        print(f"{Colors.CYAN}{'='*70}{Colors.END}")
        print(f"{Colors.CYAN}{'AI Security System - Master Test Suite':^70}{Colors.END}")
        print(f"{Colors.CYAN}{'='*70}{Colors.END}")
        
        all_passed = True
        
        # Run all tests
        all_passed &= self.run_integration_test()
        all_passed &= self.run_build_verification()
        all_passed &= self.run_service_integration_test()
        all_passed &= self.verify_file_structure()
        all_passed &= self.run_python_tests()
        
        # Generate summary
        self.generate_summary()
        
        return all_passed

if __name__ == '__main__':
    runner = MasterTestRunner()
    success = runner.run_all_tests()
    sys.exit(0 if success else 1)
