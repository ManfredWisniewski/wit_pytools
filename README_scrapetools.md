# scrapetools

`scrapetools` retrieves structured text values from server-rendered web pages.
The first implementation uses `requests` and `lxml` XPath parsing.

## Python

```python
from wit_pytools.scrapetools import scrape_text_list

output = scrape_text_list(
    "https://example.test/page",
    "//*[@id='collapse2023']/div/table/tbody/tr/td[1]/ol/li[6]",
    "values.csv",
)
```

The selector may return one or many elements. Values are normalized, empty
values are removed and duplicate values are removed while preserving order.

## CLI

```text
python -m wit_pytools.scrapetools URL XPATH --output values.csv
```

Options:

- `--method lxml` — current parser method;
- `--timeout 30` — request timeout in seconds;
- `--retries 2` — retries for connection errors and HTTP 5xx responses;
- `--user-agent` — HTTP User-Agent;
- `--overwrite` — allow replacing an existing output file.

## Output

The output is a UTF-8, one-column CSV without a header:

```csv
value1
value2
value3
```

## Limitations

The initial implementation does not support JavaScript-rendered pages,
authentication, pagination, scheduling or browser automation. The `lxml`
method is currently the only method.
