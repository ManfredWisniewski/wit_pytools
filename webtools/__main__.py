"""Command-line entry point for webtools."""

import argparse
import sys

from .config import WebtoolsConfigError
from .session import DEFAULT_PROFILE_DIR


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Browser automation for interactive websites."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    amex = sub.add_parser(
        "amex-statements", help="Download recent Amex (US) statements."
    )
    amex.add_argument("--out", default="downloads/amex")
    amex.add_argument("--profile", default=str(DEFAULT_PROFILE_DIR))
    amex.add_argument("--channel", default="chrome")
    amex.add_argument("--headless", action="store_true")
    amex.add_argument("--count", type=int, default=None)
    amex.add_argument(
        "--format", default="pdf", choices=("pdf", "csv", "excel")
    )
    amex.add_argument("--mfa-timeout", type=int, default=300)

    args = parser.parse_args(argv)

    try:
        if args.command == "amex-statements":
            from .sites import amex as amex_site

            saved = amex_site.run(
                args.out,
                profile_dir=args.profile,
                headless=args.headless,
                channel=args.channel,
                mfa_timeout=args.mfa_timeout,
                count=args.count,
                fmt=args.format,
            )
            for path in saved:
                print(path)
            return 0
    except WebtoolsConfigError as error:
        print(error, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
