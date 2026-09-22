# Intent: `imgtools`

## Package purpose

`imgtools` provides modular Python functions for handling image files. The
current module supports image compression, format conversion, EXIF/GPS
inspection, and watermark composition.

## Watermarking

### Public function

```python
add_watermark(
    input_path,
    output_path=None,
    *,
    text=None,
    watermark_image=None,
    position="bottom-right",
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
) -> str
```

At least one of `text` or `watermark_image` is required. Text and logo may be
combined into one block, with the logo above the text. The default position is
`bottom-right`; supported positions are `top-left`, `top-right`,
`bottom-left`, `bottom-right`, and `center`.

Text wraps at the configured maximum width. The default logo size is 25% of
the source dimensions, preserving aspect ratio. Initial watermarking is
horizontal; rotated or tiled watermarks are not included.

The source is never overwritten implicitly. Without `output_path`, the output
is `<stem>_watermarked<suffix>`. Existing output files require
`overwrite=True`. The function preserves EXIF and ICC metadata where the
format supports it and applies EXIF orientation before compositing. Alpha is
preserved where supported; JPEG output is composited against
`background_color`.

## Existing image functions

- `jpg_compress` — compress JPEG files with optional EXIF preservation.
- `png_compress` — compress PNG files.
- `avif_compress` — compress or estimate AVIF output.
- `png2jpg` — convert PNG to JPEG with transparency handling.
- `save_img` — select a suitable image-saving operation by extension.
- `img_getexif` — read readable EXIF data.
- `img_getgps` — extract decimal GPS coordinates from EXIF data.

All image inputs are handled through Pillow. Watermark text is literal and
logo paths are local; no network resources are loaded.
