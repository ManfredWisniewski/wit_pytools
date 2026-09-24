# Intent: `scrapetools`

## Package purpose

`scrapetools` provides modular functions for retrieving structured text from
web pages through explicit selectors.

The first implementation uses `requests` and `lxml` XPath parsing for manual
or scripted calls. Browser automation and JavaScript rendering are outside the
initial scope.

## Concepts

- **URL**: the page fetched by the scraper.
- **XPath selector**: an expression identifying one or more elements in the
  returned HTML document.
- **Value**: normalized visible text extracted from each selected element.
- **Method**: the parser implementation; currently only `lxml` is supported.

## Configuration

The Python function accepts configuration directly. The CLI and batch runner
expose the same values:

- `method` — `lxml` (default and current only implementation).
- `timeout` — request timeout in seconds, default `30`.
- `retries` — retries for connection failures and HTTP 5xx responses, default
  `2`.
- `user_agent` — default `witnctools-scrapetools/0.1`.
- `overwrite` — existing output raises unless enabled.

## Processing order

1. Validate the method, timeout, retries and output collision state.
2. Fetch the URL with `requests` and the configured User-Agent.
3. Retry connection errors and HTTP 5xx responses with exponential delays.
4. Parse the response with `lxml.html`.
5. Evaluate the XPath selector.
6. Convert selected elements to visible text.
7. Strip surrounding whitespace, collapse internal whitespace and remove empty
   values.
8. Deduplicate values while preserving page order.
9. Write one value per UTF-8 CSV row.

## Public functions

```python
scrape_text_list(
    url,
    selector,
    output_path,
    *,
    method="lxml",
    timeout=30,
    retries=2,
    user_agent="witnctools-scrapetools/0.1",
    overwrite=False,
) -> Path
```

The function returns the output `Path`. It raises `FileExistsError` unless
`overwrite=True`, `ValueError` for invalid settings or methods, and
`RuntimeError` when fetching fails after all retries.

CLI:

```text
python -m wit_pytools.scrapetools URL XPATH --output values.csv
```

Runner:

```text
runners/scrapetools_runner.bat
```

## Data and file formats

The output is a one-column UTF-8 CSV without a header:

```csv
value1
value2
value3
```

CSV quoting is used when a value contains commas, quotes or line breaks.

## Safety and preservation

- The scraper performs HTTP GET requests only.
- No credentials or cookies are handled by the initial implementation.
- The User-Agent is explicit and configurable.
- HTTP errors are surfaced; 4xx responses are not retried.
- Output files are not overwritten unless `overwrite=True`.
- No source web page is modified.

## Tests and verification

Tests should use mocked HTTP responses and local HTML fixtures. They must cover
XPath extraction, multiple results, normalization, deduplication, retries,
4xx/5xx behavior, output collision protection and CLI argument forwarding.

## Non-goals and limitations

- JavaScript-rendered pages and browser automation.
- Authentication, cookies and authenticated sessions.
- Pagination or multi-URL scraping.
- Scheduled scraping.
- CSS selector support in the first implementation.

## Open items

- Add additional parser methods after the `method` interface is stable.
- Add pagination and multi-page scraping.
- Add authenticated requests only with an explicit credential design.
