"""Utilities for scraping structured values from websites."""

import csv
import time
from pathlib import Path
from typing import Optional

import requests
from lxml import html


DEFAULT_USER_AGENT = "witnctools-scrapetools/0.1"


def _fetch(url: str, *, timeout: float, retries: int, user_agent: str) -> str:
    last_error = None
    for attempt in range(retries + 1):
        try:
            response = requests.get(
                url,
                headers={"User-Agent": user_agent},
                timeout=timeout,
            )
            if 500 <= response.status_code < 600 and attempt < retries:
                time.sleep(2**attempt)
                continue
            response.raise_for_status()
            return response.text
        except (requests.RequestException, OSError) as error:
            last_error = error
            if attempt >= retries:
                raise RuntimeError(f"Failed to fetch {url}: {error}") from error
            time.sleep(2**attempt)
    raise RuntimeError(f"Failed to fetch {url}: {last_error}")


def scrape_text_list(
    url: str,
    selector: str,
    output_path: str | Path,
    *,
    method: str = "lxml",
    timeout: float = 30,
    retries: int = 2,
    user_agent: str = DEFAULT_USER_AGENT,
    overwrite: bool = False,
) -> Path:
    """Scrape XPath-selected text values and write one value per CSV row."""
    if method != "lxml":
        raise ValueError("Unsupported method; supported methods: lxml")
    if retries < 0:
        raise ValueError("retries must not be negative")
    if timeout <= 0:
        raise ValueError("timeout must be positive")

    destination = Path(output_path)
    if destination.exists() and not overwrite:
        raise FileExistsError(destination)

    document = html.fromstring(
        _fetch(url, timeout=timeout, retries=retries, user_agent=user_agent)
    )
    values = []
    for result in document.xpath(selector):
        value = result if isinstance(result, str) else result.text_content()
        normalized = " ".join(value.split())
        if normalized and normalized not in values:
            values.append(normalized)

    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerows([[value] for value in values])
    return destination
