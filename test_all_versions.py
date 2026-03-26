#!/usr/bin/env python3
"""Test AI Security System on all Python versions"""

import subprocess
import os
import json
from pathlib import Path
from datetime import datetime

project_root = Path(__file__).parent

def run_test(version):
    """Run tests on a specific Python version"""
    print(f"\n{'='*60}")
    print(f"Testing Python {version}")
    print(f"{'='*60}")
    
    try:
        # Check if Python version exists
        check_cmd = ["py", f"-{version}", "--version"]
        check_result = subprocess.run(check_cmd, capture_output=True, text=True, timeout=5)
        
        if check_result.returncode != 0:
            print(f"❌ Python {version} not found")
            return {"version": version, "success": False, "error": "Python not found"}
        
        print(f"✓ Python {version} found: {check_result.stdout.strip()}")
        
        # Run pytest
        pytest_cmd = ["py", f"-{version}", "-m", "pytest", "tests/", "-q", "--tb=no"]
        result = subprocess.run(
            pytest_cmd,
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=120
        )
        
        # Check result
        if result.returncode == 0:
            # Extract passed count from output
            output_lines = result.stdout.strip().split('\n')
            last_line = output_lines[-1] if output_lines else ""
            print(f"✅ Tests PASSED")
            print(f"   {last_line}")
            return {
                "version": version,
                "success": True,
                "result": last_line,
                "stdout": result.stdout[-200:] if len(result.stdout) > 200 else result.stdout
            }
        else:
            print(f"❌ Tests FAILED")
            if result.stderr:
                print(f"   Error: {result.stderr[:200]}")
            if result.stdout:
                print(f"   Output: {result.stdout[-200:]}")
            return {
                "version": version,
                "success": False,
                "error": result.stderr[-200:] if result.stderr else result.stdout[-200:]
            }
    
    except subprocess.TimeoutExpired:
        print(f"❌ Tests TIMEOUT (120 seconds)")
        return {"version": version, "success": False, "error": "Timeout"}
    except Exception as e:
        print(f"❌ Exception: {str(e)}")
        return {"version": version, "success": False, "error": str(e)}

def main():
    """Main test runner"""
    print("\n" + "="*60)
    print("AI SECURITY SYSTEM - PYTHON VERSION COMPATIBILITY TEST")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("="*60)
    
    versions = ["3.12", "3.13", "3.14"]
    results = []
    
    for v in versions:
        result = run_test(v)
        results.append(result)
    
    # Print summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    
    for r in results:
        status = "✅ PASS" if r.get("success") else "❌ FAIL"
        print(f"Python {r['version']}: {status}")
        if r.get("error"):
            print(f"  → {r['error'][:100]}")
    
    # Generate report file
    report = {
        "timestamp": datetime.now().isoformat(),
        "results": results,
        "summary": {
            "total": len(versions),
            "passed": sum(1 for r in results if r.get("success")),
            "failed": sum(1 for r in results if not r.get("success"))
        }
    }
    
    report_path = project_root / "PYTHON_COMPATIBILITY_REPORT.json"
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"\n✓ Report saved to: {report_path}")
    
    # Check if all passed
    if report["summary"]["passed"] == report["summary"]["total"]:
        print(f"\n🎉 ALL TESTS PASSED on all Python versions!")
        return 0
    else:
        print(f"\n⚠️  Some versions failed ({report['summary']['failed']}/{report['summary']['total']})")
        return 1

if __name__ == "__main__":
    exit(main())
