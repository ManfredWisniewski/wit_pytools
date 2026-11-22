"""Command-line interface: KLIMAX-XLS -> CSV converter (Aufmass)."""

import argparse
import sys
from pathlib import Path

from .converter import DEFAULT_INI, convert_all, parse_xls_to_csv


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="KLIMAX-XLS -> CSV converter (Aufmass)")
    parser.add_argument("--src", required=True,
                        help="xls file or directory (recursive)")
    parser.add_argument("--out", default=None,
                        help="output file (single input) or directory")
    parser.add_argument("--ini", default=str(DEFAULT_INI),
                        help="replacement table ini (default: aufmass.ini in package)")
    parser.add_argument("--no-sums", action="store_true",
                        help="skip .summen.csv output")
    args = parser.parse_args(argv)

    src = Path(args.src)
    if src.is_dir():
        results = convert_all(src, args.out, args.ini)
    else:
        results = [parse_xls_to_csv(
            src, args.out, ini_path=args.ini, write_sums=not args.no_sums)]

    errors = 0
    for result in results:
        if "error" in result:
            errors += 1
            print(f"ERROR {result['csv'].name}: {result['error']}", file=sys.stderr)
        else:
            print(f"{result['csv'].name}: {result['rows']} Positionen, "
                  f"{result['sums']} Summen")
    return 1 if errors else 0
