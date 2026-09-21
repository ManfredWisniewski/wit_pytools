"""Convert PDF documents to Markdown.

The approach mirrors the concept of MarkPDFDown (Apache-2.0): every page is
rendered to an image and transcribed by a multimodal model. No code from that
project is used; rendering relies on ``pdfplumber`` and the model is reached
through :mod:`wit_pytools.aitools`.
"""

import argparse
import json
import os
import re
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

from eliot import log_message

from wit_pytools.aitools import chat, image_part, list_models

try:  # Optional dependency that is only needed for PDF operations
    import pdfplumber  # type: ignore
except ImportError:  # pragma: no cover - exercised in environments without pdfplumber
    pdfplumber = None

DEFAULT_MAX_COST = 0.50
DEFAULT_DPI = 150
DEFAULT_RETRY_TIMES = 3
DEFAULT_PROMPT_FILE = Path(__file__).with_name("pdf2md_prompt.txt")
PAGE_SEPARATOR = "\n\n---\n\n"
MODES = ("vision", "text")
LANGUAGES: Dict[str, Dict[str, str]] = {
    "en": {
        "illegible": "[illegible]",
        "failed": "> **Page {page}: conversion failed** — {reason}",
        "no_text": "> **Page {page}: no text layer** — use vision mode for this page",
    },
    "de": {
        "illegible": "[unleserlich]",
        "failed": "> **Seite {page}: Konvertierung fehlgeschlagen** — {reason}",
        "no_text": "> **Seite {page}: keine Textebene** — für diese Seite den Modus vision verwenden",
    },
}
_SYSTEM_PROMPT = "You convert document page images to Markdown and output Markdown only."
_FENCE_PATTERN = re.compile(r"\A\s*```(?:markdown|md)?\s*\n(.*?)\n?```\s*\Z", re.DOTALL)


def _require_pdfplumber() -> None:
    if pdfplumber is None:
        raise RuntimeError(
            "pdfplumber is required for PDF operations. "
            "Install the dependencies from requirements.txt."
        )


def _language(language: Optional[str]) -> Dict[str, str]:
    code = (language or os.environ.get("PDF2MD_LANGUAGE") or "en").strip().lower()
    if code not in LANGUAGES:
        raise ValueError(
            f"Unsupported language {code!r}; supported: {', '.join(sorted(LANGUAGES))}"
        )
    return LANGUAGES[code]


def _resolve_model(model: Optional[str]) -> str:
    chosen = (
        model
        or os.environ.get("OPENROUTER_PDF_MODEL", "")
        or os.environ.get("OPENROUTER_MODEL", "")
    )
    if not chosen:
        raise RuntimeError(
            "No model given: pass model= or set OPENROUTER_PDF_MODEL (or OPENROUTER_MODEL)"
        )
    return chosen


def _load_prompt(prompt_file: Optional[Union[str, Path]], texts: Dict[str, str]) -> str:
    path = Path(prompt_file) if prompt_file else DEFAULT_PROMPT_FILE
    if not path.is_file():
        raise FileNotFoundError(path)
    return path.read_text(encoding="utf-8").replace("{illegible}", texts["illegible"]).strip()


def _strip_fence(text: str) -> str:
    match = _FENCE_PATTERN.match(text)
    return (match.group(1) if match else text).strip()


def _page_range(page_count: int, start_page: int, end_page: Optional[int]) -> range:
    last = page_count if end_page is None else end_page
    if start_page < 1 or last > page_count or start_page > last:
        raise ValueError(
            f"Invalid page range {start_page}-{last} for a document with {page_count} pages"
        )
    return range(start_page, last + 1)


def estimate_cost(model: str, pages: int, *, api_key: Optional[str] = None) -> Optional[float]:
    """Return ``pages`` times the model's per-image price in USD, or ``None`` if unknown."""
    for entry in list_models(api_key=api_key):
        if entry.get("id") != model:
            continue
        price = (entry.get("pricing") or {}).get("image")
        try:
            value = float(price)
        except (TypeError, ValueError):
            return None
        return value * pages if value > 0 else None
    return None


