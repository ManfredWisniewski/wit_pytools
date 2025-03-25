#!/usr/bin/env python
"""
Test runner script that discovers and runs all tests in the tests directory.
"""
import os
import sys
import unittest
import pytest

# Add the parent directory to the path so we can import modules from wit_pytools
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def run_unittest_tests():
    """Run tests using unittest discovery"""
    print("Running unittest tests...")
    # Start discovery from the current directory
    test_loader = unittest.TestLoader()
    test_suite = test_loader.discover(os.path.dirname(os.path.abspath(__file__)))
    
    # Run the tests
    test_runner = unittest.TextTestRunner(verbosity=2)
    result = test_runner.run(test_suite)
    return result.wasSuccessful()

def run_pytest_tests():
    """Run tests using pytest"""
    print("Running pytest tests...")
    # Run pytest on the current directory
    result = pytest.main(["-v", os.path.dirname(os.path.abspath(__file__))])
    return result == 0

def run_individual_tests():
    """Run individual test files directly"""
    print("Running individual test files...")
    success = True
    
    # Get all Python files in the tests directory that start with 'test_' or end with '_test.py'
    test_dir = os.path.dirname(os.path.abspath(__file__))
    test_files = [f for f in os.listdir(test_dir) 
                 if f.endswith('.py') and (f.startswith('test_') or f.endswith('_test.py'))]
    
    for test_file in test_files:
        print(f"\nRunning {test_file}...")
        # Import the module
        module_name = os.path.splitext(test_file)[0]  # Remove .py extension
        try:
            # Use __import__ to dynamically import the module
            module = __import__(module_name, fromlist=['*'])
            
            # If the module has a main function, call it
            if hasattr(module, 'main'):
                result = module.main()
                if result is not None and result is False:
                    success = False
            # Otherwise, just let the module execute
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
