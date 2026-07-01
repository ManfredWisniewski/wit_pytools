import re
from pathlib import Path
from typing import List, Dict, Any, Optional

from eliot import log_message

try:  # Optional dependency that is only needed for PDF operations
    import pdfplumber  # type: ignore
except ImportError:  # pragma: no cover - exercised in environments without pdfplumber
    pdfplumber = None


def document_find_regex(
    file_path: Path | str,
    query: str,
    *,
    regex: bool = False,
    context_chars: int = 40,
    max_pages: Optional[int] = None,
    flags: int = re.IGNORECASE,
) -> List[Dict[str, Any]]:
    """Search a PDF for a literal string or regex pattern and return contexts.

    Args:
        file_path: Path to the PDF document.
        query: Literal string or regex pattern to search for.
        regex: When ``True`` the ``query`` is treated as a regular expression;
            otherwise a literal search is performed.
        context_chars: Number of characters of context to capture on both sides
            of each match.
        max_pages: Optional maximum number of pages to scan. ``None`` scans all
            pages.
        flags: Regular expression flags passed to :func:`re.compile`.

    Returns:
        A list of dictionaries containing ``page_number``, ``match``, and
        ``context`` keys for each occurrence found.

    Raises:
        RuntimeError: If ``pdfplumber`` is not available in the current
            environment.
    """

    if not pdfplumber:
        raise RuntimeError(
            "pdfplumber is required for document_find_regex. Install pdfplumber to use this function."
        )

    pattern = re.compile(query if regex else re.escape(query), flags)
    pdf_path = Path(file_path)
    results: List[Dict[str, Any]] = []

    try:
        with pdfplumber.open(str(pdf_path)) as pdf:
            pages = pdf.pages
            if max_pages is not None:
                pages = pages[:max_pages]

            for page_index, page in enumerate(pages, start=1):
                page_text = page.extract_text() or ""
                for match in pattern.finditer(page_text):
                    start = max(match.start() - context_chars, 0)
                    end = min(match.end() + context_chars, len(page_text))
                    context = page_text[start:end].replace("\n", " ")
                    results.append(
                        {
                            "page_number": page_index,
                            "match": match.group(0),
                            "context": context,
                        }
                    )
    except Exception as exc:
        log_message(f"Failed to search PDF {pdf_path}: {exc}", level="ERROR")
        raise

    return results
