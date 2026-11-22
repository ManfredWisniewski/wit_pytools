"""Image classification and markup for the inbox pipeline.

Decides whether an image is *content* (document/printed text) or *art*
(photo, graphic). The check is tiered, cheapest first: grayscale bimodal
histogram -> tesseract OCR -> vision model. Document images get a
``.md`` markup from the OCR/vision text so JEV and content crits work.
"""

import re
import shutil
import subprocess
from pathlib import Path

from eliot import log_message

from wit_pytools.aitools import chat, image_part

IMAGE_SUFFIXES = frozenset(
    ('.jpg', '.jpeg', '.png', '.tif', '.tiff', '.webp', '.bmp')
)

# Histogram thresholds (fractions of all pixels). Permissive on purpose:
# OCR/VLM do the real filtering, this only rejects obvious photos.
_DOC_WHITE_MIN = 0.35
_DOC_MID_MAX = 0.50
# Minimum alphanumeric OCR text for a confident document verdict.
_OCR_TEXT_MIN = 40

_VLM_CHECK_PROMPT = (
    "Does this image primarily depict a document, letter, form or "
    "printed/written text? Answer with the single word DOCUMENT or IMAGE "
    "as the first line. If DOCUMENT, transcribe its full text on the "
    "following lines; if IMAGE, output nothing else."
)

_TESSERACT_DEFAULT_PATHS = (
    r'C:\Program Files\Tesseract-OCR\tesseract.exe',
    r'C:\Program Files\PDF24\tesseract\tesseract.exe',
)


def looks_like_document(image_path):
    """Grayscale bimodal histogram: documents are mostly near-white with
    a small dark share and little midtone; photos spread across tones."""
    try:
        from PIL import Image
        with Image.open(str(image_path)) as img:
            histogram = img.convert('L').histogram()
    except Exception as exc:
        log_message(
            f"img2md: histogram failed for {image_path}: {exc}",
            level="WARNING",
        )
        return False
    total = sum(histogram) or 1
    white = sum(histogram[200:]) / total
    mid = sum(histogram[60:200]) / total
    return white >= _DOC_WHITE_MIN and mid <= _DOC_MID_MAX


def _tesseract_command(setting):
    """Tesseract executable: config -> PATH -> known install locations."""
    candidates = [setting] if setting else []
    found = shutil.which('tesseract')
    if found:
        candidates.append(found)
    candidates.extend(_TESSERACT_DEFAULT_PATHS)
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return str(candidate)
    return None


def ocr_image_text(image_path, setting='', timeout=120):
    """Tesseract OCR text for an image; '' when tesseract is unavailable."""
    tesseract = _tesseract_command(setting)
    if not tesseract:
        return ''
    try:
        result = subprocess.run(
            [tesseract, str(image_path), 'stdout', '-l', 'deu+eng'],
            check=True, capture_output=True, timeout=timeout,
        )
        return result.stdout.decode('utf-8', errors='replace')
    except subprocess.CalledProcessError:
        # Language data may be missing; retry with default language.
        try:
            result = subprocess.run(
                [tesseract, str(image_path), 'stdout'],
                check=True, capture_output=True, timeout=timeout,
            )
            return result.stdout.decode('utf-8', errors='replace')
        except Exception as exc:
            log_message(
                f"img2md: OCR failed for {image_path}: {exc}",
                level="WARNING",
            )
    except Exception as exc:
        log_message(
            f"img2md: OCR failed for {image_path}: {exc}",
            level="WARNING",
        )
    return ''


def _vlm_check(image_path, settings):
    """Vision model verdict -> (verdict, transcribed_text)."""
    try:
        response = chat(
            [{
                "role": "user",
                "content": [
                    {"type": "text", "text": _VLM_CHECK_PROMPT},
                    image_part(str(image_path)),
                ],
            }],
            model=settings.get('image_model') or settings.get('model'),
        )
    except Exception as exc:
        log_message(
            f"img2md: image check failed for {image_path}: {exc}",
            level="WARNING",
        )
        return 'image', ''
    first, _, rest = response.strip().partition('\n')
    verdict = (
        'document'
        if first.strip().upper().startswith('DOCUMENT')
        else 'image'
    )
    return verdict, rest.strip()


def classify_image(image_path, settings):
    """Image verdict via the tiered check -> (verdict, text).

    'document' carries usable markup text (OCR or VLM transcription);
    'image' returns empty text. VLM can be disabled via
    ``settings['classify_images_vlm']`` (then OCR-only).
    """
    if not looks_like_document(image_path):
        return 'image', ''
    text = ocr_image_text(image_path, settings.get('tesseract', ''))
    if len(re.sub(r'\W+', '', text)) >= _OCR_TEXT_MIN:
        return 'document', text
    if not settings.get('classify_images_vlm', True):
        return 'image', ''
    return _vlm_check(image_path, settings)


def image_to_markdown(source, output_path, settings):
    """Write markup for a document image (OCR or VLM text)."""
    _, text = classify_image(source, settings)
    output_path = Path(output_path)
    output_path.write_text(text, encoding='utf-8')
    return output_path
