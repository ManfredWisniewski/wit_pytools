"""Command-line entry point for webtools."""

import argparse
import sys

from .config import WebtoolsConfigError
from .sites import load_sites


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Browser automation for interactive websites."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # each sites/*.py module registers one subcommand
    sites = load_sites()
    for name, site in sorted(sites.items()):
        site_parser = sub.add_parser(name, help=site.DESCRIPTION)
        site.add_arguments(site_parser)

    args = parser.parse_args(argv)

    try:
        saved = sites[args.command].run(args) or []
        for path in saved:
            print(path)
        return 0
    except WebtoolsConfigError as error:
        print(error, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
