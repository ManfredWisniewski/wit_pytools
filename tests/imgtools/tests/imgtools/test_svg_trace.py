import pytest
from pathlib import Path
from wit_pytools.imgtools import svg_trace_monochrome

TEST_IMG_DIR = Path("/home/klaxigon/Bilder/jpg_input")
OUTPUT_DIR = Path("/home/klaxigon/Bilder/svg_outputs")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

@pytest.mark.parametrize("img_path", list(TEST_IMG_DIR.glob("*.[jp][pn]g")))
def test_svg_trace_creates_svg(img_path):
    """
    Testet, ob svg_trace_monochrome aus allen JPG/PNG-Bildern
    im Input-Ordner eine SVG erzeugt.
    """

    svg_file = svg_trace_monochrome(
        img_path,
        output_dir=OUTPUT_DIR,
        threshold=50
    )
    
    assert svg_file.exists(), f"SVG wurde nicht erstellt: {svg_file}"

    content = svg_file.read_text()
    assert "<svg" in content, "Erstellte Datei enthält kein SVG"
