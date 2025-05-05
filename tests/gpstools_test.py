import os
import sys
import pytest
import math

# Add the parent directory to the path so we can import modules from wit_pytools
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(parent_dir)
from gpstools import gps_distance
from imgtools import img_getexif, img_getgps

def test_gps_distance():
    """Test calculating distance between two GPS coordinates"""
    try:
        # Test case 1: Berlin to Paris
        berlin = (52.5200, 13.4050)
        paris = (48.8566, 2.3522)
        distance = gps_distance(berlin, paris)
        
        # Expected distance is approximately 878 km
        expected_distance = 878.0
        # Allow for small differences due to floating-point calculations
        assert abs(distance - expected_distance) < 5.0
        
        # Test case 2: New York to Los Angeles
        new_york = (40.7128, -74.0060)
        los_angeles = (34.0522, -118.2437)
        distance = gps_distance(new_york, los_angeles)
        
        # Expected distance is approximately 3935 km
        expected_distance = 3935.0
        # Allow for small differences due to floating-point calculations
        assert abs(distance - expected_distance) < 10.0
        
        # Test case 3: Same coordinates should return 0
        same_point = (51.5074, -0.1278)  # London
        distance = gps_distance(same_point, same_point)
        assert distance == 0.0
        
        return "Test gps_distance: PASSED"
    except Exception as e:
        print(f"Error: {e}")
        return f"Test gps_distance: FAILED - {str(e)}"

def test_img_getgps():
    """Test extracting GPS coordinates from an image"""
    try:
        # Test directory and image
        test_img_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "imgtools")
        test_img = "testimage.jpg"
        
        # Get GPS coordinates from the test image
        coords = img_getgps(test_img_dir, test_img)
        
        # Verify the result
        assert coords is not None
        assert isinstance(coords, tuple)
        assert len(coords) == 2
        
        # Verify latitude and longitude values
        latitude, longitude = coords
        
        # Based on the test image EXIF data from imgtools_test.py
        # The test image has coordinates around 51°N, 10°E
        assert abs(latitude - 51.0) < 1.0
        assert abs(longitude - 10.0) < 1.0
        
        # Test with non-existent image
        coords = img_getgps(test_img_dir, "nonexistent.jpg")
        assert coords is None
        
        return "Test img_getgps: PASSED"
    except Exception as e:
        print(f"Error: {e}")
        return f"Test img_getgps: FAILED - {str(e)}"

def test_distance_to_magdeburg():
    """Test calculating distance from test image to Magdeburg"""
    try:
        # Test directory and image
        test_img_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "imgtools")
        test_img = "testimage.jpg"
        
        # Magdeburg coordinates
        magdeburg_coords = (52.11594623743321, 11.603707931453604)
        
        # Get GPS coordinates from the test image
        image_coords = img_getgps(test_img_dir, test_img)
        
        # Verify we got coordinates
        assert image_coords is not None
        
        # Calculate distance to Magdeburg
        distance = gps_distance(image_coords, magdeburg_coords)
        
        # Print the results for verification
        print(f"Image coordinates: {image_coords}")
        print(f"Magdeburg coordinates: {magdeburg_coords}")
        print(f"Distance to Magdeburg: {distance:.2f} km")
        
        # The test image is expected to be somewhere in Germany
        # So the distance to Magdeburg should be reasonable (less than 500 km)
        assert distance < 60.0
        
        return "Test distance_to_magdeburg: PASSED"
    except Exception as e:
        print(f"Error: {e}")
        return f"Test distance_to_magdeburg: FAILED - {str(e)}"

# Run the tests and print the result messages
if __name__ == "__main__":
    result_distance = test_gps_distance()
    print(result_distance)
    
    result_from_img = test_img_getgps()
    print(result_from_img)
    
    result_magdeburg = test_distance_to_magdeburg()
    print(result_magdeburg)
