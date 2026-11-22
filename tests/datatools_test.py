import os, pytest
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from wit_pytools.sanitizers import prepregex

def test_prepregex_basic():
    """Test basic functionality of prepregex"""
    try:
        # Test with a simple string
        result = prepregex("hello")
        assert result == "hello"
        
        # Test with special characters
        result = prepregex("hello.world")
        assert result == "hello\\.world"
        
        result = prepregex("test[123]")
        assert result == "test\\[123\\]"
        
        print("Test prepregex_basic: PASSED")
    except Exception as e:
        print(f"Error: {e}")
        assert False, "Test prepregex_basic: FAILED"

def test_prepregex_empty():
    """Test prepregex with empty string"""
    try:
        result = prepregex("")
        assert result == ""
        print("Test prepregex_empty: PASSED")
    except Exception as e:
        print(f"Error: {e}")
        assert False, "Test prepregex_empty: FAILED"

# Run the tests using pytest
if __name__ == "__main__":
    pytest.main(['-v', __file__])
