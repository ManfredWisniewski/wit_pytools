#!/usr/bin/env python
"""
Test runner script that discovers and runs all tests in the tests directory.
"""
import os
import sys
import pytest

# Add the parent directory to the path so we can import modules from wit_pytools
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def run_unittest_tests():
    """Run tests using unittest discovery"""
    print("Running unittest tests...")
    # Since we're moving to pytest, this function is kept for backward compatibility
    # but will just use pytest with unittest-style tests
    test_dir = os.path.dirname(os.path.abspath(__file__))
    result = pytest.main(['-v', test_dir, '--pyargs'])
    return result == 0

def run_pytest_tests():
    """Run tests using pytest"""
    print("Running pytest tests...")
    # Run pytest on the current directory
    result = pytest.main(["-v", os.path.dirname(os.path.abspath(__file__))])
    return result == 0

def run_individual_tests():
    """Run individual test files directly using pytest"""
    print("Running individual test files...")
    success = True
    
    # Get all Python test files recursively from the tests directory.
    test_dir = os.path.dirname(os.path.abspath(__file__))
    test_files = []
    for root, _, files in os.walk(test_dir):
        for filename in files:
            if filename.endswith('.py') and (
                filename.startswith('test_') or filename.endswith('_test.py')
            ):
                test_files.append(os.path.join(root, filename))

    for file_path in sorted(test_files):
        test_file = os.path.relpath(file_path, test_dir)
        print(f"\nRunning {test_file}...")
        try:
            # Run the test file with pytest
            result = pytest.main(['-v', file_path])
            if result != 0:
                success = False
            print(f"Completed {test_file}")
        except Exception as e:
            print(f"Error running {test_file}: {e}")
            success = False
    
    return success

if __name__ == "__main__":
    print("=== WIT PyTools Test Runner ===")
    
    # Try different test running methods
    # First try unittest discovery
    unittest_success = run_unittest_tests()
    
    # Then try pytest
    pytest_success = run_pytest_tests()
    
    # Finally, run individual test files directly
    individual_success = run_individual_tests()
    
    # Overall success is determined by all methods succeeding
    overall_success = unittest_success and pytest_success and individual_success
    
    print("\n=== Test Summary ===")
    print(f"Unittest tests: {'PASSED' if unittest_success else 'FAILED'}")
    print(f"Pytest tests: {'PASSED' if pytest_success else 'FAILED'}")
    print(f"Individual tests: {'PASSED' if individual_success else 'FAILED'}")
    print(f"Overall result: {'PASSED' if overall_success else 'FAILED'}")
    
    # Exit with appropriate status code
    sys.exit(0 if overall_success else 1)
