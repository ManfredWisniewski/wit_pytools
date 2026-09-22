import os
import shutil
import textwrap
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

from wit_pytools.systools import checkfile

# Use absolute paths based on the script location
script_dir = os.path.dirname(os.path.abspath(__file__))

def jpg_compress(input_path, output_path=None, quality=85, maintain_exif=True, min_size_reduction=0.1, calc=False):
    """
    Compress a JPG image to a different quality level.
    
    Args:
        input_path (str): Path to the input JPG image
        output_path (str, optional): Path to save the compressed image. If None, overwrites the input file.
        quality (int, optional): Compression quality, from 1 (worst) to 95 (best). Default is 85.
        maintain_exif (bool, optional): Whether to maintain EXIF data. Default is True.
        min_size_reduction (float, optional): Minimum fraction of size reduction required (e.g. 0.1 for 10%). Default is 0.1.
        calc (bool, optional): If True, only calculate estimated compressed file size without saving. Default is False.
    
    Returns:
        if calc: int Estimated compressed file size in bytes
        else: str Path to the compressed image
              float Compression ratio (original size / new size)
    
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

        # Estimate compressed size in-memory
        buf = BytesIO()
        save_kwargs = {"quality": quality}
        if exif_data is not None:
            save_kwargs["exif"] = exif_data
        img.save(buf, "JPEG", **save_kwargs)
        estimated_size = buf.tell()
        # If calc mode, return estimated size without saving
        if calc:
            img.close()
            return estimated_size
        # Skip compression if not effective (less than specified fraction reduction)
        threshold = min_size_reduction  # require at least specified fraction reduction
        if estimated_size > original_size * (1 - threshold):
            img.close()
            if output_path != input_path:
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                shutil.copy2(input_path, output_path)
            if calc:
                return estimated_size
            else:
                return output_path, 1.0

        # If we're overwriting the original file, save to a temporary file first
        if output_path == input_path:
            temp_output = os.path.join(os.path.dirname(output_path), f"temp_{os.path.basename(output_path)}")
            save_kwargs = {"quality": quality}
            if exif_data is not None:
                save_kwargs["exif"] = exif_data
            img.save(temp_output, "JPEG", **save_kwargs)
            
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
            save_kwargs = {"quality": quality}
            if exif_data is not None:
                save_kwargs["exif"] = exif_data
            img.save(output_path, "JPEG", **save_kwargs)
            
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

def avif_compress(input_path, output_path=None, quality=85, maintain_exif=True, min_size_reduction=0.1, calc=False):
    """
    Compress an image to AVIF format.
    
    Args:
        input_path (str): Path to the input image
        output_path (str, optional): Path to save the compressed AVIF image. If None, uses same name with .avif extension.
        quality (int, optional): Compression quality (0 worst–100 best). Default is 85.
        maintain_exif (bool, optional): Whether to maintain EXIF data. Default is True.
        min_size_reduction (float, optional): Minimum fraction of size reduction required (e.g. 0.1 for 10%). Default is 0.1.
        calc (bool, optional): If True, only calculate estimated file size without saving. Default is False.
    
    Returns:
        if calc: int Estimated compressed file size in bytes
        else: str Path to the compressed image
              float Compression ratio (original size / new size)
    
    Raises:
        FileNotFoundError: If the input file doesn't exist
        ValueError: If processing fails
    """
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input file not found: {input_path}")

    if output_path is None:
        output_path = os.path.splitext(input_path)[0] + '.avif'

    try:
        img = Image.open(input_path)
        original_size = os.path.getsize(input_path)

        exif_data = None
        if maintain_exif and "exif" in img.info:
            exif_data = img.info["exif"]

        # Estimate compressed size in-memory (catch unsupported format)
        buf = BytesIO()
        try:
            img.save(buf, "AVIF", quality=quality, exif=exif_data)
            estimated_size = buf.tell()
        except (KeyError, ValueError):
            img.close()
            if calc:
                return original_size
            # format not supported: fallback to original
            if output_path != input_path:
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                shutil.copy2(input_path, output_path)
            return output_path, 1.0

        if calc:
            img.close()
            return estimated_size

        if estimated_size > original_size * (1 - min_size_reduction):
            img.close()
            if output_path != input_path:
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                shutil.copy2(input_path, output_path)
            return output_path, 1.0

        # Perform actual compression
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        img.save(output_path, "AVIF", quality=quality, exif=exif_data)
        img.close()

        new_size = os.path.getsize(output_path)
        compression_ratio = original_size / new_size if new_size > 0 else 0
        return output_path, compression_ratio

    except Exception as e:
        raise ValueError(f"Error processing AVIF image: {str(e)}")

def png_compress(input_path, output_path=None, compress_level=6, min_size_reduction=0.1, calc=False):
    """
    Compress an image to PNG format.
    
    Args:
        input_path (str): Path to the input image
        output_path (str, optional): Path to save the compressed PNG image. If None, overwrites the input file.
        compress_level (int, optional): Compression level (0 no compression–9 max). Default is 6.
        min_size_reduction (float, optional): Minimum fraction of size reduction required (e.g. 0.1 for 10%). Default is 0.1.
        calc (bool, optional): If True, only calculate estimated file size without saving. Default is False.
    
    Returns:
        if calc: int Estimated compressed file size in bytes
        else: str Path to the compressed image
              float Compression ratio (original size / new size)
    
    Raises:
        FileNotFoundError: If the input file doesn't exist
        ValueError: If processing fails
    """
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input file not found: {input_path}")

    if output_path is None:
        output_path = input_path

    try:
        img = Image.open(input_path)
        original_size = os.path.getsize(input_path)

        # Estimate compressed size in-memory
        buf = BytesIO()
        img.save(buf, "PNG", optimize=True, compress_level=compress_level)
        estimated_size = buf.tell()

        if calc:
            img.close()
            return estimated_size

        if estimated_size > original_size * (1 - min_size_reduction):
            img.close()
            if output_path != input_path:
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                shutil.copy2(input_path, output_path)
            return output_path, 1.0

        # Perform actual compression
        if output_path != input_path:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
        img.save(output_path, "PNG", optimize=True, compress_level=compress_level)
        img.close()

        new_size = os.path.getsize(output_path)
        compression_ratio = original_size / new_size if new_size > 0 else 0
        return output_path, compression_ratio

    except Exception as e:
        raise ValueError(f"Error processing PNG image: {str(e)}")

def save_img(input_path, quality=85, compress_level=6, maintain_exif=True, min_size_reduction=0.1):
    """Save image as JPEG or PNG, choosing the smaller resulting file."""
    # Prepare output names
    base, _ = os.path.splitext(input_path)
    jpg_path = base + '.jpg'
    png_path = base + '.png'
    # Estimate sizes
    est_jpg = jpg_compress(input_path, jpg_path,
                           quality=quality,
                           maintain_exif=maintain_exif,
                           min_size_reduction=min_size_reduction,
                           calc=True)
    est_png = png_compress(input_path, png_path,
                           compress_level=compress_level,
                           min_size_reduction=min_size_reduction,
                           calc=True)
    # Perform chosen compression
    if est_jpg <= est_png:
        return jpg_compress(input_path, jpg_path,
                            quality=quality,
                            maintain_exif=maintain_exif,
                            min_size_reduction=min_size_reduction)
    else:
        return png_compress(input_path, png_path,
                            compress_level=compress_level,
                            min_size_reduction=min_size_reduction)

def img_getexif(sourcedir, image):
    try:
        if not checkfile(sourcedir, image):
            return None
        from PIL import Image, ExifTags
        with Image.open(os.path.join(sourcedir, image)) as img:
            exif_data = img._getexif()
            
        # Convert numeric IDs to tag names via the PIL ExifTags module
            exif_readable = {}
            if exif_data is not None:
                for tag_id, value in exif_data.items():
                    tag_name = ExifTags.TAGS.get(tag_id, str(tag_id))
                    exif_readable[tag_name] = value
            
            return exif_readable
    except FileNotFoundError as e:
        raise e
    except Exception as e:
        raise ValueError(f"Error getting EXIF data: {str(e)}")

def _watermark_font(font_path, font_size):
    if font_path:
        return ImageFont.truetype(font_path, font_size)
    return ImageFont.load_default()


def _watermark_text_lines(draw, text, font, max_width):
    lines = []
    for paragraph in text.splitlines() or ['']:
        words = paragraph.split()
        if not words:
            lines.append('')
            continue
        current = words[0]
        for word in words[1:]:
            candidate = f'{current} {word}'
            if draw.textlength(candidate, font=font) <= max_width:
                current = candidate
            else:
                lines.append(current)
                current = word
        lines.append(current)
    return lines


def add_watermark(
    input_path,
    output_path=None,
    *,
    text=None,
    watermark_image=None,
    position='bottom-right',
    font_path=None,
    font_size=None,
    text_color=(255, 255, 255),
    text_opacity=128,
    logo_max_size=None,
    logo_opacity=128,
    margin=20,
    outline_color=(0, 0, 0),
    outline_width=2,
    max_text_width_ratio=0.40,
    background_color=(255, 255, 255),
    overwrite=False,
):
    """Add a literal text and/or logo watermark without overwriting the source."""
    source = Path(input_path)
    if not source.is_file():
        raise FileNotFoundError(source)
    if text is None and watermark_image is None:
        raise ValueError('text or watermark_image is required')
    if position not in {'top-left', 'top-right', 'bottom-left', 'bottom-right', 'center'}:
        raise ValueError('Unsupported watermark position')
    if not 0 <= text_opacity <= 255 or not 0 <= logo_opacity <= 255:
        raise ValueError('Opacity must be between 0 and 255')
    if not 0 < max_text_width_ratio <= 1 or margin < 0:
        raise ValueError('Invalid text width ratio or margin')

    target = Path(output_path) if output_path is not None else source.with_name(
        f'{source.stem}_watermarked{source.suffix}'
    )
    if target.resolve() == source.resolve():
        raise ValueError('The output path must differ from the source path')
    if target.exists() and not overwrite:
        raise FileExistsError(target)

    image = ImageOps.exif_transpose(Image.open(source))
    exif = image.info.get('exif')
    icc_profile = image.info.get('icc_profile')
    base = image.convert('RGBA')
    overlay = Image.new('RGBA', base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    elements = []
    padding = max(8, margin // 2)

    if watermark_image is not None:
        logo = ImageOps.exif_transpose(Image.open(watermark_image)).convert('RGBA')
        max_size = logo_max_size or (max(1, int(base.width * 0.25)), max(1, int(base.height * 0.25)))
        logo.thumbnail(max_size, Image.Resampling.LANCZOS)
        alpha = logo.getchannel('A').point(lambda value: value * logo_opacity // 255)
        logo.putalpha(alpha)
        elements.append(('logo', logo))

    if text is not None:
        size = font_size or max(12, int(base.width * 0.04))
        font = _watermark_font(font_path, size)
        lines = _watermark_text_lines(draw, str(text), font, base.width * max_text_width_ratio)
        bbox = draw.multiline_textbbox((0, 0), '\n'.join(lines), font=font, stroke_width=outline_width)
        text_layer = Image.new('RGBA', (bbox[2] - bbox[0], bbox[3] - bbox[1]), (0, 0, 0, 0))
        text_draw = ImageDraw.Draw(text_layer)
        fill = (*text_color[:3], text_opacity)
        stroke = (*outline_color[:3], text_opacity)
        text_draw.multiline_text((-bbox[0], -bbox[1]), '\n'.join(lines), font=font, fill=fill, stroke_width=outline_width, stroke_fill=stroke)
        elements.append(('text', text_layer))

    block_width = max(element.width for _, element in elements) + padding * 2
    block_height = sum(element.height for _, element in elements) + padding * 2 + max(0, len(elements) - 1) * padding
    block = Image.new('RGBA', (block_width, block_height), (0, 0, 0, 0))
    y = padding
    for _, element in elements:
        block.alpha_composite(element, ((block_width - element.width) // 2, y))
        y += element.height + padding

    if position in {'top-left', 'bottom-left'}:
        x = margin
    elif position in {'top-right', 'bottom-right'}:
        x = base.width - block.width - margin
    else:
        x = (base.width - block.width) // 2
    if position in {'top-left', 'top-right'}:
        y = margin
    elif position in {'bottom-left', 'bottom-right'}:
        y = base.height - block.height - margin
    else:
        y = (base.height - block.height) // 2
    overlay.alpha_composite(block, (max(0, x), max(0, y)))
    result = Image.alpha_composite(base, overlay)

    target.parent.mkdir(parents=True, exist_ok=True)
    format_name = Image.registered_extensions().get(target.suffix.lower())
    if not format_name:
        raise ValueError(f'Unsupported output image extension: {target.suffix}')
    save_kwargs = {}
    if exif and format_name not in {'PNG', 'WEBP'}:
        save_kwargs['exif'] = exif
    if icc_profile:
        save_kwargs['icc_profile'] = icc_profile
    if format_name in {'JPEG', 'JPG'}:
        result = result.convert('RGB')
    result.save(target, format=format_name, **save_kwargs)
    image.close()
    if watermark_image is not None:
        logo.close()
    return str(target)


def img_getgps(sourcedir, image):
    """
    Extract GPS coordinates from an image's EXIF data.
    
    Args:
        sourcedir (str): Directory containing the image
        image (str): Image filename
        
    Returns:
        tuple: (latitude, longitude) or None if GPS data not found or coordinates are (0,0)
    """
    from wit_pytools.gpstools import _convert_to_decimal_degrees    
    try:
        exif_data = img_getexif(sourcedir, image)
        if exif_data and 'GPSInfo' in exif_data:
            gps_info = exif_data['GPSInfo']
            lat_ref = gps_info.get(1, 'N')
            lat_data = gps_info.get(2)
            lon_ref = gps_info.get(3, 'E')
            lon_data = gps_info.get(4)
            if not (isinstance(lat_data, (list, tuple)) and len(lat_data) == 3 and isinstance(lon_data, (list, tuple)) and len(lon_data) == 3):
                print(f"Invalid GPS data structure in file {image}: lat_data={lat_data}, lon_data={lon_data}")
                return None
            latitude = _convert_to_decimal_degrees(lat_data, lat_ref)
            longitude = _convert_to_decimal_degrees(lon_data, lon_ref)
            if latitude is not None and longitude is not None:
                # Check if coordinates are (0,0) and treat as no GPS data
                if abs(latitude) < 0.000001 and abs(longitude) < 0.000001:
                    print(f"Image {image} has GPS coordinates of (0,0), treating as no GPS data")
                    return None
                return (latitude, longitude)
    except Exception as e:
        print(f"Error extracting GPS data: {e}")
    return None

#target_dir = os.path.join(script_dir, "imgtools", "done")
# Make sure the target directory exists
#if not os.path.exists(target_dir):
#    os.makedirs(target_dir, exist_ok=True)

#sourceimage = os.path.join(script_dir, "imgtools", "testimagejpg.jpg")
# Compress a single image - keep the original filename
#filename = os.path.basename(sourceimage)
#jpg_compress(sourceimage, os.path.join(target_dir, filename), quality=75)

#sourceimage = os.path.join(script_dir, "imgtools", "testimagepng.png")
#png2jpg(sourceimage, os.path.join(target_dir, filename), quality=75)

#img_getexif(script_dir, r"P:\git\witnctools\wit_pytools\tests\imgtools\testimage.jpg")