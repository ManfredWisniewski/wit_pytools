"""Rich Text (.rtf) to Markdown conversion.

RTF is a structured text format, so no OCR or model call is needed.
LibreOffice headless (soffice) converts the file to .docx and mammoth
produces the Markdown — the same pipeline as ``doc2md``.
"""

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Union


def _require_soffice() -> str:
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        raise RuntimeError(
            ".rtf conversion requires LibreOffice (soffice) in PATH"
        )
    return soffice


def rtf_to_markdown_text(
    rtf_path: Union[str, Path],
    *,
    include_images: bool = False,
    timeout: int = 120,
) -> str:
    """Convert a .rtf file to Markdown and return the text without writing files."""
    import mammoth

    source = Path(rtf_path)
    if source.suffix.lower() != ".rtf":
        raise ValueError("Only .rtf files are supported")
    if not source.is_file():
        raise FileNotFoundError(source)
    soffice = _require_soffice()
    with tempfile.TemporaryDirectory() as tmpdir:
        subprocess.run(
            [
                soffice, "--headless", "--convert-to", "docx",
                "--outdir", tmpdir, str(source),
            ],
            check=True,
            capture_output=True,
            timeout=timeout,
        )
        docx = Path(tmpdir) / f"{source.stem}.docx"
        if not docx.is_file():
            raise RuntimeError(f"LibreOffice produced no output for {source.name}")
        # Mammoth inlines images as base64 data URIs; drop them by default.
        convert_image = None if include_images else lambda image: []
        with docx.open("rb") as fp:
            return mammoth.convert_to_markdown(fp, convert_image=convert_image).value


def rtf_to_markdown(
    rtf_path: Union[str, Path],
    *,
    output_path: Optional[Union[str, Path]] = None,
    overwrite: bool = False,
    include_images: bool = False,
    timeout: int = 120,
) -> Path:
    """Convert a .rtf file to Markdown, write ``<stem>.md``, return the path."""
    source = Path(rtf_path)
    target = Path(output_path) if output_path else source.with_suffix(".md")
    if target.resolve() == source.resolve():
        raise ValueError("The output path must differ from the source path")
    if target.exists() and not overwrite:
        raise FileExistsError(target)
    target.write_text(rtf_to_markdown_text(
        source, include_images=include_images, timeout=timeout
    ), encoding="utf-8")
    return target