def _confirm(estimate: Optional[float], max_cost: float, yes: bool) -> None:
    if yes:
        return
    if estimate is None:
        question = "Price per page could not be determined."
    elif estimate <= max_cost:
        return
    else:
        question = f"Estimated cost {estimate:.2f} USD exceeds limit {max_cost:.2f} USD."
    answer = input(f"{question} Continue? [y/N] ").strip().lower()
    if answer not in ("y", "yes"):
        raise RuntimeError("Aborted by user before converting")


def _transcribe_image(
    image_path: Path,
    prompt: str,
    model: str,
    retry_times: int,
    api_key: Optional[str],
) -> str:
    last_error: Optional[Exception] = None
    for attempt in range(1, retry_times + 1):
        try:
            response = chat(
                [{"role": "user", "content": [{"type": "text", "text": prompt}, image_part(image_path)]}],
                model,
                system=_SYSTEM_PROMPT,
                api_key=api_key,
            )
            content = _strip_fence(response or "")
            if content:
                return content
            last_error = RuntimeError("Empty response from model")
        except RuntimeError as exc:
            last_error = exc
        log_message(
            f"Attempt {attempt}/{retry_times} failed for {image_path.name}: {last_error}",
            level="WARNING",
        )
        if attempt < retry_times:
            time.sleep(2 * attempt)
    raise last_error if last_error else RuntimeError("Conversion failed")


def _convert_pages(
    pdf_path: Path,
    *,
    mode: str,
    model: Optional[str],
    start_page: int,
    end_page: Optional[int],
    prompt_file: Optional[Union[str, Path]],
    dpi: int,
    retry_times: int,
    continue_on_error: bool,
    max_cost: Optional[float],
    yes: bool,
    language: Optional[str],
    api_key: Optional[str],
    pages_dir: Optional[Path],
) -> Dict[str, Any]:
    _require_pdfplumber()
    if mode not in MODES:
        raise ValueError(f"Unsupported mode {mode!r}; supported: {', '.join(MODES)}")
    if not pdf_path.is_file():
        raise FileNotFoundError(pdf_path)
    if pdf_path.suffix.lower() != ".pdf":
        raise ValueError("Only .pdf files are supported")
    texts = _language(language)

    chosen_model = None
    prompt = None
    estimate = None
    if mode == "vision":
        chosen_model = _resolve_model(model)
        prompt = _load_prompt(prompt_file, texts)

    parts: List[str] = []
    statuses: List[Dict[str, Any]] = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        pages = _page_range(len(pdf.pages), start_page, end_page)
        if mode == "vision":
            limit = max_cost if max_cost is not None else float(
                os.environ.get("OPENROUTER_MAX_COST", DEFAULT_MAX_COST)
            )
            estimate = estimate_cost(chosen_model, len(pages), api_key=api_key)
            _confirm(estimate, limit, yes)

        with tempfile.TemporaryDirectory(prefix="pdf2md-") as temp_dir:
            image_dir = pages_dir or Path(temp_dir)
            for number in pages:
                page = pdf.pages[number - 1]
                status: Dict[str, Any] = {"page": number, "status": "ok"}
                log_message(f"Converting page {number} of {pdf_path.name} ({mode})", level="INFO")
                if mode == "text":
                    content = (page.extract_text() or "").strip()
                    if not content:
                        content = texts["no_text"].format(page=number)
                        status["status"] = "no_text"
                        log_message(f"Page {number} has no text layer", level="WARNING")
                else:
                    image_path = image_dir / f"page_{number:04d}.png"
                    page.to_image(resolution=dpi).save(str(image_path), format="PNG")
                    try:
                        content = _transcribe_image(image_path, prompt, chosen_model, retry_times, api_key)
                    except RuntimeError as exc:
                        content = texts["failed"].format(page=number, reason=exc)
                        status.update(status="failed", error=str(exc))
                        log_message(f"Page {number} failed: {exc}", level="ERROR")
                if pages_dir is not None:
                    (pages_dir / f"page_{number:04d}.md").write_text(content, encoding="utf-8")
                parts.append(content)
                statuses.append(status)

    failed = [status["page"] for status in statuses if status["status"] == "failed"]
    if failed and not continue_on_error:
        raise RuntimeError(f"Conversion failed for page(s): {', '.join(map(str, failed))}")
    return {
        "markdown": PAGE_SEPARATOR.join(parts),
        "metadata": {
            "source": pdf_path.name,
            "mode": mode,
            "model": chosen_model,
            "pages": [pages.start, pages.stop - 1],
            "dpi": dpi if mode == "vision" else None,
            "language": language or os.environ.get("PDF2MD_LANGUAGE") or "en",
            "prompt_file": str(Path(prompt_file) if prompt_file else DEFAULT_PROMPT_FILE) if mode == "vision" else None,
            "estimated_cost_usd": estimate,
            "page_status": statuses,
            "created": f"{datetime.now():%Y-%m-%d %H:%M:%S}",
        },
    }


