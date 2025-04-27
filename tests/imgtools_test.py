import os
import sys
import pytest
import tempfile
import shutil
from PIL import Image

# Add the parent directory to the path so we can import modules from wit_pytools
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from wit_pytools.imgtools import jpg_compress, png2jpg, getexifdata

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
        result_path, ratio = jpg_compress(test_img_path, output_path, quality=50)
        
        # Verify the result
        assert os.path.exists(result_path)
        assert ratio > 0
        assert result_path == output_path
        
        # Test compression without output path (overwrite)
        original_size = os.path.getsize(test_img_path)
        result_path, ratio = jpg_compress(test_img_path, quality=30)
        
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

def test_getexifdata():
    try:
        test_img_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "imgtools")
        from wit_pytools.imgtools import getexifdata
        
        # Test getting EXIF data
        exif_data = getexifdata(test_img_dir, 'testimage.jpg')
        
        # Verify the result
        assert exif_data is not None
        
        # Verify key EXIF fields match expected values from testimage.jpg
        assert exif_data['Make'] == 'Google'
        assert exif_data['Model'] == 'Pixel 7 Pro'
        assert exif_data['Software'] == 'HDR+ 1.0.621982163zd'
        assert exif_data['DateTime'] == '2025:04:04 10:36:36'
        assert exif_data['DateTimeOriginal'] == '2024:05:12 16:05:39'
        assert exif_data['ExifImageWidth'] == 2080
        assert exif_data['ExifImageHeight'] == 1567
        assert exif_data['LensModel'] == 'Pixel 7 Pro back camera 6.81mm f/1.85'
        
        # Verify GPS information
        assert 'GPSInfo' in exif_data
        gps_info = exif_data['GPSInfo']
        assert gps_info[1] == 'N'  # North latitude
        assert gps_info[3] == 'E'  # East longitude
        assert isinstance(gps_info[2], tuple) and len(gps_info[2]) == 3  # Latitude values
        assert isinstance(gps_info[4], tuple) and len(gps_info[4]) == 3  # Longitude values
        assert gps_info[2][0] == 51.0  # Latitude degrees
        assert gps_info[4][0] == 10.0  # Longitude degrees
        
        return "Test getexifdata: PASSED"
    except Exception as e:
        print(f"Error: {e}")
        return f"Test getexifdata: FAILED - {str(e)}"

# Run the tests and print the result messages
if __name__ == "__main__":
    result_single = test_compress_jpg()
    print(result_single)
    
    result_getexifdata = test_getexifdata()
    print(result_getexifdata)
