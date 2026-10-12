# imgtools

`imgtools` provides Pillow-based functions for image compression, conversion,
EXIF/GPS inspection, and watermarking.

## Add a watermark

```python
from wit_pytools.imgtools import add_watermark

output = add_watermark(
    "source.jpg",
    text="Example",
    output_path="source_watermarked.jpg",
    position="bottom-right",
)
```

Text, a local logo image, or both may be supplied. A combined watermark places
the logo above the text. Supported positions are `top-left`, `top-right`,
`bottom-left`, `bottom-right`, and `center`.

If `output_path` is omitted, the output is `<stem>_watermarked<suffix>`. The
source is never overwritten implicitly and existing output requires
`overwrite=True`.

Text wraps at 40% of the image width by default. Logos preserve their aspect
ratio and fit within 25% of the source dimensions. JPEG output is composited
against `background_color`; PNG and other alpha-capable formats preserve
transparency. EXIF and ICC metadata are preserved where supported.

## Add an AI label badge

```python
from wit_pytools.imgtools import add_ai_label

output = add_ai_label("source.jpg")                    # -> source_ai.jpg, 512x512
output = add_ai_label("source.jpg", "out.jpg", size=1024)
```

The image is center-cropped to a square and resized to `size` px, then the
`LABEL_AI_black` badge (bundled in `wit_pytools/imgtools/`) is rendered at the
bottom-left with a white inside-stroke ring. CLI:

```text
python -m wit_pytools.imgtools <image-or-dir> [output] [--size 512] [--badge badge.png] [--overwrite]
```

A directory input processes every image inside into `<name>_ai<ext>` files.

## Other functions

- `jpg_compress`
- `png_compress`
- `avif_compress`
- `png2jpg`
- `save_img`
- `img_getexif`
- `img_getgps`
