import os
import sys
import pytest
import tempfile
import shutil
from PIL import Image

# Add the parent directory to the path so we can import modules from wit_pytools
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from imgtools import compress_jpg, batch_compress_jpg

def create_test_image(path, size=(100, 100), color=(255, 0, 0)):
    """Create a test image for testing"""
    img = Image.new('RGB', size, color)
    img.save(path, 'JPEG', quality=95)
    return path

def test_compress_jpg():
    """Test compressing a single JPG image"""
    try:
        # Create a temporary directory for testing
        temp_dir = tempfile.mkdtemp()
        
        # Create a test image
        test_img_path = os.path.join(temp_dir, 'test.jpg')
        create_test_image(test_img_path)
        
        # Test compression with output path
        output_path = os.path.join(temp_dir, 'compressed.jpg')
        result_path, ratio = compress_jpg(test_img_path, output_path, quality=50)
        
        # Verify the result
        assert os.path.exists(result_path)
        assert ratio > 0
        assert result_path == output_path
        
        # Test compression without output path (overwrite)
        original_size = os.path.getsize(test_img_path)
        result_path, ratio = compress_jpg(test_img_path, quality=30)
        
        # Verify the result
        assert os.path.exists(result_path)
        assert ratio > 0
        assert result_path == test_img_path
        assert os.path.getsize(test_img_path) < original_size
        
        # Clean up
        shutil.rmtree(temp_dir)
        
        return "Test compress_jpg: PASSED"
    except Exception as e:
        print(f"Error: {e}")
        # Clean up even if test fails
        if 'temp_dir' in locals():
            shutil.rmtree(temp_dir)
        return "Test compress_jpg: FAILED"

def test_batch_compress_jpg():
    """Test batch compressing JPG images"""
    try:
        # Create a temporary directory structure for testing
        temp_dir = tempfile.mkdtemp()
        sub_dir = os.path.join(temp_dir, 'subdir')
        os.makedirs(sub_dir)
        output_dir = os.path.join(temp_dir, 'output')
        
        # Create test images
        img1_path = os.path.join(temp_dir, 'test1.jpg')
        img2_path = os.path.join(temp_dir, 'test2.jpg')
        img3_path = os.path.join(sub_dir, 'test3.jpg')
        
        create_test_image(img1_path)
        create_test_image(img2_path, color=(0, 255, 0))
        create_test_image(img3_path, color=(0, 0, 255))
        
        # Test batch compression without recursion
        results, avg_ratio = batch_compress_jpg(temp_dir, output_dir, quality=50)
        
        # Verify the results
        assert len(results) == 2  # Should only process the 2 images in the main directory
        assert os.path.exists(os.path.join(output_dir, 'test1.jpg'))
        assert os.path.exists(os.path.join(output_dir, 'test2.jpg'))
        assert not os.path.exists(os.path.join(output_dir, 'subdir', 'test3.jpg'))
        
        # Test batch compression with recursion
        results, avg_ratio = batch_compress_jpg(temp_dir, output_dir, quality=30, recursive=True)
        
        # Verify the results
        assert len(results) == 3  # Should process all 3 images
        assert os.path.exists(os.path.join(output_dir, 'test1.jpg'))
        assert os.path.exists(os.path.join(output_dir, 'test2.jpg'))
        assert os.path.exists(os.path.join(output_dir, 'subdir', 'test3.jpg'))
        
        # Clean up
        shutil.rmtree(temp_dir)
        
        return "Test batch_compress_jpg: PASSED"
    except Exception as e:
        print(f"Error: {e}")
        # Clean up even if test fails
        if 'temp_dir' in locals():
            shutil.rmtree(temp_dir)
        return "Test batch_compress_jpg: FAILED"

# Run the tests and print the result messages
if __name__ == "__main__":
    result_single = test_compress_jpg()
    print(result_single)
    
    result_batch = test_batch_compress_jpg()
    print(result_batch)
