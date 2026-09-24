"""Command-line entry point for scrapetools."""

import argparse

from . import DEFAULT_USER_AGENT, scrape_text_list


def main(argv=None):
    parser = argparse.ArgumentParser(description="Scrape XPath-selected text values.")
    parser.add_argument("url")
    parser.add_argument("selector")
    parser.add_argument("--output", required=True, type=str)
    parser.add_argument("--method", default="lxml", choices=("lxml",))
    parser.add_argument("--timeout", type=float, default=30)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)
    path = scrape_text_list(
        args.url,
        args.selector,
        args.output,
        method=args.method,
        timeout=args.timeout,
        retries=args.retries,
        user_agent=args.user_agent,
        overwrite=args.overwrite,
    )
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