def pdf_to_markdown_text(
    pdf_path: Union[str, Path],
    *,
    mode: str = "vision",
    model: Optional[str] = None,
    start_page: int = 1,
    end_page: Optional[int] = None,
    prompt_file: Optional[Union[str, Path]] = None,
    dpi: int = DEFAULT_DPI,
    retry_times: int = DEFAULT_RETRY_TIMES,
    continue_on_error: bool = False,
    max_cost: Optional[float] = None,
    yes: bool = False,
    language: Optional[str] = None,
    api_key: Optional[str] = None,
) -> str:
    """Convert a PDF to Markdown and return the text without writing files."""
    result = _convert_pages(
        Path(pdf_path),
        mode=mode,
        model=model,
        start_page=start_page,
        end_page=end_page,
        prompt_file=prompt_file,
        dpi=dpi,
        retry_times=retry_times,
        continue_on_error=continue_on_error,
        max_cost=max_cost,
        yes=yes,
        language=language,
        api_key=api_key,
        pages_dir=None,
    )
    return result["markdown"]


def pdf_to_markdown(
    pdf_path: Union[str, Path],
    *,
    mode: str = "vision",
    model: Optional[str] = None,
    start_page: int = 1,
    end_page: Optional[int] = None,
    output_path: Optional[Union[str, Path]] = None,
    sidecar_path: Optional[Union[str, Path]] = None,
    write_sidecar: bool = True,
    overwrite: bool = False,
    keep_pages: bool = False,
    prompt_file: Optional[Union[str, Path]] = None,
    dpi: int = DEFAULT_DPI,
    retry_times: int = DEFAULT_RETRY_TIMES,
    continue_on_error: bool = False,
    max_cost: Optional[float] = None,
    yes: bool = False,
    language: Optional[str] = None,
    api_key: Optional[str] = None,
) -> Path:
    """Convert a PDF to Markdown, write ``<stem>.md`` plus a JSON sidecar, return the path."""
    source = Path(pdf_path)
    target = Path(output_path) if output_path is not None else source.with_suffix(".md")
    sidecar = (
        Path(sidecar_path)
        if sidecar_path is not None
        else target.with_name(f"{target.stem}_pdf2md.json")
    )
    pages_dir = target.with_name(f"{target.stem}_pages") if keep_pages else None
    output_paths = [target]
    if write_sidecar:
        output_paths.append(sidecar)
    for path in output_paths:
        if path.resolve() == source.resolve():
            raise ValueError("The output path must differ from the source path")
        if path.exists() and not overwrite:
            raise FileExistsError(path)
    if pages_dir is not None:
        if pages_dir.exists() and not overwrite:
            raise FileExistsError(pages_dir)
        pages_dir.mkdir(parents=True, exist_ok=True)

    result = _convert_pages(
        source,
        mode=mode,
        model=model,
        start_page=start_page,
        end_page=end_page,
        prompt_file=prompt_file,
        dpi=dpi,
        retry_times=retry_times,
        continue_on_error=continue_on_error,
        max_cost=max_cost,
        yes=yes,
        language=language,
        api_key=api_key,
        pages_dir=pages_dir,
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(result["markdown"] + "\n", encoding="utf-8")
    metadata = dict(result["metadata"], output=target.name, pages_dir=pages_dir.name if pages_dir else None)
    if write_sidecar:
        sidecar.parent.mkdir(parents=True, exist_ok=True)
        sidecar.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    log_message(f"Wrote {target} ({metadata['mode']}, pages {metadata['pages']})", level="INFO")
    return target


class _Tee:
    """Write to the console stream and a log file at the same time."""

    def __init__(self, stream, log_file):
        self._stream = stream
        self._log = log_file

    def write(self, text):
        self._stream.write(text)
        self._log.write(text)
        self._log.flush()

    def flush(self):
        self._stream.flush()
        self._log.flush()

    def __getattr__(self, name):
        return getattr(self._stream, name)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Convert a PDF to Markdown via OpenRouter.")
    parser.add_argument("input", type=Path, help="PDF file")
    parser.add_argument("--mode", choices=MODES, default="vision")
    parser.add_argument("--model", help="Model id; default from OPENROUTER_PDF_MODEL")
    parser.add_argument("--start", type=int, default=1, help="First page (1-based)")
    parser.add_argument("--end", type=int, help="Last page (default: last page of the document)")
    parser.add_argument("--output", type=Path, help="Output .md path (default: beside the PDF)")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--keep-pages", action="store_true", help="Keep page images and per-page Markdown")
    parser.add_argument("--prompt-file", type=Path, help="UTF-8 prompt text file")
    parser.add_argument("--dpi", type=int, default=DEFAULT_DPI)
    parser.add_argument("--retry-times", type=int, default=DEFAULT_RETRY_TIMES)
    parser.add_argument("--continue-on-error", action="store_true")
    parser.add_argument(
        "--max-cost",
        type=float,
        help=f"Confirm above this USD amount (default {DEFAULT_MAX_COST}, env OPENROUTER_MAX_COST)",
    )
    parser.add_argument("--yes", action="store_true", help="Skip cost confirmation")
    parser.add_argument("--language", help=f"Marker language: {', '.join(sorted(LANGUAGES))} (env PDF2MD_LANGUAGE)")
    parser.add_argument("--log", type=Path, metavar="FILE", help="Append console output to this file")
    args = parser.parse_args(argv)

    log_file = None
    stdout, stderr = sys.stdout, sys.stderr
    if args.log:
        args.log.parent.mkdir(parents=True, exist_ok=True)
        log_file = args.log.open("a", encoding="utf-8")
        log_file.write(f"\n=== {datetime.now():%Y-%m-%d %H:%M:%S} {args.input}\n")
        sys.stdout = _Tee(stdout, log_file)
        sys.stderr = _Tee(stderr, log_file)
    try:
        path = pdf_to_markdown(
            args.input,
            mode=args.mode,
            model=args.model,
            start_page=args.start,
            end_page=args.end,
            output_path=args.output,
            overwrite=args.overwrite,
            keep_pages=args.keep_pages,
            prompt_file=args.prompt_file,
            dpi=args.dpi,
            retry_times=args.retry_times,
            continue_on_error=args.continue_on_error,
            max_cost=args.max_cost,
            yes=args.yes,
            language=args.language,
        )
        print(path)
        return 0
    except Exception as exc:  # report to console and log, exit non-zero
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    finally:
        sys.stdout, sys.stderr = stdout, stderr
        if log_file:
            log_file.close()


if __name__ == "__main__":
    raise SystemExit(main())
