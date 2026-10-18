"""Word document to Markdown conversion.

.docx files are converted locally via mammoth. Legacy binary .doc files
have no maintained pure-Python reader; they are converted through
LibreOffice headless (soffice).
"""

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Union


def docx_to_markdown(
    docx_path: Union[str, Path],
    *,
    output_path: Optional[Union[str, Path]] = None,
    overwrite: bool = False,
) -> Path:
    """Convert a .docx file to Markdown via mammoth."""
    import mammoth

    source = Path(docx_path)
    target = Path(output_path) if output_path else source.with_suffix(".md")
    if target.exists() and not overwrite:
        raise FileExistsError(target)
    with source.open("rb") as fp:
        result = mammoth.convert_to_markdown(fp)
    target.write_text(result.value, encoding="utf-8")
    return target


def doc_to_markdown(
    doc_path: Union[str, Path],
    *,
    output_path: Optional[Union[str, Path]] = None,
    overwrite: bool = False,
    timeout: int = 120,
) -> Path:
    """Convert a legacy .doc file to Markdown via LibreOffice headless."""
    source = Path(doc_path)
    target = Path(output_path) if output_path else source.with_suffix(".md")
    if target.exists() and not overwrite:
        raise FileExistsError(target)
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        raise RuntimeError(
            ".doc conversion requires LibreOffice (soffice) in PATH"
        )
    with tempfile.TemporaryDirectory() as tmpdir:
        subprocess.run(
            [
                soffice, "--headless", "--convert-to", "txt:Text",
                "--outdir", tmpdir, str(source),
            ],
            check=True,
            capture_output=True,
            timeout=timeout,
        )
        text = (Path(tmpdir) / f"{source.stem}.txt").read_text(
            encoding="utf-8", errors="replace"
        )
    target.write_text(text.strip() + "\n", encoding="utf-8")
    return target
