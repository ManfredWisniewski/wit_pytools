import os
from PIL import Image

# Use absolute paths based on the script location
script_dir = os.path.dirname(os.path.abspath(__file__))

def jpg_compress(input_path, output_path=None, quality=85, maintain_exif=True):
    """
    Compress a JPG image to a different quality level.
    
    Args:
        input_path (str): Path to the input JPG image
        output_path (str, optional): Path to save the compressed image. If None, overwrites the input file.
        quality (int, optional): Compression quality, from 1 (worst) to 95 (best). Default is 85.
        maintain_exif (bool, optional): Whether to maintain EXIF data. Default is True.
    
    Returns:
        str: Path to the compressed image
        float: Compression ratio (original size / new size)
    
    Raises:
        FileNotFoundError: If the input file doesn't exist
        ValueError: If the input file is not a valid image
    """
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input file not found: {input_path}")
    
    if quality < 1 or quality > 95:
        raise ValueError("Quality must be between 1 and 95")
    
    # If no output path is provided, use the input path
    if output_path is None:
        output_path = input_path
    
    try:
        # Open the image
        img = Image.open(input_path)
        
        # Get original file size
        original_size = os.path.getsize(input_path)
        
        # Get EXIF data if available and requested
        exif_data = None
        if maintain_exif and "exif" in img.info:
            exif_data = img.info["exif"]
        
        # If we're overwriting the original file, save to a temporary file first
        if output_path == input_path:
            temp_output = os.path.join(os.path.dirname(output_path), f"temp_{os.path.basename(output_path)}")
            img.save(temp_output, "JPEG", quality=quality, optimize=True, exif=exif_data)
            
            # Close the image before replacing the file
            img.close()
            
            # Remove the original file and rename the temp file
            try:
                os.remove(output_path)
                os.rename(temp_output, output_path)
            except PermissionError:
                # If we can't remove/rename, return the temp file instead
                output_path = temp_output
        else:
            # Ensure the output directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Save with new compression level
            img.save(output_path, "JPEG", quality=quality, optimize=True, exif=exif_data)
            
            # Close the image
            img.close()
        
        # Get new file size
        new_size = os.path.getsize(output_path)
        
        # Calculate compression ratio
        compression_ratio = original_size / new_size if new_size > 0 else 0
        
        return output_path, compression_ratio
    
    except PermissionError as pe:
        raise PermissionError(f"Permission denied: {str(pe)}. Try running as administrator or check if the file is open in another program.")
    except Exception as e:
        raise ValueError(f"Error processing image: {str(e)}")


def batch_compress_jpg(directory, output_directory=None, quality=85, recursive=False):
    """
    Compress all JPG images in a directory.
    
    Args:
        directory (str): Directory containing JPG images
        output_directory (str, optional): Directory to save compressed images. If None, overwrites original files.
        quality (int, optional): Compression quality, from 1 (worst) to 95 (best). Default is 85.
        recursive (bool, optional): Whether to process subdirectories. Default is False.
    
    Returns:
        list: List of tuples containing (file_path, compression_ratio) for each processed file
        float: Average compression ratio
    """
    if not os.path.isdir(directory):
        raise ValueError(f"Directory not found: {directory}")
    
    # Create output directory if it doesn't exist
    if output_directory and not os.path.exists(output_directory):
        os.makedirs(output_directory)
    
    results = []
    total_ratio = 0
    count = 0
    
    # Process files in the directory
    for root, dirs, files in os.walk(directory):
        # Skip if not recursive and we're in a subdirectory
        if not recursive and root != directory:
            continue
        
        for file in files:
            if file.lower().endswith(('.jpg', '.jpeg')):
                input_path = os.path.join(root, file)
                
                # Determine output path
                if output_directory:
                    # Preserve directory structure if recursive
                    rel_path = os.path.relpath(root, directory)
                    out_dir = os.path.join(output_directory, rel_path)
                    if not os.path.exists(out_dir):
                        os.makedirs(out_dir)
                    output_path = os.path.join(out_dir, file)
                else:
                    output_path = input_path
                
                try:
                    _, ratio = compress_jpg(input_path, output_path, quality)
                    results.append((input_path, ratio))
                    total_ratio += ratio
                    count += 1
                except Exception as e:
                    print(f"Error processing {input_path}: {str(e)}")
    
    avg_ratio = total_ratio / count if count > 0 else 0
    return results, avg_ratio

def png2jpg(input_path, output_path=None, quality=85, background_color=(255, 255, 255)):
    """
    Convert a PNG image to JPG format.
    
    Args:
        input_path (str): Path to the input PNG image
        output_path (str, optional): Path to save the JPG image. If None, uses the same name with .jpg extension.
        quality (int, optional): JPG quality, from 1 (worst) to 95 (best). Default is 85.
        background_color (tuple, optional): RGB background color for transparent areas. Default is white.
    
    Returns:
        str: Path to the converted JPG image
    
    Raises:
        FileNotFoundError: If the input file doesn't exist
        ValueError: If the input file is not a valid image
    """
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input file not found: {input_path}")
    
    if not input_path.lower().endswith('.png'):
        raise ValueError("Input file must be a PNG image")
    
    # If no output path is provided, use the input path with .jpg extension
    if output_path is None:
        output_path = os.path.splitext(input_path)[0] + '.jpg'
    
    try:
        # Open the PNG image
        img = Image.open(input_path)
        
        # Handle transparency
        if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
            # Create a new image with white background
            background = Image.new('RGB', img.size, background_color)
            
            # Paste the image on the background
            if img.mode == 'RGBA':
                background.paste(img, mask=img.split()[3])  # Use alpha channel as mask
            else:
                background.paste(img, mask=img.convert('RGBA').split()[3])
            
            img = background
        
        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Save as JPG
        img.convert('RGB').save(output_path, 'JPEG', quality=quality)
        img.close()
        
        return output_path
    
    except PermissionError as pe:
        raise PermissionError(f"Permission denied: {str(pe)}. Try running as administrator or check if the file is open in another program.")
    except Exception as e:
        raise ValueError(f"Error converting image: {str(e)}")


target_dir = os.path.join(script_dir, "imgtools", "done")
# Make sure the target directory exists
if not os.path.exists(target_dir):
    os.makedirs(target_dir, exist_ok=True)

sourceimage = os.path.join(script_dir, "imgtools", "testimagejpg.jpg")
# Compress a single image - keep the original filename
filename = os.path.basename(sourceimage)
#jpg_compress(sourceimage, os.path.join(target_dir, filename), quality=75)

sourceimage = os.path.join(script_dir, "imgtools", "testimagepng.png")
png2jpg(sourceimage, os.path.join(target_dir, filename), quality=75)