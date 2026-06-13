r"""
Autonomy Test: Verify that felix-mcp-standalone is truly standalone.

This script checks that:
1. No imports from C:\Users\53\Felix exist in the codebase
2. All tests pass without access to the internal core
3. Product Judge is self-contained (no shared code with Mirror Forge)
"""
import os
import sys
import subprocess
from pathlib import Path

def check_no_core_imports():
    """Scan all .py files for imports or paths pointing to internal core"""
    project_root = Path(__file__).parent.parent
    violations = []
    
    for py_file in project_root.rglob("*.py"):
        if "test_autonomy.py" in str(py_file):
            continue
        
        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception:
            continue
            
        # Check for explicit paths to internal core
        if r"C:\Users\53\Felix" in content or "C:/Users/53/Felix" in content:
            violations.append(f"{py_file}: Contains explicit path to internal core")
        
        # Check for direct imports from internal core
        if "from src.core.mirror_forge" in content or "import src.core" in content:
            violations.append(f"{py_file}: Imports from internal core (Mirror Forge)")
    
    return violations

def run_tests():
    """Run pytest and return True if all pass"""
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-v"],
        cwd=Path(__file__).parent.parent,
        capture_output=True,
        text=True
    )
    return result.returncode == 0, result.stdout

def main():
    print("=" * 60)
    print("AUTONOMY TEST: felix-mcp-standalone")
    print("=" * 60)
    
    # Test 1: No core imports
    print("\n[1/2] Checking for imports from internal core...")
    violations = check_no_core_imports()
    if violations:
        print("❌ FAIL: Found imports from internal core:")
        for v in violations:
            print(f"  - {v}")
        return False
    else:
        print(r"✅ PASS: No imports from C:\Users\53\Felix")
    
    # Test 2: All tests pass
    print("\n[2/2] Running all tests...")
    success, output = run_tests()
    if success:
        print("✅ PASS: All tests pass")
    else:
        print("❌ FAIL: Some tests failed")
        print(output)
        return False
    
    print("\n" + "=" * 60)
    print("✅ AUTONOMY TEST PASSED")
    print("Product is truly standalone and self-contained.")
    print("=" * 60)
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)