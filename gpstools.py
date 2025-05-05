import math
import os
import sys

# Add path to parent directory to allow importing from sibling modules
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(parent_dir)
# Use direct import instead of package-style import
from wit_pytools.imgtools import img_getgps, img_getexif    

def _convert_to_decimal_degrees(degrees_data, ref):
    """
    Convert GPS coordinates from degrees/minutes/seconds to decimal degrees.
    
    Args:
        degrees_data: GPS degrees data from EXIF
        ref: Reference direction (N, S, E, W)
        
    Returns:
        float: Decimal degrees
    """
    try:
        # Handle different types of GPS data
        degrees = minutes = seconds = 0
        
        # Check if we have IFDRational objects
        if hasattr(degrees_data[0], 'numerator'):
            if (degrees_data[0].denominator == 0 or degrees_data[1].denominator == 0 or degrees_data[2].denominator == 0):
                print("Error converting GPS data: denominator is zero in IFDRational object")
                return None
            degrees = float(degrees_data[0].numerator) / float(degrees_data[0].denominator)
            minutes = float(degrees_data[1].numerator) / float(degrees_data[1].denominator)
            seconds = float(degrees_data[2].numerator) / float(degrees_data[2].denominator)
        else:
            # Handle as regular tuples/lists
            if (degrees_data[0][1] == 0 or degrees_data[1][1] == 0 or degrees_data[2][1] == 0):
                print("Error converting GPS data: denominator is zero in tuple/list")
                return None
            degrees = float(degrees_data[0][0]) / float(degrees_data[0][1])
            minutes = float(degrees_data[1][0]) / float(degrees_data[1][1])
            seconds = float(degrees_data[2][0]) / float(degrees_data[2][1])
        
        # Convert to decimal degrees
        decimal = degrees + (minutes / 60.0) + (seconds / 3600.0)
        
        # Apply reference direction
        if ref in ['S', 'W']:
            decimal = -decimal
            
        return decimal
    except Exception as e:
        print(f"Error converting GPS data: {e}")
        return None

def is_valid_gps(s):
    parts = s.split(',')
    if len(parts) == 2:
        try:
            float(parts[0].strip())
            float(parts[1].strip())
            return True
        except ValueError:
            return False
    return False

def gps_distance(coord1, coord2):
    """
    Calculate the distance between two GPS coordinates using the Haversine formula.
    
    Args:
        coord1 (tuple): First GPS coordinate as (latitude, longitude) in decimal degrees
        coord2 (tuple): Second GPS coordinate as (latitude, longitude) in decimal degrees
        
    Returns:
        float: Distance between the coordinates in kilometers
    """
    # Earth radius in kilometers
    earth_radius = 6371.0
    
    # Convert latitude and longitude from degrees to radians
    lat1 = math.radians(coord1[0])
    lon1 = math.radians(coord1[1])
    lat2 = math.radians(coord2[0])
    lon2 = math.radians(coord2[1])
    
    # Haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    distance = earth_radius * c
    
    return distance
