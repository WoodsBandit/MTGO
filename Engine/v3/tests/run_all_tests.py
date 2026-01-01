"""
Master test runner for MTG Engine V3.
Runs all unit test suites and provides a combined report.

Test Suites:
- Integration Tests (test_runner.py)
- Mana System Tests (test_mana.py)
- Zone Management Tests (test_zones.py)
- Spell Effects Tests (test_effects.py)
- Card Database Tests (test_database.py)
"""
import sys
import os
from pathlib import Path
from datetime import datetime

# Add v3 to path
v3_dir = Path(__file__).parent.parent
sys.path.insert(0, str(v3_dir))
os.chdir(str(v3_dir))


def run_test_suite(name: str, runner_func) -> tuple:
    """Run a test suite and return (name, passed, failed)."""
    print(f"\n{'#' * 70}")
    print(f"# {name}")
    print(f"{'#' * 70}")

    try:
        success = runner_func()
        return (name, success, None)
    except Exception as e:
        return (name, False, str(e))


def main():
    """Run all test suites."""
    print("=" * 70)
    print("MTG ENGINE V3 - COMPREHENSIVE TEST SUITE")
    print(f"Run at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    results = []

    # Import and run each test suite
    print("\n[1/5] Loading Integration Tests...")
    try:
        from test_runner import run_all_tests as run_integration
        results.append(run_test_suite("Integration Tests", run_integration))
    except Exception as e:
        results.append(("Integration Tests", False, str(e)))
        print(f"  ERROR: {e}")

    print("\n[2/5] Loading Mana System Tests...")
    try:
        from test_mana import run_mana_tests
        results.append(run_test_suite("Mana System Tests", run_mana_tests))
    except Exception as e:
        results.append(("Mana System Tests", False, str(e)))
        print(f"  ERROR: {e}")

    print("\n[3/5] Loading Zone Management Tests...")
    try:
        from test_zones import run_zone_tests
        results.append(run_test_suite("Zone Management Tests", run_zone_tests))
    except Exception as e:
        results.append(("Zone Management Tests", False, str(e)))
        print(f"  ERROR: {e}")

    print("\n[4/5] Loading Spell Effects Tests...")
    try:
        from test_effects import run_effect_tests
        results.append(run_test_suite("Spell Effects Tests", run_effect_tests))
    except Exception as e:
        results.append(("Spell Effects Tests", False, str(e)))
        print(f"  ERROR: {e}")

    print("\n[5/5] Loading Card Database Tests...")
    try:
        from test_database import run_database_tests
        results.append(run_test_suite("Card Database Tests", run_database_tests))
    except Exception as e:
        results.append(("Card Database Tests", False, str(e)))
        print(f"  ERROR: {e}")

    # Final Summary
    print("\n")
    print("=" * 70)
    print("FINAL TEST SUMMARY")
    print("=" * 70)

    total_passed = 0
    total_failed = 0

    for name, success, error in results:
        if success:
            status = "PASS"
            total_passed += 1
        else:
            status = "FAIL"
            total_failed += 1
            if error:
                status += f" ({error})"
        print(f"  {name}: {status}")

    print("-" * 70)
    print(f"  Total Suites: {len(results)}")
    print(f"  Passed: {total_passed}")
    print(f"  Failed: {total_failed}")
    print("=" * 70)

    if total_failed == 0:
        print("\n  ALL TESTS PASSED!")
    else:
        print(f"\n  {total_failed} test suite(s) failed.")

    return total_failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
